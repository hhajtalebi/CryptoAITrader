"""نسخهٔ ۲.۵.۶ — اصلاحات حاصل از بازبینی عمیق (اسکالپ منفی + سیگنال اشتباه)."""

from __future__ import annotations

from collections import deque

import pytest

from app.core.constants import SignalDirection
from app.core.models import Candle
from backtest.engine import BacktestConfig, BacktestEngine, Evaluation
from backtest.market import HistoricalMarket
from signals.intelligent_decision import (
    DECISION_NO_TRADE,
    DECISION_TRADE,
    DecisionConfig,
    DecisionInputs,
    IntelligentDecisionEngine,
    exhaustion_component,
    extension_atr,
    extension_bucket,
    saturation_base,
)
from signals.learning import OutcomeRecord, PerformanceLearner, record_from_snapshot
from tests.test_v255_intelligence import _auto, _cand
from trading.micro_plan import plan_levels
from trading.scalp_scanner import ROUND_TRIP_FEE_PERCENT, score_candidate


def _inputs(tech: int, **kw) -> DecisionInputs:
    base = dict(symbol="X/USDT", direction=SignalDirection.LONG, technical_confidence=tech, primary_timeframe="1h")
    base.update(kw)
    return DecisionInputs(**base)


def _trend(n: int, *, drift: float, t0: int = 1_700_000_000, step: int = 3600) -> list[Candle]:
    out, price = [], 100.0
    for i in range(n):
        close = price * (1 + drift)
        out.append(Candle(t0 + i * step, price, max(price, close) * 1.002, min(price, close) * 0.998, close, 10.0))
        price = close
    return out


# ---------------------------------------------------------------------------
# اشباع اطمینان فنی / فرسودگی حرکت
# ---------------------------------------------------------------------------
def test_saturation_base_reflects_above_start():
    cfg = DecisionConfig()
    assert saturation_base(60, cfg) == 60
    assert saturation_base(68, cfg) == 68
    assert saturation_base(75, cfg) == 61
    assert saturation_base(85, cfg) == 51
    assert saturation_base(90, DecisionConfig(saturation_start=0)) == 90


def test_exhaustion_component_is_neutral_below_start():
    cfg = DecisionConfig()
    below = exhaustion_component(65, cfg)
    assert below.reliability == 0.0 and not below.available
    above = exhaustion_component(80, cfg)
    assert above.available and -1.0 <= above.score < 0


def test_saturated_signal_is_kept_but_not_strong():
    """اشباع سیگنال را حذف نمی‌کند (نه NO_TRADE)، فقط اطمینان/کیفیت را واقعی می‌کند."""
    engine = IntelligentDecisionEngine()
    decision = engine.evaluate(_inputs(80, regime={"regime": "trend_up", "direction": 1, "confidence": 80}))
    assert decision.decision == DECISION_TRADE
    assert decision.direction == "LONG"
    assert decision.final_confidence < 70
    assert decision.quality != "STRONG"
    assert decision.size_multiplier > 0
    assert any(c.name == "exhaustion" and c.available for c in decision.components)


def test_unsaturated_signal_unchanged_by_saturation():
    on = IntelligentDecisionEngine().evaluate(_inputs(62))
    off = IntelligentDecisionEngine(DecisionConfig(saturation_start=0)).evaluate(_inputs(62))
    assert on.final_confidence == off.final_confidence == 62
    assert on.quality == off.quality


def test_saturation_never_creates_no_trade():
    engine = IntelligentDecisionEngine()
    for tech in range(50, 101, 5):
        assert engine.evaluate(_inputs(tech)).decision != DECISION_NO_TRADE


