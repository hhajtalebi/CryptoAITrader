"""
هستهٔ روند اسکلپ — نردبان چندتایم‌فریمی (خواستهٔ §۴ تسک).

برای هر معامله:

    4H  → رژیم بازار      (از Prediction Engine — همان منبع واحد)
    1H  → روند اصلی       (از Prediction Engine)
    15m → ساختار          (از Prediction Engine)
    5m  → ستاپ            (از Prediction Engine)
    1m  → ورود            (از کندل ۱ دقیقه‌ای / تیک زنده)

قاعده: تضاد جدی یعنی ممنوع یا جریمهٔ اطمینان. اطمینان به تنهایی
هرگز دلیل ورود نیست — جهت باید با روند سازگار باشد.

این ماژول هیچ داده‌ای نمی‌سازد: هرچه برمی‌گرداند از گزارش واقعی
موتور پیش‌بینی یا کندل واقعی می‌آید؛ نبود داده صادقانه «نامعلوم»
است، نه حدس.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: تایم‌فریم‌های نردبان به ترتیب اهمیت (خواستهٔ §۴)
LADDER_TIMEFRAMES: tuple[str, ...] = ("4h", "1h", "15m", "5m")

#: وزن هر پله در امتیاز نردبان — تایم‌فریم بالاتر حرف اول را می‌زند
LADDER_WEIGHTS: dict[str, float] = {"4h": 4.0, "1h": 3.0, "15m": 2.0, "5m": 1.0, "1m": 0.5}


@dataclass
class LadderStep:
    """یک پلهٔ نردبان: جهت ۱=صعودی، ۱-=نزولی، ۰=خنثی، None=نامعلوم."""

    timeframe: str
    direction: int | None
    label: str = ""
    confidence: float = 0.0

    @property
    def known(self) -> bool:
        """آیا این پله اصلاً داده دارد؟"""
        return self.direction is not None


@dataclass
class TrendLadder:
    """نردبان کامل یک نماد + حکم تضاد."""

    symbol: str
    steps: dict[str, LadderStep] = field(default_factory=dict)

    def step(self, timeframe: str) -> LadderStep:
        """پلهٔ یک تایم‌فریم؛ نبود یعنی نامعلوم."""
        return self.steps.get(timeframe, LadderStep(timeframe, None))

    @property
    def regime_4h(self) -> LadderStep:
        """رژیم بازار (4H)."""
        return self.step("4h")

    @property
    def main_trend_1h(self) -> LadderStep:
        """روند اصلی (1H)."""
        return self.step("1h")

    @property
    def known_steps(self) -> list[LadderStep]:
        """پله‌هایی که داده دارند."""
        return [s for s in (self.step(tf) for tf in LADDER_TIMEFRAMES) if s.known]

    @property
    def weighted_direction(self) -> float:
        """
        جهت وزنی نردبان بین ۱- و ۱+.

        پله‌های نامعلوم وزنشان از صورت کسر حذف می‌شود؛ نردبانِ بی‌داده
        عدد صفرِ تصادفی نمی‌دهد بلکه `has_data=False` می‌شود.
        """
        total_weight = 0.0
        weighted = 0.0
        for timeframe, weight in LADDER_WEIGHTS.items():
            step = self.step(timeframe)
            if step.known:
                total_weight += weight
                weighted += (step.direction or 0) * weight
        if total_weight <= 0:
            return 0.0
        return weighted / total_weight

    @property
    def has_data(self) -> bool:
        """آیا اصلاً پله‌ای با داده داریم؟"""
        return bool(self.known_steps)

    def conflict_with(self, direction: str) -> list[str]:
        """
        تضادهای این جهت با نردبان — هر تضاد یک رشتهٔ «tf: جهت‌مخالف».

        تضاد «جدی» فقط با پله‌های ساختاردهنده (4H/1H) است؛ اختلاف ۵m
        با ۱m طبیعی است و تضاد شمرده نمی‌شود.
        """
        wanted = 1 if str(direction).upper() == "LONG" else -1
        clashes: list[str] = []
        for timeframe in ("4h", "1h"):
            step = self.step(timeframe)
            if step.known and (step.direction or 0) != 0 and (step.direction or 0) != wanted:
                clashes.append(timeframe)
        return clashes

    def minor_friction(self, direction: str) -> bool:
        """اختلاف جزئی پله‌های پایین (15m/5m) با جهت — جریمه، نه منع."""
        wanted = 1 if str(direction).upper() == "LONG" else -1
        for timeframe in ("15m", "5m"):
            step = self.step(timeframe)
            if step.known and (step.direction or 0) != 0 and (step.direction or 0) != wanted:
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """نمای UI/گزارش."""
        return {
            "symbol": self.symbol,
            "steps": {
                tf: {
                    "direction": step.direction,
                    "label": step.label,
                    "confidence": step.confidence,
                }
                for tf, step in self.steps.items()
            },
            "weighted_direction": round(self.weighted_direction, 3),
            "has_data": self.has_data,
        }


def step_from_regime(timeframe: str, regime: dict[str, Any] | None) -> LadderStep:
    """
    ساخت پله از رکورد رژیم موتور پیش‌بینی.

    رکورد رژیم خودش `direction` (±۱/۰) دارد؛ اگر نبود از نام رژیم
    استنتاج می‌شود (strong_trend_up → +۱ و …).
    """
    if not isinstance(regime, dict):
        return LadderStep(timeframe, None)
    raw = regime.get("direction")
    if raw in (1, -1, 0):
        direction: int | None = int(raw)
    else:
        direction = _direction_from_name(str(regime.get("regime", "")))
    return LadderStep(
        timeframe=timeframe,
        direction=direction,
        label=str(regime.get("regime", "")),
        confidence=float(regime.get("confidence", 0.0) or 0.0),
    )


def _direction_from_name(name: str) -> int | None:
    """استنتاج جهت از نام رژیم — فقط برای دادهٔ قدیمی بدون direction."""
    value = str(name or "").lower()
    if not value:
        return None
    if "down" in value or "breakdown" in value or "reversal" in value:
        return -1
    if "up" in value:
        return 1
    return 0


def build_ladder(
    symbol: str,
    *,
    regimes: dict[str, Any] | None,
    candles_1m: list[Any] | None = None,
    tick_history: list[tuple[float, float]] | None = None,
) -> TrendLadder:
    """
    ساخت نردبان از دادهٔ واقعی.

    regimes: خروجی `report["regimes"]` موتور پیش‌بینی — نگاشت
    تایم‌فریم → {regime, direction, confidence}.

    candles_1m: کندل‌های ۱ دقیقه‌ای اخیر برای پلهٔ ورود؛ جهت از مقایسهٔ
    قیمت آخر با میانگین متحرک کوتاهِ ساده می‌آید (EMA بدون کتابخانه).

    tick_history: تاریخچهٔ (ts, price) تیک — جایگزین کندل ۱m وقتی
    کندل در دسترس نیست.
    """
    ladder = TrendLadder(symbol=str(symbol or "").upper())
    for timeframe in LADDER_TIMEFRAMES:
        ladder.steps[timeframe] = step_from_regime(timeframe, (regimes or {}).get(timeframe))

    ladder.steps["1m"] = LadderStep("1m", _direction_from_1m(candles_1m, tick_history))
    return ladder


def _direction_from_1m(
    candles_1m: list[Any] | None,
    tick_history: list[tuple[float, float]] | None,
) -> int | None:
    """
    جهت ورود از دادهٔ ۱ دقیقه‌ای یا تیک.

    منطق ساده و شفاف: قیمت آخر نسبت به میانگین ۲۰ نقطهٔ قبل.
    دادهٔ کمتر از ۵ نقطه یعنی «نامعلوم» — حدس زده نمی‌شود.
    """
    prices: list[float] = []
    if candles_1m:
        prices = [float(getattr(c, "close", 0.0) or 0.0) for c in candles_1m]
        prices = [p for p in prices if p > 0]
    if len(prices) < 5 and tick_history:
        prices = [p for _, p in tick_history if p > 0]
    if len(prices) < 5:
        return None
    window = prices[-20:]
    average = sum(window) / len(window)
    last = prices[-1]
    if last > average * 1.0002:
        return 1
    if last < average * 0.9998:
        return -1
    return 0


def conflict_verdict(
    ladder: TrendLadder,
    direction: str,
    *,
    policy: str = "block",
) -> tuple[str, str]:
    """
    حکم تضاد روند برای یک جهت.

    بازگشتی: ("ok" | "penalty" | "block", دلیل)

    policy:
        block   → تضاد 4H/1H ورود را ممنوع می‌کند (پیش‌فرض تسک)
        penalize → تضاد فقط اطمینان را می‌کاهد
    """
    clashes = ladder.conflict_with(direction)
    if clashes:
        reason = "trend_conflict:" + ",".join(clashes)
        return ("block" if policy != "penalize" else "penalty"), reason
    if ladder.minor_friction(direction):
        return "penalty", "minor_friction"
    return "ok", ""


__all__ = [
    "LADDER_TIMEFRAMES",
    "LADDER_WEIGHTS",
    "LadderStep",
    "TrendLadder",
    "build_ladder",
    "conflict_verdict",
    "step_from_regime",
]
