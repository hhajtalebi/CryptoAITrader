"""
موتور رژیم بازار (Market Regime Engine) — فاز ۳.

چرا این فایل وجود دارد؟
    «جهت بازار» به‌تنهایی برای تصمیم کافی نیست؛ یک سیگنال صعودی در
    رژیم «رِنج» معنای دیگری دارد با همان سیگنال در «روند قوی». کاربر
    ۱۴ رژیم خواسته و تأکید کرده تشخیص باید **به ازای هر تایم‌فریم**
    جداگانه انجام شود، گذار رژیم‌ها شناسایی شود و بازار در یک ماشین
    حالت قرار بگیرد.

روش — قاعده‌محورِ قابل توضیح، نه جعبه سیاه:
    از فیچرهای محاسبه‌شدهٔ `features.py` (ADX، ATR٪، پهنای بولینگر،
    فاصلهٔ EMA، RSI، روند حجم) + موقعیت قیمت در کانال دانچین، یک نردبان
    تصمیم صریح اجرا می‌شود. هر رژیم «درایورهای»ش را برمی‌گرداند تا
    هم برای LLM توضیح‌پذیر باشد و هم در آزمون‌ها قابل اثبات.

صداقت داده:
    رژیم `LIQUIDATION_EVENT` فقط با ورودیِ دادهٔ لیکوییداسیون واقعی
    برمی‌گردد (پارامتر `liquidation_pressure`)؛ از کندل قیمت حدس زده
    نمی‌شود.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.models import Candle
from app.logging import get_logger

logger = get_logger(__name__)


class Regime(str, Enum):
    """۱۴ رژیم بازار خواسته‌شده — مقادیر پایدار برای DB و API."""

    STRONG_TREND_UP = "strong_trend_up"
    STRONG_TREND_DOWN = "strong_trend_down"
    WEAK_TREND = "weak_trend"
    RANGE = "range"
    ACCUMULATION = "accumulation"
    DISTRIBUTION_TOP = "distribution"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    COMPRESSION = "compression"
    EXPANSION = "expansion"
    TREND_REVERSAL = "trend_reversal"
    LIQUIDATION_EVENT = "liquidation_event"
    UNKNOWN = "unknown"


#: جهت غالب هر رژیم برای موتور فیوژن: +1 صعودی، -1 نزولی، 0 خنثی.
REGIME_TILT: dict[Regime, int] = {
    Regime.STRONG_TREND_UP: 1,
    Regime.WEAK_TREND: 0,     # جهتش را درایورها تعیین می‌کند
    Regime.STRONG_TREND_DOWN: -1,
    Regime.RANGE: 0,
    Regime.ACCUMULATION: 1,
    Regime.DISTRIBUTION_TOP: -1,
    Regime.BREAKOUT: 1,
    Regime.BREAKDOWN: -1,
    Regime.HIGH_VOLATILITY: 0,
    Regime.LOW_VOLATILITY: 0,
    Regime.COMPRESSION: 0,
    Regime.EXPANSION: 0,
    Regime.TREND_REVERSAL: 0,
    Regime.LIQUIDATION_EVENT: 0,
    Regime.UNKNOWN: 0,
}


@dataclass(slots=True)
class RegimeAssessment:
    """ارزیابی رژیم یک تایم‌فریم."""

    timeframe: str
    regime: Regime = Regime.UNKNOWN
    confidence: int = 0
    drivers: dict[str, Any] = field(default_factory=dict)
    direction: int = 0  # +1/-1/0 جهت ملموس برای فیوژن

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری برای گزارش/UI/عامل."""
        return {
            "timeframe": self.timeframe,
            "regime": self.regime.value,
            "confidence": self.confidence,
            "direction": self.direction,
            "drivers": dict(self.drivers),
        }


