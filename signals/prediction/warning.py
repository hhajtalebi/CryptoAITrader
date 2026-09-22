"""
سیستم هشدار زودهنگام (Early Warning System) — خواستهٔ ۸.

چرا این فایل وجود دارد؟
    کاربر صریح نوشته: «این بخش نباید ادعا کند حتماً سقوط اتفاق
    می‌افتد؛ بلکه Potential Risk را تشخیص دهد.» پس خروجی این ماژول
    «ریسک محتمل» است نه پیش‌بینی — و هر هشدار، عوامل قابل‌استنادِ
    خودش را دارد.

قواعد (همه از دادهٔ واقعی، همه قابل توضیح):
    • واگرایی مومنتوم: قیمت بالاتر، RSI پایین‌تر → تضعیف روند
    • محوشدن حجم در روند → حرکت بی‌پشتوانه
    • نوسان در حال انبساط از انقباض → آغاز حرکت بزرگ (در هر جهت)
    • رژیم «توزیع» در سقف → ریسک توزیع
    • آنومالی ترکیبی → فعالیت غیرعادی
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: شناسه‌های پایدار هشدار — UI با کلید ترجمهٔ «prediction.warning.<id>» نمایش می‌دهد.
WARNING_MOMENTUM_DIVERGENCE = "momentum_divergence"
WARNING_VOLUME_FADING = "volume_fading"
WARNING_VOLATILITY_EXPANDING = "volatility_expanding"
WARNING_DISTRIBUTION_RISK = "distribution_risk"
WARNING_ANOMALY = "anomaly"
WARNING_REGIME_SHIFT = "regime_shift"


@dataclass(slots=True)
class EarlyWarning:
    """یک هشدار ریسک — نه پیش‌بینی سقوط."""

    kind: str
    severity: str            # info | warning | high
    confidence: int          # 0..100 — اطمینان به «وجود ریسک»
    factors: dict[str, Any] = field(default_factory=dict)
    potential_event: str = ""  # رویداد محتمل، نه قطعی

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "kind": self.kind,
            "severity": self.severity,
            "confidence": self.confidence,
            "factors": dict(self.factors),
            "potential_event": self.potential_event,
            "disclaimer": "Potential risk detected — not a prediction of a crash.",
        }


def build_warnings(
    *,
    rsi_series: list[float | None],
    closes: list[float],
    volume_series: list[float],
    volatility_regime: str = "",
    market_regime: str = "",
    anomaly_composite_z: float = 0.0,
    transition_risk: str = "low",
) -> list[EarlyWarning]:
    """
    ساخت هشدارهای زودهنگام از دادهٔ واقعی یک تایم‌فریم.

    پارامترها همه از ماژول‌های محاسباتی می‌آیند؛ این تابع هیچ چیز
    جدیدی «حدس» نمی‌زند، فقط قواعد ریسک را روی آن‌ها اعمال می‌کند.
    """
    warnings: list[EarlyWarning] = []

    # ---------- ۱) واگرایی مومنتوم ----------
    rsi_values = [v for v in rsi_series if v is not None and math.isfinite(v)]
    if len(rsi_values) >= 30 and len(closes) >= 30:
        price_change = closes[-1] / closes[-15] - 1.0 if closes[-15] > 0 else 0.0
        rsi_change = rsi_values[-1] - rsi_values[-15]
        if price_change > 0.01 and rsi_change < -5:
            warnings.append(
                EarlyWarning(
                    kind=WARNING_MOMENTUM_DIVERGENCE,
                    severity="warning",
                    confidence=70,
                    factors={
                        "price_change_percent": round(price_change * 100, 2),
                        "rsi_change": round(rsi_change, 1),
                        "rsi": round(rsi_values[-1], 1),
                    },
                    potential_event="trend_weakening",
                )
            )
        elif price_change < -0.01 and rsi_change > 5:
            warnings.append(
                EarlyWarning(
                    kind=WARNING_MOMENTUM_DIVERGENCE,
                    severity="info",
                    confidence=60,
                    factors={
                        "price_change_percent": round(price_change * 100, 2),
                        "rsi_change": round(rsi_change, 1),
                        "rsi": round(rsi_values[-1], 1),
                    },
                    potential_event="downtrend_weakening",
                )
            )

    # ---------- ۲) محوشدن حجم ----------
    if len(volume_series) >= 40:
        recent = sum(volume_series[-5:]) / 5.0
        before = sum(volume_series[-25:-5]) / 20.0
        if before > 0 and recent < before * 0.6 and abs(closes[-1] / closes[-10] - 1.0) > 0.005:
            warnings.append(
                EarlyWarning(
                    kind=WARNING_VOLUME_FADING,
                    severity="warning",
                    confidence=62,
                    factors={
                        "volume_ratio": round(recent / before, 2),
                        "move_percent": round((closes[-1] / closes[-10] - 1) * 100, 2),
                    },
                    potential_event="move_lacks_confirmation",
                )
            )

    # ---------- ۳) انبساط نوسان ----------
    if volatility_regime == "expansion":
        warnings.append(
            EarlyWarning(
                kind=WARNING_VOLATILITY_EXPANDING,
                severity="warning",
                confidence=58,
                factors={"volatility_regime": volatility_regime},
                potential_event="large_move_likely",
            )
        )

    # ---------- ۴) ریسک توزیع ----------
    if market_regime in ("distribution", "trend_reversal"):
        warnings.append(
            EarlyWarning(
                kind=WARNING_DISTRIBUTION_RISK,
                severity="high" if market_regime == "distribution" else "warning",
                confidence=55,
                factors={"market_regime": market_regime},
                potential_event="trend_exhaustion",
            )
        )

    # ---------- ۵) آنومالی ----------
    if anomaly_composite_z >= 3.0:
        warnings.append(
            EarlyWarning(
                kind=WARNING_ANOMALY,
                severity="warning",
                confidence=min(80, int(40 + anomaly_composite_z * 8)),
                factors={"composite_z": round(anomaly_composite_z, 2)},
                potential_event="unusual_market_activity",
            )
        )

    # ---------- ۶) گذار پرریسک رژیم ----------
    if transition_risk == "high":
        warnings.append(
            EarlyWarning(
                kind=WARNING_REGIME_SHIFT,
                severity="high",
                confidence=65,
                factors={"transition_risk": transition_risk},
                potential_event="structural_market_change",
            )
        )

    return warnings
