"""
سرویس قیمت زنده.

مشکلی که این ماژول حل می‌کند: پیش از این، برنامه هنگام بالا آمدن یک بار
قیمت‌ها را می‌گرفت و بعد ساکت می‌ماند؛ کاربر «آنلاین» می‌دید ولی عددها
یخ‌زده بودند و پس از مدتی وضعیت به «آفلاین» می‌رفت.

راهبرد دولایه:

    WebSocket  →  نمادهای زیر نظر کاربر، تیک‌به‌تیک (کمترین تأخیر)
    REST       →  کل فهرست بازار، هر چند ثانیه یک بار (پوشش کامل)

هر دو لایه در یک انبار قیمت مشترک می‌ریزند و مصرف‌کننده (رابط کاربری)
فقط از همان انبار می‌خواند و نمی‌داند قیمت از کدام مسیر آمده است.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.core.constants import ConnectionStatus
from app.core.models import Ticker
from app.core.timeutil import now_utc
from app.logging import get_logger
from market.engine import MarketDataEngine

logger = get_logger(__name__)

#: فاصله زمانی نظرسنجی REST برای کل بازار (ثانیه)
DEFAULT_POLL_INTERVAL = 3.0

#: حداکثر عمر فهرست کامل تیکرها که از کش مشترک پذیرفته می‌شود (ثانیه).
#: فهرست همهٔ نمادها سنگین‌ترین endpoint عمومی صرافی است؛ نسخهٔ 2.3.0 آن
#: را هر ۲ ثانیه بدون کش می‌خواند و کش بقیهٔ صفحه‌ها را هم بی‌اثر می‌کرد —
#: ترافیک چند برابر، محدودیت نرخ صرافی و «چند ثانیه آنلاین، بعد قطع».
SNAPSHOT_MAX_AGE = 5.0

#: داده‌ای که از این قدیمی‌تر باشد «تازه» حساب نمی‌شود (ثانیه).
FRESHNESS_WINDOW = 20.0

#: سقف مکث پس از شکست‌های پیاپی — بازگشت پس از قطعی نباید دقیقه‌ها طول بکشد.
MAX_POLL_BACKOFF = 30.0

#: بیشینه نمادهایی که هم‌زمان روی WebSocket مشترک می‌شوند
MAX_STREAMED_SYMBOLS = 80


@dataclass
class PriceUpdate:
    """
    یک به‌روزرسانی قیمت به‌همراه جهت تغییر نسبت به مقدار قبلی.

    `tick_direction` برای رنگ کردن لحظه‌ای سلول در جدول است: بدون آن،
    کاربر نمی‌فهمد قیمتی که همین حالا عوض شد بالا رفت یا پایین آمد.
    """

    symbol: str
    price: float
    change_percent: float
    high_24h: float = 0.0
    low_24h: float = 0.0
    volume_24h: float = 0.0
    tick_direction: int = 0  # +1 بالا، -1 پایین، 0 بدون تغییر
    updated_at: datetime = field(default_factory=now_utc)
    source: str = "rest"
    exchange_ts: int = 0
    #: قیمت یا تغییر ۲۴ساعته نسبت به قبل عوض شده (برای بازترسیم جدول‌ها)
    changed: bool = True

    @property
    def is_up(self) -> bool:
        """آیا تغییر ۲۴ ساعته مثبت است."""
        return self.change_percent > 0

    @property
    def is_down(self) -> bool:
        """آیا تغییر ۲۴ ساعته منفی است."""
        return self.change_percent < 0


class LivePriceFeed:
    """
    انبار قیمت زنده با دو منبع تغذیه.

    مثال:
        feed = LivePriceFeed(market_engine)
        feed.add_listener(on_prices)
        await feed.start()
        await feed.set_streamed_symbols(["BTC/USDT", "ETH/USDT"])
    """

    def __init__(
        self,
        market: MarketDataEngine,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._market = market
        self._poll_interval = max(0.5, float(poll_interval))
        self._prices: dict[str, PriceUpdate] = {}
        self._listeners: list[Callable[[dict[str, PriceUpdate]], None]] = []
        self._poll_task: asyncio.Task[None] | None = None
        self._streamed: list[str] = []
        self._running = False
        self._last_poll_ok: datetime | None = None
        self._last_stream_ok: datetime | None = None
        self._last_batch: object | None = None
        self._consecutive_failures = 0
        self._last_error = ""

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """شروع نظرسنجی REST و اتصال به جریان WebSocket."""
        if self._running:
            return
        self._running = True
        self._market.add_ticker_listener(self._on_live_ticker)
        self._poll_task = asyncio.create_task(self._poll_loop(), name="live-feed-poll")
        logger.info("Live price feed started (poll every %.1fs)", self._poll_interval)

    async def stop(self) -> None:
        """توقف تمیز."""
        self._running = False
        self._market.remove_ticker_listener(self._on_live_ticker)
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - خاموشی نباید خطا بدهد
                pass
            self._poll_task = None
        logger.info("Live price feed stopped")

    @property
    def running(self) -> bool:
        """آیا سرویس فعال است."""
        return self._running

    @property
    def poll_alive(self) -> bool:
        """
        آیا حلقهٔ نظرسنجی واقعاً زنده است.

        چرا جدا از `running`؟ پرچم `running` فقط یک بولین است؛ اگر وظیفهٔ
        نظرسنجی به دلیلی بمیرد، پرچم روشن می‌ماند و برنامه بی‌صدا «آنلاینِ
        یخ‌زده» می‌شود. نگهبان اتصال (market/resilience.py) با همین
        ویژگی جانِ واقعی حلقه را می‌سنجد.
        """
        return self._poll_task is not None and not self._poll_task.done()

    @property
    def is_fresh(self) -> bool:
        """
        آیا داده تازه است.

        این معیارِ «آنلاین بودن» است که به کاربر نشان داده می‌شود: مهم این
        نیست که سوکتی باز باشد، مهم این است که قیمت‌ها واقعاً به‌روز شوند.
        """
        window = max(FRESHNESS_WINDOW, self._poll_interval * 4)
        now = now_utc()
        for stamp in (self._last_poll_ok, self._last_stream_ok):
            if stamp is not None and (now - stamp).total_seconds() < window:
                return True
        return False

    @property
    def data_age_seconds(self) -> float | None:
        """سن تازه‌ترین دادهٔ رسیده از REST یا WebSocket."""
        stamps = [s for s in (self._last_poll_ok, self._last_stream_ok) if s is not None]
        if not stamps:
            return None
        return max(0.0, (now_utc() - max(stamps)).total_seconds())

    # ------------------------------------------------------------------
    # اشتراک‌ها
    # ------------------------------------------------------------------
    async def set_streamed_symbols(self, symbols: list[str]) -> None:
        """
        تعیین نمادهایی که باید تیک‌به‌تیک از WebSocket بیایند.

        معمولاً فهرست پیگیری کاربر به‌علاوه نمادی که همین حالا باز کرده.
        """
        unique = list(dict.fromkeys(s for s in symbols if s))[:MAX_STREAMED_SYMBOLS]
        if unique == self._streamed:
            return
        self._streamed = unique
        try:
            await self._market.set_watchlist_subscriptions(unique, max_symbols=MAX_STREAMED_SYMBOLS)
            logger.debug("Streaming %d symbols over WebSocket", len(unique))
        except Exception as exc:  # noqa: BLE001 - نبود WebSocket نباید کار را بخواباند
            logger.warning("Could not update WebSocket subscriptions: %s", exc)

    # ------------------------------------------------------------------
    # خواندن قیمت
    # ------------------------------------------------------------------
    def get(self, symbol: str) -> PriceUpdate | None:
        """آخرین قیمت یک نماد."""
        return self._prices.get(symbol)

    def snapshot(self) -> dict[str, PriceUpdate]:
        """کپی از وضعیت جاری همه قیمت‌ها."""
        return dict(self._prices)

    @property
    def symbol_count(self) -> int:
        """تعداد نمادهایی که قیمت دارند."""
        return len(self._prices)

    # ------------------------------------------------------------------
    # شنوندگان
    # ------------------------------------------------------------------
    def add_listener(self, callback: Callable[[dict[str, PriceUpdate]], None]) -> None:
        """افزودن شنونده تغییر قیمت."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[dict[str, PriceUpdate]], None]) -> None:
        """حذف شنونده."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, changed: dict[str, PriceUpdate]) -> None:
        """
        اطلاع‌رسانی به شنوندگان.

        خطای یک شنونده نباید بقیه را از کار بیندازد یا حلقه نظرسنجی را
        بشکند.
        """
        if not changed:
            return
        for callback in list(self._listeners):
            try:
                callback(changed)
            except Exception:  # noqa: BLE001 - شنونده خراب نباید جریان داده را قطع کند
                logger.exception("Price listener failed")

    # ------------------------------------------------------------------
    # منابع داده
    # ------------------------------------------------------------------
    def _store(self, ticker: Ticker, source: str) -> PriceUpdate | None:
        """
        ثبت یک تیکر در انبار و محاسبه جهت تیک.

        تیک واقعیِ بدون تغییر قیمت نیز زمان دریافت تازه دارد؛ حذف آن
        نباید قیمت معتبر را در کش اجرا کهنه نشان دهد.
        """
        previous = self._prices.get(ticker.symbol)
        price = float(ticker.last_price or 0.0)
        if price <= 0:
            return None

        direction = 0
        changed = True
        if previous is not None:
            if price > previous.price:
                direction = 1
            elif price < previous.price:
                direction = -1
            else:
                # تیک واقعی بدون تغییر هم نشانهٔ تازگی است، ولی نیازی به
                # بازترسیم جدول ندارد.
                changed = abs((ticker.change_percent or 0.0) - previous.change_percent) >= 1e-9

        update = PriceUpdate(
            symbol=ticker.symbol,
            price=price,
            change_percent=float(ticker.change_percent or 0.0),
            high_24h=float(ticker.high_24h or 0.0),
            low_24h=float(ticker.low_24h or 0.0),
            volume_24h=float(ticker.volume_24h or 0.0),
            tick_direction=direction,
            source=source,
            exchange_ts=ticker.timestamp,
            changed=changed,
        )
        self._prices[ticker.symbol] = update
        return update

    def _on_live_ticker(self, ticker: Ticker) -> None:
        """دریافت تیک زنده از WebSocket."""
        update = self._store(ticker, source="websocket")
        if update is not None:
            self._last_stream_ok = update.updated_at
            self._notify({update.symbol: update})

    async def _poll_loop(self) -> None:
        """
        نظرسنجی دوره‌ای REST برای کل بازار.

        WebSocket فقط نمادهای مشترک‌شده را می‌دهد؛ این حلقه تضمین می‌کند
        که صفحه بازارها (با صدها نماد) هم زنده بماند.
        """
        while self._running:
            try:
                tickers = await self._market.get_all_tickers(max_age_seconds=SNAPSHOT_MAX_AGE)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - قطعی شبکه عادی است
                self._consecutive_failures += 1
                self._last_error = type(exc).__name__
                logger.debug("Price poll failed (%d in a row): %s", self._consecutive_failures, exc)
                # عقب‌نشینی تدریجی تا در قطعی طولانی، صرافی را بمباران نکنیم؛
                # اگر صرافی زمان مکث را گفته، دقیقاً همان رعایت می‌شود.
                backoff = min(self._poll_interval * (2 ** min(self._consecutive_failures, 4)), MAX_POLL_BACKOFF)
                details = getattr(exc, "details", None) or {}
                try:
                    hinted = float(details.get("retry_after") or 0) if isinstance(details, dict) else 0.0
                except (TypeError, ValueError):
                    hinted = 0.0
                if hinted > 0:
                    backoff = max(1.0, min(hinted, 300.0))
                await asyncio.sleep(backoff)
                continue

            self._consecutive_failures = 0
            self._last_error = ""
            if tickers is self._last_batch:
                # همان فهرستِ کش‌شدهٔ قبلی؛ دوباره ثبت نمی‌شود تا سنِ داده
                # جوان‌تر از واقعیت نشان داده نشود.
                await asyncio.sleep(self._poll_interval)
                continue
            self._last_batch = tickers
            fetched = getattr(self._market, "all_tickers_fetched_at", None)
            self._last_poll_ok = fetched if isinstance(fetched, datetime) else now_utc()
            changed: dict[str, PriceUpdate] = {}
            for ticker in tickers:
                # تیک WebSocket تازه‌تر از نظرسنجی است؛ رویش را ننویس
                existing = self._prices.get(ticker.symbol)
                if existing is not None and existing.source == "websocket":
                    age = (now_utc() - existing.updated_at).total_seconds()
                    if age < self._poll_interval:
                        continue
                update = self._store(ticker, source="rest")
                if update is not None:
                    update.updated_at = self._last_poll_ok
                    changed[update.symbol] = update

            self._notify(changed)
            await asyncio.sleep(self._poll_interval)

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    def status(self) -> dict[str, object]:
        """خلاصه وضعیت برای نمایش در نوار وضعیت و داشبورد."""
        websocket = self._market.websocket_status
        return {
            "fresh": self.is_fresh,
            "symbols": len(self._prices),
            "streamed": len(self._streamed),
            "websocket": websocket is ConnectionStatus.CONNECTED,
            "websocket_status": websocket.value,
            "last_update": self._last_poll_ok,
            "last_stream": self._last_stream_ok,
            "data_age": self.data_age_seconds,
            "failures": self._consecutive_failures,
            "last_error": self._last_error,
        }
