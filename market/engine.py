"""
موتور داده بازار (Market Data Engine).

چرا وجود دارد؟
    این ماژول تنها نقطه‌ای است که بقیه برنامه برای گرفتن داده بازار به آن
    مراجعه می‌کند. مسئولیت‌ها:
        • هماهنگی بین REST و WebSocket
        • حافظه نهان و جلوگیری از درخواست تکراری
        • ذخیره داده برای حالت آفلاین
        • مدیریت هوشمند اشتراک‌ها (فقط نمادهای در حال مشاهده)
        • انتشار رویداد تغییر قیمت برای رابط کاربری

ارتباط با ماژول‌های دیگر:
    بالادست : ابزارهای عامل هوش مصنوعی، موتور اندیکاتور، صفحات UI
    پایین‌دست: ExchangeProvider (فعلاً LBank) و CandleRepository

اصل مهم (بند ۵۲ و ۵۳ سند پروژه):
    این موتور هرگز داده نمی‌سازد. اگر داده‌ای در دسترس نباشد، یا از حافظه
    نهان/پایگاه داده خوانده می‌شود یا خطای صریح داده می‌شود.
"""

from __future__ import annotations

from collections.abc import Callable

import asyncio
from typing import Any

from app.core.constants import ConnectionStatus
from app.core.events import EventBus, EventType
from app.core.models import Candle, OrderBook, SymbolInfo, Ticker
from app.database.repositories.candle_repository import CandleRepository
from app.exceptions import AppError, InsufficientDataError, NetworkError
from app.logging import get_logger
from market.cache.memory_cache import MarketCache
from market.providers.base import ExchangeProvider
from market.timeframes import timeframe_seconds

logger = get_logger(__name__)

# چند شکستِ پشت‌سرهمِ REST لازم است تا واقعاً «آفلاین» اعلام کنیم.
# روی اینترنت ناپایدار، یک درخواست ازدست‌رفته عادی است و نباید کل
# برنامه را آفلاین نشان دهد. سه بار یعنی قطعیِ واقعی، نه یک چاله.
REST_FAILURE_TOLERANCE = 3


