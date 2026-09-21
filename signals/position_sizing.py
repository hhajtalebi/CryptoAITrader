"""
محاسبهٔ حجم پوزیشن.

چرا جدا از `risk_engine`؟
    موتور ریسک یک **ستاپ مشخص** را ارزیابی می‌کند و پارامترهایش از
    تنظیمات کاربر می‌آید. ماشین‌حساب اما ابزاری دستی است: کاربر عددها را
    خودش می‌گذارد، سرمایه‌اش را موقتاً عوض می‌کند و «چه می‌شود اگر»
    بازی می‌کند — بدون آنکه تنظیمات ریسکش تغییر کند.

    ضمناً اینجا مارجین و فاصلهٔ تقریبی لیکوییدیشن هم حساب می‌شود که موتور
    ریسک اصلاً نمی‌دهد، چون به اهرم انتخابی کاربر بستگی دارد نه به ستاپ.

قاعدهٔ بنیادی (همان که در آموزش نوشته شده):
    حجم از **حد ضرر** به دست می‌آید، نه برعکس. کاربر نباید اول تصمیم
    بگیرد «۵۰۰ دلار وارد می‌کنم» و بعد دنبال جای حد ضرر بگردد.
"""

from __future__ import annotations

from dataclasses import dataclass

#: بیشترین اهرم منطقی؛ بالاتر از این عملاً قمار است و ورودی بریده می‌شود
MAX_LEVERAGE = 125

#: کارمزد رفت‌وبرگشت پیش‌فرض (درصد) — تقریبی برای بازار فیوچرز
DEFAULT_FEE_PERCENT = 0.08

#: آستانهٔ هشدار: ریسک بیش از این درصد از سرمایه در یک معامله
RISK_WARNING_PERCENT = 2.0

#: آستانهٔ هشدار: فاصلهٔ حد ضرر از لیکوییدیشن کمتر از این ضریب
LIQUIDATION_SAFETY_FACTOR = 1.5


@dataclass(frozen=True)
class PositionPlan:
    """
    نتیجهٔ محاسبهٔ حجم پوزیشن.

    `warnings` فهرست **کلید ترجمه** است نه متن آماده؛ محاسبه نباید به
    زبان رابط کاربری گره بخورد.
    """

    #: تعداد واحد دارایی (مثلاً بیت‌کوین)
    quantity: float
    #: ارزش کل پوزیشن به واحد نقل قول (معمولاً دلار)
    notional: float
    #: وجه تضمین لازم با اهرم انتخابی
    margin: float
    #: مبلغی که با خوردن حد ضرر از دست می‌رود
    risk_amount: float
    #: همان مبلغ به‌صورت درصدی از سرمایه (واقعیِ محاسبه‌شده)
    risk_percent_actual: float
    #: فاصلهٔ حد ضرر تا ورود، بر حسب درصد
    stop_distance_percent: float
    #: قیمت تقریبی لیکوییدیشن (صفر یعنی محاسبه‌نشدنی)
    liquidation_price: float
    #: فاصلهٔ لیکوییدیشن از ورود، بر حسب درصد
    liquidation_distance_percent: float
    #: سود در صورت رسیدن به هدف (صفر اگر هدفی داده نشده باشد)
    reward_amount: float
    #: نسبت سود به ریسک
    risk_reward: float
    #: کارمزد تقریبی رفت‌وبرگشت (باز و بسته کردن پوزیشن)
    fee_amount: float
    #: جهت استنتاج‌شده از محل حد ضرر
    direction: str = "LONG"
    #: سرمایه‌ای که محاسبه بر مبنای آن انجام شده
    capital: float = 0.0
    #: اهرم واقعاً به‌کاررفته (پس از محدود شدن به سقف صرافی)
    leverage: int = 1
    #: آیا محاسبه معتبر است
    valid: bool = True
    #: کلید ترجمهٔ دلیل نامعتبر بودن
    error_key: str = ""
    #: کلیدهای ترجمهٔ هشدارها
    warnings: tuple[str, ...] = ()


