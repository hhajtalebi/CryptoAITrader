"""
موتور معاملهٔ خودکار — باز کردن، پایش و بستن خودکار معامله‌ها.

### قانون ایمنی اصلی

پیش‌فرض **همیشه کاغذی** است. برای معاملهٔ واقعی، کاربر باید سه کار را
جداگانه انجام دهد:

    ۱. `trading.auto_enabled` را روشن کند
    ۲. `trading.mode` را روی `live` بگذارد
    ۳. عبارت تأیید را دقیقاً تایپ کند (`LIVE_CONFIRMATION_PHRASE`)

یک تیک ساده کافی نیست. کسی که با پول واقعی معامله می‌کند باید بداند
دارد چه می‌کند، و هیچ‌کدام از این سه گام نباید تصادفی رخ دهد.

### چرا سفارش واقعی هنوز اجرا نمی‌شود

`LiveOrderGateway` عمداً استثنا می‌دهد. آداپتور صرافی هنوز متد ثبت
سفارش امضاشده ندارد. نوشتن یک مسیر «شبه‌واقعی» که در سکوت شکست بخورد،
از نداشتنش بدتر است: کاربر فکر می‌کند معامله باز شده در حالی که نشده.

وقتی آداپتور آماده شد، فقط همین کلاس پیاده‌سازی می‌شود و بقیهٔ موتور
دست نمی‌خورد.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: کاربر باید دقیقاً این عبارت را تایپ کند تا معاملهٔ واقعی فعال شود.
LIVE_CONFIRMATION_PHRASE = "معامله واقعی را می‌پذیرم"

#: سقف سخت تعداد معامله‌های همزمان. حتی اگر کاربر عدد بزرگ‌تری بگذارد.
HARD_MAX_CONCURRENT = 10

#: سقف سخت اهرم. اهرم ۱۲۵ یعنی ۰٫۸٪ حرکت مخالف، کل پول را می‌برد.
HARD_MAX_LEVERAGE = 25.0


class LiveTradingNotEnabledError(RuntimeError):
    """تلاش برای معاملهٔ واقعی بدون تأیید کامل کاربر."""


class LiveOrderGateway:
    """
    درگاه سفارش واقعی — هنوز پیاده نشده و عمداً صریح شکست می‌خورد.

    وقتی آداپتور صرافی متد سفارش امضاشده گرفت، اینجا پیاده می‌شود.
    """

    def __init__(self, exchange_name: str) -> None:
        self.exchange_name = exchange_name

    async def open_position(self, **_kwargs: Any) -> dict[str, Any]:
        """ثبت سفارش واقعی."""
        raise LiveTradingNotEnabledError(
            f"ثبت سفارش واقعی روی «{self.exchange_name}» هنوز پیاده‌سازی "
            "نشده است. حالت کاغذی همهٔ منطق را با قیمت زنده اجرا می‌کند."
        )

    async def close_position(self, **_kwargs: Any) -> dict[str, Any]:
        """بستن سفارش واقعی."""
        raise LiveTradingNotEnabledError(
            f"بستن سفارش واقعی روی «{self.exchange_name}» هنوز پیاده‌سازی نشده است."
        )


@dataclass
class AutoTradeConfig:
    """
    تنظیم‌های معاملهٔ خودکار — همه‌چیز دست کاربر است.

    هیچ‌کدام از این عددها حدس زده نمی‌شوند؛ کاربر آن‌ها را در تنظیمات
    می‌گذارد.
    """

    #: مبلغ مارجین هر معامله به دلار
    margin_per_trade: float = 10.0
    #: هدف سود به دلار (نه درصد — چون کاربر این‌طور فکر می‌کند)
    target_profit: float = 2.0
    #: حداکثر زیان قابل تحمل به دلار
    max_loss: float = 3.0
    #: اهرم
    leverage: float = 10.0
    #: بیشترین معاملهٔ همزمان
    max_concurrent: int = 3
    #: بیشترین زمان باز ماندن یک معامله (ثانیه) — اسکلپ نباید طولانی شود
    max_hold_seconds: int = 900
    #: فاصلهٔ پایش قیمت (ثانیه)
    poll_seconds: float = 5.0
    #: سقف زیان روزانه؛ با رسیدن به آن، موتور خودش می‌ایستد
    daily_loss_limit: float = 20.0
    #: `paper` یا `live`
    mode: str = "paper"
    #: عبارت تأیید معاملهٔ واقعی
    live_confirmation: str = ""

    def validated(self) -> AutoTradeConfig:
        """
        اعمال سقف‌های سخت.

        کاربر می‌تواند محتاط‌تر باشد ولی نمی‌تواند از این حدها فراتر
        برود. این محافظ در برابر یک صفر اضافی هنگام تایپ است.
        """
        self.leverage = max(1.0, min(float(self.leverage or 1.0), HARD_MAX_LEVERAGE))
        self.max_concurrent = max(
            1, min(int(self.max_concurrent or 1), HARD_MAX_CONCURRENT)
        )
        self.margin_per_trade = max(1.0, float(self.margin_per_trade or 1.0))
        self.target_profit = max(0.01, float(self.target_profit or 0.01))
        self.max_loss = max(0.01, float(self.max_loss or 0.01))
        self.poll_seconds = max(1.0, float(self.poll_seconds or 5.0))
        self.max_hold_seconds = max(30, int(self.max_hold_seconds or 900))
        return self

    @property
    def is_live(self) -> bool:
        """
        آیا واقعاً باید سفارش واقعی برود؟

        هر دو شرط لازم است: هم حالت `live` و هم عبارت تأیید دقیق.
        """
        return (
            str(self.mode).lower() == "live"
            and self.live_confirmation.strip() == LIVE_CONFIRMATION_PHRASE
        )

    @property
    def notional(self) -> float:
        """ارزش کل موقعیت (مارجین × اهرم)."""
        return self.margin_per_trade * self.leverage

    def target_percent(self) -> float:
        """هدف سود بر حسب درصدِ حرکت قیمت."""
        return (self.target_profit / self.notional * 100.0) if self.notional else 0.0

    def stop_percent(self) -> float:
        """حد ضرر بر حسب درصدِ حرکت قیمت."""
        return (self.max_loss / self.notional * 100.0) if self.notional else 0.0


@dataclass
class ManagedTrade:
    """یک معاملهٔ باز که موتور آن را پایش می‌کند."""

    trade_id: int
    symbol: str
    side: str
    entry_price: float
    quantity: float
    leverage: float
    target_price: float
    stop_price: float
    opened_at: datetime
    mode: str = "paper"
    extra: dict[str, Any] = field(default_factory=dict)

    def unrealised(self, price: float) -> float:
        """سود یا زیان فعلی به دلار."""
        direction = 1.0 if self.side == "long" else -1.0
        return (price - self.entry_price) * direction * self.quantity

    def should_close(self, price: float, now: datetime, max_hold: int) -> str:
        """
        آیا باید بسته شود؟ رشتهٔ خالی یعنی نه.

        ترتیب بررسی مهم است: حد ضرر **اول**. اگر قیمت در یک پرش از هر
        دو سطح رد شود، باید محافظه‌کارانه‌ترین نتیجه ثبت شود، نه
        خوش‌بینانه‌ترین.
        """
        direction = 1.0 if self.side == "long" else -1.0
        moved = (price - self.entry_price) * direction

        if moved <= (self.stop_price - self.entry_price) * direction:
            return "stop_loss"
        if moved >= (self.target_price - self.entry_price) * direction:
            return "take_profit"
        if (now - self.opened_at).total_seconds() >= max_hold:
            return "timeout"
        return ""


class AutoTrader:
    """
    موتور معاملهٔ خودکار.

    چرخهٔ کار: نامزد بگیر ← اگر جا هست باز کن ← تا رسیدن به هدف یا حد
    ضرر پایش کن ← ببند ← تکرار.
    """

    def __init__(
        self,
        *,
        config: AutoTradeConfig,
        price_source: Callable[[str], Awaitable[float]],
        repository: Any,
        candidate_source: Callable[[], Awaitable[list[Any]]] | None = None,
        gateway: LiveOrderGateway | None = None,
        user_id: int | None = None,
    ) -> None:
        self.config = config.validated()
        self._price_source = price_source
        self._repo = repository
        self._candidate_source = candidate_source
        self._gateway = gateway
        self._user_id = user_id

        self._open: dict[int, ManagedTrade] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._realised_today = 0.0
        self._listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._halted_reason = ""

    # ---- وضعیت ------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """آیا حلقه فعال است؟"""
        return self._running

    @property
    def open_trades(self) -> list[ManagedTrade]:
        """معامله‌های باز."""
        return list(self._open.values())

    @property
    def realised_today(self) -> float:
        """سود یا زیان محقق‌شدهٔ امروز."""
        return round(self._realised_today, 4)

    @property
    def halted_reason(self) -> str:
        """اگر موتور خودش ایستاده، چرا."""
        return self._halted_reason

    def add_listener(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """افزودن شنونده برای رویدادها (باز شدن، بسته شدن، توقف)."""
        self._listeners.append(callback)

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        """
        اعلام رویداد.

        خطای یک شنونده نباید موتور معاملات را از کار بیندازد.
        """
        for callback in self._listeners:
            try:
                callback(event, payload)
            except Exception:  # noqa: BLE001
                logger.exception("Auto-trade listener failed for %s", event)

    # ---- محافظ‌ها ---------------------------------------------------

    def _check_daily_limit(self) -> bool:
        """
        آیا سقف زیان روزانه رد شده است؟

        این آخرین خط دفاع در برابر یک روز بد است.
        """
        if self._realised_today <= -abs(self.config.daily_loss_limit):
            self._halted_reason = (
                f"سقف زیان روزانه ({self.config.daily_loss_limit} دلار) رد شد"
            )
            return False
        return True

    def preflight(self) -> tuple[bool, str]:
        """
        بررسی پیش از شروع — هرگز با پیکربندی مشکوک شروع نکن.
        """
        config = self.config
        if config.mode == "live" and not config.is_live:
            return False, (
                "برای معاملهٔ واقعی باید عبارت تأیید را دقیقاً وارد کنید: "
                f"«{LIVE_CONFIRMATION_PHRASE}»"
            )
        if config.max_loss <= 0:
            return False, "حد ضرر باید بزرگ‌تر از صفر باشد"
        if config.target_profit <= 0:
            return False, "هدف سود باید بزرگ‌تر از صفر باشد"
        if config.target_profit > config.max_loss * 5:
            return False, (
                "هدف سود نسبت به حد ضرر بسیار بزرگ است؛ چنین معامله‌ای "
                "تقریباً هرگز به هدف نمی‌رسد"
            )
        return True, "آماده"

    # ---- عملیات -----------------------------------------------------

    async def open_trade(self, candidate: Any) -> ManagedTrade | None:
        """
        باز کردن یک معامله بر پایهٔ نامزد.

        در حالت کاغذی، قیمت زنده است و فقط سفارش واقعی نمی‌رود.
        """
        if len(self._open) >= self.config.max_concurrent:
            return None
        if not self._check_daily_limit():
            return None

        symbol = getattr(candidate, "symbol", "")
        direction = str(getattr(candidate, "direction", "LONG")).upper()
        side = "long" if direction == "LONG" else "short"

        price = await self._price_source(symbol)
        if price <= 0:
            logger.warning("Auto-trade skipped %s: no price", symbol)
            return None

        config = self.config
        quantity = config.notional / price
        sign = 1.0 if side == "long" else -1.0
        target = price * (1 + sign * config.target_percent() / 100.0)
        stop = price * (1 - sign * config.stop_percent() / 100.0)

        if config.is_live:
            if self._gateway is None:
                raise LiveTradingNotEnabledError("درگاه سفارش واقعی تنظیم نشده است")
            await self._gateway.open_position(
                symbol=symbol, side=side, quantity=quantity, leverage=config.leverage
            )

        record = self._repo.open_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
            user_id=self._user_id,
            stop_loss=stop,
            take_profit=target,
            leverage=config.leverage,
            mode="live" if config.is_live else "paper",
            note="معاملهٔ خودکار اسکلپ",
            extra={
                "auto": True,
                "score": float(getattr(candidate, "score", 0.0)),
                "target_profit": config.target_profit,
                "max_loss": config.max_loss,
            },
        )

        managed = ManagedTrade(
            trade_id=int(record["id"]),
            symbol=symbol,
            side=side,
            entry_price=price,
            quantity=quantity,
            leverage=config.leverage,
            target_price=target,
            stop_price=stop,
            opened_at=datetime.now(UTC),
            mode="live" if config.is_live else "paper",
        )
        self._open[managed.trade_id] = managed
        logger.info(
            "Auto-trade opened %s %s @ %.6f target=%.6f stop=%.6f",
            side, symbol, price, target, stop,
        )
        self._emit("opened", {"trade": managed, "record": record})
        return managed

    async def close_trade(self, managed: ManagedTrade, reason: str) -> dict[str, Any] | None:
        """بستن یک معامله و ثبت نتیجه."""
        price = await self._price_source(managed.symbol)
        if price <= 0:
            return None

        if managed.mode == "live" and self._gateway is not None:
            await self._gateway.close_position(
                symbol=managed.symbol, side=managed.side, quantity=managed.quantity
            )

        record = self._repo.close_trade(
            managed.trade_id, exit_price=price, note=f"بسته شد: {reason}"
        )
        self._open.pop(managed.trade_id, None)

        if record:
            self._realised_today += float(record.get("pnl") or 0.0)
        logger.info(
            "Auto-trade closed %s reason=%s pnl=%s",
            managed.symbol, reason, (record or {}).get("pnl"),
        )
        self._emit("closed", {"trade": managed, "record": record, "reason": reason})

        if not self._check_daily_limit():
            await self.stop()
            self._emit("halted", {"reason": self._halted_reason})
        return record

    async def check_open_trades(self) -> None:
        """پایش همهٔ معامله‌های باز و بستن آن‌هایی که باید بسته شوند."""
        now = datetime.now(UTC)
        for managed in list(self._open.values()):
            try:
                price = await self._price_source(managed.symbol)
            except Exception:  # noqa: BLE001
                logger.exception("Price check failed for %s", managed.symbol)
                continue
            if price <= 0:
                continue
            reason = managed.should_close(price, now, self.config.max_hold_seconds)
            if reason:
                await self.close_trade(managed, reason)

    async def _loop(self) -> None:
        """حلقهٔ اصلی."""
        while self._running:
            try:
                await self.check_open_trades()

                if (
                    self._candidate_source is not None
                    and len(self._open) < self.config.max_concurrent
                    and self._check_daily_limit()
                ):
                    candidates = await self._candidate_source()
                    held = {trade.symbol for trade in self._open.values()}
                    for candidate in candidates:
                        if len(self._open) >= self.config.max_concurrent:
                            break
                        # هرگز دو معامله روی یک نماد.
                        if getattr(candidate, "symbol", "") in held:
                            continue
                        await self.open_trade(candidate)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("Auto-trade loop iteration failed")

            await asyncio.sleep(self.config.poll_seconds)

    async def start(self) -> tuple[bool, str]:
        """شروع موتور."""
        if self._running:
            return True, "از قبل در حال اجراست"
        ok, message = self.preflight()
        if not ok:
            return False, message
        self._running = True
        self._halted_reason = ""
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Auto-trader started (mode=%s)", "live" if self.config.is_live else "paper"
        )
        self._emit("started", {"mode": "live" if self.config.is_live else "paper"})
        return True, "شروع شد"

    async def stop(self) -> None:
        """
        توقف موتور.

        معامله‌های باز **بسته نمی‌شوند** — بستن ناگهانی همه با قیمت
        بازار می‌تواند زیان را قفل کند. کاربر خودش تصمیم می‌گیرد.
        """
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        logger.info("Auto-trader stopped (%d open trades left)", len(self._open))
        self._emit("stopped", {"open": len(self._open)})

    async def close_all(self, reason: str = "manual") -> list[dict[str, Any]]:
        """بستن دستی همهٔ معامله‌های باز."""
        results = []
        for managed in list(self._open.values()):
            record = await self.close_trade(managed, reason)
            if record:
                results.append(record)
        return results