def _percentile_of_latest(series: list[float | None]) -> float:
    """
    صدکِ آخرین مقدار در تاریخ خودِ سری (۰ تا ۱۰۰).

    چرا صدک نسبت به خود سری؟ چون «پهنای بولینگرِ ۲٪» برای بیت‌کوین
    فشرده است و برای یک آلت‌کوین کوچک گسترده؛ مقایسهٔ مطلق بی‌معناست.
    """
    values = [v for v in series if v is not None and math.isfinite(v)]
    if len(values) < 20:
        return 50.0
    latest = values[-1]
    below = sum(1 for v in values[:-1] if v <= latest)
    return below / (len(values) - 1) * 100.0


def _donchian_position(candles: list[Candle], window: int = 20) -> float:
    """موقعیت آخرین بسته‌شده در کانال دانچین: ۰ کف، ۱ سقف."""
    closed = candles[-window:]
    if len(closed) < 5:
        return 0.5
    high = max(c.high for c in closed)
    low = min(c.low for c in closed)
    if high <= low:
        return 0.5
    return (closed[-1].close - low) / (high - low)


def _last(series: list[float | None], default: float = 0.0) -> float:
    """آخرین مقدار معتبر سری یا پیش‌فرض."""
    for value in reversed(series):
        if value is not None and math.isfinite(value):
            return float(value)
    return default


def _series_from_features(features: Any, name: str) -> list[float | None]:
    """ستون فیچر به‌صورت سری؛ نبودِ فیچر = لیست خالی."""
    if features is None:
        return []
    return [vector.get(name) for vector in getattr(features, "vectors", [])]


