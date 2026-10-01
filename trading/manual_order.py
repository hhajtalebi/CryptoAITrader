"""
معاملهٔ دستی — منطق خالص بدون Qt (نسخهٔ ۲.۵.۹).

خواستهٔ کاربر: بخشی که خودش نماد را انتخاب کند، مقداری از دارایی را
بگذارد، نوع معامله (اسپات یا فیوچرز) و اهرم (۱ تا ۱۰۰) را تعیین کند، حد سود
و حد ضرر بدهد و معامله را باز کند. هم از روی سیگنال (مقادیر از پیش پر شده
و قابل ویرایش) و هم از صفحهٔ تاریخچهٔ معاملات.

تفاوت با «اقدام روی سیگنال» (۲.۵.۰): آن مسیر حجم را از «درصد ریسک» حساب
می‌کند؛ اینجا کاربر **مبلغ** را می‌گذارد:

    حجم (تعداد) = مبلغ × اهرم ÷ قیمت ورود        (اسپات: اهرم = ۱)

این ماژول فقط محاسبه و اعتبارسنجی می‌کند؛ ثبت معامله با کنترلر است و همچنان
کاغذی است (دروازهٔ اجرای واقعی دور زده نمی‌شود).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MARKET_SPOT = "spot"
MARKET_FUTURES = "futures"
MARKET_TYPES = (MARKET_FUTURES, MARKET_SPOT)

MIN_LEVERAGE = 1
#: سقف اهرم معاملهٔ دستی (خواستهٔ کاربر: ۱ تا ۱۰۰)
MAX_MANUAL_LEVERAGE = 100
#: کارمزد پیش‌فرض هر طرف (taker) — همان `scalp.taker_fee_rate`
DEFAULT_FEE_RATE = 0.0006
#: نرخ نگه‌داری تقریبی برای برآورد قیمت لیکوییدیشن (حالت ایزوله)
MAINTENANCE_MARGIN_RATE = 0.005
#: میان‌برهای «درصد از موجودی آزاد»
AMOUNT_PRESETS = (10, 25, 50, 100)


@dataclass
class ManualOrderRequest:
    """ورودی‌های کاربر."""

    symbol: str
    market_type: str = MARKET_FUTURES
    direction: str = "LONG"
    amount: float = 0.0
    leverage: int = 1
    entry: float = 0.0
    take_profit: float = 0.0
    stop_loss: float = 0.0
    #: موجودی آزاد (۰ = نامعلوم، بدون سقف)
    available: float = 0.0
    fee_rate: float = DEFAULT_FEE_RATE


@dataclass
class ManualOrderPlan:
    """نتیجهٔ محاسبه + خطاها (کلید ترجمه) + هشدارها."""

    symbol: str = ""
    market_type: str = MARKET_FUTURES
    direction: str = "LONG"
    amount: float = 0.0
    leverage: int = 1
    entry: float = 0.0
    take_profit: float = 0.0
    stop_loss: float = 0.0
    quantity: float = 0.0
    notional: float = 0.0
    fees: float = 0.0
    profit_at_tp: float = 0.0
    loss_at_sl: float = 0.0
    risk_reward: float = 0.0
    liquidation: float = 0.0
    tp_percent: float = 0.0
    sl_percent: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """آیا معامله قابل باز شدن است؟"""
        return not self.errors

    @property
    def side(self) -> str:
        """long/short برای دفتر معاملات."""
        return "long" if self.direction == "LONG" else "short"

    def to_dict(self) -> dict[str, Any]:
        """برای انتقال بین پنجره و کنترلر."""
        data = asdict(self)
        data["valid"] = self.valid
        data["side"] = self.side
        return data


#: ارزهای مظنه برای جدا کردن `BTCUSDT` به `BTC/USDT` (قالب نماد برنامه)
KNOWN_QUOTES = ("FDUSD", "USDT", "USDC", "BUSD", "TUSD", "IRT", "TMN", "BTC", "ETH", "EUR", "TRY")


def normalize_symbol(symbol: str) -> str:
    """`btc/usdt`، `btc-usdt`، `btc_usdt` و `btcusdt` همه `BTC/USDT` می‌شوند."""
    text = str(symbol or "").strip().upper().replace(" ", "")
    for sep in ("-", "_", ":"):
        text = text.replace(sep, "/")
    if "/" in text:
        base, _, quote = text.partition("/")
        quote = quote.split("/")[0]
        return f"{base}/{quote}" if base and quote else base or quote
    for quote in KNOWN_QUOTES:
        if text.endswith(quote) and len(text) > len(quote):
            return f"{text[: -len(quote)]}/{quote}"
    return text


def price_from_percent(entry: float, percent: float, direction: str, kind: str) -> float:
    """
    قیمت حد سود/ضرر از درصد فاصله تا ورود.

    kind: "tp" یا "sl". برای LONG حد سود بالاتر و حد ضرر پایین‌تر است؛ SHORT برعکس.
    """
    if entry <= 0 or percent <= 0:
        return 0.0
    sign = 1.0 if str(direction).upper() == "LONG" else -1.0
    if kind == "sl":
        sign = -sign
    return max(0.0, entry * (1.0 + sign * percent / 100.0))


def percent_from_price(entry: float, price: float) -> float:
    """فاصلهٔ درصدی (همیشه مثبت) یک قیمت تا ورود."""
    if entry <= 0 or price <= 0:
        return 0.0
    return abs(price - entry) / entry * 100.0


def liquidation_price(entry: float, leverage: int, direction: str,
                      mmr: float = MAINTENANCE_MARGIN_RATE) -> float:
    """برآورد سادهٔ قیمت لیکوییدیشن ایزوله (بدون کارمزد تأمین مالی)."""
    if entry <= 0 or leverage <= 1:
        return 0.0
    move = 1.0 / float(leverage) - mmr
    if move <= 0:
        return entry
    if str(direction).upper() == "LONG":
        return max(0.0, entry * (1.0 - move))
    return entry * (1.0 + move)


def plan_manual_order(request: ManualOrderRequest) -> ManualOrderPlan:
    """محاسبه و اعتبارسنجی کامل یک معاملهٔ دستی."""
    direction = str(request.direction or "").upper()
    market = str(request.market_type or MARKET_FUTURES).lower()
    if market not in MARKET_TYPES:
        market = MARKET_FUTURES
    plan = ManualOrderPlan(
        symbol=normalize_symbol(request.symbol),
        market_type=market,
        direction=direction,
        amount=max(0.0, float(request.amount or 0.0)),
        entry=max(0.0, float(request.entry or 0.0)),
        take_profit=max(0.0, float(request.take_profit or 0.0)),
        stop_loss=max(0.0, float(request.stop_loss or 0.0)),
    )
    errors, warnings = plan.errors, plan.warnings

    if not plan.symbol:
        errors.append("symbol_required")
    if direction not in ("LONG", "SHORT"):
        errors.append("direction_required")
    try:
        # صفر نباید بی‌صدا ۱ شود؛ خطای بازه گرفته می‌شود
        leverage = int(request.leverage if request.leverage is not None else 1)
    except (TypeError, ValueError):
        leverage = 1
    if market == MARKET_SPOT:
        # اسپات اهرم و فروش استقراضی ندارد
        leverage = 1
        if direction == "SHORT":
            errors.append("spot_no_short")
    elif not MIN_LEVERAGE <= leverage <= MAX_MANUAL_LEVERAGE:
        errors.append("leverage_range")
        leverage = max(MIN_LEVERAGE, min(MAX_MANUAL_LEVERAGE, leverage))
    plan.leverage = leverage

    if plan.amount <= 0:
        errors.append("amount_required")
    elif request.available and plan.amount > float(request.available) + 1e-9:
        errors.append("amount_exceeds_balance")
    if plan.entry <= 0:
        errors.append("entry_required")

    sign = 1.0 if direction == "LONG" else -1.0
    entry = plan.entry
    if entry > 0 and direction in ("LONG", "SHORT"):
        if plan.take_profit and (plan.take_profit - entry) * sign <= 0:
            errors.append("tp_wrong_side")
        if plan.stop_loss and (plan.stop_loss - entry) * sign >= 0:
            errors.append("sl_wrong_side")
        if not plan.stop_loss:
            warnings.append("no_stop_loss")
        if not plan.take_profit:
            warnings.append("no_take_profit")

    if entry > 0 and plan.amount > 0:
        plan.notional = plan.amount * leverage
        plan.quantity = plan.notional / entry
        fee_rate = max(0.0, float(request.fee_rate or 0.0))
        plan.fees = plan.notional * fee_rate * 2.0
        if market == MARKET_FUTURES and direction in ("LONG", "SHORT"):
            plan.liquidation = liquidation_price(entry, leverage, direction)
        if plan.take_profit:
            plan.profit_at_tp = (plan.take_profit - entry) * plan.quantity * sign - plan.fees
            plan.tp_percent = percent_from_price(entry, plan.take_profit)
        if plan.stop_loss:
            plan.loss_at_sl = (plan.stop_loss - entry) * plan.quantity * sign - plan.fees
            plan.sl_percent = percent_from_price(entry, plan.stop_loss)
        if plan.take_profit and plan.stop_loss and plan.loss_at_sl < 0:
            plan.risk_reward = max(0.0, plan.profit_at_tp) / abs(plan.loss_at_sl)
        if plan.liquidation and plan.stop_loss and "sl_wrong_side" not in errors:
            beyond = (plan.stop_loss - plan.liquidation) * sign <= 0
            if beyond:
                errors.append("sl_beyond_liquidation")
        if plan.liquidation and not plan.stop_loss:
            warnings.append("liquidation_risk")
        if leverage >= 50:
            warnings.append("high_leverage")
    return plan


def prefill_from_signal(signal: dict[str, Any] | None) -> dict[str, Any]:
    """
    مقادیر اولیهٔ پنجره از یک سیگنال: نماد، جهت، ورود، حد ضرر، TP1، اهرم.

    ورود: `entry_price` یا وسط بازهٔ `entry_min/entry_max`.
    """
    data = dict(signal or {})

    def number(value: Any) -> float:
        if isinstance(value, (list, tuple)):
            value = value[0] if value else 0
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    entry = number(data.get("entry_price") or data.get("entry"))
    if entry <= 0:
        low, high = number(data.get("entry_min")), number(data.get("entry_max"))
        entry = (low + high) / 2.0 if low > 0 and high > 0 else (low or high)
    targets = data.get("take_profits") or data.get("take_profit") or []
    if not isinstance(targets, (list, tuple)):
        targets = [targets]
    take_profit = next((number(t) for t in targets if number(t) > 0), 0.0)
    direction = str(data.get("direction") or "LONG").upper()
    try:
        leverage = int(float(data.get("leverage") or 1))
    except (TypeError, ValueError):
        leverage = 1
    return {
        "symbol": normalize_symbol(data.get("symbol") or ""),
        "direction": direction if direction in ("LONG", "SHORT") else "LONG",
        "entry": entry,
        "stop_loss": number(data.get("stop_loss")),
        "take_profit": take_profit,
        "leverage": max(MIN_LEVERAGE, min(MAX_MANUAL_LEVERAGE, leverage)),
        "market_type": MARKET_FUTURES,
        "signal_id": data.get("id"),
    }


__all__ = [
    "AMOUNT_PRESETS",
    "DEFAULT_FEE_RATE",
    "MARKET_FUTURES",
    "MARKET_SPOT",
    "MARKET_TYPES",
    "MAX_MANUAL_LEVERAGE",
    "ManualOrderPlan",
    "ManualOrderRequest",
    "liquidation_price",
    "normalize_symbol",
    "percent_from_price",
    "plan_manual_order",
    "prefill_from_signal",
    "price_from_percent",
]
