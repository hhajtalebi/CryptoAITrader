"""
موتور احتمال شکست و شکستِ کاذب — خواسته‌های ۹ و ۱۰.

چرا این فایل وجود دارد؟
    «مقاومت ۱۱۴,۲۰۰» به‌تنهایی تصمیم‌ساز نیست؛ معامله‌گر باید بداند
    احتمال عبور چقدر است و — مهم‌تر — احتمال اینکه عبور «کاذب» باشد.
    این ماژول از سطوحِ واقعی `find_support_resistance` موجود شروع
    می‌کند و احتمال‌ها را از فاصلهٔ نسبت به نوسان، مومنتوم و حجم
    می‌سازد.

صداقت عوامل:
    کاربر هشت عامل خواسته (Volume، Order Flow، OI، Funding،
    Liquidation، Momentum، Volatility، Historical Reaction). ما فقط
    عواملی را می‌سنجیم که داده‌شان موجود است (حجم، مومنتوم، نوسان،
    فاصله). عوامل بدون منبع داده صریحاً «unavailable» برچسب می‌خورند —
    هرگز عدد fabricated نمی‌گیرند.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models import Candle
from app.logging import get_logger
from indicators.support_resistance import find_support_resistance

logger = get_logger(__name__)


@dataclass(slots=True)
class BreakoutAssessment:
    """ارزیابی شکست نزدیک‌ترین سطح معنادار."""

    level_price: float
    level_kind: str            # support | resistance
    distance_atr: float        # فاصلهٔ قیمت تا سطح بر حسب ATR
    breakout_probability: int  # احتمال عبور موفق
    false_breakout_probability: int
    breakdown_probability: int
    factors: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "level_price": round(self.level_price, 8),
            "level_kind": self.level_kind,
            "distance_atr": round(self.distance_atr, 2),
            "breakout_probability": self.breakout_probability,
            "false_breakout_probability": self.false_breakout_probability,
            "breakdown_probability": self.breakdown_probability,
            "factors": dict(self.factors),
            "note": self.note,
        }


def _atr(candles: list[Candle], period: int = 14) -> float:
    """ATR محلی — مستقل از موتور اندیکاتور تا این ماژول سبز بماند."""
    if len(candles) < 2:
        return 0.0
    ranges = [
        max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        for previous, current in zip(candles[:-1], candles[1:], strict=False)
    ]
    window = ranges[-period:]
    return sum(window) / len(window) if window else 0.0


def assess_breakout(candles: list[Candle]) -> BreakoutAssessment | None:
    """
    ارزیابی شکست نزدیک‌ترین سطح به قیمت فعلی.

    بازگشتی: None اگر سطح یا دادهٔ کافی نباشد — بدون عددسازی.
    """
    if len(candles) < 60:
        return None

    price = float(candles[-1].close)
    atr = _atr(candles)
    if atr <= 0 or price <= 0:
        return None

    levels = find_support_resistance(candles, max_levels=8)
    if not levels:
        return None

    # نزدیک‌ترین سطح «معنادار» (major اگر بود وگرنه نزدیک‌ترین)
    majors = [lvl for lvl in levels if lvl.strength == "major"]
    pool = majors or levels
    level = min(pool, key=lambda lvl: abs(lvl.price - price))
    distance_atr = (level.price - price) / atr

    # ---------- عوامل واقعی ----------
    volume_mean = sum(c.volume for c in candles[-20:]) / 20.0
    recent_volume = sum(c.volume for c in candles[-3:]) / 3.0
    volume_ratio = recent_volume / volume_mean if volume_mean > 0 else 1.0

    closes = [c.close for c in candles]
    ema = _ema(closes, 20)
    momentum = 0.0
    if ema and atr > 0:
        momentum = (price - ema) / atr

    # فاصلهٔ زیاد = عبور بعید؛ مومنتوم و حجم هم‌جهت = محتمل‌تر
    proximity = max(0.0, 1.0 - abs(distance_atr) / 3.0)  # ۱=چسبیده، ۰=دور
    directional_push = max(0.0, min(1.0, 0.5 + momentum / 4.0)) if distance_atr > 0 else max(
        0.0, min(1.0, 0.5 - momentum / 4.0)
    )
    volume_push = max(0.0, min(1.0, (volume_ratio - 0.5) / 1.5))

    base = 40.0
    breakout_probability = base + 20.0 * proximity + 15.0 * directional_push + 10.0 * volume_push
    breakout_probability = max(10.0, min(85.0, breakout_probability))

    # شکست کاذب: عبورِ بدون حجم — عامل اصلیِ قابل‌اندازه‌گیری
    false_probability = 45.0 - 25.0 * volume_push - 10.0 * directional_push
    false_probability = max(5.0, min(60.0, false_probability))

    breakdown_probability = max(
        5.0, min(80.0, 100.0 - breakout_probability - false_probability * 0.6)
    )

    # نرمال‌سازی سه‌تایی به ۱۰۰
    total = breakout_probability + false_probability + breakdown_probability
    breakout_probability = int(round(breakout_probability / total * 100))
    false_probability = int(round(false_probability / total * 100))
    breakdown_probability = 100 - breakout_probability - false_probability

    return BreakoutAssessment(
        level_price=level.price,
        level_kind=level.kind,
        distance_atr=distance_atr,
        breakout_probability=breakout_probability,
        false_breakout_probability=false_probability,
        breakdown_probability=breakdown_probability,
        factors={
            "volume_ratio": round(volume_ratio, 2),
            "momentum_atr": round(momentum, 2),
            "proximity": round(proximity, 2),
            "order_flow": "unavailable",
            "open_interest": "unavailable",
            "funding": "unavailable",
            "historical_reaction": "unavailable",
        },
        note=(
            "Only factors with real data are measured; derivative factors "
            "are marked unavailable and never guessed."
        ),
    )


def detect_false_breakout(candles: list[Candle], *, lookback: int = 6) -> dict[str, Any] | None:
    """
    تشخیص شکست کاذب — خواستهٔ ۱۰.

    منطق: اگر قیمت در چند کندل اخیر از سقف/کفِ قبلی عبور کرده ولی
    حجم ضعیف و مومنتوم در حال افت باشد، احتمال کاذب‌بودن بالا می‌رود.
    عوامل OI/CVD/Whale که داده‌شان نیست صریحاً unavailable می‌مانند.
    """
    if len(candles) < 60:
        return None

    recent = candles[-lookback:]
    before = candles[-(lookback + 20):-lookback]
    if not before:
        return None

    prior_high = max(c.high for c in before)
    prior_low = min(c.low for c in before)
    price = float(candles[-1].close)

    broke_up = any(c.close > prior_high for c in recent)
    broke_down = any(c.close < prior_low for c in recent)
    if not (broke_up or broke_down):
        return None

    volume_mean = sum(c.volume for c in before) / len(before)
    recent_volume = sum(c.volume for c in recent) / len(recent)
    volume_ratio = recent_volume / volume_mean if volume_mean > 0 else 1.0

    closes = [c.close for c in candles]
    ema = _ema(closes, 20)
    atr = _atr(candles)
    momentum = (price - ema) / atr if ema and atr > 0 else 0.0

    # عبول + حجم ضعیف + مومنتوم مخالف/افت‌کرده = شکست کاذب محتمل
    side = "up" if broke_up else "down"
    expected_momentum = 1.0 if broke_up else -1.0
    momentum_fading = momentum * expected_momentum < 0.3
    weak_volume = volume_ratio < 0.85

    confidence = 30.0
    if weak_volume:
        confidence += 30.0
    if momentum_fading:
        confidence += 25.0
    if volume_ratio < 0.6:
        confidence += 15.0
    confidence = int(round(max(20.0, min(85.0, confidence))))

    result = {
        "side": side,
        "confidence": confidence,
        "is_suspected": confidence >= 60,
        "factors": {
            "volume_ratio": round(volume_ratio, 2),
            "momentum_atr": round(momentum, 2),
            "cvd": "unavailable",
            "open_interest": "unavailable",
            "whale_flow": "unavailable",
        },
        "move_percent": round((price / closes[-lookback] - 1) * 100, 2),
        "note": "Suspected false breakout — potential risk, not a certainty.",
    }
    return result


def _ema(values: list[float], period: int) -> float | None:
    """آخرین مقدار EMA؛ داده کم = None."""
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = alpha * value + (1 - alpha) * result
    return result