def test_rescore_applies_saturation_to_old_snapshots():
    engine = IntelligentDecisionEngine(DecisionConfig(saturation_start=0))
    old = engine.evaluate(_inputs(80)).to_dict()  # عکس قدیمی بدون شاهد exhaustion فعال
    new = IntelligentDecisionEngine().rescore(old)
    assert new["final_confidence"] < 70
    assert new["decision"] == DECISION_TRADE
    again = IntelligentDecisionEngine().evaluate(_inputs(80)).to_dict()
    assert IntelligentDecisionEngine().rescore(again)["final_confidence"] == new["final_confidence"]


# ---------------------------------------------------------------------------
# کشیدگی حرکت + حافظهٔ الگو
# ---------------------------------------------------------------------------
def test_extension_sign_follows_direction():
    candles = _trend(80, drift=0.004)
    long_ext = extension_atr(candles, 1)
    short_ext = extension_atr(candles, -1)
    assert long_ext is not None and long_ext > 0
    assert short_ext == pytest.approx(-long_ext)
    assert extension_atr(candles[:10], 1) is None
    assert extension_bucket(None) == ""
    assert extension_bucket(0.4) == "<1"
    assert extension_bucket(1.5) == "1-2"
    assert extension_bucket(3.2) == ">=2"


def _records(extension: str, wins: int, losses: int) -> list[OutcomeRecord]:
    return [
        OutcomeRecord(direction="LONG", won=w, r_multiple=1.5 if w else -1.0, regime="trend_up", extension=extension)
        for w in [True] * wins + [False] * losses
    ]


def test_learner_uses_extension_pattern_only_with_enough_samples():
    records = _records(">=2", 8, 32) + _records("<1", 24, 16)
    learner = PerformanceLearner(min_samples=30).fit(records)
    chased = learner.historical_edge("LONG", "trend_up", "1h", extension=">=2")
    calm = learner.historical_edge("LONG", "trend_up", "1h", extension="<1")
    assert chased["reliable"] and calm["reliable"]
    assert chased["edge"] < 50 < calm["edge"]
    assert "ext:>=2" in chased["level"]
    # سطل کم‌نمونه → بازگشت به سطح جهت/رژیم (بدون حدس)
    thin = PerformanceLearner(min_samples=30).fit(_records("1-2", 3, 3) + _records("<1", 30, 30))
    fallback = thin.historical_edge("LONG", "trend_up", "1h", extension="1-2")
    assert "ext:" not in str(fallback.get("level"))


def test_record_from_snapshot_carries_extension():
    record = record_from_snapshot({"regime": "range", "extension_bucket": "1-2"}, direction="SHORT", r_multiple=-1.0)
    assert record is not None and record.extension == "1-2"


def test_annotate_extension_has_no_lookahead():
    base = _trend(24 * 12 * 12, drift=0.0003, step=300)
    market = HistoricalMarket("5m")
    market.add_symbol("A/USDT", base, ["5m", "1h"])
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.market, engine.config = market, BacktestConfig(prediction_replay=False)
    t = base[2000].timestamp + 300

    def make() -> Evaluation:
        return Evaluation(symbol="A/USDT", time=t, index=2000, base_direction="LONG", technical_confidence=60,
                          final_confidence=60, decision="TRADE", quality="NORMAL", size_multiplier=1.0,
                          stop_loss=90.0, take_profits=[110.0], risk_reward=2.0,
                          intelligence={"primary_timeframe": "1h", "regime": "trend_up"})

    first = make()
    assert engine.annotate_extension([first]) == 1
    # آیندهٔ متفاوت نباید مقدار لحظهٔ t را تغییر دهد
    crashed = base[:2001] + _trend(len(base) - 2001, drift=-0.01, t0=base[2001].timestamp, step=300)
    market2 = HistoricalMarket("5m")
    market2.add_symbol("A/USDT", crashed, ["5m", "1h"])
    engine.market = market2
    second = make()
    engine.annotate_extension([second])
    assert first.intelligence["extension_atr"] == second.intelligence["extension_atr"]
    assert first.intelligence["extension_bucket"] in ("<1", "1-2", ">=2")
    assert engine.annotate_extension([first]) == 0  # دوباره‌کاری نمی‌کند


