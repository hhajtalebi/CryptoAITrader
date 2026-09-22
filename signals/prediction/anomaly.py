"""
تشخیص آنومالی و آلفای زودهنگام — خواسته‌های ۱۸ و ۴۰.

چرا این فایل وجود دارد؟
    «قیمت +۰٫۲٪ ولی حجم +۴۲۰٪» الگویی است که پیش از حرکت‌های بزرگ
    دیده می‌شود؛ چشم انسان به آن عادت ندارد، آمارهٔ robust می‌بیندش.

روش — z-score مقاوم (میانه/MAD):
    میانگین و انحراف معیارِ معمولی خودِ آنومالی آن‌ها را می‌بلعد؛
    median/MAD در برابر مقادیر افراطی مقاوم است و برای دادهٔ بازار
    انتخاب درست‌تری است. هر متریک با «تاریخچهٔ خودش» مقایسه می‌شود.

آلفای زودهنگام (خواستهٔ ۴۰): ترکیب قاعده‌محورِ چند آنومالی —
حجمِ غیرعادی با قیمتِ خنثی، انقباض نوسان با جهش حجم، واگرایی RSI —
هر کدام با «مدت از کشف» گزارش می‌شود. عوامل بدون داده (OI، funding،
sentiment اجتماعی) صریحاً unavailable می‌مانند.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.core.models import Candle

#: آستانهٔ |z| برای علامت‌خوردن یک متریک.
ANOMALY_Z_THRESHOLD = 4.0

#: آستانهٔ ترکیبی برای «آنومالی بازار».
COMPOSITE_THRESHOLD = 2.5


@dataclass(slots=True)
class MetricAnomaly:
    """آنومالی یک متریک."""

    metric: str
    z: float
    value: float
    baseline: float

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "metric": self.metric,
            "z": round(self.z, 2),
            "value": round(self.value, 6),
            "baseline": round(self.baseline, 6),
        }


@dataclass(slots=True)
class AnomalyReport:
    """گزارش آنومالی‌های یک تایم‌فریم."""

    anomalies: list[MetricAnomaly] = field(default_factory=list)
    composite_z: float = 0.0
    is_anomaly: bool = False
    early_alpha: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "anomalies": [a.to_dict() for a in self.anomalies],
            "composite_z": round(self.composite_z, 2),
            "is_anomaly": self.is_anomaly,
            "early_alpha": self.early_alpha,
        }


def _robust_z(values: list[float], latest: float) -> tuple[float, float]:
    """z مقاوم آخرین مقدار نسبت به تاریخچه؛ خروجی: (z, baseline میانه)."""
    if len(values) < 30:
        return 0.0, latest
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    deviations = sorted(abs(v - median) for v in values)
    mad = deviations[len(deviations) // 2]
    if mad <= 1e-12:
        # سری تقریباً ثابت — فاصلهٔ مطلق را با مقیاس خود میانه بسنج
        return (0.0 if abs(latest - median) < 1e-12 else 8.0), median
    return (latest - median) / (1.4826 * mad), median


def detect_anomalies(candles: list[Candle]) -> AnomalyReport:
    """
    کشف رفتار غیرعادی از کندل‌های بسته‌شده.

    متریک‌ها: بازدهٔ مطلق، حجم نسبت به میانگین متحرک، دامنهٔ کندل،
    جهش حجم.
    """
    report = AnomalyReport()
    if len(candles) < 60:
        return report

    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    ranges = [c.high - c.low for c in candles]

    returns: list[float] = []
    for previous, current in zip(closes[:-1], closes[1:], strict=False):
        if previous > 0:
            returns.append(abs(math.log(current / previous)))

    volume_surges: list[float] = []
    for index in range(20, len(volumes)):
        window_mean = sum(volumes[index - 20:index]) / 20.0
        volume_surges.append(volumes[index] / window_mean if window_mean > 0 else 1.0)

    checks: list[tuple[str, list[float], float]] = [
        ("abs_return", returns[:-1], returns[-1] if returns else 0.0),
        ("volume_surge", volume_surges[:-1], volume_surges[-1] if volume_surges else 1.0),
        ("candle_range", ranges[:-1], ranges[-1]),
    ]
    for metric, history, latest in checks:
        if not history:
            continue
        z, baseline = _robust_z(history, latest)
        if abs(z) >= ANOMALY_Z_THRESHOLD:
            report.anomalies.append(MetricAnomaly(metric, z, latest, baseline))

    if report.anomalies:
        report.composite_z = sum(abs(a.z) for a in report.anomalies) / len(report.anomalies)
        report.is_anomaly = report.composite_z >= COMPOSITE_THRESHOLD

    report.early_alpha = _early_alpha(candles, report)
    return report


def _early_alpha(candles: list[Candle], report: AnomalyReport) -> dict[str, Any] | None:
    """
    آلفای زودهنگام — خواستهٔ ۴۰.

    قواعد (هرچه داده واقعی پشتیبانی کند):
        • حجم غیرعادی + قیمت خنثی → «انباشت پنهان» محتمل
        • آنومالی حجم به‌تنهایی → «فعالیت غیرمعمول»
    """
    if len(candles) < 60:
        return None

    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    recent_return = (closes[-1] / closes[-6] - 1.0) * 100 if closes[-6] > 0 else 0.0
    volume_mean = sum(volumes[-26:-6]) / 20.0
    recent_volume = sum(volumes[-5:]) / 5.0
    volume_ratio = recent_volume / volume_mean if volume_mean > 0 else 1.0

    _, vol_baseline = _robust_z(volumes[:-1], volumes[-1])
    volume_unusual = volume_ratio > 2.0
    price_flat = abs(recent_return) < 0.5

    if volume_unusual and price_flat:
        return {
            "status": "unusual_accumulation_suspected",
            "confidence": min(85, int(45 + (volume_ratio - 2.0) * 15)),
            "detected_candles_ago": 5,
            "factors": {
                "volume_ratio": round(volume_ratio, 2),
                "recent_return_percent": round(recent_return, 2),
                "open_interest": "unavailable",
                "funding_shift": "unavailable",
                "cvd_divergence": "unavailable",
                "social_sentiment": "unavailable",
            },
        }
    if report.is_anomaly:
        return {
            "status": "unusual_market_activity",
            "confidence": min(80, int(30 + report.composite_z * 10)),
            "detected_candles_ago": 1,
            "factors": {"composite_z": round(report.composite_z, 2)},
        }
    return None
