"""
موتور توزیع احتمال (Probability Distribution Engine) — فاز ۴.

چرا این فایل وجود دارد؟
    خواستهٔ دوم کاربر: به‌جای «BTC می‌رسد به ۱۱۵ هزار»، توزیع احتمال
    (P10/P25/P50/P75/P90) و احتمال رسیدن به هر محدوده. حدسِ یک عدد
    قطعی، دروغِ آماری است؛ چندک‌ها می‌گویند «با چه احتمالی کجا».

روش — دو حالت، هر دو از دادهٔ واقعی:
    • تجربی (empirical): همهٔ بازده‌های «گام‌به‌گامِ هم‌طولِ افق» از
      تاریخِ همین نماد جمع می‌شوند و چندک‌ها مستقیم از توزیع واقعیِ
      گذشته برآورد می‌شوند. نیازمند حداقل نمونه.
    • تحلیلی (analytic): وقتی نمونه کافی نیست، بازه از ATR با مقیاس
      جذر زمان ساخته می‌شود (همان روش صادقانهٔ forecast.py موجود) و
      خروجی صریحاً برچسب «analytic» می‌خورد.

    احتمال جهت از سهم بازده‌های مثبتِ گذشته می‌آید و حداکثر با ۱۰ واحد
    درصد تحت تأثیر تمایل لحظه‌ای (momentum tilt) جابه‌جا می‌شود؛ سقف
    نهایی ۸۰٪ است — هیچ پیش‌بینی قطعی اعلام نمی‌شود.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.core.models import Candle
from app.logging import get_logger

logger = get_logger(__name__)

#: کمینهٔ نمونهٔ بازده برای روش تجربی.
MIN_EMPIRICAL_SAMPLES = 50

#: سقف احتمال اعلام‌شده — همان سقف صداقت forecast.py موجود.
MAX_PROBABILITY = 80

#: کف احتمال — زیر این، ادعای جهت بی‌معناست.
MIN_PROBABILITY = 20

#: حداکثر اثر تمایل لحظه‌ای بر احتمال (واحد درصد).
MAX_TILT_EFFECT = 10.0

#: چندک‌های استاندارد خواسته‌شده و z معادل آن‌ها برای روش تحلیلی.
_QUANTILE_Z: tuple[tuple[str, float], ...] = (
    ("p10", -1.2816),
    ("p25", -0.6745),
    ("p50", 0.0),
    ("p75", 0.6745),
    ("p90", 1.2816),
)


@dataclass(slots=True)
class HorizonDistribution:
    """توزیع احتمال قیمت در یک افق."""

    horizon: str
    steps: int
    method: str                 # empirical | analytic | disabled
    samples: int
    last_price: float
    quantiles: dict[str, float]  # p10..p90 به «قیمت»
    returns_quantiles: dict[str, float]  # همان چندک‌ها به «بازده لگاریتمی»
    direction: str              # bullish | bearish | neutral
    probability: int            # احتمال جهت اعلام‌شده
    expected_range: tuple[float, float]  # بازهٔ P25..P75
    sigma: float                # انحراف معیار بازدهٔ افق
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری برای گزارش/UI/عامل."""
        return {
            "horizon": self.horizon,
            "steps": self.steps,
            "method": self.method,
            "samples": self.samples,
            "last_price": round(self.last_price, 8),
            "quantiles": {k: round(v, 8) for k, v in self.quantiles.items()},
            "direction": self.direction,
            "probability": self.probability,
            "expected_range": [round(self.expected_range[0], 8), round(self.expected_range[1], 8)],
            "sigma_percent": round(self.sigma * 100, 4),
            "note": self.note,
        }


def forward_log_returns(candles: list[Candle], steps: int) -> list[float]:
    """
    بازده‌های لگاریتمی «steps کندل جلوتر» برای همهٔ نقاط ممکن.

    فقط از کندل‌های بسته‌شده ساخته می‌شود؛ کندل در حال شکل‌گیری هرگز
    ورود نمی‌کند (ضد look-ahead). هم‌پوشانی پنجره‌ها آگاهانه است: با
    دادهٔ محدود، حذف هم‌پوشانی نیمی از اطلاعات را می‌ریزد؛ چندک‌گیری
    به استقلال نمونه‌ها حساسیت کمتری دارد.
    """
    returns: list[float] = []
    for index in range(len(candles) - steps):
        base = candles[index].close
        ahead = candles[index + steps].close
        if base > 0 and ahead > 0:
            returns.append(math.log(ahead / base))
    return returns