# ---------------------------------------------------------------------------
# اسکالپ: اقتصاد صادقانه و دروازهٔ هزینه
# ---------------------------------------------------------------------------
def test_no_edge_expectancy_equals_minus_fees():
    plan = plan_levels(10, 50, 2, 2, 0.0006)
    assert plan.target_move_percent == pytest.approx(0.52)
    assert plan.stop_move_percent == pytest.approx(0.28)
    assert plan.breakeven_win_rate == pytest.approx(50.0)
    assert plan.random_win_rate == pytest.approx(35.0)
    assert plan.no_edge_expectancy == pytest.approx(-plan.round_trip_fee)
    assert set(plan.economics()) >= {"breakeven_win_rate", "random_win_rate", "no_edge_expectancy"}


class _Ticker:
    symbol = "A/USDT"
    last_price = 100.0
    turnover_24h = 50_000_000.0


def _vol_candles(range_pct: float, n: int = 40) -> list[Candle]:
    out, price = [], 100.0
    for i in range(n):
        close = price * (1 + 0.001)
        half = price * range_pct / 200.0
        out.append(Candle(1_700_000_000 + i * 300, price, price + half, price - half, close, 100.0))
        price = close
    return out


def test_cost_gate_rejects_volatility_too_small_for_costs():
    candles = _vol_candles(0.40)  # نوسان کمتر از ۳× هزینه (۰٫۱۲+۰٫۰۵)
    assert score_candidate(_Ticker(), candles, spread=0.05, min_cost_multiple=0.0) is not None
    assert score_candidate(_Ticker(), candles, spread=0.05) is None


def test_candidate_reports_breakeven_and_cost():
    candidate = score_candidate(_Ticker(), _vol_candles(1.2), spread=0.05)
    assert candidate is not None
    assert candidate.cost_percent == pytest.approx(ROUND_TRIP_FEE_PERCENT + 0.05)
    assert candidate.breakeven_win_rate > 50.0
    assert candidate.no_edge_expectancy_percent == pytest.approx(-candidate.cost_percent)
    assert any("سربه‌سر" in r for r in candidate.reasons)


# ---------------------------------------------------------------------------
# محافظ برتری منفی
# ---------------------------------------------------------------------------
def test_edge_guard_needs_samples_and_significance():
    trader = _auto(lambda: (False, "locked"), live=False)
    trader._edge_pnls = deque([-0.6] * 30 + [1.0] * 10, maxlen=500)
    assert trader._edge_guard_ok()  # هنوز کمتر از ۵۰ معامله
    trader._edge_pnls = deque([2.0, -2.0] * 40, maxlen=500)
    assert trader._edge_guard_ok()  # میانگین صفر → معنادار منفی نیست
    trader._edge_pnls = deque([2.0] * 20 + [-2.0] * 40, maxlen=500)
    assert not trader._edge_guard_ok()
    assert "برتری منفی" in trader._halted_reason
    trader.config.edge_guard_enabled = False
    assert trader._edge_guard_ok()


async def test_edge_guard_blocks_new_entries_and_resets_on_start():
    trader = _auto(lambda: (False, "locked"), live=False)
    trader._edge_pnls = deque([2.0] * 20 + [-2.0] * 40, maxlen=500)
    assert await trader.open_trade(_cand()) is None
    assert trader.rejection_reason("A/USDT") == "negative_edge"
    trader._edge_pnls = deque(maxlen=500)
    assert await trader.open_trade(_cand()) is not None


async def test_closed_trades_feed_edge_stats():
    trader = _auto(lambda: (False, "locked"), live=False)
    trade = await trader.open_trade(_cand())
    await trader.close_trade(trade, "manual")
    stats = trader.edge_stats()
    assert stats["trades"] == 1 and stats["upper95"] is None
