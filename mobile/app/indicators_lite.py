"""
موتور اندیکاتور «سبک» — همان ریاضی، بدون pandas و numpy.

چرا این فایل وجود دارد؟
    نسخهٔ دسکتاپ اندیکاتورها را با pandas حساب می‌کند. روی اندروید،
    pandas یکی از بدنام‌ترین بسته‌ها برای کامپایل است: دستورهای ساخت
    آن مرتب می‌شکنند و حتی وقتی APK ساخته می‌شود، اپ هنگام import با
    خطای پیوند بسته می‌شود.

    راه‌حل سالم، حذف وابستگی است نه جنگیدن با آن. این ماژول همان
    فرمول‌ها را با پایتون خالص پیاده می‌کند: هیچ وابستگی بیرونی، و
    نتیجهٔ عددی یکسان.

هم‌ارزی با نسخهٔ دسکتاپ **آزموده شده** است:
    `tests/test_v1912_mobile.py` خروجی این توابع را با همان اندیکاتور
    pandas مقایسه می‌کند و اختلاف بیش از ۱e-۹ را شکست می‌شمارد. اگر
    روزی یکی از دو طرف تغییر کند، آزمون می‌شکند — نه کاربر.

نکتهٔ کارایی:
    برای چند صد کندل (چیزی که یک گوشی نمایش می‌دهد) پایتون خالص کاملاً
    سریع است؛ سربار ساخت DataFrame اینجا اصلاً وجود ندارد.
"""

from __future__ import annotations

from collections.abc import Sequence

# مقدار «نامعلوم». در pandas این `NaN` است؛ اینجا `None` می‌گذاریم تا
# هیچ‌جا یک عدد جعلی وارد محاسبه نشود.
Number = float | None


def _ewm(values: Sequence[float], alpha: float, min_periods: int) -> list[Number]:
    """
    میانگین متحرک نمایی، معادل `Series.ewm(alpha=..., adjust=False)`.

    `adjust=False` یعنی فرمول بازگشتی ساده:
        y[0] = x[0]
        y[i] = alpha*x[i] + (1-alpha)*y[i-1]

    تا پیش از `min_periods` مقدار `None` برمی‌گردد؛ دقیقاً مثل pandas.
    """
    out: list[Number] = []
    previous: float | None = None
    for index, value in enumerate(values):
        previous = value if previous is None else alpha * value + (1 - alpha) * previous
        out.append(previous if index + 1 >= min_periods else None)
    return out


def ema(values: Sequence[float], period: int) -> list[Number]:
    """میانگین متحرک نمایی با `span=period` (همان تعریف pandas)."""
    if period <= 0:
        raise ValueError("period باید مثبت باشد")
    return _ewm(values, 2.0 / (period + 1.0), period)


def sma(values: Sequence[float], period: int) -> list[Number]:
    """میانگین متحرک ساده."""
    if period <= 0:
        raise ValueError("period باید مثبت باشد")
    out: list[Number] = []
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        out.append(running / period if index + 1 >= period else None)
    return out


def rsi(closes: Sequence[float], period: int = 14) -> list[Number]:
    """
    شاخص قدرت نسبی با هموارسازی وایلدر.

    وایلدر معادل `ewm(alpha=1/period)` است — نه میانگین ساده. این نکته
    جایی است که بیشتر پیاده‌سازی‌های دست‌ساز با نسخهٔ مرجع فرق پیدا
    می‌کنند، و آزمون هم‌ارزی دقیقاً همین را می‌گیرد.
    """
    if len(closes) < 2:
        return [None] * len(closes)

    gains: list[float] = [0.0]
    losses: list[float] = [0.0]
    for index in range(1, len(closes)):
        delta = closes[index] - closes[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    alpha = 1.0 / period
    # pandas روی سری `diff()` کار می‌کند که خانهٔ نخستش NaN است و در
    # شمارش `min_periods` حساب نمی‌شود؛ برای همین از اندیس ۱ شروع
    # می‌کنیم و یک `None` به ابتدا می‌چسبانیم.
    avg_gain = _ewm(gains[1:], alpha, period)
    avg_loss = _ewm(losses[1:], alpha, period)

    out: list[Number] = [None]
    for gain, loss in zip(avg_gain, avg_loss, strict=True):
        if gain is None or loss is None:
            out.append(None)
        elif loss == 0:
            # بدون هیچ زیانی، RSI برابر ۱۰۰ است.
            out.append(100.0)
        else:
            out.append(100.0 - 100.0 / (1.0 + gain / loss))
    return out


def macd(
    closes: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, list[Number]]:
    """خط مکدی، خط سیگنال و هیستوگرام."""
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    line: list[Number] = [
        None if f is None or s is None else f - s
        for f, s in zip(ema_fast, ema_slow, strict=True)
    ]

    # خط سیگنال فقط روی بخش معتبر مکدی حساب می‌شود.
    valid = [v for v in line if v is not None]
    smoothed = ema(valid, signal)
    padding = len(line) - len(valid)
    signal_line: list[Number] = [None] * padding + smoothed

    histogram: list[Number] = [
        None if m is None or s is None else m - s
        for m, s in zip(line, signal_line, strict=True)
    ]
    return {"macd": line, "signal": signal_line, "histogram": histogram}


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[Number]:
    """
    میانگین دامنهٔ واقعی — پایهٔ حد ضرر و اندازهٔ موقعیت.

    اینجا هموارسازی وایلدر است، نه میانگین ساده.
    """
    true_ranges: list[float] = []
    for index in range(len(closes)):
        if index == 0:
            true_ranges.append(highs[index] - lows[index])
            continue
        previous_close = closes[index - 1]
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - previous_close),
                abs(lows[index] - previous_close),
            )
        )
    return _ewm(true_ranges, 1.0 / period, period)


def bollinger(
    closes: Sequence[float], period: int = 20, deviations: float = 2.0
) -> dict[str, list[Number]]:
    """
    باندهای بولینگر.

    انحراف معیار **جمعیتی** (تقسیم بر n) است تا با `rolling().std(ddof=0)`
    نسخهٔ دسکتاپ یکی باشد. تفاوت ddof یک اشتباه کلاسیک است که باندها را
    کمی جابه‌جا می‌کند و در نگاه اول دیده نمی‌شود.
    """
    middle = sma(closes, period)
    upper: list[Number] = []
    lower: list[Number] = []
    for index in range(len(closes)):
        center = middle[index]
        if center is None:
            upper.append(None)
            lower.append(None)
            continue
        window = closes[index - period + 1 : index + 1]
        variance = sum((value - center) ** 2 for value in window) / period
        spread = deviations * (variance**0.5)
        upper.append(center + spread)
        lower.append(center - spread)
    return {"upper": upper, "middle": middle, "lower": lower}


def stochastic(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    k_period: int = 14,
    d_period: int = 3,
) -> dict[str, list[Number]]:
    """نوسان‌نمای استوکاستیک (%K و %D)."""
    k_values: list[Number] = []
    for index in range(len(closes)):
        if index + 1 < k_period:
            k_values.append(None)
            continue
        window_high = max(highs[index - k_period + 1 : index + 1])
        window_low = min(lows[index - k_period + 1 : index + 1])
        span = window_high - window_low
        # بازار کاملاً تخت: تقسیم بر صفر. ۵۰ یعنی «وسط»، که درست است.
        k_values.append(
            50.0 if span == 0 else 100.0 * (closes[index] - window_low) / span
        )

    valid = [v for v in k_values if v is not None]
    smoothed = sma(valid, d_period)
    padding = len(k_values) - len(valid)
    return {"k": k_values, "d": [None] * padding + smoothed}