class MarketDataEngine:
    """
    هماهنگ‌کننده دریافت داده بازار.

    نمونه‌سازی با تزریق وابستگی انجام می‌شود تا در تست بتوان صرافی جعلی
    جایگزین کرد:
        engine = MarketDataEngine(provider, cache, repository, event_bus)
    """

    def __init__(
        self,
        provider: ExchangeProvider,
        *,
        cache: MarketCache | None = None,
        candle_repository: CandleRepository | None = None,
        event_bus: EventBus | None = None,
        websocket_enabled: bool = True,
        history_candles: int = 300,
    ) -> None:
        self._provider = provider
        self._cache = cache or MarketCache()
        self._repository = candle_repository
        self._event_bus = event_bus
        self._websocket_enabled = websocket_enabled
        self._history_candles = history_candles

        #: کلاینت وب‌سوکت صرافی فعال (نوعش به صرافی بستگی دارد)
        self._websocket: Any | None = None
        self._live_tickers: dict[str, Ticker] = {}
        self._live_candles: dict[tuple[str, str], Candle] = {}
        self._connection_status = ConnectionStatus.DISCONNECTED
        self._ticker_listeners: list[Callable[[Ticker], None]] = []
        #: آیا آخرین فراخوانی REST موفق بوده — مبنای «آنلاین بودن»
        self._rest_alive = False
        # شمارندهٔ شکست‌های پشت‌سرهم REST (برای تحمل قطعی‌های گذرا)
        self._rest_failures = 0
        self._symbols: dict[str, SymbolInfo] = {}
        self._inflight: dict[str, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """
        راه‌اندازی موتور: اتصال REST و در صورت فعال بودن، شروع WebSocket.

        اگر اینترنت در دسترس نباشد، خطا پرتاب نمی‌شود؛ برنامه در حالت آفلاین
        بالا می‌آید و داده ذخیره‌شده را نشان می‌دهد.
        """
        await self._provider.connect()
        is_online = await self._provider.ping()
        self._update_status(ConnectionStatus.CONNECTED if is_online else ConnectionStatus.DISCONNECTED)
        if is_online:
            self._mark_rest_alive(True)

        # پینگ اول اگر شکست بخورد، سوکت را هم خاموش نمی‌کنیم. REST
        # جایگزین است و سوکت باید دوباره تلاش کند، نه اینکه تا ری‌استارت
        # هرگز شروع نشود.
        if self._websocket_enabled:
            await self.ensure_streaming()
        logger.info("Market data engine started (online=%s)", is_online)

    async def ensure_streaming(self) -> None:
        """
        شروع وب‌سوکت اگر هنوز شروع نشده باشد.

        نبود کلاینت یا شکست شروع، برنامه را آفلاین نمی‌کند. REST می‌ماند.
        """
        if self._websocket is not None or not self._websocket_enabled:
            return
        capabilities = getattr(self._provider, "capabilities", None)
        if capabilities is None or not getattr(capabilities, "supports_websocket", False):
            return
        try:
            client = self._provider.create_websocket_client(
                on_ticker=self._handle_live_ticker,
                on_candle=self._handle_live_candle,
                on_status_change=self._handle_ws_status,
            )
        except Exception as exc:  # noqa: BLE001 - سوکت نباید بالا آمدن برنامه را بشکند
            logger.warning("Live stream unavailable, using REST: %s", exc)
            return
        if client is None:
            logger.warning(
                "Exchange '%s' advertises WebSocket support but provides no client; "
                "falling back to REST polling",
                self._provider.name,
            )
            return
        self._websocket = client
        try:
            await self._websocket.start()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Live stream start failed, using REST: %s", exc)
            self._websocket = None

    async def keepalive(self) -> bool:
        """
        نگه داشتن اتصال.

        یک پینگ ناموفق بلافاصله آفلاین اعلام نمی‌شود؛ تحمل شکست REST
        همان قانون قبلی است. سوکت افتاده هم اینجا دوباره راه می‌افتد.
        """
        await self.ensure_streaming()
        try:
            ok = await self._provider.ping()
        except Exception:  # noqa: BLE001
            self._mark_rest_alive(False)
            return bool(self.is_online)
        self._mark_rest_alive(bool(ok))
        return bool(self.is_online)

    async def stop(self) -> None:
        """توقف کامل موتور و آزادسازی منابع."""
        if self._websocket is not None:
            await self._websocket.stop()
            self._websocket = None
        await self._provider.close()
        self._update_status(ConnectionStatus.DISCONNECTED)
        logger.info("Market data engine stopped")

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    @property
    def exchange_name(self) -> str:
        """نام صرافی فعال."""
        return self._provider.name

    @property
    def connection_status(self) -> ConnectionStatus:
        """وضعیت اتصال به صرافی."""
        return self._connection_status

    @property
    def is_online(self) -> bool:
        """آیا اتصال زنده برقرار است؟"""
        return self._connection_status is ConnectionStatus.CONNECTED

    @property
    def websocket_status(self) -> ConnectionStatus:
        """وضعیت اتصال WebSocket."""
        return self._websocket.status if self._websocket else ConnectionStatus.DISCONNECTED

    @property
    def cache_stats(self) -> dict[str, Any]:
        """آمار حافظه نهان."""
        return self._cache.stats

    def _update_status(self, status: ConnectionStatus) -> None:
        """به‌روزرسانی وضعیت و انتشار رویداد مربوطه."""
        if self._connection_status is status:
            return
        self._connection_status = status
        if self._event_bus is None:
            return
        if status is ConnectionStatus.CONNECTED:
            self._event_bus.publish(
                EventType.EXCHANGE_CONNECTED, {"exchange": self._provider.name}, source="MarketDataEngine"
            )
        elif status is ConnectionStatus.RECONNECTING:
            self._event_bus.publish(EventType.EXCHANGE_RECONNECTING, {"exchange": self._provider.name})
        else:
            self._event_bus.publish(EventType.EXCHANGE_DISCONNECTED, {"exchange": self._provider.name})

    def _mark_rest_alive(self, alive: bool) -> None:
        """
        ثبت سلامت مسیر REST و به‌روزرسانی وضعیت کلی.

        «آنلاین» یعنی داده تازه می‌رسد — از هر مسیری. تا وقتی REST جواب
        می‌دهد، افتادن WebSocket نباید کاربر را آفلاین نشان دهد.

        کاربر گزارش کرد «خیلی آفلاین می‌زند». علتش این بود که **یک**
        درخواست ناموفق بی‌درنگ وضعیت را آفلاین می‌کرد؛ روی اینترنت
        ناپایدار این یعنی چشمک‌زدن مداوم بین آنلاین و آفلاین. حالا
        آفلاین فقط پس از `REST_FAILURE_TOLERANCE` شکستِ پشت‌سرهم اعلام
        می‌شود، ولی **یک** موفقیت فوراً به آنلاین برمی‌گرداند —
        بدبینی کند، خوش‌بینی سریع.
        """
        if alive:
            self._rest_failures = 0
            self._rest_alive = True
            self._update_status(ConnectionStatus.CONNECTED)
            return

        self._rest_failures = getattr(self, "_rest_failures", 0) + 1
        if self._rest_failures < REST_FAILURE_TOLERANCE:
            # هنوز آفلاین اعلام نمی‌کنیم: احتمالاً یک قطعی گذرا بود.
            logger.debug(
                "REST failure %d/%d; staying online",
                self._rest_failures,
                REST_FAILURE_TOLERANCE,
            )
            return

        self._rest_alive = False
        if self.websocket_status is not ConnectionStatus.CONNECTED:
            self._update_status(ConnectionStatus.DISCONNECTED)

    def add_ticker_listener(self, callback: Callable[[Ticker], None]) -> None:
        """افزودن شنونده تیک زنده."""
        if callback not in self._ticker_listeners:
            self._ticker_listeners.append(callback)

    def remove_ticker_listener(self, callback: Callable[[Ticker], None]) -> None:
        """حذف شنونده تیک زنده."""
        if callback in self._ticker_listeners:
            self._ticker_listeners.remove(callback)

    def _handle_ws_status(self, status: ConnectionStatus) -> None:
        """
        همگام‌سازی وضعیت کلی با وضعیت WebSocket.

        نکته مهم: افتادن WebSocket به‌تنهایی یعنی «آفلاین» نیست. تا وقتی
        REST پاسخ می‌دهد، برنامه آنلاین است و فقط تأخیر داده بیشتر می‌شود.
        پیش از این، قطع شدن سوکت وضعیت را آفلاین می‌کرد و کاربر با وجود
        اتصال سالم، پیام آفلاین می‌دید.
        """
        if status is ConnectionStatus.CONNECTED:
            self._update_status(ConnectionStatus.CONNECTED)
        elif status is ConnectionStatus.RECONNECTING and not self._rest_alive:
            self._update_status(ConnectionStatus.RECONNECTING)

    # ------------------------------------------------------------------
    # پردازش داده زنده
    # ------------------------------------------------------------------
    def _handle_live_ticker(self, ticker: Ticker) -> None:
        """
        دریافت قیمت زنده از WebSocket.

        داده در حافظه نگه داشته می‌شود و رویداد منتشر می‌گردد؛ نوشتن در
        پایگاه داده در این مسیر انجام نمی‌شود تا فشار I/O ایجاد نکند.
        """
        self._live_tickers[ticker.symbol] = ticker
        # تیک زنده یعنی داده می‌رسد. افتادن یک درخواست REST نباید
        # برنامه‌ای را که قیمت لحظه‌ای دارد آفلاین نشان دهد.
        self._mark_rest_alive(True)
        for listener in list(self._ticker_listeners):
            try:
                listener(ticker)
            except Exception:  # noqa: BLE001 - شنونده خراب نباید جریان را قطع کند
                logger.exception("Ticker listener failed")
        if self._event_bus is not None:
            self._event_bus.publish(
                EventType.TICKER_UPDATED,
                {"symbol": ticker.symbol, "price": ticker.last_price, "change": ticker.change_percent},
                source="MarketDataEngine",
            )

    def _handle_live_candle(self, symbol: str, timeframe: str, candle: Candle) -> None:
        """
        دریافت کندل زنده از WebSocket.

        کندل جاری در حافظه به‌روز می‌شود و حافظه نهان همان نماد/تایم‌فریم
        باطل می‌گردد تا محاسبه بعدی اندیکاتور با داده تازه انجام شود.
        """
        self._live_candles[(symbol, timeframe)] = candle
        self._cache.invalidate_prefix(MarketCache.make_key("candles", self._provider.name, symbol, timeframe))
        if self._event_bus is not None:
            self._event_bus.publish(
                EventType.CANDLE_UPDATED,
                {"symbol": symbol, "timeframe": timeframe, "close": candle.close},
                source="MarketDataEngine",
            )

    # ------------------------------------------------------------------
    # جلوگیری از درخواست تکراری
    # ------------------------------------------------------------------
    async def _deduplicated(self, key: str, factory) -> Any:
        """
        اجرای یک عملیات با تضمین «یک درخواست در هر لحظه» برای هر کلید.

        اگر دو بخش برنامه هم‌زمان یک داده را بخواهند، فقط یک درخواست شبکه
        ارسال می‌شود و هر دو از نتیجه یکسان استفاده می‌کنند.

        پیاده‌سازی با Task انجام شده (نه Future دستی) تا اگر عملیات خطا دهد و
        هیچ‌کس منتظر نباشد، هشدار «استثنای بازیابی‌نشده» در لاگ ظاهر نشود.
        """
        async with self._lock:
            task = self._inflight.get(key)
            is_owner = task is None
            if task is None:
                task = asyncio.ensure_future(factory())
                self._inflight[key] = task

        try:
            return await asyncio.shield(task)
        finally:
            if is_owner:
                async with self._lock:
                    self._inflight.pop(key, None)
                # بازیابی استثنا برای جلوگیری از هشدار asyncio
                if task.done() and not task.cancelled():
                    task.exception()

    # ------------------------------------------------------------------
    # نمادها
    # ------------------------------------------------------------------
    async def get_symbols(self, *, force_refresh: bool = False) -> list[SymbolInfo]:
        """
        دریافت فهرست نمادها با حافظه نهان طولانی‌مدت.

        فهرست نمادها به‌ندرت تغییر می‌کند، بنابراین یک ساعت معتبر می‌ماند.
        """
        cache_key = MarketCache.make_key("symbols", self._provider.name)
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        async def _fetch() -> list[SymbolInfo]:
            symbols = await self._provider.get_symbols()
            self._symbols = {s.symbol: s for s in symbols}
            self._cache.set(cache_key, symbols, ttl_seconds=3600)
            return symbols

        return await self._deduplicated(cache_key, _fetch)

    def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """اطلاعات یک نماد از حافظه (بدون درخواست شبکه)."""
        return self._symbols.get(symbol)

    # ------------------------------------------------------------------
    # قیمت و تیکر
    # ------------------------------------------------------------------
    async def get_ticker(self, symbol: str, *, max_age_seconds: float = 5.0) -> Ticker:
        """
        دریافت وضعیت ۲۴ ساعته یک نماد.

        اولویت با داده زنده WebSocket است؛ در نبود آن از REST استفاده
        می‌شود و نتیجه برای مدت کوتاهی در حافظه نهان می‌ماند.
        """
        live = self._live_tickers.get(symbol)
        if live is not None:
            return live

        cache_key = MarketCache.make_key("ticker", self._provider.name, symbol)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        async def _fetch() -> Ticker:
            ticker = await self._provider.get_ticker(symbol)
            self._cache.set(cache_key, ticker, ttl_seconds=max_age_seconds)
            self._persist_ticker(ticker)
            return ticker

        return await self._deduplicated(cache_key, _fetch)


    @staticmethod
    def _ticker_is_fresh(ticker: Ticker, max_age: float = 15.0) -> bool:
        """تیکر بدون زمان دیده‌شدن کهنه حساب نمی‌شود."""
        import time

        seen = int(getattr(ticker, "timestamp", 0) or 0)
        if seen <= 0:
            return True
        stamp = seen / 1000.0 if seen > 10_000_000_000 else float(seen)
        return time.time() - stamp <= max_age

    async def get_current_price(self, symbol: str) -> float:
        """
        قیمت لحظه‌ای یک نماد.

        ترتیب اولویت: داده زنده ← حافظه نهان ← درخواست REST.
        هرگز قیمت حدسی برگردانده نمی‌شود.
        """
        live = self._live_tickers.get(symbol)
        if live is not None and live.last_price > 0 and self._ticker_is_fresh(live):
            return live.last_price

        cache_key = MarketCache.make_key("price", self._provider.name, symbol)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        async def _fetch() -> float:
            price = await self._provider.get_current_price(symbol)
            self._cache.set(cache_key, price, ttl_seconds=3)
            self._mark_rest_alive(True)
            return price

        return await self._deduplicated(cache_key, _fetch)

    def peek_candles(self, symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        """
        کندل‌های موجود در حافظه، بدون درخواست شبکه.

        نمودار زنده نباید برای هر تیک قیمت، کل تاریخ را دوباره بکشد.
        اگر چیزی در حافظه نباشد، فهرست خالی برمی‌گردد و REST جایگزین است.
        """
        count = limit or self._history_candles
        cache_key = MarketCache.make_key("candles", self._provider.name, symbol, timeframe, count)
        cached = self._cache.get(cache_key)
        if cached:
            return self._merge_live_candle(symbol, timeframe, list(cached))
        live = self._live_candles.get((symbol, timeframe))
        if live is None:
            return []
        return [live]

    async def get_all_tickers(self, *, max_age_seconds: float = 10.0) -> list[Ticker]:
        """
        دریافت وضعیت تمام نمادها در یک درخواست (برای صفحه بازارها).

        استفاده از این متد به‌جای حلقه روی نمادها، فشار API را به شدت کم
        می‌کند.
        """
        cache_key = MarketCache.make_key("all_tickers", self._provider.name)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        async def _fetch() -> list[Ticker]:
            tickers = await self._provider.get_all_tickers()
            # موفقیت REST یعنی واقعاً آنلاین هستیم، حتی اگر WebSocket افتاده باشد
            self._mark_rest_alive(True)
            self._cache.set(cache_key, tickers, ttl_seconds=max_age_seconds)
            for ticker in tickers[:50]:
                self._persist_ticker(ticker)
            return tickers

        try:
            return await self._deduplicated(cache_key, _fetch)
        except Exception:
            self._mark_rest_alive(False)
            raise

    def _persist_ticker(self, ticker: Ticker) -> None:
        """ذخیره وضعیت لحظه‌ای در پایگاه داده برای حالت آفلاین."""
        if self._repository is None:
            return
        try:
            self._repository.save_ticker_snapshot(
                self._provider.name,
                ticker.symbol,
                last_price=ticker.last_price,
                high_24h=ticker.high_24h,
                low_24h=ticker.low_24h,
                volume_24h=ticker.volume_24h,
                turnover_24h=ticker.turnover_24h,
                change_percent=ticker.change_percent,
            )
        except AppError as exc:
            logger.debug("Persisting ticker failed: %s", exc.message)

    # ------------------------------------------------------------------
    # کندل‌ها
    # ------------------------------------------------------------------
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        *,
        force_refresh: bool = False,
        allow_offline: bool = True,
    ) -> list[Candle]:
        """
        دریافت کندل‌ها با راهبرد چندلایه.

        ترتیب: حافظه نهان ← درخواست شبکه ← داده ذخیره‌شده (حالت آفلاین).

        طول عمر حافظه نهان متناسب با تایم‌فریم تعیین می‌شود: کندل یک‌دقیقه‌ای
        سریع کهنه می‌شود، اما کندل روزانه ساعت‌ها معتبر می‌ماند.
        """
        count = limit or self._history_candles
        cache_key = MarketCache.make_key("candles", self._provider.name, symbol, timeframe, count)

        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return self._merge_live_candle(symbol, timeframe, cached)

        async def _fetch() -> list[Candle]:
            candles = await self._provider.get_ohlcv(symbol, timeframe, limit=count)
            # کندل گرفتن هم یک مسیر زندهٔ REST است. پیش از این فقط
            # `get_all_tickers` سلامت را گزارش می‌کرد، برای همین کاربری
            # که در صفحهٔ تحلیل بود آفلاین می‌ماند با اینکه داده می‌آمد.
            self._mark_rest_alive(True)
            ttl = self._cache_ttl_for(timeframe)
            self._cache.set(cache_key, candles, ttl_seconds=ttl)
            self._persist_candles(symbol, timeframe, candles)
            return candles

        try:
            candles = await self._deduplicated(cache_key, _fetch)
            return self._merge_live_candle(symbol, timeframe, candles)
        except (NetworkError, AppError) as exc:
            if not allow_offline:
                raise
            logger.warning(
                "Falling back to stored candles for %s %s: %s", symbol, timeframe, exc.__class__.__name__
            )
            self._mark_rest_alive(False)
            stored = self._load_stored_candles(symbol, timeframe, count)
            if stored:
                return stored
            raise InsufficientDataError(
                f"No market data available for {symbol} {timeframe} (offline and no cached data)",
                details={"symbol": symbol, "timeframe": timeframe},
            ) from exc

    def _merge_live_candle(self, symbol: str, timeframe: str, candles: list[Candle]) -> list[Candle]:
        """
        جایگزینی آخرین کندل با نسخه زنده WebSocket در صورت وجود.

        بدون این کار، نمودار تا رسیدن زمان انقضای حافظه نهان «یخ‌زده» به نظر
        می‌رسد.
        """
        live = self._live_candles.get((symbol, timeframe))
        if live is None or not candles:
            return candles
        if live.timestamp < candles[-1].timestamp:
            return candles
        merged = list(candles)
        if live.timestamp == merged[-1].timestamp:
            merged[-1] = live
        else:
            merged.append(live)
        return merged

    @staticmethod
    def _cache_ttl_for(timeframe: str) -> float:
        """
        محاسبه طول عمر مناسب حافظه نهان بر اساس تایم‌فریم.

        قاعده: یک‌بیستم طول تایم‌فریم، با کف ۳ ثانیه و سقف ۳۰۰ ثانیه.
        """
        seconds = timeframe_seconds(timeframe)
        return max(3.0, min(300.0, seconds / 20))

    def _persist_candles(self, symbol: str, timeframe: str, candles: list[Candle]) -> None:
        """ذخیره کندل‌ها در پایگاه داده برای استفاده آفلاین."""
        if self._repository is None or not candles:
            return
        try:
            self._repository.save_candles(self._provider.name, symbol, timeframe, candles[-500:])
        except AppError as exc:
            logger.debug("Persisting candles failed: %s", exc.message)

    def _load_stored_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        """خواندن کندل‌های ذخیره‌شده هنگام قطع اینترنت."""
        if self._repository is None:
            return []
        try:
            return self._repository.get_candles(self._provider.name, symbol, timeframe, limit)
        except AppError:
            return []

    async def get_multi_timeframe_candles(
        self, symbol: str, timeframes: list[str], limit: int | None = None
    ) -> dict[str, list[Candle]]:
        """
        دریافت هم‌زمان کندل چند تایم‌فریم.

        درخواست‌ها به‌صورت موازی ارسال می‌شوند تا زمان تحلیل چند تایم‌فریمی
        به‌جای مجموع، برابر کندترین درخواست باشد. شکست یک تایم‌فریم، بقیه را
        از بین نمی‌برد.
        """
        tasks = {
            timeframe: asyncio.create_task(self.get_candles(symbol, timeframe, limit))
            for timeframe in timeframes
        }
        results: dict[str, list[Candle]] = {}
        for timeframe, task in tasks.items():
            try:
                results[timeframe] = await task
            except AppError as exc:
                logger.warning("Timeframe %s unavailable for %s: %s", timeframe, symbol, exc.message)
                results[timeframe] = []
        return results

    # ------------------------------------------------------------------
    # دفتر سفارش
    # ------------------------------------------------------------------
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """دریافت دفتر سفارش با حافظه نهان بسیار کوتاه‌مدت."""
        cache_key = MarketCache.make_key("orderbook", self._provider.name, symbol, depth)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        async def _fetch() -> OrderBook:
            orderbook = await self._provider.get_orderbook(symbol, depth)
            self._cache.set(cache_key, orderbook, ttl_seconds=2)
            return orderbook

        return await self._deduplicated(cache_key, _fetch)

    # ------------------------------------------------------------------
    # مدیریت اشتراک
    # ------------------------------------------------------------------
    async def subscribe_symbol(self, symbol: str, timeframe: str | None = None) -> None:
        """
        اشتراک داده زنده یک نماد.

        فقط نمادهایی که کاربر واقعاً می‌بیند مشترک می‌شوند تا پهنای باند و
        منابع بیهوده مصرف نشود.
        """
        if self._websocket is None:
            return
        await self._websocket.subscribe_ticker(symbol)
        if timeframe:
            await self._websocket.subscribe_candles(symbol, timeframe)

    async def unsubscribe_symbol(self, symbol: str, timeframe: str | None = None) -> None:
        """لغو اشتراک داده زنده یک نماد."""
        if self._websocket is None:
            return
        await self._websocket.unsubscribe_ticker(symbol)
        if timeframe:
            await self._websocket.unsubscribe_candles(symbol, timeframe)

    async def set_watchlist_subscriptions(self, symbols: list[str], max_symbols: int = 80) -> None:
        """
        هم‌گام‌سازی اشتراک‌ها با فهرست پیگیری کاربر.

        تعداد اشتراک‌ها محدود می‌شود تا در فهرست‌های بزرگ، برنامه سبک بماند.
        """
        if self._websocket is None:
            return
        await self._websocket.unsubscribe_all()
        for symbol in symbols[:max_symbols]:
            await self._websocket.subscribe_ticker(symbol)
        logger.debug("Watchlist subscriptions updated (%d symbols)", min(len(symbols), max_symbols))