def classify_timeframe(
    timeframe: str,
    candles: list[Candle],
    features: Any,
    *,
    liquidation_pressure: float = 0.0,
) -> RegimeAssessment:
    """
    تشخیص رژیم یک تایم‌فریم.

    پارامترها:
        timeframe            : کد تایم‌فریم (فقط برای گزارش).
        candles              : کندل‌های بسته‌شدهٔ همان تایم‌فریم.
        features             : خروجی FeatureStore همان تایم‌فریم.
        liquidation_pressure : حجم لیکوییداسیون نرمال‌شده (۰..۱) اگر
                               منبع داده باشد؛ بدون آن هرگز حدس زده
                               نمی‌شود.

    بازگشتی: RegimeAssessment با رژیم، اطمینان، جهت و درایورها.
    """
    adx = _last(_series_from_features(features, "adx"))
    rsi = _last(_series_from_features(features, "rsi"), 50.0)
    atr_percentile = _percentile_of_latest(_series_from_features(features, "atr_percent"))
    bb_percentile = _percentile_of_latest(_series_from_features(features, "bollinger_width"))
    ema_distance = _last(_series_from_features(features, "ema_distance"))
    macd_hist = _last(_series_from_features(features, "macd_histogram"))
    volume_changes = _series_from_features(features, "volume_change")
    volume_trend = sum(
        v for v in volume_changes[-10:] if v is not None and math.isfinite(v)
    ) / 10.0 if len(volume_changes) >= 10 else 0.0

    position = _donchian_position(candles)
    assessment = RegimeAssessment(timeframe=timeframe)
    assessment.drivers = {
        "adx": round(adx, 1),
        "rsi": round(rsi, 1),
        "atr_percentile": round(atr_percentile, 1),
        "bb_width_percentile": round(bb_percentile, 1),
        "ema_distance_atr": round(ema_distance, 2),
        "donchian_position": round(position, 2),
        "volume_trend": round(volume_trend, 3),
    }

    if len(candles) < 60 or not features or len(features) < 40 or adx <= 0:
        assessment.regime = Regime.UNKNOWN
        assessment.confidence = 20
        assessment.drivers["reason"] = "insufficient_data"
        return assessment

    # ---------- نردبان تصمیم (ترتیب مهم است) ----------
    # ۱) رویداد لیکوییداسیون فقط با دادهٔ واقعی
    if liquidation_pressure >= 0.8:
        assessment.regime = Regime.LIQUIDATION_EVENT
        assessment.confidence = 70
        assessment.drivers["liquidation_pressure"] = round(liquidation_pressure, 2)
        return assessment

    trending_up = ema_distance > 0.5 and macd_hist > 0
    trending_down = ema_distance < -0.5 and macd_hist < 0
    strong = adx >= 25
    weak = 18 <= adx < 25

    # ۲) شکست/فروپاشی کانال با تایید حجم
    if position >= 0.98 and volume_trend > 0.15:
        assessment.regime = Regime.BREAKOUT
        assessment.confidence = 60
    elif position <= 0.02 and volume_trend > 0.15:
        assessment.regime = Regime.BREAKDOWN
        assessment.confidence = 60
    # ۳) روند قوی
    elif strong and trending_up:
        assessment.regime = Regime.STRONG_TREND_UP
        assessment.confidence = min(85, 55 + int(adx))
    elif strong and trending_down:
        assessment.regime = Regime.STRONG_TREND_DOWN
        assessment.confidence = min(85, 55 + int(adx))
    # ۴) واژگونی روند: روندِ قویِ مخالف شتاب
    elif strong and ((ema_distance > 0.5 and macd_hist < 0) or (ema_distance < -0.5 and macd_hist > 0)):
        assessment.regime = Regime.TREND_REVERSAL
        assessment.confidence = 55
    # ۵) انبساط/انقباض نوسان — ویژهٔ خواسته‌های ۱۲ و ۵
    elif bb_percentile >= 85 and atr_percentile >= 80:
        assessment.regime = Regime.EXPANSION
        assessment.confidence = 60
    elif bb_percentile <= 15 and atr_percentile <= 20:
        assessment.regime = Regime.COMPRESSION
        assessment.confidence = 60
    # ۶) نوسان بسیار بالا/پایین به‌تنهایی
    elif atr_percentile >= 90:
        assessment.regime = Regime.HIGH_VOLATILITY
        assessment.confidence = 55
    elif atr_percentile <= 10:
        assessment.regime = Regime.LOW_VOLATILITY
        assessment.confidence = 50
    # ۷) روند ضعیف
    elif weak and abs(ema_distance) > 0.3:
        assessment.regime = Regime.WEAK_TREND
        assessment.confidence = 45
    # ۸) تجمیع/توزیع در رِنج — بر پایهٔ جهت بلندمدت‌ترِ خودِ سری
    elif adx < 18:
        # جهت زمینه از مجموع فاصلهٔ EMAهای اخیر
        context = sum(
            v for v in _series_from_features(features, "ema_distance")[-40:]
            if v is not None and math.isfinite(v)
        )
        if context < -2.0 and position < 0.45 and volume_trend <= 0:
            assessment.regime = Regime.ACCUMULATION
            assessment.confidence = 45
        elif context > 2.0 and position > 0.55 and volume_trend <= 0:
            assessment.regime = Regime.DISTRIBUTION_TOP
            assessment.confidence = 45
        else:
            assessment.regime = Regime.RANGE
            assessment.confidence = 40
    else:
        assessment.regime = Regime.RANGE
        assessment.confidence = 35

    # جهت ملموس برای فیوژن
    if assessment.regime in (Regime.STRONG_TREND_UP, Regime.BREAKOUT, Regime.ACCUMULATION):
        assessment.direction = 1
    elif assessment.regime in (Regime.STRONG_TREND_DOWN, Regime.BREAKDOWN, Regime.DISTRIBUTION_TOP):
        assessment.direction = -1
    elif assessment.regime is Regime.WEAK_TREND:
        assessment.direction = 1 if ema_distance > 0 else -1
    elif assessment.regime is Regime.TREND_REVERSAL:
        # جهت مخالف روندِ موجود
        assessment.direction = -1 if ema_distance > 0 else 1
    return assessment


# ---------------------------------------------------------------------------
# گذار رژیم و ماشین حالت
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class RegimeTransition:
    """گذار از رژیم قبلی به فعلی."""

    previous: Regime
    current: Regime
    confidence: int = 0
    risk_level: str = "low"  # low | medium | high

    @property
    def changed(self) -> bool:
        """آیا گذار واقعاً رخ داده است؟"""
        return self.previous is not self.current

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "previous": self.previous.value,
            "current": self.current.value,
            "changed": self.changed,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
        }


