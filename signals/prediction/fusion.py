"""
موتور فیوژن هوشمند (Smart Signal Fusion) — خواسته‌های ۴، ۱۹ و ۳۶.

چرا این فایل وجود دارد؟
    کاربر صریح نوشته: «سیگنال‌های مختلف را کورکورانه جمع نکن.» هر
    منبع (توزیع آماری، آنسامبل ML، رژیم، آنومالی، order flow) وزن
    خودش را دارد و اختلاف بزرگِ مدل‌ها باید «تعارض» اعلام شود نه
    میانگین‌گیریِ خوش‌بینانه.

وزن‌ها:
    پیش‌فرض‌ها اینجا تعریف شده‌اند و از بیرون قابل‌تنظیم‌اند (تنظیمات
    کاربر) — بر اساس عملکرد تاریخی، فاز ۱۰ وزن‌ها را تطبیق می‌دهد.

چندتایم‌فریمی (خواستهٔ ۴): دید کوتاه‌مدت/میان‌مدت/بلندمدت از رژیم‌های
تفکیک‌شدهٔ تایم‌فریم‌ها ساخته می‌شود و «واژگونی کوتاه‌مدت داخل روند
بلندمدت» تشخیص داده می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: وزن‌های پیش‌فرض اجزا — مجموع لازم نیست ۱ باشد (نرمال می‌شود).
DEFAULT_WEIGHTS: dict[str, float] = {
    "distribution": 1.0,   # توزیع آماری از تاریخ خود نماد
    "ensemble": 1.2,       # آنسامبل ML
    "regime": 0.8,         # جهت رژیم غالب
    "momentum": 0.6,       # مومنتوم لحظه‌ای فیچرها
    "anomaly": 0.3,        # آنومالی (معمولاً خنثی مگر غیرعادی)
}

#: اختلاف جفتیِ بیشتر از این (۰..۱) یعنی تعارض جدی مدل‌ها.
CONFLICT_THRESHOLD = 0.35


@dataclass(slots=True)
class FusionComponent:
    """یک منبع نظریه‌پردازی جهت."""

    name: str
    direction: str      # bullish | bearish | neutral
    probability: int    # احتمال جهت مثبت (به سود صعود) 0..100
    weight: float
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "name": self.name,
            "direction": self.direction,
            "probability": self.probability,
            "weight": round(self.weight, 3),
            "note": self.note,
        }


@dataclass(slots=True)
class FusionResult:
    """نتیجهٔ فیوژن وزن‌دار."""

    direction: str
    probability: int
    agreement: float          # 0..1 توافق اجزا
    conflict: bool
    reliability: str          # high | medium | low
    components: list[FusionComponent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "direction": self.direction,
            "probability": self.probability,
            "agreement": round(self.agreement, 3),
            "conflict": self.conflict,
            "reliability": self.reliability,
            "components": [c.to_dict() for c in self.components],
        }


def fuse(
    components: list[FusionComponent],
    *,
    weights: dict[str, float] | None = None,
) -> FusionResult:
    """
    ترکیب وزن‌دار اجزا با تشخیص تعارض.

    احتمال نهایی میانگین وزن‌دار «احتمال صعودی» اجزاست؛ توافق از
    پراکندگی آن‌ها می‌آید. تعارض جدی، reliability را LOW می‌کند —
    سیستم به‌جای پنهان‌کردن اختلاف، آن را اعلام می‌کند.
    """
    if not components:
        return FusionResult("neutral", 50, 0.0, False, "low")

    merged: dict[str, FusionComponent] = {}
    for component in components:
        weight = (weights or DEFAULT_WEIGHTS).get(component.name, component.weight)
        if component.name in merged:
            previous = merged[component.name]
            # میانگین وزنی مؤلفه‌های هم‌نام (مثلاً چند تایم‌فریم)
            total = previous.weight + weight
            merged[component.name] = FusionComponent(
                name=component.name,
                direction=component.direction,
                probability=int(round(
                    (previous.probability * previous.weight + component.probability * weight) / total
                )),
                weight=total,
                note=previous.note or component.note,
            )
        else:
            merged[component.name] = FusionComponent(
                name=component.name,
                direction=component.direction,
                probability=component.probability,
                weight=weight,
                note=component.note,
            )

    items = list(merged.values())
    total_weight = sum(item.weight for item in items) or 1.0
    fused_probability = sum(item.probability * item.weight for item in items) / total_weight

    # توافق: ۱ منهای نصفِ دامنهٔ نرمال‌شده
    probabilities = [item.probability for item in items]
    spread = (max(probabilities) - min(probabilities)) / 100.0
    agreement = max(0.0, 1.0 - spread)
    conflict = spread > CONFLICT_THRESHOLD and len(items) > 1

    probability = int(round(max(1.0, min(99.0, fused_probability))))
    if probability > 55:
        direction = "bullish"
    elif probability < 45:
        direction = "bearish"
    else:
        direction = "neutral"

    if conflict:
        reliability = "low"
    elif agreement >= 0.75:
        reliability = "high"
    else:
        reliability = "medium"

    return FusionResult(
        direction=direction,
        probability=probability,
        agreement=agreement,
        conflict=conflict,
        reliability=reliability,
        components=items,
    )


# ---------------------------------------------------------------------------
# فیوژن چندتایم‌فریمی — خواستهٔ ۴
# ---------------------------------------------------------------------------
#: دسته‌بندی تایم‌فریم‌ها به افق دید.
SHORT_TERM_TFS = ("1m", "3m", "5m", "15m", "30m")
MEDIUM_TERM_TFS = ("1h", "2h", "4h")
LONG_TERM_TFS = ("6h", "12h", "24h", "1d", "3d", "1w", "1M")


def _bucket_direction(assessments: list[tuple[str, int]]) -> str:
    """جهت غالب یک سبد تایم‌فریمی از (tf, direction) ها."""
    if not assessments:
        return "neutral"
    score = sum(direction for _, direction in assessments)
    if score > 0:
        return "bullish"
    if score < 0:
        return "bearish"
    return "neutral"


def multi_timeframe_view(regimes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    دید کوتاه/میان/بلندمدت از رژیم‌های تفکیک‌شده + مرحلهٔ بازار.

    ورودی: نگاشت tf → خروجی to_dict رژیم (حداقل کلید direction).
    خروجی: برچسب سه سبد + تشخیص «واژگونی کوتاه‌مدت داخل روند
    بلندمدت» — همان چیزی که کاربر مثال زد.
    """
    short = [(tf, int(a.get("direction", 0))) for tf, a in regimes.items() if tf in SHORT_TERM_TFS]
    medium = [(tf, int(a.get("direction", 0))) for tf, a in regimes.items() if tf in MEDIUM_TERM_TFS]
    longs = [(tf, int(a.get("direction", 0))) for tf, a in regimes.items() if tf in LONG_TERM_TFS]

    short_dir = _bucket_direction(short)
    medium_dir = _bucket_direction(medium)
    long_dir = _bucket_direction(longs)

    # واژگونی کوتاه‌مدت داخل روند بلندمدت
    reversal_inside_trend = (
        long_dir in ("bullish", "bearish")
        and short_dir in ("bullish", "bearish")
        and short_dir != long_dir
        and medium_dir == long_dir
    )

    return {
        "short_term": short_dir,
        "medium_term": medium_dir,
        "long_term": long_dir,
        "reversal_inside_trend": reversal_inside_trend,
        "market_stage_note": (
            "short_term_reversal_inside_long_term_trend" if reversal_inside_trend else ""
        ),
        "per_timeframe": {tf: a.get("regime", "unknown") for tf, a in sorted(regimes.items())},
    }
