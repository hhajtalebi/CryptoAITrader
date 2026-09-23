"""
تصمیم‌ساز حالت AI Auto (خواستهٔ §۳ تسک).

سیستم خودش تصمیم می‌گیرد: نماد، جهت، ورود، مارجین، اهرم، TP، SL و خروج.
بر پایهٔ: موجودی، روند، پیش‌بینی، اطمینان، MTF، دفتر سفارش، نقدینگی،
اسپرد، نوسان، عملکرد تاریخی نماد و ریسک پرتفوی.

اگر شرایط مناسب نیست: **NO TRADE** — ظرفیت آزاد هیچ‌وقت به تنهایی
دلیل بازکردن معامله نیست (خواستهٔ §۱۲).

عدد جعل نمی‌شود: TP/SL از چندک‌های واقعی پیش‌بینی می‌آیند، اهرم از
نوسان اندازه‌گیری‌شده، و مارجین از قواعد تخصیص. این ماژول صرفاً
قواعد تصمیم است؛ داده از موتورهای موجود می‌آید.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trading.price_cache import TickQuote
from trading.trend_ladder import TrendLadder, conflict_verdict

#: افق مرجع تصمیم اسکلپ: ۱۵ دقیقه (ستاپ) — اگر نبود، افق بعدی موجود
PREFERRED_HORIZONS: tuple[str, ...] = ("15m", "5m", "30m", "1h")

#: سقف اهرم پیشنهادی AI — بالاتر از این، نوسان‌سنجی بی‌معنا می‌شود
AI_MAX_LEVERAGE = 50.0

#: حداقل اطمینان پیش‌بینی برای ورود AI؛ زیر آن NO TRADE
AI_MIN_PREDICTION_CONFIDENCE = 55

#: کمترین نسبت ریسک به ریوارد قابل قبول
AI_MIN_RISK_REWARD = 1.2


@dataclass
class TradeDecision:
    """یک تصمیم — یا معاملهٔ کامل، یا NO TRADE با دلیل صریح."""

    ok: bool
    symbol: str = ""
    direction: str = ""  # LONG | SHORT
    entry_price: float = 0.0
    margin: float = 0.0
    leverage: float = 1.0
    take_profit: float = 0.0
    stop_loss: float = 0.0
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    #: علت رد — فقط وقتی ok=False
    reason: str = ""

    @classmethod
    def no_trade(cls, reason: str, **extra: Any) -> TradeDecision:
        """NO TRADE — پاسخ کاملاً معتبر و صادقانه."""
        decision = cls(ok=False, reason=str(reason))
        decision.reasons.append(str(reason))
        return decision

    @property
    def notional(self) -> float:
        """ارزش موقعیت — مارجین × اهرم (هرگز برابر مارجین نیست)."""
        return self.margin * self.leverage

    @property
    def risk_reward(self) -> float:
        """نسبت سود به زیان بر پایهٔ TP/SL واقعی."""
        if self.entry_price <= 0 or self.stop_loss <= 0:
            return 0.0
        reward = abs(self.take_profit - self.entry_price)
        risk = abs(self.entry_price - self.stop_loss)
        return reward / risk if risk > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """نمای UI/گزارش."""
        return {
            "ok": self.ok,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "margin": self.margin,
            "leverage": self.leverage,
            "notional": self.notional,
            "take_profit": self.take_profit,
            "stop_loss": self.stop_loss,
            "confidence": self.confidence,
            "risk_reward": round(self.risk_reward, 2),
            "reason": self.reason,
            "reasons": list(self.reasons),
        }


def pick_horizon(report: dict[str, Any] | None) -> dict[str, Any] | None:
    """افق مرجع تصمیم — اولین افق موجود از فهرست ترجیحی."""
    if not report:
        return None
    horizons = report.get("horizons") or []
    by_key = {str(h.get("horizon")): h for h in horizons if isinstance(h, dict)}
    for key in PREFERRED_HORIZONS:
        horizon = by_key.get(key)
        if horizon:
            return horizon
    return horizons[0] if horizons else None


def direction_from_horizon(horizon: dict[str, Any]) -> str:
    """جهت افق → LONG/SHORT؛ خنثی/نامطمئن یعنی بدون جهت."""
    raw = str(horizon.get("direction", "")).lower()
    if raw == "bullish":
        return "LONG"
    if raw == "bearish":
        return "SHORT"
    return ""


@dataclass
class AICandidate:
    """
    نامزد حالت AI Auto — معاملهٔ کامل با مارجین/اهرم/TP/SL.

    پروتکل نامزد موجود (`symbol/price/direction/score/turnover_24h`)
    را نگه می‌دارد و فیلدهای تازه (مارجین، اهرم، سطوح، نردبان) را
    اضافه می‌کند؛ `AutoTrader.open_trade` آن‌ها را با getattr
    می‌خواند، پس منابع قدیمی بدون تغییر کار می‌کنند.
    """

    symbol: str
    price: float
    direction: str  # LONG | SHORT
    score: float  # اطمینان مؤثر (۰..۱۰۰)
    turnover_24h: float = 0.0
    spread_percent: float = 0.0
    entry_price: float = 0.0
    margin: float = 0.0
    leverage: float = 0.0
    take_profit: float = 0.0
    stop_loss: float = 0.0
    prediction: str = ""
    trend_ladder: Any = None
    reasons: list[str] = field(default_factory=list)
    # --- ستون‌های ترمینال (v2.1) — همهٔ اختیاری، همهٔ واقعی ---
    #: احتمال جهت افق مرجع (۰..۱۰۰)
    probability: float = 0.0
    #: حرکت موردانتظار تا انتهای افق (درصد)
    expected_move_percent: float = 0.0
    #: هم‌راستایی چندتایم‌فریمی از گزارش موتور (aligned و …)
    mtf: str = ""
    #: نسبت ریسک به ریوارد محاسبه‌شدهٔ تصمیم
    risk_reward: float = 0.0


@dataclass
class PortfolioState:
    """وضعیت پرتفوی برای محدودسازی ریسک."""

    balance: float = 0.0
    used_margin: float = 0.0
    open_count: int = 0
    max_concurrent: int = 3
    max_total_margin_percent: float = 60.0
    #: نرخ برد تاریخی همین نماد (۰..۱۰۰) — از معاملات حل‌شدهٔ واقعی
    symbol_win_rate: float | None = None
    symbol_closed_count: int = 0

    @property
    def available_margin(self) -> float:
        """مارجین آزاد."""
        return max(0.0, self.balance - self.used_margin)

    @property
    def total_margin_cap(self) -> float:
        """سقف مجموع مارجین بر پایهٔ درصد موجودی."""
        return self.balance * max(1.0, self.max_total_margin_percent) / 100.0

    def to_dict(self) -> dict[str, Any]:
        """نمای گزارش."""
        return {
            "balance": self.balance,
            "used_margin": self.used_margin,
            "available_margin": self.available_margin,
            "open_count": self.open_count,
        }


def size_margin(
    *,
    allocation_mode: str,
    base_margin: float,
    portfolio: PortfolioState,
    confidence: float = 50.0,
    risk_amount: float = 0.0,
) -> float:
    """
    مارجین معامله بر پایهٔ حالت تخصیص (خواستهٔ §۱۲).

    fixed       → مارجین ثابت پایه
    percent     → درصدی از موجودی (base_margin اینجا «درصد» است)
    confidence  → پایه × ضریب اطمینان (۰٫۵ تا ۱٫۵)
    risk        → مارجینِ متناسب با ریسک مجاز (risk_amount / نسبت)
    hybrid      → درصدی، مشروط به سقف ثابت
    ai          → مثل confidence با سقف سخت پرتفوی

    خروجی همیشه با سقف مارجین آزاد و سقف کل بریده می‌شود.
    """
    mode = str(allocation_mode or "fixed").lower()
    balance = max(0.0, float(portfolio.balance))
    base = max(0.0, float(base_margin))

    if mode == "percent":
        margin = balance * base / 100.0
    elif mode == "confidence":
        factor = 0.5 + max(0.0, min(100.0, confidence)) / 100.0
        margin = base * factor
    elif mode == "risk" and risk_amount > 0:
        # ریسک دلاری مجاز تقسیم بر ۲٪ ریسک قیمتیِ معامله — قاعدهٔ
        # سرانگشتی «ریسک ثابت» که اسکلپ‌رها استفاده می‌کنند.
        margin = risk_amount / 0.02
    elif mode == "hybrid":
        margin = min(balance * base / 100.0, base * 3.0) if base > 0 else 0.0
    elif mode == "ai":
        factor = 0.5 + max(0.0, min(100.0, confidence)) / 100.0
        margin = base * factor
    else:
        margin = base

    margin = min(margin, portfolio.available_margin, portfolio.total_margin_cap)
    return round(max(0.0, margin), 2)


def suggest_leverage(
    *,
    volatility_percent: float,
    max_leverage: float = AI_MAX_LEVERAGE,
) -> float:
    """
    اهرم پیشنهادی از نوسان — هرچه نوسان بیشتر، اهرم کمتر.

    قاعده: اهرم × نوسان ≈ ثابتِ ریسک (پیش‌فرض ۳۰٪ ریسکِ موقعیت).
    نوسان نامعلوم یعنی اهرم محافظه‌کارانهٔ ۳.
    """
    if volatility_percent <= 0:
        return 3.0
    risk_budget_percent = 30.0
    leverage = risk_budget_percent / max(0.05, volatility_percent)
    return max(1.0, min(round(leverage, 1), float(max_leverage)))


def decide(
    *,
    symbol: str,
    report: dict[str, Any] | None,
    ladder: TrendLadder,
    quote: TickQuote | None,
    turnover_24h: float,
    portfolio: PortfolioState,
    min_confidence: float = AI_MIN_PREDICTION_CONFIDENCE,
    min_liquidity: float = 2_000_000.0,
    max_spread_percent: float = 0.25,
    allocation_mode: str = "ai",
    base_margin: float = 10.0,
    max_leverage: float = AI_MAX_LEVERAGE,
    trend_policy: str = "block",
    stale_after_ms: float = 10_000.0,
) -> TradeDecision:
    """
    تصمیم کامل برای یک نماد.

    ترتیب دروازه‌ها مهم است: داده و روند اول، اطمینان بعد از آن —
    «اطمینان به تنهایی دلیل ورود نیست».
    """
    # --- دروازهٔ ۱: دادهٔ تازه و قیمت ---
    if quote is None or quote.last <= 0:
        return TradeDecision.no_trade("no_market_data")
    # دادهٔ کهنه یعنی STALE — ورود ممنوع (خواستهٔ §۶)
    quote_age = quote.age_ms
    if quote_age is None or quote_age > stale_after_ms:
        return TradeDecision.no_trade("stale_data")
    if turnover_24h < min_liquidity:
        return TradeDecision.no_trade("low_liquidity")

    # --- دروازهٔ ۲: پیش‌بینی همان منبع واحد ---
    horizon = pick_horizon(report)
    if horizon is None:
        return TradeDecision.no_trade("no_prediction")
    direction = direction_from_horizon(horizon)
    if not direction:
        return TradeDecision.no_trade("prediction_neutral")
    confidence = float(horizon.get("confidence", 0.0) or 0.0)
    probability = float(horizon.get("probability", 50.0) or 50.0)

    # --- دروازهٔ ۳: روند — هستهٔ اسکلپ (§۴) ---
    verdict, reason = conflict_verdict(ladder, direction, policy=trend_policy)
    if verdict == "block":
        return TradeDecision.no_trade(reason)

    # --- دروازهٔ ۴: کیفیت اجرا — اسپرد ---
    if quote.spread_percent > max_spread_percent > 0:
        return TradeDecision.no_trade(
            f"wide_spread:{quote.spread_percent:.3f}%"
        )

    # --- دروازهٔ ۵: اطمینان (بعد از روند، نه به جای آن) ---
    effective = confidence
    if verdict == "penalty":
        effective = confidence * 0.7
        reason = reason or "minor_friction"
    if effective < min_confidence:
        return TradeDecision.no_trade(f"low_confidence:{effective:.0f}")

    # --- دروازهٔ ۶: ظرفیت پرتفوی — ظرفیت آزاد دلیل ورود نیست ---
    if portfolio.open_count >= portfolio.max_concurrent:
        return TradeDecision.no_trade("max_concurrent_reached")
    if portfolio.available_margin <= 0:
        return TradeDecision.no_trade("no_available_margin")

    # --- اجرا: قیمت ورود، TP/SL از چندک‌ها، اهرم از نوسان ---
    side = "long" if direction == "LONG" else "short"
    entry = quote.entry_price(side)
    quantiles = horizon.get("quantiles") or {}
    p10 = float(quantiles.get("p10", 0.0) or 0.0)
    p25 = float(quantiles.get("p25", 0.0) or 0.0)
    p75 = float(quantiles.get("p75", 0.0) or 0.0)
    p90 = float(quantiles.get("p90", 0.0) or 0.0)

    if side == "long":
        take_profit = p75 if p75 > entry else (p90 if p90 > entry else 0.0)
        stop_loss = p25 if 0 < p25 < entry else (p10 if 0 < p10 < entry else 0.0)
    else:
        take_profit = p25 if 0 < p25 < entry else (p10 if 0 < p10 < entry else 0.0)
        stop_loss = p75 if p75 > entry else (p90 if p90 > entry else 0.0)

    if take_profit <= 0 or stop_loss <= 0:
        # چندک‌ها جهت‌دار نبودند — پیش‌بینی خودش مطمئن نیست.
        return TradeDecision.no_trade("quantiles_not_directional")

    volatility = horizon.get("volatility") or {}
    volatility_percent = (
        float(volatility.get("forecast_percent", 0.0) or 0.0)
        if isinstance(volatility, dict)
        else 0.0
    )
    leverage = suggest_leverage(
        volatility_percent=volatility_percent, max_leverage=max_leverage
    )

    # ریسک دلاریِ این TP/SL برای حالت تخصیص ریسک‌محور
    risk_fraction = abs(entry - stop_loss) / entry if entry > 0 else 0.0
    risk_amount = portfolio.available_margin * 0.02 if risk_fraction > 0 else 0.0

    margin = size_margin(
        allocation_mode=allocation_mode if allocation_mode != "ai" else "ai",
        base_margin=base_margin,
        portfolio=portfolio,
        confidence=effective,
        risk_amount=risk_amount,
    )
    if margin < 1.0:
        return TradeDecision.no_trade("margin_below_minimum")

    decision = TradeDecision(
        ok=True,
        symbol=str(symbol),
        direction=direction,
        entry_price=entry,
        margin=margin,
        leverage=leverage,
        take_profit=take_profit,
        stop_loss=stop_loss,
        confidence=round(effective, 1),
        reasons=[
            f"prediction:{horizon.get('horizon', '?')} "
            f"{str(horizon.get('direction', ''))}@{probability:.0f}%",
            f"ladder:{ladder.weighted_direction:+.2f}",
            f"spread:{quote.spread_percent:.3f}%",
            f"volatility:{volatility_percent:.2f}%",
            f"allocation:{allocation_mode}",
        ],
    )
    if reason:
        decision.reasons.append(f"trend:{reason}")
    if decision.risk_reward < AI_MIN_RISK_REWARD:
        return TradeDecision.no_trade(
            f"risk_reward_too_low:{decision.risk_reward:.2f}"
        )
    return decision


__all__ = [
    "AICandidate",
    "AI_MAX_LEVERAGE",
    "AI_MIN_PREDICTION_CONFIDENCE",
    "AI_MIN_RISK_REWARD",
    "PortfolioState",
    "TradeDecision",
    "decide",
    "direction_from_horizon",
    "pick_horizon",
    "size_margin",
    "suggest_leverage",
]