def calculate_position(
    *,
    capital: float,
    risk_percent: float,
    entry: float,
    stop_loss: float,
    leverage: int = 1,
    take_profit: float = 0.0,
    fee_percent: float = DEFAULT_FEE_PERCENT,
) -> PositionPlan:
    """
    محاسبهٔ کامل یک پوزیشن از روی حد ضرر.

    ورودی نامعتبر خطا نمی‌دهد؛ نتیجه‌ای با `valid=False` و کلید دلیل
    برمی‌گرداند تا رابط کاربری بتواند پیام مناسب نشان دهد. ماشین‌حسابی که
    هنگام تایپ‌کردن استثنا پرتاب کند، غیرقابل‌استفاده است.

    مثال:
        plan = calculate_position(
            capital=1000, risk_percent=1, entry=60000, stop_loss=58800
        )
        plan.quantity   →  0.00833…
        plan.risk_amount →  10.0
    """
    invalid = _validate(capital, risk_percent, entry, stop_loss)
    if invalid:
        return _empty_plan(invalid)

    leverage = max(1, min(MAX_LEVERAGE, int(leverage or 1)))
    stop_distance = abs(entry - stop_loss)
    stop_distance_percent = stop_distance / entry * 100

    risk_amount = capital * (risk_percent / 100)
    quantity = risk_amount / stop_distance
    notional = quantity * entry
    margin = notional / leverage

    # جهت از روی محل حد ضرر فهمیده می‌شود؛ پرسیدنش از کاربر اضافه است و
    # جای اشتباه باز می‌کند.
    is_long = stop_loss < entry

    liquidation_price, liquidation_distance = _liquidation(entry, leverage, is_long=is_long)


    reward_amount = 0.0
    risk_reward = 0.0
    # هدفی که در سمت اشتباه قیمت باشد سود نیست؛ `abs` آن را به‌غلط سود
    # نشان می‌داد و نسبت ریسک‌به‌سود را جعل می‌کرد.
    target_is_profitable = (
        take_profit > entry if is_long else 0 < take_profit < entry
    )
    if take_profit > 0 and target_is_profitable:
        reward_amount = abs(take_profit - entry) * quantity
        risk_reward = reward_amount / risk_amount if risk_amount > 0 else 0.0

    # کارمزد رفت‌وبرگشت: یک بار هنگام باز کردن و یک بار هنگام بستن.
    # حساب‌کردن یک‌طرفه، سود را بزرگ‌تر از واقع نشان می‌دهد.
    fee_amount = notional * (max(0.0, fee_percent) / 100) * 2

    warnings = _collect_warnings(
        capital=capital,
        risk_percent=risk_percent,
        margin=margin,
        stop_distance_percent=stop_distance_percent,
        liquidation_distance=liquidation_distance,
        leverage=leverage,
        risk_reward=risk_reward,
        has_target=take_profit > 0,
        fee_amount=fee_amount,
        risk_amount=risk_amount,
    )

    return PositionPlan(
        quantity=round(quantity, 8),
        notional=round(notional, 2),
        margin=round(margin, 2),
        risk_amount=round(risk_amount, 2),
        risk_percent_actual=round(risk_percent, 3),
        direction="LONG" if is_long else "SHORT",
        capital=round(capital, 2),
        leverage=leverage,
        stop_distance_percent=round(stop_distance_percent, 3),
        liquidation_price=round(liquidation_price, 8),
        liquidation_distance_percent=round(liquidation_distance, 3),
        reward_amount=round(reward_amount, 2),
        risk_reward=round(risk_reward, 2),
        fee_amount=round(fee_amount, 2),
        warnings=warnings,
    )


def required_win_rate(risk_reward: float) -> float:
    """
    کمینهٔ نرخ برد لازم برای سربه‌سر شدن، بر حسب درصد.

    همان جدولی که در آموزش آمده، ولی محاسبه‌شده: با R/R برابر ۳، نرخ
    برد ۲۵ درصد کافی است.
    """
    if risk_reward <= 0:
        return 100.0
    return round(100.0 / (1.0 + risk_reward), 2)


def breakeven_price(
    *, entry: float, direction: str = "LONG", fee_percent: float = DEFAULT_FEE_PERCENT
) -> float:
    """
    قیمتی که در آن، پس از کسر کارمزد رفت‌وبرگشت، نه سود است نه زیان.

    معامله‌گر تازه‌کار فکر می‌کند نقطهٔ سربه‌سر همان قیمت ورود است؛ با
    کارمزد این‌طور نیست.
    """
    if entry <= 0:
        return 0.0
    is_long = str(direction).upper() != "SHORT"
    factor = max(0.0, fee_percent) / 100 * 2
    return round(entry * (1 + factor) if is_long else entry * (1 - factor), 8)