def _empirical_quantile(sorted_values: list[float], q: float) -> float:
    """چندک با درون‌یابی خطی روی لیست مرتب."""
    if not sorted_values:
        return 0.0
    position = q * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def build_distribution(
    *,
    horizon: str,
    steps: int,
    candles: list[Candle],
    momentum_tilt: float = 0.0,
    atr: float | None = None,
) -> HorizonDistribution | None:
    """
    ساخت توزیع احتمال یک افق از کندل‌های بسته‌شدهٔ تایم‌فریم مبدأ.

    پارامترها:
        horizon       : کد افق مثل "4h".
        steps         : چند کندل جلوتر (از plan_horizons).
        candles       : کندل‌های بسته‌شدهٔ تایم‌فریم مبدأ.
        momentum_tilt : تمایل لحظه‌ای بین -1 و +1 (از رژیم/فیوژن).
        atr           : ATR تایم‌فریم مبدأ برای روش تحلیلی.

    بازگشتی: HorizonDistribution یا None اگر داده اصلاً کافی نباشد —
    هیچ عددی بدون پشتوانه ساخته نمی‌شود.
    """
    if len(candles) < steps + 30 or candles[-1].close <= 0:
        return None

    last_price = float(candles[-1].close)
    returns = forward_log_returns(candles, steps)

    if len(returns) >= MIN_EMPIRICAL_SAMPLES:
        method = "empirical"
        samples = len(returns)
        ordered = sorted(returns)
        ret_q = {name: _empirical_quantile(ordered, q) for q, name in _QUANTILE_Z_QUANTILES}
        sigma = _std(returns)
        positive_share = sum(1 for r in returns if r > 0) / len(returns)
        note = ""
    elif atr is not None and atr > 0 and len(candles) >= 60:
        # روش تحلیلی: نوسان تک‌گام ATR، مقیاس جذر گام
        method = "analytic"
        samples = len(returns)
        step_sigma = atr / last_price
        sigma = step_sigma * math.sqrt(steps)
        ret_q = {name: z * sigma for name, z in _QUANTILE_Z_NAMES.items()}
        positive_share = 0.5  # بدون جهت‌داری داده‌ای — خنثی
        note = "quantiles from ATR scaling, not empirical history"
    else:
        return None

    # احتمال جهت: سهم مثبت‌های گذشته ± حداکثر ۱۰ واحد تمایل لحظه‌ای
    probability = positive_share * 100.0
    probability += max(-MAX_TILT_EFFECT, min(MAX_TILT_EFFECT, momentum_tilt * MAX_TILT_EFFECT))
    probability = max(MIN_PROBABILITY, min(MAX_PROBABILITY, probability))

    if probability > 55:
        direction = "bullish"
    elif probability < 45:
        direction = "bearish"
    else:
        direction = "neutral"
        probability = 50

    quantiles = {name: last_price * math.exp(value) for name, value in ret_q.items()}

    return HorizonDistribution(
        horizon=horizon,
        steps=steps,
        method=method,
        samples=samples,
        last_price=last_price,
        quantiles=quantiles,
        returns_quantiles={k: round(v, 6) for k, v in ret_q.items()},
        direction=direction,
        probability=int(round(probability)),
        expected_range=(quantiles["p25"], quantiles["p75"]),
        sigma=sigma,
        note=note,
    )


def probability_of_range(dist: HorizonDistribution, lower: float, upper: float) -> float:
    """
    احتمال رسیدن قیمت به یک محدودهٔ دلخواه — خواستهٔ ۲.

    از چندک‌های بازده با درون‌یابی، سطح احتمال بین دو قیمت را می‌دهد.
    """
    ret_lower = math.log(lower / dist.last_price) if lower > 0 else float("-inf")
    ret_upper = math.log(upper / dist.last_price) if upper > 0 else float("inf")

    # تابع توزیع تجمعی تقریبی از چندک‌های موجود
    def cdf(value: float) -> float:
        points = [(-1e9, 0.0)]
        points += [
            (dist.returns_quantiles[name], float(name[1:]) / 100.0)
            for name in ("p10", "p25", "p50", "p75", "p90")
        ]
        points.append((1e9, 1.0))
        for (x0, y0), (x1, y1) in zip(points[:-1], points[1:], strict=False):
            if x0 <= value <= x1:
                if x1 == x0:
                    return y0
                return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
        return 1.0 if value > points[-1][0] else 0.0

    return max(0.0, min(1.0, cdf(ret_upper) - cdf(ret_lower)))


def _std(values: list[float]) -> float:
    """انحراف معیار نمونه‌ای."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


#: نگاشت نام چندک → مقدار q برای حالت تجربی.
_QUANTILE_Z_QUANTILES: tuple[tuple[float, str], ...] = (
    (0.10, "p10"),
    (0.25, "p25"),
    (0.50, "p50"),
    (0.75, "p75"),
    (0.90, "p90"),
)

#: نگاشت نام چندک → z برای حالت تحلیلی.
_QUANTILE_Z_NAMES: dict[str, float] = dict(_QUANTILE_Z)