def detect_transition(
    previous: RegimeAssessment | None,
    current: RegimeAssessment,
) -> RegimeTransition:
    """
    تشخیص گذار رژیم — خواستهٔ ۶.

    اطمینان گذار از میانگین اطمینان دو ارزیابی می‌آید؛ گذار به رژیم‌های
    «ساختاری» (شکست/فروپاشی/توزیع/واژگونی) ریسک بالا دارد چون معمولاً
    آغاز حرکت‌های بزرگ‌اند.
    """
    if previous is None or previous.regime is Regime.UNKNOWN:
        return RegimeTransition(Regime.UNKNOWN, current.regime, 0, "low")

    confidence = (previous.confidence + current.confidence) // 2
    risky = {
        Regime.BREAKDOWN,
        Regime.DISTRIBUTION_TOP,
        Regime.TREND_REVERSAL,
        Regime.LIQUIDATION_EVENT,
        Regime.BREAKOUT,
    }
    risk = "high" if current.regime in risky else ("medium" if previous.regime in risky else "low")
    return RegimeTransition(previous.regime, current.regime, confidence, risk)


#: مراحل چرخهٔ عمر بازار — خواستهٔ ۷ (ماشین حالت).
MARKET_STAGES: tuple[str, ...] = (
    "ACCUMULATION",
    "EXPANSION",
    "TREND",
    "EXHAUSTION",
    "DISTRIBUTION",
    "BREAKDOWN",
)

#: نگاشت رژیم → مرحلهٔ ماشین حالت.
_STAGE_OF: dict[Regime, str] = {
    Regime.ACCUMULATION: "ACCUMULATION",
    Regime.COMPRESSION: "ACCUMULATION",
    Regime.EXPANSION: "EXPANSION",
    Regime.BREAKOUT: "EXPANSION",
    Regime.STRONG_TREND_UP: "TREND",
    Regime.STRONG_TREND_DOWN: "TREND",
    Regime.WEAK_TREND: "TREND",
    Regime.HIGH_VOLATILITY: "EXHAUSTION",
    Regime.TREND_REVERSAL: "EXHAUSTION",
    Regime.DISTRIBUTION_TOP: "DISTRIBUTION",
    Regime.RANGE: "DISTRIBUTION",
    Regime.BREAKDOWN: "BREAKDOWN",
    Regime.LOW_VOLATILITY: "ACCUMULATION",
    Regime.LIQUIDATION_EVENT: "BREAKDOWN",
    Regime.UNKNOWN: "ACCUMULATION",
}


def stage_of(regime: Regime) -> str:
    """مرحلهٔ ماشین حالت متناظر با رژیم."""
    return _STAGE_OF.get(regime, "ACCUMULATION")


def transition_probabilities(history: list[Regime]) -> dict[str, dict[str, float]]:
    """
    احتمال گذار مرحله‌ها از تاریخچه — از داده، نه حدس.

    ورودی توالی رژیم‌های متوالی (قدیم → جدید) است؛ مراحل متناظر شمرده
    می‌شوند. با تاریخچهٔ کوتاه، هر برآورد صریحاً «نمونهٔ کم» برچسب
    می‌خورد تا مصرف‌کننده بداند روی چه پایه‌ای است.
    """
    counts: dict[str, dict[str, int]] = {stage: {} for stage in MARKET_STAGES}
    for previous, current in zip(history[:-1], history[1:], strict=False):
        if previous is Regime.UNKNOWN or current is Regime.UNKNOWN:
            continue
        source = stage_of(previous)
        target = stage_of(current)
        counts[source][target] = counts[source].get(target, 0) + 1

    probabilities: dict[str, dict[str, float]] = {}
    for stage, targets in counts.items():
        total = sum(targets.values())
        if total == 0:
            continue
        probabilities[stage] = {
            target: round(count / total * 100, 1)
            for target, count in sorted(targets.items(), key=lambda kv: -kv[1])
        }
        probabilities[stage]["_samples"] = total  # type: ignore[assignment]
    return probabilities