# ---------------------------------------------------------------- درونی


def _validate(capital: float, risk_percent: float, entry: float, stop_loss: float) -> str:
    """بررسی ورودی‌ها؛ بازگشتی کلید ترجمهٔ خطا یا رشتهٔ خالی."""
    if capital <= 0:
        return "sizing.error_capital"
    if risk_percent <= 0 or risk_percent > 100:
        return "sizing.error_risk"
    if entry <= 0:
        return "sizing.error_entry"
    if stop_loss <= 0:
        return "sizing.error_stop"
    if abs(entry - stop_loss) < 1e-12:
        return "sizing.error_same_price"
    return ""


def _empty_plan(error_key: str) -> PositionPlan:
    """نتیجهٔ خالی برای ورودی نامعتبر."""
    return PositionPlan(
        quantity=0.0,
        notional=0.0,
        margin=0.0,
        risk_amount=0.0,
        risk_percent_actual=0.0,
        stop_distance_percent=0.0,
        liquidation_price=0.0,
        liquidation_distance_percent=0.0,
        reward_amount=0.0,
        risk_reward=0.0,
        fee_amount=0.0,
        valid=False,
        error_key=error_key,
    )


def _liquidation(entry: float, leverage: int, *, is_long: bool) -> tuple[float, float]:
    """
    قیمت تقریبی لیکوییدیشن و فاصله‌اش تا ورود.

    **تقریبی** است و عمداً هم همین‌طور: هر صرافی نرخ نگهداری مارجین و
    کارمزد خودش را دارد، پس عدد دقیق فقط از خود صرافی می‌آید. این تخمین
    محافظه‌کارانه است — فاصلهٔ واقعی کمی **کمتر** از این خواهد بود، نه
    بیشتر؛ پس کاربر را در امنیت کاذب نمی‌گذارد.
    """
    if leverage <= 1:
        # بدون اهرم، لیکوییدیشن عملاً در صفر است (برای لانگ)
        return (0.0, 100.0) if is_long else (0.0, 0.0)

    distance_percent = 100.0 / leverage
    if is_long:
        price = entry * (1 - distance_percent / 100)
    else:
        price = entry * (1 + distance_percent / 100)
    return price, distance_percent


def _collect_warnings(
    *,
    capital: float,
    risk_percent: float,
    margin: float,
    stop_distance_percent: float,
    liquidation_distance: float,
    leverage: int,
    risk_reward: float,
    has_target: bool,
    fee_amount: float,
    risk_amount: float,
) -> tuple[str, ...]:
    """
    جمع‌آوری هشدارهای معنادار.

    هشدارها کلید ترجمه‌اند. ترتیبشان از خطرناک‌ترین به کم‌اهمیت‌ترین است
    تا اگر رابط کاربری فقط چندتا را جا داد، مهم‌ترین‌ها دیده شوند.
    """
    warnings: list[str] = []

    # خطرناک‌ترین حالت: حد ضرر آن‌سوی لیکوییدیشن است، یعنی پیش از رسیدن
    # به حد ضرر، پوزیشن بسته شده و کل مارجین رفته.
    if liquidation_distance > 0 and stop_distance_percent >= liquidation_distance:
        warnings.append("sizing.warn_stop_beyond_liquidation")
    elif (
        liquidation_distance > 0
        and stop_distance_percent * LIQUIDATION_SAFETY_FACTOR >= liquidation_distance
    ):
        warnings.append("sizing.warn_near_liquidation")

    if margin > capital:
        warnings.append("sizing.warn_margin_exceeds_capital")

    if risk_percent > RISK_WARNING_PERCENT:
        warnings.append("sizing.warn_high_risk")

    if leverage > 10:
        warnings.append("sizing.warn_high_leverage")

    if has_target and 0 < risk_reward < 1.5:
        warnings.append("sizing.warn_low_rr")

    # کارمزد وقتی مهم است که با ریسک قابل‌مقایسه شود
    if risk_amount > 0 and fee_amount > risk_amount * 0.25:
        warnings.append("sizing.warn_fees_significant")

    return tuple(warnings)


__all__ = [
    "DEFAULT_FEE_PERCENT",
    "LIQUIDATION_SAFETY_FACTOR",
    "MAX_LEVERAGE",
    "RISK_WARNING_PERCENT",
    "PositionPlan",
    "breakeven_price",
    "calculate_position",
    "required_win_rate",
]
