"""
نسخهٔ ۲.۵.۸ — آزمون باگ‌های شناسایی‌شده در موتور سیگنال.

B1 mean_reversion: %B در مقیاس ۰..۱۰۰ با آستانهٔ کسری (0.05/0.95) مقایسه می‌شد
B2 momentum: اندیکاتور «STOCHASTIC» (وجود ندارد؛ نام درست STOCH)
B3 volatility_regime: اندیکاتور «BOLLINGER» (وجود ندارد؛ نام درست BBANDS)
B4 تحلیل زنده روی کندل باز (repaint، ناسازگار با بک‌تست)
B5 لایهٔ هوشمند: BREAKDOWN در شاهد structure صفر بود (نامتقارن با BREAKOUT)
B6 لایهٔ هوشمند: BREAKOUT/BREAKDOWN در شاهد mtf صفر بودند
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from app.core.constants import MarketStructureType, SignalDirection, TrendDirection
from app.core.models import Candle, MarketStructure
from indicators.engine import IndicatorEngine
from indicators.registry import indicator_registry, register_builtin_indicators
from signals.engine import REQUIRED_INDICATORS, SignalEngine, closed_candles
from signals.forecast import forecast_next
from signals.intelligent_decision import (
    DecisionInputs,
    IntelligentDecisionEngine,
    structure_sign,
)
from signals.strategies.base import StrategyContext
from signals.strategies.mean_reversion import MeanReversionStrategy
from signals.strategies.momentum import MomentumStrategy
from signals.strategies.volatility_regime import VolatilityRegimeStrategy
from tests.conftest import FakeMarketEngine, make_candles

ROOT = Path(__file__).resolve().parents[1]


def _ind(**payload):
    return {name: {"signal": data.pop("signal", "NEUTRAL"), "latest": data} for name, data in payload.items()}


def _ctx(indicators, candles=None, **kw) -> StrategyContext:
    return StrategyContext(
        symbol="X/USDT", timeframe="1h", candles=candles or make_candles(80), indicators=indicators, **kw
    )


# ---------------------------------------------------------------- نام/کلید
def test_every_indicator_reference_is_computed_by_engine():
    """هر («نام»، «کلید») که راهبردها و لایهٔ هوشمند می‌خوانند باید واقعاً ساخته شود."""
    register_builtin_indicators()
    outputs = {
        name.upper(): set(indicator_registry.get_metadata(name)["outputs"])
        for name in indicator_registry._indicators
    }
    required = {name.upper() for name in REQUIRED_INDICATORS}
    files = list((ROOT / "signals" / "strategies").glob("*.py")) + [ROOT / "signals" / "intelligent_decision.py"]
    problems = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r'(?:indicator_value|_latest)\(\s*(?:analysis\s*,\s*)?"([A-Z_]+)"\s*,\s*"([a-z_]+)"', source):
            name, key = match.groups()
            if name not in required or key not in outputs.get(name, set()):
                problems.append(f"{path.name}: {name}.{key}")
        for match in re.finditer(r'(?:indicator_signal|_indicator_signal)\(\s*(?:analysis\s*,\s*)?"([A-Z_]+)"', source):
            if match.group(1) not in required:
                problems.append(f"{path.name}: signal {match.group(1)}")
    assert problems == []


# ---------------------------------------------------------------- B1
def test_percent_b_scale_is_percent():
    """%B موتور در مقیاس ۰..۱۰۰ است (پایهٔ اصلاح B1)."""
    register_builtin_indicators()
    candles = make_candles(120, noise=0.01)
    result = IndicatorEngine().calculate("BBANDS", candles, "1h")
    value = result.to_summary()["latest"]["percent_b"]
    assert value is not None and (value > 1.5 or value < -0.5 or 0 <= value <= 100)
    upper, lower = result.to_summary()["latest"]["upper"], result.to_summary()["latest"]["lower"]
    expected = (candles[-1].close - lower) / (upper - lower) * 100
    assert abs(value - expected) < 1e-6


def test_mean_reversion_mid_band_has_no_band_vote():
    """قیمت وسط باند (%B=50) نباید رأی «بالای باند بالا» بسازد (قبلاً −۰٫۲۵ SHORT)."""
    vote = MeanReversionStrategy().evaluate(_ctx(_ind(ADX={"adx": 15}, RSI={"rsi": 50}, BBANDS={"percent_b": 50.0})))
    assert not vote.applicable or vote.score == 0.0
    assert vote.direction != SignalDirection.SHORT


def test_mean_reversion_band_extremes_are_symmetric():
    above = MeanReversionStrategy().evaluate(_ctx(_ind(ADX={"adx": 15}, RSI={"rsi": 50}, BBANDS={"percent_b": 97.0})))
    below = MeanReversionStrategy().evaluate(_ctx(_ind(ADX={"adx": 15}, RSI={"rsi": 50}, BBANDS={"percent_b": 3.0})))
    assert above.direction == SignalDirection.SHORT and below.direction == SignalDirection.LONG
    assert abs(above.score + below.score) < 1e-9


def test_mean_reversion_is_not_short_biased_on_random_walks():
    """روی ۴۰ سری بی‌روند، رأی SHORT و LONG هم‌مرتبه‌اند (قبلاً ~۹۴٪ SHORT)."""
    register_builtin_indicators()
    from signals.engine import compute_timeframe_analysis

    engine = IndicatorEngine()
    longs = shorts = 0
    for seed in range(40):
        candles = make_candles(250, noise=0.006, seed=seed)
        analysis = compute_timeframe_analysis(engine, "X/USDT", "1h", candles)
        vote = MeanReversionStrategy().evaluate(
            _ctx(analysis["indicators"], candles, levels=analysis["levels"], structure=analysis["structure"])
        )
        longs += vote.direction == SignalDirection.LONG
        shorts += vote.direction == SignalDirection.SHORT
    assert shorts <= max(4, 3 * longs + 2)


# ---------------------------------------------------------------- B2
def test_momentum_reads_stoch():
    """فقط استوکاستیک صعودی (k>d، k<80) → +۰٫۲ → LONG. قبلاً N/A بود."""
    vote = MomentumStrategy().evaluate(
        _ctx(_ind(MACD={"histogram": 0.0}, RSI={"rsi": 50}, STOCH={"k": 60.0, "d": 50.0}))
    )
    assert vote.applicable and vote.direction == SignalDirection.LONG
    assert abs(vote.score - 0.2) < 1e-9


# ---------------------------------------------------------------- B3
def test_volatility_regime_reads_bbands_bandwidth():
    candles = make_candles(80, drift=0.002, noise=0.004)
    base = _ind(ATR={"atr": 0.01})
    atr = sum(c.high - c.low for c in candles[-30:]) / 30
    base["ATR"]["latest"]["atr"] = atr
    plain = VolatilityRegimeStrategy().evaluate(_ctx(base, candles, trend=TrendDirection.BULLISH))
    squeezed = dict(base, BBANDS={"signal": "NEUTRAL", "latest": {"bandwidth": 1.5}})
    boosted = VolatilityRegimeStrategy().evaluate(_ctx(squeezed, candles, trend=TrendDirection.BULLISH))
    assert abs(boosted.score - min(1.0, plain.score * 1.15)) < 1e-9
    assert any("Bollinger" in reason for reason in boosted.reasons)


# ---------------------------------------------------------------- B4
def test_closed_candles_drops_only_forming():
    now = 1_700_000_000 + 10 * 3600 + 120  # دو دقیقه پس از باز شدن کندل یازدهم
    candles = [Candle(1_700_000_000 + i * 3600, 1, 1, 1, 1, 1) for i in range(11)]
    assert len(closed_candles(candles, "1h", now=now)) == 10
    assert len(closed_candles(candles[:10], "1h", now=now)) == 10
    ms = [Candle(c.timestamp * 1000, 1, 1, 1, 1, 1) for c in candles]
    assert len(closed_candles(ms, "1h", now=now)) == 10
    assert closed_candles([], "1h") == []


def _live_series(count: int = 260, timeframe_seconds: int = 3600) -> list[Candle]:
    base = make_candles(count, noise=0.006, seed=11)
    start = int(time.time()) - (count - 1) * timeframe_seconds - 60  # کندل آخر ۶۰ ثانیه پیش باز شده
    shifted = [
        Candle(start + i * timeframe_seconds, c.open, c.high, c.low, c.close, c.volume)
        for i, c in enumerate(base)
    ]
    last = shifted[-1]
    # کندل باز با جهش شدید؛ نباید در اندیکاتورها دیده شود
    shifted[-1] = Candle(last.timestamp, last.open, last.close * 1.2, last.low, last.close * 1.15, last.volume)
    return shifted


def test_live_analysis_excludes_forming_candle_but_keeps_live_price():
    register_builtin_indicators()
    series = _live_series()
    engine = SignalEngine(FakeMarketEngine({"1h": series}), IndicatorEngine())
    analysis = asyncio.run(engine._analyze_timeframe("X/USDT", "1h"))
    assert analysis["candles"][-1].timestamp == series[-2].timestamp
    assert analysis["last_price"] == series[-1].close


def test_live_signal_is_stable_within_the_forming_candle():
    """دو جهش متفاوت در کندل باز → همان رأی‌ها (بدون repaint)."""
    register_builtin_indicators()
    series = _live_series()
    other = list(series)
    last = other[-1]
    other[-1] = Candle(last.timestamp, last.open, last.open * 1.01, last.open * 0.8, last.open * 0.85, last.volume)
    a = asyncio.run(SignalEngine(FakeMarketEngine({"1h": series}), IndicatorEngine())._analyze_timeframe("X", "1h"))
    b = asyncio.run(SignalEngine(FakeMarketEngine({"1h": other}), IndicatorEngine())._analyze_timeframe("X", "1h"))
    assert a["indicators"] == b["indicators"]
    assert a["last_price"] != b["last_price"]


def test_historical_market_is_untouched():
    """بازار تاریخی (live=False، بک‌تست) هیچ کندلی از دست نمی‌دهد."""
    register_builtin_indicators()
    series = _live_series()
    market = FakeMarketEngine({"1h": series})
    market.live = False
    analysis = asyncio.run(SignalEngine(market, IndicatorEngine())._analyze_timeframe("X", "1h"))
    assert analysis["candles"][-1].timestamp == series[-1].timestamp


def test_forecast_centres_on_live_price():
    candles = make_candles(120)
    result = forecast_next(symbol="X", timeframe="1h", candles=candles, price=candles[-1].close * 1.05)
    assert abs(result.last_price - candles[-1].close * 1.05) < 1e-9


# ---------------------------------------------------------------- B5/B6
def test_structure_sign_is_symmetric():
    assert structure_sign(MarketStructureType.BREAKOUT) == 1
    assert structure_sign(MarketStructureType.BREAKDOWN) == -1
    assert structure_sign("BULLISH") == 1 and structure_sign("BEARISH") == -1
    assert structure_sign(MarketStructureType.RANGING) == 0 and structure_sign(None) == 0


def _analysis(structure_type: MarketStructureType, trend: TrendDirection) -> dict:
    structure = MarketStructure(timeframe="1h", structure=structure_type, trend=trend)
    return {"candles": [], "indicators": {}, "structure": structure, "levels": [], "trend": trend}


def _inputs(direction, analyses, primary="1h") -> DecisionInputs:
    return DecisionInputs(
        symbol="X/USDT", direction=direction, technical_confidence=60, primary_timeframe=primary,
        total_score=0.3, analyses=analyses, votes_by_timeframe={},
    )


def test_structure_evidence_breakdown_supports_short_like_breakout_supports_long():
    engine = IntelligentDecisionEngine()
    long_score = engine._structure(
        _inputs(SignalDirection.LONG, {"1h": _analysis(MarketStructureType.BREAKOUT, TrendDirection.BULLISH)}), 1
    ).score
    short_score = engine._structure(
        _inputs(SignalDirection.SHORT, {"1h": _analysis(MarketStructureType.BREAKDOWN, TrendDirection.BEARISH)}), -1
    ).score
    assert long_score > 0.5 and abs(long_score - short_score) < 1e-9


def test_mtf_counts_breakout_structure():
    engine = IntelligentDecisionEngine()
    analyses = {
        "1h": _analysis(MarketStructureType.RANGING, TrendDirection.NEUTRAL),
        "4h": _analysis(MarketStructureType.BREAKDOWN, TrendDirection.NEUTRAL),
    }
    component, _ = engine._mtf(_inputs(SignalDirection.SHORT, analyses), -1)
    assert abs(component.score - 0.35) < 1e-9


def test_closed_candles_accepts_datetime_and_never_raises():
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc)
    candles = [Candle(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i), 1, 1, 1, 1, 1) for i in range(11)]
    assert len(closed_candles(candles, "1h", now=now.timestamp())) == 10
    broken = [Candle("not-a-time", 1, 1, 1, 1, 1)]
    assert closed_candles(broken, "1h") == broken
    assert closed_candles(candles, "not-a-timeframe") == candles
