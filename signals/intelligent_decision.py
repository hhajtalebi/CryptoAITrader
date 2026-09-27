"""
لایهٔ تصمیم هوشمند — نسخهٔ ۲.۵.۵.

خط لوله:
    Base Signal (موتور سیگنال + ۷ راهبرد، بدون تغییر)
        → Intelligent Analysis (پیش‌بینی + چندتایم‌فریم + رژیم + بافت بازار)
        → Enhancement (همین ماژول)
        → Final Signal

اصل طراحی: **شواهد وزن‌دار، نه آستانه‌های سخت پشت‌سرهم.**
هر مؤلفه یک امتیاز s ∈ [-1, +1] «نسبت به جهت سیگنال پایه» می‌دهد
(+1 یعنی کاملاً تأیید، -1 یعنی کاملاً مخالف) و یک اعتبار r ∈ [0, 1]
(چقدر به این شاهد اعتماد داریم؛ دادهٔ غایب → r = 0 و بی‌اثر).

    ratio    = Σ w·s·r / Σ w·r                       ∈ [-1, 1]
    coverage = min(1, Σ w·r / coverage_norm)          (شواهد کم → اثر کم)
    adjust   = ratio × coverage × (bonus اگر مثبت، penalty اگر منفی)
    final    = clamp(technical + adjust, 0, 100)

کیفیت:
    STRONG  final ≥ 70، ratio ≥ 0.25 و بدون تعارض شدید  → اندازه ×1.00
    WEAK    final < 55 یا ratio < -0.10 یا ≥2 تعارض عمده  → اندازه ×0.50
    NORMAL  بقیه                                          → اندازه ×0.75

NO_TRADE فقط در تعارض شدید: دست‌کم ۳ عامل مستقل از {پیش‌بینی، تایم‌فریم
بالاتر، رژیم، سابقه} به‌شدت مخالف باشند **و** ratio ≤ -0.45. شواهد متوسط
هرگز سیگنال را حذف نمی‌کنند؛ فقط اطمینان و اندازهٔ پوزیشن را کم می‌کنند.

خروجی‌های جدا (خواستهٔ کاربر):
    technical_confidence, prediction_probability, mtf_alignment,
    regime_score, historical_edge, execution_quality, final_confidence.

هیچ تضمینی برای سود یا دقت وجود ندارد؛ این لایه فقط شواهد موجود را
شفاف و قابل‌سنجش جمع می‌کند.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from app.core.constants import MarketStructureType, SignalDirection, TrendDirection

#: وزن تایم‌فریم‌ها (هم‌سان با signals.engine؛ اینجا تکرار شده تا وابستگی
#: چرخه‌ای ایجاد نشود).
_TF_WEIGHTS: dict[str, float] = {
    "1m": 0.3, "3m": 0.4, "5m": 0.5, "15m": 0.7, "30m": 0.8,
    "1h": 1.0, "2h": 1.1, "4h": 1.3, "6h": 1.4, "8h": 1.45,
    "12h": 1.5, "1d": 1.8, "1w": 2.0,
}
_TF_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
    "4h": 240, "6h": 360, "8h": 480, "12h": 720, "1d": 1440, "1w": 10080,
}

QUALITY_STRONG = "STRONG"
QUALITY_NORMAL = "NORMAL"
QUALITY_WEAK = "WEAK"
DECISION_TRADE = "TRADE"
DECISION_NO_TRADE = "NO_TRADE"
DECISION_WAIT = "WAIT"

#: عواملی که در شمارش «تعارض شدید» برای NO_TRADE حساب می‌شوند
SEVERE_FACTORS: tuple[str, ...] = ("prediction", "mtf", "regime", "history")


@dataclass(slots=True, frozen=True)
class DecisionConfig:
    """پارامترهای قابل‌تنظیم (walk-forward فقط روی train/validation تنظیمشان می‌کند)."""

    weights: dict[str, float] = field(default_factory=lambda: {
        "trend": 18.0, "momentum": 14.0, "prediction": 16.0, "mtf": 12.0,
        "volume": 8.0, "regime": 8.0, "structure": 12.0, "orderflow": 6.0,
        "btc": 6.0, "history": 10.0, "execution": 6.0,
    })
    bonus: float = 14.0
    penalty: float = 20.0
    coverage_norm: float = 40.0
    strong_final: int = 70
    strong_ratio: float = 0.25
    weak_final: int = 55
    weak_ratio: float = -0.10
    no_trade_ratio: float = -0.45
    no_trade_min_opposing: int = 3
    strong_opposition: float = -0.5
    size_strong: float = 1.0
    size_normal: float = 0.75
    size_weak: float = 0.5
    #: برای تایم‌فریم اصلی ≤ ۱۵ دقیقه، وزن تایم‌فریم‌های بالاتر نصف می‌شود
    short_primary_htf_factor: float = 0.5
    #: نسخهٔ ۲.۵.۶ — «اشباع/فرسودگی»: بالاتر از این اطمینان فنی، توافق کامل
    #: استراتژی‌های روند عمدتاً یعنی ورود دیرهنگام پس از حرکت کشیده. در
    #: بک‌تست هر دو دوره (۲۰۱۸ و ۲۰۲۵) اطمینان فنی ≥۷۰ فقط ۲۷–۲۹٪ درست بود
    #: در برابر ۴۶–۵۷٪ برای ۵۰–۶۹. پایهٔ اطمینان نهایی بالاتر از این مقدار
    #: بازتاب می‌شود و شاهد «exhaustion» اضافه می‌شود. ۰ = غیرفعال.
    saturation_start: int = 68
    saturation_span: float = 15.0
    exhaustion_weight: float = 10.0

    def with_overrides(self, **overrides: Any) -> DecisionConfig:
        """نسخهٔ جدید با مقادیر جایگزین (برای جست‌وجوی walk-forward)."""
        return replace(self, **overrides)

    def to_dict(self) -> dict[str, Any]:
        """نمایش قابل ذخیره."""
        return asdict(self)


@dataclass(slots=True)
class EvidenceComponent:
    """یک شاهد: امتیاز نسبت به جهت سیگنال، اعتبار و وزن."""

    name: str
    score: float
    reliability: float
    weight: float
    detail: str = ""

    @property
    def available(self) -> bool:
        return self.reliability > 0 and self.weight > 0

    @property
    def contribution(self) -> float:
        return self.weight * self.score * self.reliability

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 3),
            "reliability": round(self.reliability, 3),
            "weight": round(self.weight, 2),
            "contribution": round(self.contribution, 3),
            "available": self.available,
            "detail": self.detail,
        }


@dataclass(slots=True)
class DecisionInputs:
    """همهٔ داده‌هایی که لایهٔ هوشمند می‌بیند (همه اختیاری جز جهت/اطمینان)."""

    symbol: str
    direction: SignalDirection
    technical_confidence: int
    primary_timeframe: str = ""
    total_score: float = 0.0
    analyses: dict[str, dict[str, Any]] = field(default_factory=dict)
    votes_by_timeframe: dict[str, list[Any]] = field(default_factory=dict)
    risk_reward: float | None = None
    prediction: dict[str, Any] | None = None
    regime: dict[str, Any] | None = None
    btc: dict[str, Any] | None = None
    orderflow: Any = None
    execution: dict[str, Any] | None = None
    history: dict[str, Any] | None = None


@dataclass(slots=True)
class IntelligentDecision:
    """خروجی نهایی لایهٔ هوشمند."""

    symbol: str
    base_direction: str
    direction: str
    decision: str
    quality: str
    technical_confidence: int
    final_confidence: int
    prediction_probability: int | None
    prediction_direction: str
    mtf_alignment: int | None
    regime: str
    regime_score: int | None
    historical_edge: int
    historical_samples: int
    execution_quality: int | None
    evidence_ratio: float
    coverage: float
    size_multiplier: float
    primary_timeframe: str = ""
    btc_bias: float | None = None
    components: list[EvidenceComponent] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    weak_reason: str = ""
    strategy_scores: dict[str, float] = field(default_factory=dict)
    orderflow: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """نمایش قابل ذخیره در market_snapshot / paper_trades.extra."""
        return {
            "version": 1,
            "symbol": self.symbol,
            "base_direction": self.base_direction,
            "direction": self.direction,
            "decision": self.decision,
            "quality": self.quality,
            "technical_confidence": self.technical_confidence,
            "final_confidence": self.final_confidence,
            "prediction_probability": self.prediction_probability,
            "prediction_direction": self.prediction_direction,
            "mtf_alignment": self.mtf_alignment,
            "regime": self.regime,
            "regime_score": self.regime_score,
            "historical_edge": self.historical_edge,
            "historical_samples": self.historical_samples,
            "execution_quality": self.execution_quality,
            "evidence_ratio": round(self.evidence_ratio, 4),
            "coverage": round(self.coverage, 3),
            "size_multiplier": self.size_multiplier,
            "primary_timeframe": self.primary_timeframe,
            "btc_bias": None if self.btc_bias is None else round(self.btc_bias, 3),
            "components": [c.to_dict() for c in self.components],
            "conflicts": list(self.conflicts),
            "reasons": list(self.reasons),
            "weak_reason": self.weak_reason,
            "strategy_scores": {k: round(v, 3) for k, v in self.strategy_scores.items()},
            "orderflow": self.orderflow,
        }


# ----------------------------------------------------------------------
# کمکی‌ها
# ----------------------------------------------------------------------
def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    if not math.isfinite(value):
        return 0.0
    return max(low, min(high, value))


def _latest(analysis: dict[str, Any], name: str, key: str) -> float | None:
    payload = (analysis.get("indicators") or {}).get(name)
    if not isinstance(payload, dict):
        return None
    latest = payload.get("latest")
    if not isinstance(latest, dict):
        return None
    value = latest.get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def _indicator_signal(analysis: dict[str, Any], name: str) -> str:
    payload = (analysis.get("indicators") or {}).get(name)
    return str(payload.get("signal", "")) if isinstance(payload, dict) else ""


def _trend_sign(trend: Any) -> int:
    value = getattr(trend, "value", trend)
    if value == TrendDirection.BULLISH.value:
        return 1
    if value == TrendDirection.BEARISH.value:
        return -1
    return 0


def structure_sign(value: Any) -> int:
    """
    علامت جهت ساختار بازار — نسخهٔ ۲.۵.۸.

    BREAKOUT (بسته‌شدن بالای آخرین سقف نوسانی) صعودی و BREAKDOWN (زیر
    آخرین کف) نزولی است؛ همان تعریف `analyze_market_structure`. پیش از این
    `_structure` فقط BREAKOUT را جهت‌دار می‌دید (BREAKDOWN = ۰، یعنی شکست
    نزولی هیچ تأییدی برای SHORT نمی‌داد) و `_mtf` هر دو را صفر می‌گرفت.
    """
    value = str(getattr(value, "value", value) or "").upper()
    if value in ("BULLISH", "BREAKOUT"):
        return 1
    if value in ("BEARISH", "BREAKDOWN"):
        return -1
    return 0


def _signal_sign(text: str) -> int:
    upper = text.upper()
    if "BULL" in upper:
        return 1
    if "BEAR" in upper:
        return -1
    return 0


def timeframe_minutes(timeframe: str) -> int:
    """دقیقهٔ تایم‌فریم؛ ناشناخته → ۶۰."""
    return _TF_MINUTES.get(timeframe, 60)


#: سازگاری رژیم با جهت: (امتیاز برای LONG، امتیاز برای SHORT)
_REGIME_FIT: dict[str, tuple[float, float]] = {
    "strong_trend_up": (1.0, -1.0),
    "strong_trend_down": (-1.0, 1.0),
    "breakout": (0.6, -0.5),
    "breakdown": (-0.5, 0.6),
    "accumulation": (0.3, -0.2),
    "distribution": (-0.3, 0.3),
    "range": (0.0, 0.0),
    "compression": (0.0, 0.0),
    "low_volatility": (-0.1, -0.1),
    "expansion": (0.1, 0.1),
    "high_volatility": (-0.3, -0.3),
    "liquidation_event": (-0.5, -0.5),
}


def regime_fit(regime: str, regime_direction: int, direction: SignalDirection) -> float:
    """امتیاز سازگاری رژیم با جهت سیگنال ∈ [-1, 1]."""
    sign = 1 if direction == SignalDirection.LONG else -1
    if regime in ("weak_trend", "trend_reversal"):
        return _clamp((0.35 if regime == "weak_trend" else 0.5) * regime_direction * sign)
    pair = _REGIME_FIT.get(regime)
    if pair is None:
        return 0.0
    return pair[0] if sign > 0 else pair[1]


def btc_context_from_candles(frames: dict[str, list[Any]]) -> dict[str, Any] | None:
    """
    بافت BTC از کندل‌های چند تایم‌فریم (بسته‌شده).

    برای هر تایم‌فریم: علامت EMA20−EMA50 و بازده ۱۲ کندل اخیر. سوگیری
    نهایی میانگین وزن‌دار است. داده ناکافی → None.
    """
    per_tf: dict[str, dict[str, float]] = {}
    num = 0.0
    den = 0.0
    for timeframe, candles in frames.items():
        closes = [float(c.close) for c in candles or []]
        if len(closes) < 55:
            continue
        ema20 = _ema(closes, 20)
        ema50 = _ema(closes, 50)
        change = (closes[-1] / closes[-13] - 1.0) * 100.0 if closes[-13] else 0.0
        trend = 1.0 if ema20 > ema50 else -1.0 if ema20 < ema50 else 0.0
        momentum = _clamp(change / 2.0)
        bias = _clamp(0.6 * trend + 0.4 * momentum)
        weight = _TF_WEIGHTS.get(timeframe, 1.0)
        per_tf[timeframe] = {"trend": trend, "change_percent": round(change, 3), "bias": round(bias, 3)}
        num += bias * weight
        den += weight
    if den <= 0:
        return None
    return {"bias": round(num / den, 4), "frames": per_tf}


def _ema(values: list[float], period: int) -> float:
    k = 2.0 / (period + 1.0)
    ema = values[0]
    for value in values[1:]:
        ema = value * k + ema * (1.0 - k)
    return ema


def strategy_scores(votes_by_timeframe: dict[str, list[Any]]) -> dict[str, float]:
    """امتیاز خالص هر راهبرد در همهٔ تایم‌فریم‌ها (وزن تایم‌فریم) — برای یادگیری."""
    totals: dict[str, float] = {}
    weights: dict[str, float] = {}
    for timeframe, votes in votes_by_timeframe.items():
        tf_weight = _TF_WEIGHTS.get(timeframe, 1.0)
        for vote in votes:
            if not getattr(vote, "applicable", True):
                continue
            name = str(getattr(vote, "strategy", ""))
            totals[name] = totals.get(name, 0.0) + float(getattr(vote, "score", 0.0)) * tf_weight
            weights[name] = weights.get(name, 0.0) + tf_weight
    return {name: totals[name] / weights[name] for name in totals if weights.get(name)}


# ----------------------------------------------------------------------
# موتور
# ----------------------------------------------------------------------
class IntelligentDecisionEngine:
    """ترکیب شواهد و ساخت تصمیم نهایی (بدون حالت؛ قابل استفاده در بک‌تست)."""

    def __init__(self, config: DecisionConfig | None = None) -> None:
        self.config = config or DecisionConfig()

    # ---------------------------------------------------------- مؤلفه‌ها
    def _weight(self, name: str) -> float:
        return float(self.config.weights.get(name, 0.0))

    def _trend(self, inp: DecisionInputs, sign: int) -> EvidenceComponent:
        analysis = inp.analyses.get(inp.primary_timeframe) or {}
        if not analysis:
            return EvidenceComponent("trend", 0.0, 0.0, self._weight("trend"), "no primary analysis")
        parts: list[float] = []
        ema_sign = _signal_sign(_indicator_signal(analysis, "EMA"))
        parts.append(float(ema_sign))
        adx = _latest(analysis, "ADX", "adx")
        plus = _latest(analysis, "ADX", "plus_di")
        minus = _latest(analysis, "ADX", "minus_di")
        if adx is not None and plus is not None and minus is not None:
            di = 1.0 if plus > minus else -1.0 if minus > plus else 0.0
            parts.append(di * min(1.0, adx / 30.0))
        parts.append(float(_trend_sign(analysis.get("trend"))))
        score = _clamp(sign * sum(parts) / len(parts))
        detail = f"EMA {ema_sign:+d}, ADX {adx:.0f}" if adx is not None else f"EMA {ema_sign:+d}"
        return EvidenceComponent("trend", score, 1.0, self._weight("trend"), detail)

    def _momentum(self, inp: DecisionInputs, sign: int) -> EvidenceComponent:
        analysis = inp.analyses.get(inp.primary_timeframe) or {}
        parts: list[float] = []
        rsi = _latest(analysis, "RSI", "rsi")
        if rsi is not None:
            rsi_part = _clamp((rsi - 50.0) / 20.0)
            # ورود در اشباع شدید هم‌جهت → تأیید کمتر (ریسک برگشت)
            if (sign > 0 and rsi > 78) or (sign < 0 and rsi < 22):
                rsi_part *= 0.3
            parts.append(rsi_part)
        hist = _latest(analysis, "MACD", "histogram")
        if hist is not None:
            parts.append(1.0 if hist > 0 else -1.0 if hist < 0 else 0.0)
        k = _latest(analysis, "STOCH", "k")
        d = _latest(analysis, "STOCH", "d")
        if k is not None and d is not None:
            parts.append(_clamp((k - d) / 15.0))
        if not parts:
            return EvidenceComponent("momentum", 0.0, 0.0, self._weight("momentum"), "no momentum data")
        score = _clamp(sign * sum(parts) / len(parts))
        return EvidenceComponent(
            "momentum", score, 1.0, self._weight("momentum"),
            f"RSI {rsi:.0f}" if rsi is not None else "",
        )

    def _prediction(self, inp: DecisionInputs, sign: int) -> tuple[EvidenceComponent, int | None, str]:
        report = inp.prediction or {}
        horizons = [h for h in report.get("horizons") or [] if isinstance(h, dict)]
        weight = self._weight("prediction")
        if not horizons:
            return EvidenceComponent("prediction", 0.0, 0.0, weight, "prediction unavailable"), None, ""
        target = timeframe_minutes(inp.primary_timeframe) * 3
        horizon = min(horizons, key=lambda h: abs(int(h.get("minutes") or 0) - target))
        label = str(horizon.get("direction", "")).lower()
        pred_sign = 1 if label == "bullish" else -1 if label == "bearish" else 0
        probability = int(horizon.get("probability") or 50)
        confidence = float(horizon.get("confidence") or 0) / 100.0
        agreement = float(horizon.get("model_agreement") or 0.0)
        reliability = _clamp(confidence * (0.5 + 0.5 * agreement), 0.0, 1.0)
        if horizon.get("conflict"):
            reliability *= 0.5
        strength = _clamp((probability - 50.0) / 20.0, 0.0, 1.0)
        score = float(sign * pred_sign) * strength
        in_favour = probability if pred_sign == sign else (100 - probability if pred_sign else 50)
        detail = f"{horizon.get('horizon')}: {label} {probability}% (agreement {agreement:.2f})"
        return EvidenceComponent("prediction", score, reliability, weight, detail), in_favour, label

    def _mtf(self, inp: DecisionInputs, sign: int) -> tuple[EvidenceComponent, int | None]:
        primary_w = _TF_WEIGHTS.get(inp.primary_timeframe, 1.0)
        num = 0.0
        den = 0.0
        agree = 0
        total = 0
        for timeframe, analysis in inp.analyses.items():
            if timeframe == inp.primary_timeframe:
                continue
            tf_w = _TF_WEIGHTS.get(timeframe, 1.0)
            if tf_w < primary_w:
                continue
            trend = _trend_sign(analysis.get("trend"))
            structure = analysis.get("structure")
            s_type = getattr(getattr(structure, "structure", None), "value", "")
            struct_sign = structure_sign(s_type)
            frame_sign = _clamp(0.65 * trend + 0.35 * struct_sign)
            num += sign * frame_sign * tf_w
            den += tf_w
            total += 1
            if sign * frame_sign > 0.2:
                agree += 1
        weight = self._weight("mtf")
        if timeframe_minutes(inp.primary_timeframe) <= 15:
            weight *= self.config.short_primary_htf_factor
        if den <= 0:
            return EvidenceComponent("mtf", 0.0, 0.0, weight, "no higher timeframe"), None
        score = _clamp(num / den)
        alignment = int(round(50 + 50 * score))
        return EvidenceComponent("mtf", score, 1.0, weight, f"{agree}/{total} higher frames agree"), alignment

    def _volume(self, inp: DecisionInputs, sign: int) -> EvidenceComponent:
        analysis = inp.analyses.get(inp.primary_timeframe) or {}
        obv = _signal_sign(_indicator_signal(analysis, "OBV"))
        ratio = _latest(analysis, "VOLUME_SMA", "volume_ratio")
        if ratio is None and not obv:
            return EvidenceComponent("volume", 0.0, 0.0, self._weight("volume"), "no volume data")
        participation = 0.0
        if ratio is not None:
            participation = 0.4 if ratio >= 1.3 else -0.25 if ratio < 0.5 else 0.0
        score = _clamp(0.6 * sign * obv + participation)
        return EvidenceComponent(
            "volume", score, 1.0, self._weight("volume"),
            f"OBV {obv:+d}, vol ratio {ratio:.2f}" if ratio is not None else f"OBV {obv:+d}",
        )

    def _regime(self, inp: DecisionInputs) -> tuple[EvidenceComponent, str, int | None]:
        regime = inp.regime or {}
        name = str(regime.get("regime") or "unknown")
        if name == "unknown":
            return EvidenceComponent("regime", 0.0, 0.0, self._weight("regime"), "regime unknown"), name, None
        fit = regime_fit(name, int(regime.get("direction") or 0), inp.direction)
        reliability = _clamp(float(regime.get("confidence") or 50) / 100.0, 0.0, 1.0)
        return (
            EvidenceComponent("regime", fit, reliability, self._weight("regime"), f"{name} ({regime.get('timeframe', '')})"),
            name,
            int(round(50 + 50 * fit)),
        )

    def _structure(self, inp: DecisionInputs, sign: int) -> EvidenceComponent:
        analysis = inp.analyses.get(inp.primary_timeframe) or {}
        structure = analysis.get("structure")
        weight = self._weight("structure")
        if structure is None:
            return EvidenceComponent("structure", 0.0, 0.0, weight, "no structure")
        s_type = getattr(structure, "structure", MarketStructureType.UNDEFINED)
        value = getattr(s_type, "value", str(s_type))
        base = float(structure_sign(value))
        score = sign * base * 0.8
        # سطح مخالف نزدیک (مقاومت برای خرید / حمایت برای فروش) → کاهش
        candles = analysis.get("candles") or []
        atr = _latest(analysis, "ATR", "atr")
        if candles and atr:
            price = float(candles[-1].close)
            for level in analysis.get("levels") or []:
                kind = getattr(level, "kind", "")
                lp = float(getattr(level, "price", 0.0) or 0.0)
                ahead = (sign > 0 and kind == "resistance" and lp > price) or (
                    sign < 0 and kind == "support" and lp < price
                )
                if ahead and abs(lp - price) < 0.6 * atr:
                    score -= 0.4 if getattr(level, "strength", "") == "major" else 0.2
                    break
        return EvidenceComponent("structure", _clamp(score), 1.0, weight, value)

    def _orderflow(self, inp: DecisionInputs, sign: int) -> tuple[EvidenceComponent, dict[str, Any] | None]:
        snapshot = inp.orderflow
        weight = self._weight("orderflow")
        if snapshot is None or not getattr(snapshot, "available", False):
            return EvidenceComponent("orderflow", 0.0, 0.0, weight, "order flow unavailable"), (
                snapshot.to_dict() if snapshot is not None else None
            )
        bias = float(snapshot.bias())
        return (
            EvidenceComponent(
                "orderflow", _clamp(sign * bias), float(snapshot.reliability()), weight,
                ("proxy " if snapshot.proxy else "") + f"bias {bias:+.2f}",
            ),
            snapshot.to_dict(),
        )

    def _btc(self, inp: DecisionInputs, sign: int) -> tuple[EvidenceComponent, float | None]:
        context = inp.btc
        weight = self._weight("btc")
        if not context or not isinstance(context.get("bias"), (int, float)):
            return EvidenceComponent("btc", 0.0, 0.0, weight, "BTC context n/a"), None
        bias = float(context["bias"])
        return EvidenceComponent("btc", _clamp(sign * bias), 0.6, weight, f"BTC bias {bias:+.2f}"), bias

    def _history(self, inp: DecisionInputs) -> tuple[EvidenceComponent, int, int]:
        history = inp.history or {}
        weight = self._weight("history")
        edge = int(history.get("edge") or 50)
        samples = int(history.get("samples") or 0)
        if not history.get("reliable"):
            return EvidenceComponent("history", 0.0, 0.0, weight, f"insufficient history (n={samples})"), 50, samples
        score = _clamp((edge - 50.0) / 25.0)
        reliability = _clamp(samples / 100.0, 0.3, 1.0)
        return (
            EvidenceComponent("history", score, reliability, weight, f"edge {edge} (n={samples}, {history.get('level')})"),
            edge,
            samples,
        )

    def _execution(self, inp: DecisionInputs) -> tuple[EvidenceComponent, int | None]:
        parts: list[float] = []
        notes: list[str] = []
        if inp.risk_reward is not None:
            parts.append(_clamp((float(inp.risk_reward) - 1.5) / 1.0))
            notes.append(f"R/R {float(inp.risk_reward):.2f}")
        execution = inp.execution or {}
        spread = execution.get("spread_percent")
        if isinstance(spread, (int, float)):
            parts.append(_clamp(1.0 - float(spread) / 0.08, -1.0, 1.0))
            notes.append(f"spread {float(spread):.3f}%")
        analysis = inp.analyses.get(inp.primary_timeframe) or {}
        atr_pct = _latest(analysis, "ATR", "atr_percent")
        if atr_pct is not None:
            limit = 3.0 if timeframe_minutes(inp.primary_timeframe) <= 15 else 8.0
            parts.append(-0.6 if atr_pct > limit else 0.2)
        if not parts:
            return EvidenceComponent("execution", 0.0, 0.0, self._weight("execution"), "n/a"), None
        score = _clamp(sum(parts) / len(parts))
        return (
            EvidenceComponent("execution", score, 1.0, self._weight("execution"), ", ".join(notes)),
            int(round(50 + 50 * score)),
        )

    # ---------------------------------------------------------- ترکیب
    def evaluate(self, inp: DecisionInputs) -> IntelligentDecision:
        """ساخت تصمیم نهایی از شواهد."""
        cfg = self.config
        base = inp.direction.value if hasattr(inp.direction, "value") else str(inp.direction)
        tech = int(max(0, min(100, inp.technical_confidence)))
        scores_by_strategy = strategy_scores(inp.votes_by_timeframe)

        if inp.direction not in (SignalDirection.LONG, SignalDirection.SHORT):
            return IntelligentDecision(
                symbol=inp.symbol, base_direction=base, direction=base, decision=DECISION_WAIT,
                quality="", technical_confidence=tech, final_confidence=tech,
                prediction_probability=None, prediction_direction="", mtf_alignment=None,
                regime=str((inp.regime or {}).get("regime") or "unknown"), regime_score=None,
                historical_edge=50, historical_samples=0, execution_quality=None,
                evidence_ratio=0.0, coverage=0.0, size_multiplier=0.0,
                primary_timeframe=inp.primary_timeframe, strategy_scores=scores_by_strategy,
            )

        sign = 1 if inp.direction == SignalDirection.LONG else -1
        pred, pred_prob, pred_dir = self._prediction(inp, sign)
        mtf, mtf_alignment = self._mtf(inp, sign)
        regime, regime_name, regime_score = self._regime(inp)
        orderflow, orderflow_dict = self._orderflow(inp, sign)
        btc, btc_bias = self._btc(inp, sign)
        history, edge, samples = self._history(inp)
        execution, execution_quality = self._execution(inp)
        components = [
            self._trend(inp, sign), self._momentum(inp, sign), pred, mtf,
            self._volume(inp, sign), regime, self._structure(inp, sign),
            orderflow, btc, history, execution, exhaustion_component(tech, cfg),
        ]

        weight_rel = sum(c.weight * c.reliability for c in components)
        ratio = sum(c.contribution for c in components) / weight_rel if weight_rel > 0 else 0.0
        coverage = min(1.0, weight_rel / cfg.coverage_norm) if cfg.coverage_norm > 0 else 1.0
        scale = cfg.bonus if ratio > 0 else cfg.penalty
        final = int(round(max(0.0, min(100.0, saturation_base(tech, cfg) + ratio * coverage * scale))))

        conflicts = [
            f"{c.name} ({c.detail})" for c in components
            if c.weight >= 10 and c.score <= cfg.strong_opposition and c.reliability >= 0.4
        ]
        severe = [
            c.name for c in components
            if c.name in SEVERE_FACTORS and c.score <= cfg.strong_opposition and c.reliability >= 0.35
        ]

        decision = DECISION_TRADE
        if len(severe) >= cfg.no_trade_min_opposing and ratio <= cfg.no_trade_ratio:
            decision = DECISION_NO_TRADE

        if final >= cfg.strong_final and ratio >= cfg.strong_ratio and not conflicts:
            quality, size = QUALITY_STRONG, cfg.size_strong
        elif final < cfg.weak_final or ratio < cfg.weak_ratio or len(conflicts) >= 2:
            quality, size = QUALITY_WEAK, cfg.size_weak
        else:
            quality, size = QUALITY_NORMAL, cfg.size_normal
        if decision == DECISION_NO_TRADE:
            size = 0.0

        supporting = sorted((c for c in components if c.contribution > 0), key=lambda c: -c.contribution)
        opposing = sorted((c for c in components if c.contribution < 0), key=lambda c: c.contribution)
        reasons = [f"+ {c.name}: {c.detail}" for c in supporting[:4]]
        reasons += [f"- {c.name}: {c.detail}" for c in opposing[:3]]
        weak_reason = ""
        if quality == QUALITY_WEAK or decision == DECISION_NO_TRADE:
            weak_reason = "; ".join(f"{c.name}: {c.detail}" for c in opposing[:3]) or (
                f"low technical confidence ({tech})"
            )

        return IntelligentDecision(
            symbol=inp.symbol,
            base_direction=base,
            direction=base if decision == DECISION_TRADE else SignalDirection.WAIT.value,
            decision=decision,
            quality=quality,
            technical_confidence=tech,
            final_confidence=final,
            prediction_probability=pred_prob,
            prediction_direction=pred_dir,
            mtf_alignment=mtf_alignment,
            regime=regime_name,
            regime_score=regime_score,
            historical_edge=edge,
            historical_samples=samples,
            execution_quality=execution_quality,
            evidence_ratio=ratio,
            coverage=coverage,
            size_multiplier=size,
            primary_timeframe=inp.primary_timeframe,
            btc_bias=btc_bias,
            components=components,
            conflicts=conflicts,
            reasons=reasons,
            weak_reason=weak_reason,
            strategy_scores=scores_by_strategy,
            orderflow=orderflow_dict,
        )

    def rescore(self, snapshot: dict[str, Any], config: DecisionConfig | None = None) -> dict[str, Any]:
        """
        بازامتیازدهی یک عکس لحظه‌ای ذخیره‌شده با پیکربندی دیگر — بدون
        محاسبهٔ دوبارهٔ اندیکاتورها. walk-forward از این برای تنظیم
        آستانه‌ها روی بازهٔ آموزش استفاده می‌کند.
        """
        cfg = config or self.config
        components = snapshot.get("components") or []
        tech = int(snapshot.get("technical_confidence") or 0)
        weights = cfg.weights
        items = []
        exhaustion = exhaustion_component(tech, cfg)
        components = [c for c in components if c.get("name") != "exhaustion"] + [exhaustion.to_dict()]
        for comp in components:
            name = comp["name"]
            w = float(weights.get(name, comp.get("weight", 0.0)))
            if name == "mtf" and timeframe_minutes(snapshot.get("primary_timeframe", "")) <= 15:
                w *= cfg.short_primary_htf_factor
            items.append((name, float(comp["score"]), float(comp["reliability"]), w))
        weight_rel = sum(w * r for _, _, r, w in items)
        ratio = sum(w * s * r for _, s, r, w in items) / weight_rel if weight_rel > 0 else 0.0
        coverage = min(1.0, weight_rel / cfg.coverage_norm) if cfg.coverage_norm > 0 else 1.0
        final = int(round(max(0.0, min(100.0, saturation_base(tech, cfg)
                                        + ratio * coverage * (cfg.bonus if ratio > 0 else cfg.penalty)))))
        conflicts = [n for n, s, r, w in items if w >= 10 and s <= cfg.strong_opposition and r >= 0.4]
        severe = [n for n, s, r, _ in items if n in SEVERE_FACTORS and s <= cfg.strong_opposition and r >= 0.35]
        decision = (
            DECISION_NO_TRADE
            if len(severe) >= cfg.no_trade_min_opposing and ratio <= cfg.no_trade_ratio
            else DECISION_TRADE
        )
        if final >= cfg.strong_final and ratio >= cfg.strong_ratio and not conflicts:
            quality, size = QUALITY_STRONG, cfg.size_strong
        elif final < cfg.weak_final or ratio < cfg.weak_ratio or len(conflicts) >= 2:
            quality, size = QUALITY_WEAK, cfg.size_weak
        else:
            quality, size = QUALITY_NORMAL, cfg.size_normal
        return {
            "decision": decision,
            "quality": quality,
            "final_confidence": final,
            "evidence_ratio": ratio,
            "size_multiplier": 0.0 if decision == DECISION_NO_TRADE else size,
        }


def saturation_base(tech: int, cfg: DecisionConfig) -> int:
    """پایهٔ اطمینان نهایی: بالاتر از saturation_start بازتاب می‌شود (۷۵→۶۱ با شروع ۶۸)."""
    start = int(cfg.saturation_start or 0)
    if start <= 0 or tech <= start:
        return tech
    return max(0, start - (tech - start))


def exhaustion_component(tech: int, cfg: DecisionConfig) -> EvidenceComponent:
    """شاهد فرسودگی حرکت؛ زیر آستانه خنثی و غیرفعال (reliability=0)."""
    start = int(cfg.saturation_start or 0)
    if start <= 0 or tech <= start or cfg.exhaustion_weight <= 0:
        return EvidenceComponent("exhaustion", 0.0, 0.0, cfg.exhaustion_weight, "not saturated")
    score = -min(1.0, (tech - start) / max(1.0, cfg.saturation_span))
    return EvidenceComponent(
        "exhaustion", score, 1.0, cfg.exhaustion_weight,
        f"technical {tech} is saturated (>{start}): late-entry risk after an extended move",
    )


def extension_atr(candles: list[Any], sign: int, *, ema_period: int = 20, atr_period: int = 14) -> float | None:
    """
    کشیدگی حرکت در جهت سیگنال: (close − EMA20) / ATR14 × جهت — نسخهٔ ۲.۵.۶.

    مثبت بزرگ یعنی ورود پس از یک حرکت کشیده (دنبال‌کردن حرکت). تشخیص
    ۲.۵.۶ نشان داد اطمینان بالا عمدتاً همین کشیدگی است و اثرش بین رژیم‌ها
    عکس می‌شود؛ پس فیلتر ثابت نمی‌سازیم و یادگیرنده اثرش را می‌آموزد.
    """
    if not candles or len(candles) < max(ema_period, atr_period) + 2 or sign == 0:
        return None
    closes = [float(c.close) for c in candles]
    ema = _ema(closes, ema_period)
    trs = [
        max(candles[i].high - candles[i].low, abs(candles[i].high - candles[i - 1].close),
            abs(candles[i].low - candles[i - 1].close))
        for i in range(len(candles) - atr_period, len(candles))
    ]
    atr = sum(trs) / len(trs) if trs else 0.0
    if atr <= 0 or not math.isfinite(atr):
        return None
    value = (closes[-1] - ema) / atr * (1 if sign > 0 else -1)
    return value if math.isfinite(value) else None


def extension_bucket(value: float | None) -> str:
    """سطل کشیدگی برای حافظهٔ الگو (کم‌تعداد تا نمونه کافی جمع شود)."""
    if value is None:
        return ""
    if value < 1.0:
        return "<1"
    if value < 2.0:
        return "1-2"
    return ">=2"


def eligibility_confidence(signal: Any) -> int:
    """
    اطمینانی که با آستانهٔ کاربر مقایسه می‌شود.

    لایهٔ هوشمند `confidence` را به final تبدیل می‌کند؛ اگر آستانهٔ
    پویش/معاملهٔ خودکار روی final اعمال می‌شد، هر شاهد متوسط سیگنال را
    بی‌صدا حذف می‌کرد (همان «آستانهٔ سخت پنهان» که کاربر منع کرد).
    پس صلاحیت با اطمینان فنی (همان مجموعهٔ قبلی) سنجیده می‌شود و final
    فقط نمایش، کیفیت و اندازهٔ پوزیشن را تعیین می‌کند.
    """
    intel = getattr(signal, "intelligence", None) or {}
    technical = intel.get("technical_confidence") if isinstance(intel, dict) else None
    if isinstance(technical, (int, float)):
        return int(technical)
    return int(getattr(signal, "confidence", 0) or 0)


def resolve_direction(
    evidence: dict[str, float],
    *,
    weights: dict[str, float] | None = None,
    min_margin: float = 0.12,
) -> tuple[SignalDirection, float]:
    """
    حل جهت از شواهد چندتایم‌فریمی (برای اسکالپ — جهت فقط از مومنتوم نیست).

    evidence: نام → سوگیری ∈ [-1, 1] (مثبت = خرید). خروجی (جهت، قدرت).
    اگر قدر مطلق میانگین وزن‌دار کمتر از min_margin باشد → WAIT.
    """
    weights = weights or {}
    num = 0.0
    den = 0.0
    for name, value in evidence.items():
        if value is None or not math.isfinite(value):
            continue
        w = float(weights.get(name, 1.0))
        num += w * _clamp(value)
        den += w
    if den <= 0:
        return SignalDirection.WAIT, 0.0
    strength = num / den
    if strength >= min_margin:
        return SignalDirection.LONG, strength
    if strength <= -min_margin:
        return SignalDirection.SHORT, strength
    return SignalDirection.WAIT, strength


__all__ = [
    "DECISION_NO_TRADE",
    "DECISION_TRADE",
    "DECISION_WAIT",
    "QUALITY_NORMAL",
    "QUALITY_STRONG",
    "QUALITY_WEAK",
    "DecisionConfig",
    "DecisionInputs",
    "EvidenceComponent",
    "IntelligentDecision",
    "IntelligentDecisionEngine",
    "btc_context_from_candles",
    "eligibility_confidence",
    "extension_atr",
    "extension_bucket",
    "regime_fit",
    "resolve_direction",
    "strategy_scores",
    "structure_sign",
    "timeframe_minutes",
]
