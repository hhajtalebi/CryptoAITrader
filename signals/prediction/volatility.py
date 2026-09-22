"""
پیش‌بینی نوسان (Volatility Forecasting) — خواسته‌های ۱۱ و ۱۲.

چرا این فایل وجود دارد؟
    پیش‌بینی «جهت» بدون پیش‌بینی «نوسان» ناقص است: بازهٔ ۴ ساعته‌ای که
    نوسانش فشرده است با بازهٔ ۴ ساعتهٔ بحرانی، درست‌فرق دارند حتی اگر
    جهت یکی باشد. کاربر خواسته نوسان آینده برای هر افق + تشخیص گذار
    از «انقباض» به «انبساط» را دارد.

روش:
    • سیگما لختی‌دار EWMA (سبک RiskMetrics) روی بازده‌های لگاریتمی —
      وزن نمایی به دادهٔ تازه؛ بدون فرض توزیع.
    • مقیاس جذر زمان برای افق‌ها — قاعدهٔ استاندارد انتشار نوسان.
    • برچسب نوسان نسبت به «تاریخچهٔ خودِ نماد» (صدک EWMA در گذشتهٔ
      خودش) — چون ۲٪ برای بیت‌کوین و یک آلت کوچک معنای یکسان ندارد.
    • تشخیص انقباض→انبساط از شیب EWMA + صدک فعلی.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.core.models import Candle

#: ضریب میرایی EWMA — مقدار متعارف برای دادهٔ روزانه/ساعتی.
EWMA_LAMBDA = 0.94

#: برچسب‌های کلاس نوسان — پایدار برای DB و UI.
VOL_LABELS = ("low", "medium", "high", "very_high")

#: برچسب گذار ساختاری.
COMPRESSION = "compression"
EXPANSION = "expansion"
STABLE = "stable"


@dataclass(slots=True)
class VolatilityForecast:
    """پیش‌بینی نوسان یک افق."""

    horizon: str
    sigma: float            # سیگمای بازدهٔ لگاریتمی افق
    percentile: float       # صدک سیگمای گام نسبت به تاریخچهٔ خودش
    label: str              # low | medium | high | very_high
    regime: str             # compression | expansion | stable
    samples: int = 0
    note: str = ""

    @property
    def sigma_percent(self) -> float:
        """سیگما به درصد قیمت — برای نمایش."""
        return self.sigma * 100.0

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "horizon": self.horizon,
            "sigma_percent": round(self.sigma_percent, 4),
            "percentile": round(self.percentile, 1),
            "label": self.label,
            "regime": self.regime,
            "samples": self.samples,
            "note": self.note,
        }


def ewma_sigma(returns: list[float], *, lam: float = EWMA_LAMBDA) -> float:
    """
    سیگمای لختی‌دار بازده‌ها.

    چرا EWMA و نه انحراف معیار ساده؟ چون ساده، سقوط دیشب و سه هفته پیش
    را هم‌وزن می‌بیند؛ بازار به تازه‌ها واکنش نشان می‌دهد.
    """
    values = [r for r in returns if math.isfinite(r)]
    if len(values) < 5:
        return 0.0
    variance = values[0] ** 2
    weight_total = 1.0
    for value in values[1:]:
        variance = lam * variance + (1 - lam) * value * value
        weight_total = lam * weight_total + 1 - lam
    return math.sqrt(max(variance, 0.0))


def ewma_history(returns: list[float], *, window: int = 60) -> list[float]:
    """سری سیگمای EWMA برای محاسبهٔ صدک — فقط مقادیر «گذشته» هر نقطه."""
    history: list[float] = []
    for end in range(10, len(returns) + 1):
        history.append(ewma_sigma(returns[max(0, end - window):end]))
    return history


def forecast_for_horizon(
    *,
    horizon: str,
    steps: int,
    candles: list[Candle],
) -> VolatilityForecast | None:
    """
    پیش‌بینی نوسان یک افق از کندل‌های بسته‌شدهٔ تایم‌فریم مبدأ.

    بازگشتی: None اگر داده کافی نباشد — بدون عددسازی.
    """
    returns: list[float] = []
    for previous, current in zip(candles[:-1], candles[1:], strict=False):
        if previous.close > 0 and current.close > 0:
            returns.append(math.log(current.close / previous.close))
    if len(returns) < 30:
        return None

    step_sigma = ewma_sigma(returns)
    sigma = step_sigma * math.sqrt(max(steps, 1))

    # صدک نسبت به تاریخچهٔ خودِ سری
    history = ewma_history(returns[:-1])
    if len(history) >= 20:
        below = sum(1 for value in history if value <= step_sigma)
        percentile = below / len(history) * 100.0
    else:
        percentile = 50.0

    # شیب اخیر سیگما برای گذار ساختاری
    recent = ewma_sigma(returns[-10:])
    older = ewma_sigma(returns[-30:-10]) if len(returns) >= 30 else recent
    rising = recent > older * 1.15
    falling = recent < older * 0.85

    if percentile >= 80 and rising:
        regime = EXPANSION
    elif percentile <= 20 and falling:
        regime = COMPRESSION
    else:
        regime = STABLE

    if percentile >= 90:
        label = "very_high"
    elif percentile >= 70:
        label = "high"
    elif percentile >= 30:
        label = "medium"
    else:
        label = "low"

    return VolatilityForecast(
        horizon=horizon,
        sigma=sigma,
        percentile=percentile,
        label=label,
        regime=regime,
        samples=len(returns),
    )
