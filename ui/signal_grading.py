"""
درجه‌بندی دیداری سیگنال‌ها — رنگ و نشانه.

کاربر خواست: «سیگنال‌ها از ۵۰ یا ۶۰ به بالا با علامت و رنگ سبز مشخص
بشن، به همین ترتیب اونایی که ریسک معامله کم [رنگی از خانوادهٔ] سبز و
اونایی که ریسک معامله زیاد با رنگ‌های مناسب، انتظار هم رنگ مناسب.»

چرا یک ماژول جداگانه؟
    رنگ سیگنال در چند جا لازم می‌شود: جدول پویش، سابقهٔ سیگنال، کارت
    سیگنال جاری و مدال جزئیات. اگر هر کدام برای خودش آستانه تعریف کند،
    یک روز جدول می‌گوید «خوب» و کارت می‌گوید «متوسط». اینجا یک منبع
    حقیقت داریم.

چرا رنگ‌ها از توکن پوسته می‌آیند و ثابت نیستند؟
    قاعدهٔ پروژه: هیچ رنگ سختی در صفحه‌ها نوشته نمی‌شود. این ماژول نام
    توکن (`success`, `warning`, …) را برمی‌گرداند و فراخوان، رنگ را از
    پوستهٔ فعال می‌گیرد. پس درجه‌بندی در هر هفت‌هشت پوسته درست دیده
    می‌شود، نه فقط در پوستهٔ تیره.

آستانه‌ها
    ۶۰ به بالا  → قوی  (سبز پررنگ + علامت ✓)
    ۵۰ تا ۵۹    → خوب  (سبز + علامت ✓)
    ۳۵ تا ۴۹    → متوسط (کهربایی)
    زیر ۳۵      → ضعیف  (خاکستری)
    کاربر «۵۰ یا ۶۰» گفت؛ هر دو مرز پیاده شد تا هم ۵۰ سبز باشد و هم
    ۶۰ به بالا از آن متمایز بماند.
"""

from __future__ import annotations

from dataclasses import dataclass

#: مرز پایین «سیگنال سبز» — از این عدد به بالا سبز است
CONFIDENCE_GOOD = 50
#: مرز «سیگنال قوی» — سبز پررنگ‌تر و علامت دوتایی
CONFIDENCE_STRONG = 60
#: زیر این عدد سیگنال ضعیف شمرده می‌شود
CONFIDENCE_WEAK = 35


@dataclass(frozen=True, slots=True)
class Grade:
    """
    یک درجهٔ دیداری.

    فیلدها:
        key       : شناسه (برای آزمون و کلید ترجمه)
        token     : نام توکن رنگ در پوسته — نه خود رنگ
        mark      : نشانهٔ متنی کوتاه که کنار عدد می‌نشیند
        emphasis  : آیا باید پررنگ (bold) نمایش داده شود
    """

    key: str
    token: str
    mark: str
    emphasis: bool = False


#: درجه‌های ضریب اطمینان
CONFIDENCE_GRADES: dict[str, Grade] = {
    "strong": Grade(key="strong", token="success", mark="✓✓", emphasis=True),
    "good": Grade(key="good", token="success", mark="✓"),
    "fair": Grade(key="fair", token="warning", mark="•"),
    "weak": Grade(key="weak", token="neutral", mark="–"),
}

#: درجه‌های ریسک معامله
RISK_GRADES: dict[str, Grade] = {
    "low": Grade(key="low", token="success", mark="▼", emphasis=True),
    "medium": Grade(key="medium", token="warning", mark="■"),
    "high": Grade(key="high", token="danger", mark="▲", emphasis=True),
    "unknown": Grade(key="unknown", token="neutral", mark="?"),
}

#: درجه‌های تازگی سیگنال.
#:
#: کاربر گفت «باید خرید و فروش در چه زمانی مشخص باشد تا سیگنال سوخته
#: نباشد». رنگ اینجا نقش هشدار دارد نه تزئین: سیگنال سوخته باید در
#: نگاه اول از سیگنال تازه جدا باشد، وگرنه کاربر روی فرصتی که دیگر
#: وجود ندارد معامله می‌کند.
FRESHNESS_GRADES: dict[str, Grade] = {
    "FRESH": Grade(key="fresh", token="success", mark="●", emphasis=True),
    "AGING": Grade(key="aging", token="warning", mark="◐"),
    "STALE": Grade(key="stale", token="danger", mark="○", emphasis=True),
    "EXPIRED": Grade(key="expired", token="neutral", mark="✕"),
    "INVALIDATED": Grade(key="invalidated", token="danger", mark="✕", emphasis=True),
}


#: درجه‌های جهت سیگنال — «انتظار» هم رنگ مخصوص خودش را دارد
DIRECTION_GRADES: dict[str, Grade] = {
    "LONG": Grade(key="long", token="success", mark="▲", emphasis=True),
    "SHORT": Grade(key="short", token="danger", mark="▼", emphasis=True),
    "WAIT": Grade(key="wait", token="info", mark="⏸"),
}


def confidence_grade(confidence: int | float | None) -> Grade:
    """
    درجهٔ دیداری یک ضریب اطمینان.

    مقدار نامعتبر (None یا متن) «ضعیف» گرفته می‌شود نه خطا؛ یک ردیف
    خراب در جدول نباید صفحه را از کار بیندازد.
    """
    try:
        value = int(confidence or 0)
    except (TypeError, ValueError):
        value = 0
    if value >= CONFIDENCE_STRONG:
        return CONFIDENCE_GRADES["strong"]
    if value >= CONFIDENCE_GOOD:
        return CONFIDENCE_GRADES["good"]
    if value >= CONFIDENCE_WEAK:
        return CONFIDENCE_GRADES["fair"]
    return CONFIDENCE_GRADES["weak"]


