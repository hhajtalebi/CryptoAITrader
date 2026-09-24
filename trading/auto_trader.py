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

### معماری رویدادمحور (v2.0)

پایش موقعیت دیگر منتظر تایمر نیست (خواستهٔ §۵/§۶):

    WebSocket tick → TickEngine → AutoTrader._on_tick
        → همان لحظه: TP / SL / سر‌به‌سر / تریلینگ / تایم‌اوت

حلقهٔ پس‌زمینه فقط سه کار باقی‌مانده دارد:
    • پویش نامزد برای ورود (هر `scan_interval_seconds`)
    • پایش fallback وقتی تیک نمی‌رسد (`poll_seconds`)
    • ابطال سیگنال و به‌روزرسانی فرصت‌ها

خروج معامله هرگز با `asyncio.sleep` کنترل نمی‌شود؛ خواب فقط برای
پویش دوره‌ای است.
"""

from __future__ import annotations

import asyncio
import math
import time
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

#: سقف سخت اهرم. کاربر صریحاً ۲۰۰ خواست. بالاتر از این دیگر سقف ایمنی نیست:
#: با اهرم ۲۰۰، حرکت مخالف حدود ۰٫۵٪ کل مارجین را می‌سوزاند.
HARD_MAX_LEVERAGE = 200.0

#: حالت‌های معتبر موتور (خواستهٔ §۳)
ENGINE_MODES = ("selected", "scan", "ai")

#: حالت‌های تخصیص سرمایه (خواستهٔ §۱۲)
ALLOCATION_MODES = ("fixed", "percent", "confidence", "risk", "hybrid", "ai")


class LiveTradingNotEnabledError(RuntimeError):
    """تلاش برای معاملهٔ واقعی بدون تأیید کامل کاربر."""


class LiveOrderGateway:
    """
    درگاه سفارش واقعی.

    بدون اجراکنندهٔ تأییدشده، باز و بستن هر دو بلند شکست می‌خورند.
    payload صرافی اینجا ساخته نمی‌شود. اگر اجراکننده باشد ولی حجم
    قرارداد مثبت نباشد، پیش از هر فراخوانی رد می‌شود.
    """

    def __init__(self, exchange_name: str, executor: Any | None = None) -> None:
        self.exchange_name = str(exchange_name or "").strip()
        self._executor = executor

    async def open_position(self, **kwargs: Any) -> dict[str, Any]:
        """ثبت سفارش واقعی، یا شکست صریح اگر مسیر تأیید نشده باشد."""
        if self._executor is None:
            raise LiveTradingNotEnabledError(
                f"ثبت سفارش واقعی روی «{self.exchange_name}» هنوز پیاده‌سازی "
                "نشده است. حالت کاغذی همهٔ منطق را با قیمت زنده اجرا می‌کند."
            )
        quantity = float(kwargs.get("quantity") or 0.0)
        if quantity <= 0:
            raise LiveTradingNotEnabledError(
                "حجم قرارداد تأیید نشده است؛ سفارش واقعی ارسال نشد"
            )
        result = self._executor.open_position(**kwargs)
        if hasattr(result, "__await__"):
            result = await result
        return dict(result or {})

    async def close_position(self, **kwargs: Any) -> dict[str, Any]:
        """بستن سفارش واقعی، یا شکست صریح اگر مسیر تأیید نشده باشد."""
        if self._executor is None:
            raise LiveTradingNotEnabledError(
                f"بستن سفارش واقعی روی «{self.exchange_name}» هنوز پیاده‌سازی نشده است."
            )
        quantity = float(kwargs.get("quantity") or 0.0)
        if quantity <= 0:
            raise LiveTradingNotEnabledError(
                "حجم قرارداد تأیید نشده است؛ سفارش واقعی ارسال نشد"
            )
        result = self._executor.close_position(**kwargs)
        if hasattr(result, "__await__"):
            result = await result
        return dict(result or {})


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
    #: فاصلهٔ پایش fallback (ثانیه) — خروج تیک‌محور است؛ این فقط وقتی
    #: وب‌سوکت خاموش است نجات می‌دهد (خواستهٔ §۵/§۶)
    poll_seconds: float = 5.0
    #: سقف زیان روزانه؛ با رسیدن به آن، موتور خودش می‌ایستد
    daily_loss_limit: float = 20.0
    #: `paper` یا `live`
    mode: str = "paper"
    #: عبارت تأیید معاملهٔ واقعی
    live_confirmation: str = ""
    #: کارمزد گیرندهٔ هر طرف. پیش‌فرض ۰٫۰۶٪ است.
    fee_rate: float = 0.0006

    # ---- v2.0: حالت‌ها و محافظ‌های رویدادمحور ----
    #: حالت موتور: selected | scan | ai (خواستهٔ §۳)
    engine_mode: str = "scan"
    #: نمادهای حالت Selected — رشتهٔ جداشده با ویرگول
    selected_symbols: str = ""
    #: فاصلهٔ پویش ورود (ثانیه) — جدا از پایش خروج
    scan_interval_seconds: float = 15.0
    #: حداقل گردش ۲۴ ساعته (دلار) برای واجد شرایط بودن نماد
    min_liquidity: float = 2_000_000.0
    #: بیشترین اسپرد قابل قبول (درصد)
    max_spread_percent: float = 0.25
    #: سن دادهٔ مجاز (ثانیه) — کهنه‌تر یعنی STALE و ورود ممنوع
    stale_after_seconds: float = 10.0
    #: لغزش تقریبی هر اجرا (درصد، علیه ما)
    slippage_percent: float = 0.02
    #: سر‌به‌سر: بعد از این میزان سود (دلار) حد ضرر به ورود + کارمزد می‌رود
    break_even_enabled: bool = True
    break_even_trigger: float = 1.0
    #: تریلینگ: بعد از این سود (دلار) حد ضرر دنبال می‌شود
    trailing_enabled: bool = False
    trailing_activation: float = 1.5
    trailing_offset: float = 0.4
    #: بستن وقتی جهت پیش‌بینی نماد برمی‌گردد
    signal_invalidation: bool = True
    #: سیاست تضاد روند: block (منع ورود) یا penalize (کاهش اطمینان)
    trend_conflict_policy: str = "block"
    #: حالت تخصیص سرمایه (خواستهٔ §۱۲)
    allocation_mode: str = "fixed"
    #: پارامتر حالت percent — درصد موجودی
    allocation_percent: float = 5.0
    #: سقف مجموع مارجین باز نسبت به موجودی (درصد)
    max_total_margin_percent: float = 60.0

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
        self.poll_seconds = max(0.25, float(self.poll_seconds or 5.0))
        self.max_hold_seconds = max(30, int(self.max_hold_seconds or 900))
        self.fee_rate = max(0.0, float(self.fee_rate or 0.0))
        self.engine_mode = (
            self.engine_mode if self.engine_mode in ENGINE_MODES else "scan"
        )
        self.scan_interval_seconds = max(
            3.0, float(self.scan_interval_seconds or 15.0)
        )
        self.min_liquidity = max(0.0, float(self.min_liquidity or 0.0))
        self.max_spread_percent = max(0.0, float(self.max_spread_percent or 0.0))
        self.stale_after_seconds = max(1.0, float(self.stale_after_seconds or 10.0))
        self.slippage_percent = max(0.0, float(self.slippage_percent or 0.0))
        self.break_even_trigger = max(0.01, float(self.break_even_trigger or 1.0))
        self.trailing_activation = max(0.01, float(self.trailing_activation or 1.5))
        self.trailing_offset = max(0.01, float(self.trailing_offset or 0.4))
        self.trend_conflict_policy = (
            "penalize" if str(self.trend_conflict_policy) == "penalize" else "block"
        )
        self.allocation_mode = (
            self.allocation_mode if self.allocation_mode in ALLOCATION_MODES else "fixed"
        )
        self.allocation_percent = max(0.1, min(100.0, float(self.allocation_percent or 5.0)))
        self.max_total_margin_percent = max(
            1.0, min(100.0, float(self.max_total_margin_percent or 60.0))
        )
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
        """ارزش کل موقعیت (مارجین × اهرم) — هرگز برابر مارجین نیست."""
        return self.margin_per_trade * self.leverage

    @property
    def selected_symbol_list(self) -> list[str]:
        """فهرست نمادهای حالت Selected — پاک‌شده و یکتا."""
        raw = str(self.selected_symbols or "")
        items = [part.strip().upper() for part in raw.replace(";", ",").split(",")]
        seen: list[str] = []
        for item in items:
            if item and item not in seen:
                seen.append(item)
        return seen

    def target_percent(self) -> float:
        """هدف سود بر حسب درصدِ حرکت قیمت."""
        return (self.target_profit / self.notional * 100.0) if self.notional else 0.0

    def stop_percent(self) -> float:
        """حد ضرر بر حسب درصدِ حرکت قیمت."""
        return (self.max_loss / self.notional * 100.0) if self.notional else 0.0


@dataclass
class ManagedTrade:
    """
    یک معاملهٔ باز که موتور آن را پایش می‌کند.

    فیلدهای v2.0 همگی اختیاری‌اند تا سازنده‌های قدیمی بدون تغییر
    کار کنند؛ همهٔ آن‌ها وضعیت خروج هوشمند را توصیف می‌کنند.
    """

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
    #: مارجین اختصاص‌یافته (برای سقف پرتفوی) — صفر یعنی از config پایه
    margin: float = 0.0
    #: Bid/Ask لحظهٔ ورود
    entry_bid: float = 0.0
    entry_ask: float = 0.0
    #: بهترین/بدترین قیمت دیده‌شده از ورود — سوخت تریلینگ
    extreme_price: float = 0.0
    #: حد ضرر فعلی (با سر‌به‌سر/تریلینگ جابه‌جا می‌شود)
    effective_stop: float = 0.0
    break_even_armed: bool = False
    trailing_active: bool = False
    #: مهر آخرین تیک پردازش‌شده (میلی‌ثانیه)
    last_tick_ms: float = 0.0

    def __post_init__(self) -> None:
        """مقدارهای وابسته که باید از روز اول درست باشند."""
        if self.extreme_price <= 0:
            self.extreme_price = self.entry_price
        if self.effective_stop <= 0:
            self.effective_stop = self.stop_price

    @property
    def is_long(self) -> bool:
        """جهت موقعیت."""
        return self.side == "long"

    @property
    def direction_sign(self) -> float:
        """۱ برای LONG و ۱- برای SHORT."""
        return 1.0 if self.is_long else -1.0

    def unrealised(self, price: float) -> float:
        """سود یا زیان فعلی به دلار."""
        return (price - self.entry_price) * self.direction_sign * self.quantity

    def net_unrealised(self, price: float) -> float:
        """برآورد خالص پس از کارمزد ورود و خروج در قیمت فعلی."""
        rate = float(self.extra.get("fee_rate", 0.0) or 0.0)
        entry_fee = float(self.extra.get("entry_fee", self.quantity * self.entry_price * rate))
        return self.unrealised(price) - entry_fee - self.quantity * price * rate

    def used_margin(self) -> float:
        """مارجین اشغال‌شده — مارجین واقعی یا برآیندِ config پایه."""
        if self.margin > 0:
            return self.margin
        return self.extra.get("margin", 0.0) or 0.0

    def mark(self, price: float, config: AutoTradeConfig) -> list[str]:
        """
        به‌روزرسانی وضعیت با یک تیک تازه — قلب خروج هوشمند.

        کارها: به‌روزرسانی اوج قیمت، فعال‌سازی سر‌به‌سر، دنبال‌کردن
        تریلینگ. بازگشتی: فهرست رویدادهای رخ‌داده (برای گزارش).
        """
        events: list[str] = []
        self.last_tick_ms = time.time() * 1000.0

        # اوج/کف قیمت از لحظهٔ ورود
        if self.is_long:
            self.extreme_price = max(self.extreme_price, price)
        else:
            self.extreme_price = min(self.extreme_price, price)

        profit = self.net_unrealised(price)

        # --- سر‌به‌سر: بعد از پوشش هزینه‌ها حد ضرر به ورود می‌رود ---
        if (
            config.break_even_enabled
            and not self.break_even_armed
            and profit >= config.break_even_trigger
        ):
            fees = float(self.extra.get("round_trip_fee", 0.0) or 0.0)
            rate = float(self.extra.get("fee_rate", 0.0) or 0.0)
            cover = fees / (self.quantity * (1 - self.direction_sign * rate)) if self.quantity > 0 else 0.0
            stop = self.entry_price + self.direction_sign * cover
            self.effective_stop = max(self.effective_stop, stop) if self.is_long else min(self.effective_stop, stop)
            self.break_even_armed = True
            events.append("break_even_armed")

        # --- تریلینگ: حد ضرر دنبال قیمت می‌آید ---
        if (
            config.trailing_enabled
            and not self.trailing_active
            and profit >= config.trailing_activation
        ):
            self.trailing_active = True
            events.append("trailing_started")
        if self.trailing_active and self.quantity > 0:
            offset = config.trailing_offset / self.quantity
            trailed = self.extreme_price - self.direction_sign * offset
            # حد ضرر فقط در جهت سود حرکت می‌کند — هرگز عقب نمی‌رود
            if self.is_long:
                self.effective_stop = max(self.effective_stop, trailed)
            else:
                self.effective_stop = min(self.effective_stop, trailed)
        return events

    def should_close(self, price: float, now: datetime, max_hold: int) -> str:
        """
        آیا باید بسته شود؟ رشتهٔ خالی یعنی نه.

        ترتیب بررسی مهم است: حد ضرر **اول**. اگر قیمت در یک پرش از هر
        دو سطح رد شود، باید محافظه‌کارانه‌ترین نتیجه ثبت شود، نه
        خوش‌بینانه‌ترین.
        """
        moved = (price - self.entry_price) * self.direction_sign
        stop = self.effective_stop if self.effective_stop > 0 else self.stop_price

        if (price - stop) * self.direction_sign <= 0:
            if self.trailing_active:
                return "trailing_stop"
            if self.break_even_armed:
                return "break_even"
            return "stop_loss"
        if moved >= (self.target_price - self.entry_price) * self.direction_sign:
            return "take_profit"
        if (now - self.opened_at).total_seconds() >= max_hold:
            return "timeout"
        return ""

    def data_age_ms(self, now_ms: float | None = None) -> float:
        """سن آخرین تیک این معامله — برای ستون Data Age."""
        if self.last_tick_ms <= 0:
            return -1.0
        return max(0.0, (now_ms or time.time() * 1000.0) - self.last_tick_ms)


class AutoTrader:
    """
    موتور معاملهٔ خودکار.

    چرخهٔ کار: نامزد بگیر ← اگر جا و اجازه هست باز کن ← با هر تیک
    بپایش ← در اولین شرط خروج ببند ← تکرار.

    رویدادها (برای UI):
        started / stopped / opened / closed / halted
        rejected  — نامزدی رد شد (با دلیل)؛ سوخت جدول Opportunity
        stale     — دادهٔ بازار کهنه شد
        tick      — تیک پردازش شد (برای نمایش تأخیر)
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
        portfolio_source: Callable[[], dict[str, Any]] | None = None,
        invalidation_source: Callable[[str], str] | None = None,
    ) -> None:
        self.config = config.validated()
        self._price_source = price_source
        self._repo = repository
        self._candidate_source = candidate_source
        self._gateway = gateway
        self._user_id = user_id
        #: وضعیت پرتفوی (موجودی/مارجین استفاده‌شده/تعداد باز) — sync
        self._portfolio_source = portfolio_source
        #: جهت پیش‌بینی فعلی نماد (LONG/SHORT/"") برای ابطال سیگنال — sync
        self._invalidation_source = invalidation_source

        self._open: dict[int, ManagedTrade] = {}
        self._entry_lock = asyncio.Lock()
        self._closing: set[int] = set()
        self._scan_task: asyncio.Task | None = None
        self._last_rejections: dict[str, str] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._realised_today = 0.0
        self._pnl_date = datetime.now(UTC).date()
        self._listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._halted_reason = ""
        self._tick_engine: Any | None = None
        self._tick_check_pending: set[str] = set()
        self._last_scan_monotonic = 0.0
        self._last_stale_notice = 0.0
        #: آخرین ردیف‌های فرصت برای جدول Opportunity — واقعی، از پویش
        self._opportunities: list[dict[str, Any]] = []
        #: آخرین شیء نامزد هر نماد (برای ورود دستی از جدول فرصت‌ها)
        self._opportunity_candidates: dict[str, Any] = {}

    def apply_config(self, config: AutoTradeConfig) -> None:
        """
        عوض کردن تنظیم موتور در حال اجرا.

        حلقهٔ پایش هر دور `self.config` را می‌خواند. اگر این متد نباشد،
        ذخیرهٔ عددهای تازه تا ری‌استارت موتور بی‌اثر می‌ماند.
        """
        self.config = config.validated()
        if self._tick_engine is not None:
            # سن مجاز داده در cache متصل هم نگهداری می‌شود؛ ذخیرهٔ تنظیم
            # نباید فقط config را عوض کند و محافظ STALE روی عدد قدیمی بماند.
            self._tick_engine.stale_after_ms = self.config.stale_after_seconds * 1000.0

    def attach_tick_engine(self, tick_engine: Any) -> None:
        """
        وصل‌کردن کش تیک — از این لحظه خروج معامله رویدادمحور است.

        هر تیک نمادِ موقعیتِ باز، بلافاصله TP/SL/سر‌به‌سر/تریلینگ را
        می‌سنجد؛ هیچ تایمری در میان نیست.
        """
        self._tick_engine = tick_engine
        tick_engine.stale_after_ms = self.config.stale_after_seconds * 1000.0
        tick_engine.add_listener(self._on_tick)

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

    def opportunities(self) -> list[dict[str, Any]]:
        """آخرین فرصت‌های دیده‌شده — دادهٔ جدول Opportunity Monitor."""
        return list(self._opportunities)

    def portfolio(self) -> dict[str, Any]:
        """
        وضعیت پرتفوی — از منبع خارجی یا برآیند داخلی.

        همیشه یک dict کامل برمی‌گرداند تا UI هرگز با KeyError نیفتد.
        """
        if self._portfolio_source is not None:
            try:
                data = self._portfolio_source() or {}
                return {
                    "balance": float(data.get("balance", 0.0) or 0.0),
                    "used_margin": float(data.get("used_margin", 0.0) or 0.0),
                    "available_margin": float(data.get("available_margin", 0.0) or 0.0),
                    "open_count": int(data.get("open_count", len(self._open)) or 0),
                    "daily_pnl": float(data.get("daily_pnl", self._realised_today) or 0.0),
                    "win_rate": float(data.get("win_rate", 0.0) or 0.0),
                }
            except Exception:  # noqa: BLE001
                logger.exception("Portfolio source failed; using internal state")
        return {
            "balance": 0.0,
            "used_margin": sum(t.used_margin() for t in self._open.values()),
            "available_margin": 0.0,
            "open_count": len(self._open),
            "daily_pnl": self._realised_today,
            "win_rate": 0.0,
        }

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

    # ---- مسیر تیک: خروج رویدادمحور ----------------------------------

    def _on_tick(self, quote: Any) -> None:
        """
        تیک تازه رسید — همان لحظه پردازش (خواستهٔ §۶).

        این فراخوان روی نخ asyncio انجام می‌شود؛ بستن معامله async
        است پس به‌صورت وظیفهٔ فوری زمان‌بندی می‌شود — بدون تایمر و
        بدون خواب. چند تیک پیاپی همان نماد در یک بررسی ادغام می‌شوند.
        """
        try:
            symbol = str(getattr(quote, "symbol", "") or "")
            if self._is_stale(symbol):
                return
            managed_trades = [t for t in self._open.values() if t.symbol == symbol]
            for managed in managed_trades:
                price = self._exit_price_for(managed, quote)
                if price > 0:
                    managed.mark(price, self.config)

            if not managed_trades:
                return
            if symbol in self._tick_check_pending:
                return  # بررسی همین نماد در صف است؛ تکرار نکن
            self._tick_check_pending.add(symbol)
            asyncio.get_running_loop().call_soon(
                self._schedule_tick_check, symbol
            )
        except Exception:  # noqa: BLE001 - تیک بد نباید موتور را بکشد
            logger.exception("Tick handling failed")

    def _schedule_tick_check(self, symbol: str) -> None:
        """اجرای بررسی فوری نماد بیرون از مسیر شنونده."""
        async def check():
            try:
                await self.check_symbol(symbol)
            except Exception:
                logger.exception("Tick exit check failed for %s", symbol)
            finally:
                self._tick_check_pending.discard(symbol)
        try:
            asyncio.create_task(check())
        except RuntimeError:
            self._tick_check_pending.discard(symbol)

    def _exit_price_for(self, managed: ManagedTrade, quote: Any) -> float:
        """قیمت خروج واقعی از تیک (Bid/Ask) با لغزش علیه ما."""
        price = float(getattr(quote, "last", 0.0) or 0.0)
        side = str(getattr(managed, "side", "long"))
        exit_method = getattr(quote, "exit_price", None)
        if callable(exit_method):
            price = float(exit_method(side) or price)
        if price <= 0:
            return 0.0
        slip = self.config.slippage_percent / 100.0
        if slip > 0:
            price *= 1.0 - slip if managed.is_long else 1.0 + slip
        return price

    async def check_symbol(self, symbol: str) -> None:
        """بررسی فوری موقعیت‌های باز یک نماد — مسیر تیک."""
        now = datetime.now(UTC)
        for managed in [t for t in list(self._open.values()) if t.symbol == symbol]:
            price = await self._price_for_exit(managed)
            if price <= 0:
                continue
            reason = managed.should_close(price, now, self.config.max_hold_seconds)
            if reason:
                await self.close_trade(managed, reason)

    async def _price_for_entry(self, symbol: str, side: str) -> tuple[float, dict[str, Any]]:
        """
        قیمت ورود واقعی + اطلاعات اجرا.

        بازگشتی: (قیمت، اطلاعات اجرا برای ثبت). قیمت ورود همیشه از
        سمت گرانِ اسپرد است: LONG با Ask، SHORT با Bid (خواستهٔ §۷).
        """
        info: dict[str, Any] = {}
        quote = None
        if self._tick_engine is not None:
            quote = self._tick_engine.get(symbol)
        if quote is not None and float(getattr(quote, "last", 0.0) or 0.0) > 0:
            entry = float(quote.entry_price(side) or quote.last)
            info = {
                "bid": getattr(quote, "bid", 0.0),
                "ask": getattr(quote, "ask", 0.0),
                "spread_percent": getattr(quote, "spread_percent", 0.0),
                "tick_source": getattr(quote, "source", ""),
                "receive_latency_ms": getattr(quote, "receive_latency_ms", None),
                "total_latency_ms": getattr(quote, "total_latency_ms", None),
                "data_age_ms": getattr(quote, "age_ms", None),
            }
        else:
            entry = float(await asyncio.wait_for(self._price_source(symbol), timeout=5.0) or 0.0)
        if entry <= 0:
            return 0.0, info
        slip = self.config.slippage_percent / 100.0
        if slip > 0:
            entry *= 1.0 + slip if side == "long" else 1.0 - slip
        return entry, info

    async def _price_for_exit(self, managed: ManagedTrade) -> float:
        """قیمت خروج واقعی — Bid برای LONG و Ask برای SHORT + لغزش."""
        if self._tick_engine is not None:
            quote = self._tick_engine.get(managed.symbol)
            if quote is not None and not self._is_stale(managed.symbol):
                price = self._exit_price_for(managed, quote)
                if price > 0:
                    managed.last_tick_ms = time.time() * 1000.0
                    return price
        price = float(await asyncio.wait_for(self._price_source(managed.symbol), timeout=5.0) or 0.0)
        if self._tick_engine is not None:
            if self._is_stale(managed.symbol):
                return 0.0
            quote = self._tick_engine.get(managed.symbol)
            return self._exit_price_for(managed, quote)
        if price <= 0:
            return 0.0
        slip = self.config.slippage_percent / 100.0
        if slip > 0:
            price *= 1.0 - slip if managed.is_long else 1.0 + slip
        return price

    # ---- محافظ‌ها ---------------------------------------------------

    def _check_daily_limit(self) -> bool:
        """
        آیا سقف زیان روزانه رد شده است؟

        این آخرین خط دفاع در برابر یک روز بد است.
        """
        today = datetime.now(UTC).date()
        if today != self._pnl_date:
            self._pnl_date = today
            self._realised_today = 0.0
        total = self._realised_today
        persisted = getattr(self._repo, "daily_realised_pnl", None)
        if callable(persisted):
            total = float(persisted(self._user_id))
        if total <= -abs(self.config.daily_loss_limit):
            self._halted_reason = (
                f"سقف زیان روزانه ({self.config.daily_loss_limit} دلار) رد شد"
            )
            return False
        return True

    def _is_stale(self, symbol: str) -> bool:
        """آیا دادهٔ نماد کهنه است؟ (STALE DATA — خواستهٔ §۶)"""
        if self._tick_engine is None:
            return False
        try:
            return bool(self._tick_engine.is_stale(symbol))
        except Exception:  # noqa: BLE001
            return True

    def _notify_stale_if_new(self, symbol: str) -> None:
        """اعلام STALE فقط یک‌بار در هر بازهٔ کوتاه — نه هر دور پویش."""
        now = time.monotonic()
        if now - self._last_stale_notice < 10.0:
            return
        self._last_stale_notice = now
        self._emit("stale", {"symbol": symbol})

    def _check_entry_guards(
        self,
        candidate: Any,
        side: str,
    ) -> tuple[bool, str]:
        """
        دروازه‌های ورود — قبل از هر بازکردن (خواستهٔ §۱۳).

        بازگشتی: (اجازه؟, دلیل رد). دادهٔ کهنه، اسپرد عجیب، نقدینگی
        کم و تضاد روند هرکدام جدا گزارش می‌شوند تا UI بتواند دلیلِ
        «چرا معامله باز نشد» را صادقانه نشان دهد.
        """
        symbol = str(getattr(candidate, "symbol", "") or "").strip().upper()
        config = self.config

        if self._is_stale(symbol):
            self._notify_stale_if_new(symbol)
            return False, "stale_data"

        if self._tick_engine is not None:
            quote = self._tick_engine.get(symbol)
            spread = float(getattr(quote, "spread_percent", 0.0) or 0.0) if quote else 0.0
            if quote is not None and config.max_spread_percent > 0:
                if spread > config.max_spread_percent and quote.spread > 0:
                    return False, f"wide_spread:{spread:.3f}%"

        # گردش «موجود اما کم» یعنی بازار راکد → رد. نامعلوم (فیلد نبود)
        # رد نمی‌شود چون منبع اطمینان این فیلد را ندارد.
        turnover_raw = getattr(candidate, "turnover_24h", None)
        if turnover_raw is not None:
            turnover = float(turnover_raw or 0.0)
            if config.min_liquidity > 0 and turnover < config.min_liquidity:
                return False, "low_liquidity"

        ladder = getattr(candidate, "trend_ladder", None)
        if ladder is not None and config.trend_conflict_policy == "block":
            direction = "LONG" if side == "long" else "SHORT"
            clashes = ladder.conflict_with(direction)
            if clashes:
                return False, "trend_conflict:" + ",".join(clashes)
        return True, ""

    def _allowed_symbols(self) -> list[str] | None:
        """
        نمادهای مجاز حالت فعلی.

        None یعنی بدون محدودیت (حالت scan). حالت selected فقط نمادهای
        کاربر؛ خالی بودن فهرست یعنی «فعلاً هیچ نمادی» — موتور کار
        می‌کند ولی ورودی ندارد.
        """
        if self.config.engine_mode == "selected":
            return self.config.selected_symbol_list
        return None

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
        if not self._check_daily_limit():
            return False, self._halted_reason
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

    def _resolve_margin(self, candidate: Any, confidence: float) -> float:
        """
        مارجین معامله بر پایهٔ حالت تخصیص (خواستهٔ §۱۲).

        نامزد AI می‌تواند مارجین خودش را بیاورد؛ در غیر این صورت از
        قاعدهٔ پیکربندی محاسبه می‌شود. Margin هرگز Notional نیست.
        """
        candidate_margin = float(getattr(candidate, "margin", 0.0) or 0.0)
        if candidate_margin > 0:
            return candidate_margin
        config = self.config
        mode = config.allocation_mode
        if mode == "fixed":
            return config.margin_per_trade
        portfolio = self.portfolio()
        balance = float(portfolio.get("balance", 0.0) or 0.0)
        used = float(portfolio.get("used_margin", 0.0) or 0.0)
        available = max(0.0, balance - used)
        cap = balance * config.max_total_margin_percent / 100.0
        if mode == "percent":
            margin = balance * config.allocation_percent / 100.0
        elif mode == "confidence":
            margin = config.margin_per_trade * (0.5 + max(0.0, min(100.0, confidence)) / 100.0)
        elif mode == "risk":
            margin = config.max_loss / 0.02
        elif mode == "hybrid":
            margin = min(
                balance * config.allocation_percent / 100.0,
                config.margin_per_trade * 3.0,
            )
        elif mode == "ai":
            margin = config.margin_per_trade * (0.5 + max(0.0, min(100.0, confidence)) / 100.0)
        else:
            margin = config.margin_per_trade
        return max(0.0, min(margin, available, cap))

    def rejection_reason(self, symbol: str) -> str:
        return self._last_rejections.get(symbol.upper(), "rejected_by_guards")

    async def open_trade(self, candidate: Any) -> ManagedTrade | None:
        """ظرفیت و ورود تکراری زیر قفل مشترک دستی/خودکار دوباره بررسی می‌شوند."""
        # Slow quote I/O must not hold the portfolio lock and delay a fresh manual entry.
        symbol = str(getattr(candidate, "symbol", "") or "").strip().upper()
        if symbol and self._tick_engine is not None and self._is_stale(symbol):
            reason = ""
            try:
                await asyncio.wait_for(self._price_source(symbol), timeout=5.0)
                if self._is_stale(symbol):
                    reason = "stale_data"
            except Exception:
                reason = "price_unavailable"
            if reason:
                self._last_rejections[symbol] = reason
                self._emit("rejected", {"symbol": symbol, "reason": reason})
                self._record_opportunity(candidate, decision="skip", reason=reason)
                return None
        async with self._entry_lock:
            return await self._open_trade_locked(candidate)

    async def _open_trade_locked(self, candidate: Any) -> ManagedTrade | None:
        """
        باز کردن یک معامله بر پایهٔ نامزد.

        در حالت کاغذی، قیمت زنده (Bid/Ask اگر باشد) است و فقط سفارش
        واقعی نمی‌رود. نامزد رد‌شده هرگز بی‌صدا دور ریخته نمی‌شود —
        رویداد `rejected` با دلیل صریح منتشر می‌شود.
        """
        symbol = str(getattr(candidate, "symbol", "") or "").strip().upper()
        direction = str(getattr(candidate, "direction", "LONG")).upper()
        side = "long" if direction == "LONG" else "short"
        confidence = float(getattr(candidate, "score", 0.0) or 0.0)

        def reject(reason: str) -> None:
            self._last_rejections[symbol.upper()] = reason
            self._emit("rejected", {"symbol": symbol, "reason": reason})
            self._record_opportunity(candidate, decision="skip", reason=reason)

        if not symbol or direction not in {"LONG", "SHORT"} or not math.isfinite(confidence):
            reject("invalid_candidate")
            return None
        observed_at = float(getattr(candidate, "observed_at", 0) or 0)
        if observed_at and time.time() - observed_at > max(60, 2 * self.config.scan_interval_seconds):
            reject("stale_candidate")
            return None
        if any(t.symbol.upper() == symbol.upper() for t in self._open.values()):
            reject("symbol_already_open")
            return None
        lookup = getattr(self._repo, "open_trades", None)
        if callable(lookup) and any(str(r.get("symbol", "")).upper() == symbol.upper() for r in lookup(self._user_id)):
            reject("symbol_already_open")
            return None
        if len(self._open) >= self.config.max_concurrent or int(self.portfolio().get("open_count", 0)) >= self.config.max_concurrent:
            reject("max_concurrent_reached")
            return None
        if not self._check_daily_limit():
            reject("daily_loss_limit")
            return None

        allowed = self._allowed_symbols()
        if allowed is not None and symbol not in allowed:
            reject("symbol_not_selected")
            return None

        ok, reason = self._check_entry_guards(candidate, side)
        if not ok:
            reject(reason)
            return None

        margin = self._resolve_margin(candidate, confidence)
        if not math.isfinite(margin) or margin < 1.0:
            reject("no_available_margin")
            return None

        entry, execution = await self._price_for_entry(symbol, side)
        if not math.isfinite(entry) or entry <= 0:
            reject("no_price")
            return None

        config = self.config
        if not math.isfinite(config.fee_rate) or not 0 <= config.fee_rate < 1:
            reject("invalid_fee_rate")
            return None
        # نامزد AI می‌تواند اهرم و سطوح خودش را بیاورد (TP/SL از چندک‌ها)
        leverage = float(getattr(candidate, "leverage", 0.0) or 0.0) or config.leverage
        leverage = max(1.0, min(leverage, HARD_MAX_LEVERAGE))
        candidate_tp = float(getattr(candidate, "take_profit", 0.0) or 0.0)
        candidate_sl = float(getattr(candidate, "stop_loss", 0.0) or 0.0)

        from trading.micro_plan import plan_levels

        plan = plan_levels(
            margin,
            leverage,
            config.target_profit,
            config.max_loss,
            config.fee_rate,
        )
        if plan.round_trip_fee >= config.max_loss:
            reject("fees_exceed_loss_budget")
            return None
        quantity = plan.notional / entry
        sign = 1.0 if side == "long" else -1.0
        if candidate_tp > 0:
            target = candidate_tp
        else:
            target = (entry * sign + (config.target_profit + plan.entry_fee) / quantity) / (sign - config.fee_rate)
        if candidate_sl > 0:
            stop = candidate_sl
        else:
            stop = (entry * sign + (plan.entry_fee - config.max_loss) / quantity) / (sign - config.fee_rate)

        net_reward = (target - entry) * sign * quantity - plan.entry_fee - quantity * target * config.fee_rate
        net_risk = -(stop - entry) * sign * quantity + plan.entry_fee + quantity * stop * config.fee_rate
        if not all(math.isfinite(v) and v > 0 for v in (target, stop, quantity)) or (target - entry) * sign <= 0 or (entry - stop) * sign <= 0:
            reject("invalid_risk_levels")
            return None
        if net_risk > config.max_loss + 1e-8:
            reject("risk_exceeds_loss_budget")
            return None
        if net_reward <= 0 or net_reward + 1e-8 < net_risk * min(1.0, config.target_profit / config.max_loss):
            reject("poor_net_reward_risk")
            return None
        portfolio = self.portfolio()
        balance = float(portfolio.get("balance", 0) or 0)
        used = float(portfolio.get("used_margin", 0) or 0)
        if balance > 0 and (used + margin > balance * config.max_total_margin_percent / 100 or margin > balance - used):
            reject("no_available_margin")
            return None
        # Revalidate freshness/spread after awaited I/O.
        ok, reason = self._check_entry_guards(candidate, side)
        if not ok:
            reject(reason)
            return None
        if config.mode == "live" and not config.is_live:
            raise LiveTradingNotEnabledError("تأیید معامله واقعی کامل نیست")
        if config.is_live:
            if self._gateway is None:
                raise LiveTradingNotEnabledError("درگاه سفارش واقعی تنظیم نشده است")
            await self._gateway.open_position(
                symbol=symbol, side=side, quantity=quantity, leverage=leverage
            )

        record = self._repo.open_trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry,
            user_id=self._user_id,
            stop_loss=stop,
            take_profit=target,
            leverage=leverage,
            fee=plan.entry_fee,
            mode="live" if config.is_live else "paper",
            note="معاملهٔ خودکار اسکلپ",
            extra={
                "auto": True,
                "score": confidence,
                "margin": margin,
                "target_profit": config.target_profit,
                "max_loss": config.max_loss,
                "round_trip_fee": plan.round_trip_fee,
                "entry_fee": plan.entry_fee,
                "gross_target": plan.gross_target,
                "fee_rate": config.fee_rate,
                "engine_mode": config.engine_mode,
                "allocation_mode": config.allocation_mode,
                "execution": execution,
            },
        )

        managed = ManagedTrade(
            trade_id=int(record["id"]),
            symbol=symbol,
            side=side,
            entry_price=entry,
            quantity=quantity,
            leverage=leverage,
            target_price=target,
            stop_price=stop,
            opened_at=datetime.now(UTC),
            mode="live" if config.is_live else "paper",
            margin=margin,
            extra={"round_trip_fee": plan.round_trip_fee, "entry_fee": plan.entry_fee,
                   "fee_rate": config.fee_rate},
            entry_bid=float(execution.get("bid", 0.0) or 0.0),
            entry_ask=float(execution.get("ask", 0.0) or 0.0),
        )
        self._open[managed.trade_id] = managed
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        logger.info(
            "Auto-trade opened %s %s @ %.6f target=%.6f stop=%.6f margin=%.2f lev=%g",
            side, symbol, entry, target, stop, margin, leverage,
        )
        self._emit("opened", {"trade": managed, "record": record})
        self._record_opportunity(candidate, decision="enter", reason="")
        return managed

    async def close_trade(self, managed: ManagedTrade, reason: str) -> dict[str, Any] | None:
        """فقط یک خروج در جریان برای هر موقعیت؛ تیک/دکمه/تایمر هم‌زمان مجاز نیست."""
        if managed.trade_id not in self._open or managed.trade_id in self._closing:
            return None
        self._closing.add(managed.trade_id)
        try:
            return await self._close_trade_once(managed, reason)
        finally:
            self._closing.discard(managed.trade_id)

    async def _close_trade_once(self, managed: ManagedTrade, reason: str) -> dict[str, Any] | None:
        """بستن یک معامله و ثبت نتیجه."""
        price = await self._price_for_exit(managed)
        if price <= 0:
            return None

        if managed.mode == "live":
            if self._gateway is None:
                raise LiveTradingNotEnabledError("درگاه سفارش واقعی تنظیم نشده است")
            await self._gateway.close_position(
                symbol=managed.symbol, side=managed.side, quantity=managed.quantity
            )

        from trading.micro_plan import exit_fee_from_notional

        exit_fee = exit_fee_from_notional(
            managed.quantity * price,
            float(managed.extra.get("fee_rate", self.config.fee_rate)),
        )
        record = self._repo.close_trade(
            managed.trade_id,
            exit_price=price,
            fee=exit_fee,
            note=f"بسته شد: {reason}",
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
        """پایش fallback همهٔ معامله‌های باز — وقتی تیک نمی‌آید."""
        now = datetime.now(UTC)
        async def check(managed):
            try:
                price = await self._price_for_exit(managed)
            except Exception:  # noqa: BLE001
                logger.exception("Price check failed for %s", managed.symbol)
                return
            if price <= 0:
                return
            managed.mark(price, self.config)
            reason = managed.should_close(price, now, self.config.max_hold_seconds)
            if reason:
                await self.close_trade(managed, reason)
                return
            update = getattr(self._repo, "update_live_pnl", None)
            if callable(update):
                net = managed.net_unrealised(price)
                update(managed.trade_id, price=price, pnl=net,
                       pnl_percent=net / managed.margin * 100 if managed.margin else 0)
            protection = getattr(self._repo, "update_protection", None)
            if callable(protection):
                protection(managed.trade_id, stop_loss=managed.effective_stop)

        await asyncio.gather(*(check(t) for t in list(self._open.values())))

    async def check_signal_invalidation(self) -> None:
        """
        ابطال سیگنال: جهت پیش‌بینی نماد برگشت؟ (خواستهٔ §۱۳)

        منبع جهت همان موتور پیش‌بینی است (منبع واحد). برگشت جهت یعنی
        دلیل ورود دیگر وجود ندارد — ماندن قمار است، معامله نیست.
        """
        if not self.config.signal_invalidation or self._invalidation_source is None:
            return
        for managed in list(self._open.values()):
            try:
                current = str(self._invalidation_source(managed.symbol) or "").upper()
            except Exception:  # noqa: BLE001
                continue
            if current not in ("LONG", "SHORT"):
                continue
            trade_direction = "LONG" if managed.is_long else "SHORT"
            if current != trade_direction:
                await self.close_trade(managed, "signal_invalid")

    async def emergency_exit_all(self, reason: str = "emergency") -> list[dict[str, Any]]:
        """خروج اضطراری همهٔ موقعیت‌ها — دکمهٔ پانیک کاربر."""
        results = []
        for managed in list(self._open.values()):
            record = await self.close_trade(managed, reason)
            if record:
                results.append(record)
        return results

    # ---- پویش و ثبت فرصت‌ها ------------------------------------------

    def _record_opportunity(
        self, candidate: Any, *, decision: str, reason: str
    ) -> None:
        """
        ثبت یک ردیف جدول Opportunity — ورود یا رد با دلیل.

        ستون‌های ترمینال (احتمال، حرکت موردانتظار، MTF، ریسک، سطوح
        ورود/TP/SL، اهرم و مارجین) فقط وقتی پر می‌شوند که نامزد واقعاً
        آن‌ها را داشته باشد — نامزدِ بدون سطح، صادقانه «—» می‌گیرد.
        نامزدِ رد‌شده نگه داشته می‌شود تا کاربر بتواند از جدول، ورود
        دستی بخواهد؛ همهٔ دروازه‌ها دوباره سنجیده می‌شوند.
        """
        symbol = str(getattr(candidate, "symbol", "") or "").strip().upper()
        if not symbol:
            return
        ladder = getattr(candidate, "trend_ladder", None)
        row = {
            "symbol": symbol,
            "direction": str(getattr(candidate, "direction", "") or ""),
            "confidence": float(getattr(candidate, "score", 0.0) or 0.0),
            "probability": self._optional_number(candidate, "probability"),
            "expected_move": self._optional_number(
                candidate, "expected_move_percent"
            ),
            "trend": "",
            "mtf": str(getattr(candidate, "mtf", "") or ""),
            "risk": self._optional_number(candidate, "risk_reward"),
            "spread": None,
            "liquidity": float(getattr(candidate, "turnover_24h", 0.0) or 0.0),
            "score": float(getattr(candidate, "score", 0.0) or 0.0),
            "entry": self._optional_number(candidate, "entry_price"),
            "tp": self._optional_number(candidate, "take_profit"),
            "sl": self._optional_number(candidate, "stop_loss"),
            "leverage": self._optional_number(candidate, "leverage"),
            "margin": self._optional_number(candidate, "margin"),
            "prediction": str(getattr(candidate, "prediction", "") or ""),
            "decision": decision,
            "reason": reason,
            #: آیا کاربر می‌تواند از جدول ورود دستی بخواهد؟ فقط برای
            #: نامزد رد‌شده‌ای که شیءش موجود است (دروازه‌ها دوباره
            #: سنجیده می‌شوند؛ ردِ مجدد صادقانه است).
            "actionable": bool(
                decision == "skip"
                and candidate is not None
                and float(getattr(candidate, "score", 0.0) or 0.0) > 0
                and not any(
                    t.symbol == symbol for t in self._open.values()
                )
            ),
        }
        if ladder is not None:
            row["trend"] = f"{ladder.weighted_direction:+.2f}"
        if self._tick_engine is not None:
            quote = self._tick_engine.get(symbol)
            if quote is not None:
                row["spread"] = round(quote.spread_percent, 4)
        # نامزد برای ورود دستی (فقط اگر شیء معتبر است)
        if getattr(candidate, "symbol", None):
            self._opportunity_candidates[symbol] = candidate
        # همیشه جدیدترین بالای فهرست؛ حداکثر ۵۰ ردیف نگه می‌داریم
        self._opportunities.insert(0, row)
        del self._opportunities[50:]

    @staticmethod
    def _optional_number(candidate: Any, field: str) -> float | None:
        """عدد اختیاری نامزد — نبود یعنی None، نه صفرِ قلابی."""
        try:
            value = getattr(candidate, field, None)
            if value is None:
                return None
            number = float(value)
            return number if number > 0 else None
        except (TypeError, ValueError):
            return None

    def opportunity_candidate(self, symbol: str) -> Any | None:
        """
        آخرین نامزد ثبت‌شدهٔ یک نماد — برای ورود دستی از جدول فرصت‌ها.

        ورود از این مسیر از `open_trade` می‌گذرد؛ یعنی همهٔ دروازه‌ها
        (دادهٔ تازه، اسپرد، نقدینگی، روند، ظرفیت) دوباره سنجیده
        می‌شوند و ردِ مجدد ممکن است.
        """
        return self._opportunity_candidates.get(str(symbol or "").upper())

    def note_rejected(
        self,
        *,
        symbol: str,
        direction: str,
        confidence: float,
        reason: str,
        turnover_24h: float = 0.0,
        trend_ladder: Any = None,
    ) -> None:
        """
        ثبت یک فرصتِ رد‌شده از بیرون (مسیر AI) در جدول فرصت‌ها.

        تصمیم‌ساز AI نامزدی که NO TRADE شد اینجا گزارش می‌شود تا
        جدول Opportunity دلیلِ «چرا وارد نشد» را نشان دهد — شفافیت
        به‌جای سکوت.
        """

        class _Row:
            pass

        row = _Row()
        row.symbol = symbol
        row.direction = direction
        row.score = confidence
        row.turnover_24h = turnover_24h
        row.trend_ladder = trend_ladder
        row.prediction = ""
        self._record_opportunity(row, decision="skip", reason=reason)

    async def _scan_for_entries(self) -> None:
        """یک دور پویش نامزد و تلاش برای ورود."""
        if self._candidate_source is None:
            return
        allowed = self._allowed_symbols()
        candidates = await self._candidate_source()
        held = {trade.symbol for trade in self._open.values()}
        for candidate in candidates:
            if len(self._open) >= self.config.max_concurrent:
                break
            # هرگز دو معامله روی یک نماد.
            if getattr(candidate, "symbol", "") in held:
                continue
            if allowed is not None and getattr(candidate, "symbol", "") not in allowed:
                continue
            await self.open_trade(candidate)

    async def _run_scan(self) -> None:
        try:
            await self._scan_for_entries()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Candidate scan failed")

    async def _loop(self) -> None:
        """
        حلقهٔ پس‌زمینه — فقط پویش و fallback.

        خروج معامله اینجا نیست؛ خروج با هر تیک در `_on_tick` همان لحظه
        انجام می‌شود. این حلقه حداکثر هر `poll_seconds` بیدار می‌شود
        و ورودها هر `scan_interval_seconds` بررسی می‌شوند.
        """
        while self._running or self._open:
            try:
                await self.check_open_trades()
                await self.check_signal_invalidation()

                now = time.monotonic()
                if (
                    self._running
                    and (self._scan_task is None or self._scan_task.done())
                    and self._candidate_source is not None
                    and len(self._open) < self.config.max_concurrent
                    and self._check_daily_limit()
                    and now - self._last_scan_monotonic >= self.config.scan_interval_seconds
                ):
                    self._last_scan_monotonic = now
                    self._scan_task = asyncio.create_task(self._run_scan())
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
        self._last_scan_monotonic = 0.0
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        logger.info(
            "Auto-trader started (mode=%s engine=%s)",
            "live" if self.config.is_live else "paper",
            self.config.engine_mode,
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
        current = asyncio.current_task()
        if self._scan_task is not None and self._scan_task is not current:
            if not self._scan_task.done():
                self._scan_task.cancel()
                await asyncio.gather(self._scan_task, return_exceptions=True)
            self._scan_task = None
        # Stopping automatic entries must not abandon protective exits.
        # Do not cancel a parent monitor from its own per-position child task.
        # With no positions the loop exits at its next wake-up.
        if self._task is not None and self._task.done():
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


__all__ = [
    "ALLOCATION_MODES",
    "ENGINE_MODES",
    "AutoTradeConfig",
    "AutoTrader",
    "HARD_MAX_CONCURRENT",
    "HARD_MAX_LEVERAGE",
    "LiveOrderGateway",
    "LiveTradingNotEnabledError",
    "LIVE_CONFIRMATION_PHRASE",
    "ManagedTrade",
]
