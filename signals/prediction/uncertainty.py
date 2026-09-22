"""
موتور عدم‌قطعیت و اعتبار زمانی — خواسته‌های ۳۳ و ۳۴.

چرا این فایل وجود دارد؟
    مهم‌ترین قابلیت یک سیستم پیش‌بینی صادق، توانایی گفتنِ «نمی‌دانم»
    است. سیستم‌هایی که همیشه Bullish/Bearish اعلام می‌کنند، آمار
    می‌سازند تا حق باشند — و کاربر را گمراه می‌کنند.

    این ماژول دو چیز می‌سنجد:
    • اطمینان مؤثر: احتمال خام را با توافق مدل‌ها، کیفیت داده،
      پایداری رژیم و نزدیکی رویداد مهم تعدیل می‌کند؛ زیر آستانه،
      جهتِ «uncertain» صادقانه اعلام می‌شود.
    • زوال اعتبار: پیش‌بینیِ ۴۵ دقیقه پیش نباید اعتبارِ همین الان را
      داشته باشد؛ با گذشت زمان و تغییر شرایط، اعتبار می‌سوزد.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

#: زیر این اطمینان مؤثر، جهت «uncertain» اعلام می‌شود.
UNCERTAIN_THRESHOLD = 40

#: ضریب زوال اعتبار — هر «یک افق» عمر، اعتبار تا این کسر می‌رسد.
DECAY_FRACTION = 0.35


@dataclass(slots=True)
class UncertaintyAdjustment:
    """نتیجهٔ تعدیل عدم‌قطعیت."""

    direction: str        # bullish | bearish | neutral | uncertain
    probability: int      # احتمال مؤثر جهت
    confidence: int       # اطمینان مؤثر (می‌تواند از احتمال کمتر باشد)
    uncertain: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "direction": self.direction,
            "probability": self.probability,
            "confidence": self.confidence,
            "uncertain": self.uncertain,
            "reasons": list(self.reasons),
        }


def effective_confidence(
    *,
    probability: int,
    model_agreement: float = 1.0,      # 0..1
    data_quality_ratio: float = 1.0,   # 0..1 سهم ردیف‌های سالم
    regime_stability: float = 1.0,     # 0..1
    event_pressure: float = 0.0,       # 0..1 فشار رویداد نزدیک
    method_reliability: float = 1.0,   # تجربی=0.9 تحلیلی=0.7 از موتور
) -> UncertaintyAdjustment:
    """
    اطمینان مؤثر از ترکیب عوامل کاهنده.

    هیچ عاملی اطمینان را «بالا» نمی‌برد؛ فقط پایین می‌آورند — چون
    خوش‌بینی ساختگی در بازار گران تمام می‌شود.
    """
    reasons: list[str] = []
    confidence = float(probability)

    if model_agreement < 0.6:
        confidence *= 0.55 + 0.45 * model_agreement
        reasons.append("model_disagreement")
    if data_quality_ratio < 0.9:
        confidence *= 0.5 + 0.5 * data_quality_ratio
        reasons.append("data_quality_below_par")
    if regime_stability < 0.6:
        confidence *= 0.6 + 0.4 * regime_stability
        reasons.append("unstable_regime")
    if event_pressure > 0.0:
        confidence *= 1.0 - 0.5 * event_pressure
        reasons.append("high_impact_event_near")
    confidence *= method_reliability
    if method_reliability < 0.8:
        reasons.append("limited_sample_method")

    confidence = int(round(max(0.0, min(100.0, confidence))))
    uncertain = confidence < UNCERTAIN_THRESHOLD

    if uncertain:
        direction = "uncertain"
    elif probability > 55:
        direction = "bullish"
    elif probability < 45:
        direction = "bearish"
    else:
        direction = "neutral"

    return UncertaintyAdjustment(
        direction=direction,
        probability=probability,
        confidence=confidence,
        uncertain=uncertain,
        reasons=reasons,
    )


def decayed_validity(
    *,
    original_confidence: int,
    age_minutes: float,
    horizon_minutes: int,
) -> int:
    """
    اعتبار فعلی یک پیش‌بینی به‌گذشت زمان — خواستهٔ ۳۴.

    مدل: تا ۲۰٪ اولِ افق (دورهٔ عسل) اعتبار کامل می‌ماند؛ بعد به‌طور
    نمایی می‌سوزد و در پایان افق به `DECAY_FRACTION` می‌رسد. بعد از
    دو برابرِ افق، عملاً صفر — پیش‌بینیِ گذشته شده اعتبار ندارد.
    """
    if age_minutes <= 0 or horizon_minutes <= 0:
        return max(0, min(100, original_confidence))

    grace = 0.2 * horizon_minutes
    if age_minutes <= grace:
        return max(0, min(100, original_confidence))

    life = max(1.0, horizon_minutes - grace)
    elapsed = min(age_minutes - grace, 2.0 * horizon_minutes)
    fraction = math.exp(-2.0 * elapsed / life)
    # در پایان افق به DECAY_FRACTION برسد: e^{-2}≈0.135 نزدیک است؛
    # خطی ترکیب می‌کنیم تا عدد خوانا باشد.
    validity = original_confidence * (
        DECAY_FRACTION + (1.0 - DECAY_FRACTION) * fraction
    ) if elapsed < life else original_confidence * DECAY_FRACTION * max(
        0.0, 1.0 - (elapsed - life) / life
    )
    return int(round(max(0.0, min(100.0, validity))))