def risk_level(
    *,
    stop_distance_percent: float | None = None,
    leverage: int | None = None,
    risk_reward: float | None = None,
) -> str:
    """
    تعیین سطح ریسک یک معامله: `low` / `medium` / `high` / `unknown`.

    چرا این سه ورودی؟
        * **فاصلهٔ حد ضرر** مستقیم‌ترین معیار است: حد ضرر دور یعنی
          سرمایهٔ بیشتری در معرض خطر.
        * **اهرم** ضریب همان خطر است؛ اهرم ۱۰ یعنی نوسان ۱٪ می‌شود ۱۰٪.
        * **نسبت ریسک به ریوارد** پاداش را می‌سنجد: معامله‌ای با R/R
          پایین حتی با حد ضرر نزدیک، ارزش ریسکش را ندارد.

    بدترین معیار تعیین‌کننده است (بیشینهٔ سه امتیاز)، نه میانگین. یک
    اهرم ۲۰ با حد ضرر نزدیک، باز هم معاملهٔ پرریسکی است و میانگین‌گیری
    آن را پنهان می‌کرد.
    """
    scores: list[int] = []

    if stop_distance_percent is not None:
        try:
            distance = abs(float(stop_distance_percent))
        except (TypeError, ValueError):
            distance = -1.0
        if distance >= 0:
            scores.append(0 if distance <= 2.0 else 1 if distance <= 5.0 else 2)

    if leverage is not None:
        try:
            lev = int(leverage)
        except (TypeError, ValueError):
            lev = 1
        scores.append(0 if lev <= 3 else 1 if lev <= 10 else 2)

    if risk_reward is not None:
        try:
            ratio = float(risk_reward)
        except (TypeError, ValueError):
            ratio = 0.0
        if ratio > 0:
            scores.append(0 if ratio >= 2.5 else 1 if ratio >= 1.5 else 2)

    if not scores:
        return "unknown"
    worst = max(scores)
    return ("low", "medium", "high")[worst]


def risk_grade(level: str) -> Grade:
    """درجهٔ دیداری یک سطح ریسک."""
    return RISK_GRADES.get(str(level or "").lower(), RISK_GRADES["unknown"])


def direction_grade(direction: str) -> Grade:
    """درجهٔ دیداری جهت سیگنال (LONG/SHORT/WAIT)."""
    return DIRECTION_GRADES.get(str(direction or "").upper(), DIRECTION_GRADES["WAIT"])


def signal_risk_level(payload: dict) -> str:
    """
    سطح ریسک از روی دیکشنری یک سیگنال.

    داده گاهی از موتور می‌آید (`risk` تودرتو) و گاهی از پایگاه داده
    (فیلدهای مسطح). هر دو شکل پشتیبانی می‌شود تا فراخوان مجبور نباشد
    بداند داده از کجا آمده.
    """
    # «انتظار» معامله‌ای نیست، پس ریسکی هم ندارد. اگر اینجا سطح می‌دادیم،
    # ردیف انتظار با اهرم پیش‌فرض ۱ برچسب «کم‌ریسک» می‌گرفت و کاربر
    # گمان می‌کرد فرصت امنی است.
    if str(payload.get("direction", "")).upper() == "WAIT":
        return "unknown"

    risk = payload.get("risk") or {}
    if not isinstance(risk, dict):
        risk = {}
    stop = risk.get("stop_distance_percent", payload.get("stop_distance_percent"))
    ratio = payload.get("risk_reward")

    # اهرم به‌تنهایی معیار کافی نیست: هر سیگنالی اهرم دارد (دست‌کم ۱) و
    # اگر تنها همان را بسنجیم، سیگنالِ بدون حد ضرر و بدون R/R هم
    # «کم‌ریسک» اعلام می‌شود. صادقانه‌تر آن است که بگوییم نامشخص.
    if stop is None and not ratio:
        return "unknown"

    return risk_level(
        stop_distance_percent=stop,
        leverage=payload.get("leverage"),
        risk_reward=ratio,
    )


def freshness_grade(freshness: str | None) -> Grade:
    """
    درجهٔ دیداری تازگی سیگنال.

    مقدار ناشناخته «منقضی» گرفته می‌شود، نه «تازه». این انتخاب عمدی و
    محافظه‌کارانه است: اگر نمی‌دانیم سیگنال تازه است یا نه، نباید با
    رنگ سبز به کاربر بگوییم تازه است.
    """
    key = str(freshness or "").strip().upper()
    return FRESHNESS_GRADES.get(key, FRESHNESS_GRADES["EXPIRED"])


def color_for(grade: Grade, theme: object, fallback: str = "#94a3b8") -> str:
    """
    رنگ واقعی یک درجه از روی پوستهٔ فعال.

    اگر پوسته‌ای داده نشده باشد (آزمون بدون رابط گرافیکی) رنگ پشتیبان
    برمی‌گردد، پس فراخوان هیچ‌وقت `None` نمی‌گیرد.
    """
    colors = getattr(theme, "colors", None)
    if colors is None:
        return fallback
    return str(getattr(colors, grade.token, fallback) or fallback)


__all__ = [
    "CONFIDENCE_GOOD",
    "CONFIDENCE_GRADES",
    "CONFIDENCE_STRONG",
    "CONFIDENCE_WEAK",
    "DIRECTION_GRADES",
    "Grade",
    "RISK_GRADES",
    "color_for",
    "confidence_grade",
    "direction_grade",
    "risk_grade",
    "risk_level",
    "signal_risk_level",
]
