"""
پیش‌بینی تایم‌فریم بعدی.

کاربر خواست: «از روی داده‌های ۱۵ دقیقه‌ای، ۱۵ دقیقه، یک ساعت یا چهار
ساعت آیندهٔ بازار پیش‌بینی شود.»

فلسفهٔ این ماژول — و دلیل اینکه عمداً محافظه‌کار است:
    بازار قابل پیش‌بینی قطعی نیست. هر ابزاری که ادعای پیش‌بینی دقیق
    قیمت کند، دارد دروغ می‌گوید. کاری که *می‌شود* صادقانه انجام داد،
    برآورد یک **بازهٔ محتمل** است: بر پایهٔ نوسان اندازه‌گیری‌شدهٔ خودِ
    بازار، قیمت با احتمال مشخصی داخل چه محدوده‌ای می‌ماند.

    این همان کاری است که یک معامله‌گر حرفه‌ای انجام می‌دهد و دقیقاً
    همان چیزی است که کاربر برای تصمیم‌گیری لازم دارد: «تا یک ساعت آینده
    احتمالاً بین این دو عدد می‌ماند و تمایلش رو به بالاست».

روش:
    ۱. نوسان هر کندل از ATR گرفته می‌شود (نوسان واقعیِ اندازه‌گیری‌شده،
       نه فرضی).
    ۲. نوسان با جذر تعداد کندل مقیاس می‌خورد — قاعدهٔ استاندارد انتشار
       نوسان در زمان. نوسان چهار کندل، دو برابر یک کندل است نه چهار برابر.
    ۳. تمایل جهت‌دار از سیگنال موتور می‌آید و فقط مرکز بازه را کمی
       جابه‌جا می‌کند؛ اجازه ندارد بازه را تنگ کند.
    ۴. احتمال، از اطمینان سیگنال می‌آید و سقفش همان سقف صداقت است.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.core.constants import SignalDirection

#: چند کندل جلوتر برای هر افق پیش‌بینی می‌شود.
#: کلید: تایم‌فریم پایه، مقدار: نگاشت افق به تعداد کندل.
HORIZON_STEPS: dict[str, dict[str, int]] = {
    "1m": {"5m": 5, "15m": 15, "1h": 60},
    "5m": {"15m": 3, "1h": 12, "4h": 48},
    "15m": {"15m": 1, "1h": 4, "4h": 16},
    "30m": {"1h": 2, "4h": 8, "1d": 48},
    "1h": {"1h": 1, "4h": 4, "1d": 24},
    "4h": {"4h": 1, "1d": 6, "1w": 42},
    "1d": {"1d": 1, "1w": 7, "1M": 30},
}

#: بازهٔ اطمینان ۸۰٪ تقریباً ۱٫۲۸ انحراف معیار است.
#: عدد بزرگ‌تر بازه را پهن‌تر و بی‌مصرف‌تر می‌کند.
SIGMA_MULTIPLIER = 1.28

#: بیشترین جابه‌جایی مرکز بازه بر اثر تمایل جهت‌دار، به‌صورت کسری از
#: نوسان. بیش از این یعنی ادعای پیش‌بینی قیمت، نه برآورد بازه.
MAX_DRIFT_FRACTION = 0.6

#: سقف احتمالی که اعلام می‌شود. هیچ پیش‌بینی‌ای قطعی نیست.
MAX_PROBABILITY = 80


@dataclass(slots=True)
class HorizonForecast:
    """پیش‌بینی یک افق زمانی مشخص."""

    horizon: str
    steps: int
    expected_price: float
    lower: float
    upper: float
    bias: str
    probability: int
    range_percent: float

    def as_dict(self) -> dict[str, object]:
        """تبدیل به دیکشنری برای ذخیره و نمایش."""
        return {
            "horizon": self.horizon,
            "steps": self.steps,
            "expected_price": round(self.expected_price, 8),
            "lower": round(self.lower, 8),
            "upper": round(self.upper, 8),
            "bias": self.bias,
            "probability": self.probability,
            "range_percent": round(self.range_percent, 3),
        }


@dataclass(slots=True)
class Forecast:
    """مجموعهٔ پیش‌بینی‌های چند افق برای یک نماد."""

    symbol: str
    base_timeframe: str
    last_price: float
    horizons: list[HorizonForecast] = field(default_factory=list)
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        """تبدیل به دیکشنری برای ذخیره و نمایش."""
        return {
            "symbol": self.symbol,
            "base_timeframe": self.base_timeframe,
            "last_price": round(self.last_price, 8),
            "note": self.note,
            "horizons": [h.as_dict() for h in self.horizons],
        }


def _atr_from_candles(candles: list, period: int = 14) -> float:
    """
    محاسبهٔ میانگین دامنهٔ واقعی.

    اگر ATR از بیرون در دسترس نباشد، اینجا مستقیم از کندل‌ها حساب
    می‌شود تا این ماژول به موتور اندیکاتور وابسته نباشد.
    """
    if len(candles) < 2:
        return 0.0
    true_ranges: list[float] = []
    for previous, current in zip(candles[:-1], candles[1:], strict=False):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    window = true_ranges[-period:]
    if not window:
        return 0.0
    return sum(window) / len(window)


def _bias_label(direction: SignalDirection | str) -> str:
    """برچسب تمایل جهت‌دار."""
    value = direction.value if isinstance(direction, SignalDirection) else str(direction)
    value = value.upper()
    if value == "LONG":
        return "bullish"
    if value == "SHORT":
        return "bearish"
    return "neutral"


def forecast_next(
    *,
    symbol: str,
    timeframe: str,
    candles: list,
    direction: SignalDirection | str = SignalDirection.WAIT,
    confidence: int = 0,
    atr: float | None = None,
) -> Forecast:
    """
    برآورد بازهٔ محتمل قیمت برای افق‌های بعدی.

    پارامترها:
        symbol: نماد بازار.
        timeframe: تایم‌فریم داده‌های ورودی.
        candles: کندل‌های تاریخی (هرچه بیشتر، برآورد نوسان دقیق‌تر).
        direction: جهت سیگنال موتور؛ فقط مرکز بازه را جابه‌جا می‌کند.
        confidence: اطمینان سیگنال؛ مبنای احتمال اعلام‌شده.
        atr: در صورت محاسبه‌شدن از بیرون، دوباره حساب نمی‌شود.

    بازگشتی: شیء Forecast. اگر داده کافی نباشد، فهرست افق‌ها خالی است و
    `note` دلیل را توضیح می‌دهد — بدون عددسازی.
    """
    if not candles:
        return Forecast(
            symbol=symbol,
            base_timeframe=timeframe,
            last_price=0.0,
            note="no_candles",
        )

    last_price = float(candles[-1].close)
    if last_price <= 0:
        return Forecast(
            symbol=symbol,
            base_timeframe=timeframe,
            last_price=0.0,
            note="invalid_price",
        )

    if len(candles) < 20:
        return Forecast(
            symbol=symbol,
            base_timeframe=timeframe,
            last_price=last_price,
            note="not_enough_history",
        )

    volatility = float(atr) if atr and atr > 0 else _atr_from_candles(candles)
    if volatility <= 0:
        return Forecast(
            symbol=symbol,
            base_timeframe=timeframe,
            last_price=last_price,
            note="flat_market",
        )

    steps_map = HORIZON_STEPS.get(timeframe)
    if not steps_map:
        return Forecast(
            symbol=symbol,
            base_timeframe=timeframe,
            last_price=last_price,
            note="unsupported_timeframe",
        )

    bias = _bias_label(direction)
    # اطمینان به کسری بین ۰ و ۱ تبدیل می‌شود و شدت جابه‌جایی مرکز را
    # تعیین می‌کند. سیگنال ضعیف، مرکز را تکان نمی‌دهد.
    strength = max(0.0, min(float(confidence) / 100.0, 1.0))
    if bias == "neutral":
        strength = 0.0

    horizons: list[HorizonForecast] = []
    for horizon, steps in steps_map.items():
        # نوسان با جذر زمان منتشر می‌شود.
        horizon_sigma = volatility * math.sqrt(steps)
        half_width = horizon_sigma * SIGMA_MULTIPLIER

        drift = horizon_sigma * MAX_DRIFT_FRACTION * strength
        if bias == "bearish":
            drift = -drift
        elif bias == "neutral":
            drift = 0.0

        expected = last_price + drift
        lower = expected - half_width
        upper = expected + half_width

        # قیمت منفی بی‌معناست.
        lower = max(lower, 0.0)

        # احتمال: از اطمینان سیگنال می‌آید ولی هرچه افق دورتر، کمتر.
        # پیش‌بینی چهار ساعت آینده ذاتاً از پانزده دقیقهٔ آینده ضعیف‌تر است.
        decay = 1.0 / (1.0 + math.log1p(steps) * 0.25)
        if bias == "neutral":
            probability = 50
        else:
            probability = int(round(min(confidence * decay, MAX_PROBABILITY)))

        horizons.append(
            HorizonForecast(
                horizon=horizon,
                steps=steps,
                expected_price=expected,
                lower=lower,
                upper=upper,
                bias=bias,
                probability=probability,
                range_percent=(upper - lower) / last_price * 100,
            )
        )

    return Forecast(
        symbol=symbol,
        base_timeframe=timeframe,
        last_price=last_price,
        horizons=horizons,
        note="ok",
    )

def score_forecast(
    horizons: list[dict],
    actual_prices: dict[str, float],
) -> dict[str, object]:
    """
    سنجش دقت یک پیش‌بینی در برابر قیمت واقعی.

    چرا لازم است: پیش‌بینی‌ای که هرگز ارزیابی نشود، ادعای بی‌پشتوانه
    است. بازهٔ اعلام‌شده با اطمینان ۸۰٪ ساخته می‌شود، پس در بلندمدت
    باید تقریباً **۸۰٪ مواقع** قیمت واقعی داخلش بیفتد.

        • خیلی کمتر از ۸۰٪ ⇒ بازه‌ها بیش از حد تنگ‌اند
          (`SIGMA_MULTIPLIER` باید بالا برود).
        • خیلی بیشتر از ۸۰٪ ⇒ بازه‌ها آن‌قدر پهن‌اند که بی‌فایده‌اند.

    پارامترها:
        horizons: خروجی `HorizonForecast.as_dict()`.
        actual_prices: نگاشت افق به قیمت واقعیِ مشاهده‌شده.

    بازگشتی: دیکشنری شامل تعداد بررسی‌شده، تعداد داخل بازه، نرخ اصابت و
    جزئیات هر افق. افقی که قیمت واقعی‌اش نرسیده باشد **شمرده نمی‌شود**.
    """
    checked = 0
    hits = 0
    details: list[dict[str, object]] = []

    for item in horizons:
        # ردیف خراب (رشته، None، …) نباید کل سنجش را از کار بیندازد؛
        # این داده از پایگاه داده می‌آید و ممکن است از نسخه‌های قدیمی
        # یا یک ذخیره‌سازی ناقص مانده باشد.
        if not isinstance(item, dict):
            continue
        horizon = str(item.get("horizon", ""))
        if horizon not in actual_prices:
            continue
        try:
            actual = float(actual_prices[horizon])
            lower = float(item.get("lower", 0.0))
            upper = float(item.get("upper", 0.0))
        except (TypeError, ValueError):
            continue
        if upper < lower:
            continue

        inside = lower <= actual <= upper
        checked += 1
        hits += 1 if inside else 0

        # خطای جهت‌دار: چقدر بیرون از بازه افتاده (صفر یعنی داخل).
        if actual < lower:
            miss = lower - actual
        elif actual > upper:
            miss = actual - upper
        else:
            miss = 0.0

        details.append(
            {
                "horizon": horizon,
                "actual": actual,
                "lower": lower,
                "upper": upper,
                "inside": inside,
                "miss": round(miss, 8),
            }
        )

    return {
        "checked": checked,
        "hits": hits,
        "hit_rate": round(hits / checked * 100, 2) if checked else 0.0,
        "target_rate": 80.0,
        "details": details,
    }
