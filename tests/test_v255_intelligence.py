"""آزمون‌های نسخهٔ ۲.۵.۵ — لایهٔ هوشمند سیگنال، بک‌تست، دروازهٔ اعتبارسنجی."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace as NS

import pytest

from app.core.constants import SignalDirection
from app.core.models import Candle, RiskParameters
from backtest.data import resample
from backtest.execution import ExecutionModel, TradeResult, simulate_trade
from backtest.market import HistoricalMarket
from backtest.metrics import by_key, calibration, summarize
from backtest.walk_forward import make_folds
from signals.intelligent_decision import (
    DECISION_NO_TRADE,
    DECISION_TRADE,
    DecisionInputs,
    IntelligentDecisionEngine,
    eligibility_confidence,
    resolve_direction,
)
from signals.learning import OutcomeRecord, PerformanceLearner, wilson_interval
from signals.orderflow import (
    build_snapshot,
    cvd_slope,
    orderbook_imbalance,
    series_for_features,
)
from trading.auto_trader import LIVE_CONFIRMATION_PHRASE, AutoTradeConfig, AutoTrader
from trading.scalp_scanner import ScalpCandidate, apply_direction_evidence
from trading.validation_gate import ValidationGate, summarize_pnls


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------
def _candles(n: int, *, start: float = 100.0, drift: float = 0.0, step: int = 300, t0: int = 1_700_000_100) -> list[Candle]:
    t0 = t0 - t0 % step
    out = []
    price = start
    for i in range(n):
        open_ = price
        close = price * (1 + drift)
        high = max(open_, close) * 1.001
        low = min(open_, close) * 0.999
        out.append(Candle(t0 + i * step, open_, high, low, close, 10.0 + i % 3))
        price = close
    return out


def _prediction(direction: str, probability: int, *, confidence: int = 80, agreement: float = 0.9) -> dict:
    return {"horizons": [{
        "horizon": "3h", "minutes": 180, "direction": direction, "probability": probability,
        "confidence": confidence, "model_agreement": agreement,
    }]}


def _frame(trend: str) -> dict:
    return {"trend": trend, "structure": None}


def _inputs(**kw) -> DecisionInputs:
    base = dict(symbol="X/USDT", direction=SignalDirection.LONG, technical_confidence=65, primary_timeframe="1h")
    base.update(kw)
    return DecisionInputs(**base)


# ---------------------------------------------------------------------------
# جریان سفارش
# ---------------------------------------------------------------------------
def test_cvd_slope_positive_when_closes_near_highs():
    candles = [Candle(i * 300, 100, 101, 99, 100.9, 10) for i in range(30)]
    assert cvd_slope(candles, 20) > 0.5
    bearish = [Candle(i * 300, 100, 101, 99, 99.1, 10) for i in range(30)]
    assert cvd_slope(bearish, 20) < -0.5


def test_cvd_slope_needs_enough_candles():
    assert cvd_slope(_candles(5), 20) is None


def test_orderbook_imbalance_handles_levels_and_missing():
    book = NS(bids=[(100, 3.0), (99, 1.0)], asks=[(101, 1.0)])
    value = orderbook_imbalance(book)
    assert value is not None and value > 0.4
    assert orderbook_imbalance(None) is None


def test_snapshot_marks_missing_futures_data_unavailable():
    snap = build_snapshot(_candles(30))
    assert snap.available and snap.proxy
    assert "funding_rate" in snap.unavailable and "orderbook_imbalance" in snap.unavailable
    assert snap.reliability() == 0.5
    empty = build_snapshot([])
    assert not empty.available and empty.reliability() == 0.0
    assert json.dumps(empty.to_dict())


def test_feature_series_match_candle_length():
    candles = _candles(40)
    series = series_for_features(candles, futures_series={"funding_rate": [0.0] * 39})
    assert len(series["cvd"]) == len(series["volume_delta"]) == 40
    assert "funding_rate" not in series  # طول نادرست کنار گذاشته می‌شود


# ---------------------------------------------------------------------------
# یادگیرنده / حافظهٔ الگو
# ---------------------------------------------------------------------------
def test_three_losses_do_not_create_a_block():
    learner = PerformanceLearner().fit(
        [OutcomeRecord("LONG", False, -1.0, regime="trend_up", timeframe="1h") for _ in range(3)]
    )
    edge = learner.historical_edge("LONG", "trend_up", "1h")
    assert edge["edge"] == 50 and edge["reliable"] is False
    assert learner.strategy_multiplier("trend", "trend_up") == 1.0
    assert learner.health()["status"] == "learning"


def test_learner_edge_is_bounded_and_shrunk():
    records = [OutcomeRecord("LONG", True, 2.0, regime="trend_up", timeframe="1h",
                             strategy_scores={"trend": 0.8}) for _ in range(60)]
    records += [OutcomeRecord("LONG", False, -1.0, regime="trend_up", timeframe="1h",
                              strategy_scores={"meanrev": 0.8}) for _ in range(40)]
    learner = PerformanceLearner().fit(records)
    edge = learner.historical_edge("LONG", "trend_up", "1h")
    assert edge["reliable"] and 50 < edge["edge"] <= 90
    low, high = learner.bounds
    for value in learner.multipliers_for("trend_up").values():
        assert low <= value <= high
    assert learner.strategy_multiplier("trend", "trend_up") > learner.strategy_multiplier("meanrev", "trend_up")
    assert learner.health()["status"] == "ok"


def test_wilson_interval_contains_rate():
    low, high = wilson_interval(6, 10)
    assert 0 < low < 0.6 < high < 1


# ---------------------------------------------------------------------------
# تصمیم هوشمند
# ---------------------------------------------------------------------------
def test_supportive_evidence_raises_confidence_and_keeps_direction():
    engine = IntelligentDecisionEngine()
    decision = engine.evaluate(_inputs(
        prediction=_prediction("bullish", 70),
        analyses={"1h": {}, "4h": _frame("BULLISH"), "1d": _frame("BULLISH")},
        regime={"regime": "trend_up", "direction": 1, "confidence": 80},
        history={"edge": 70, "samples": 120, "reliable": True},
        risk_reward=2.5,
    ))
    assert decision.decision == DECISION_TRADE
    assert decision.direction == "LONG"
    assert decision.final_confidence > decision.technical_confidence
    assert decision.quality in ("STRONG", "NORMAL")
    assert decision.prediction_probability == 70


def test_moderate_opposition_lowers_confidence_but_keeps_signal():
    engine = IntelligentDecisionEngine()
    decision = engine.evaluate(_inputs(
        prediction=_prediction("bearish", 60, confidence=50),
        analyses={"1h": {}, "4h": _frame("BEARISH")},
    ))
    assert decision.decision == DECISION_TRADE
    assert decision.direction == "LONG"
    assert decision.final_confidence < decision.technical_confidence
    assert decision.size_multiplier > 0


def test_no_trade_only_on_severe_conflict():
    engine = IntelligentDecisionEngine()
    decision = engine.evaluate(_inputs(
        prediction=_prediction("bearish", 80),
        analyses={"1h": {}, "4h": _frame("BEARISH"), "1d": _frame("BEARISH")},
        regime={"regime": "trend_down", "direction": -1, "confidence": 90},
        history={"edge": 15, "samples": 200, "reliable": True},
        risk_reward=0.8,
    ))
    assert decision.decision == DECISION_NO_TRADE
    assert decision.size_multiplier == 0.0
    assert decision.weak_reason
    assert decision.base_direction == "LONG"  # سیگنال پایه برای نمایش حفظ می‌شود


def test_missing_evidence_is_neutral_not_a_penalty():
    decision = IntelligentDecisionEngine().evaluate(_inputs())
    assert decision.decision == DECISION_TRADE
    assert decision.final_confidence == decision.technical_confidence
    assert decision.historical_edge == 50


def test_wait_passes_through_untouched():
    decision = IntelligentDecisionEngine().evaluate(_inputs(direction=SignalDirection.WAIT))
    assert decision.decision == "WAIT" and decision.size_multiplier == 0.0


def test_rescore_matches_evaluate():
    engine = IntelligentDecisionEngine()
    decision = engine.evaluate(_inputs(
        prediction=_prediction("bullish", 65),
        analyses={"1h": {}, "4h": _frame("BEARISH")},
        regime={"regime": "range", "direction": 0, "confidence": 60},
    ))
    snapshot = decision.to_dict()
    again = engine.rescore(snapshot)
    assert again["decision"] == decision.decision
    assert again["quality"] == decision.quality
    assert abs(again["final_confidence"] - decision.final_confidence) <= 1


def test_eligibility_uses_technical_confidence():
    signal = NS(confidence=48, intelligence={"technical_confidence": 72})
    assert eligibility_confidence(signal) == 72
    assert eligibility_confidence(NS(confidence=61, intelligence=None)) == 61


def test_resolve_direction_needs_margin():
    assert resolve_direction({"a": 0.5, "b": 0.3})[0] == SignalDirection.LONG
    assert resolve_direction({"a": -0.6})[0] == SignalDirection.SHORT
    assert resolve_direction({"a": 0.5, "b": -0.5})[0] == SignalDirection.WAIT
    assert resolve_direction({})[0] == SignalDirection.WAIT


# ---------------------------------------------------------------------------
# یکپارچگی با موتور سیگنال (همان ۷ مؤلفه؛ فقط غنی‌سازی)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_signal_engine_attaches_intelligence_without_changing_direction(risk_parameters: RiskParameters):
    from indicators import IndicatorEngine
    from signals import RiskEngine, SignalEngine
    from tests.conftest import FakeMarketEngine, make_candles

    data = {tf: make_candles(drift=0.006, seed=s, volume_spike_at_end=True)
            for tf, s in (("1d", 1), ("4h", 2), ("1h", 3))}
    plain = SignalEngine(FakeMarketEngine(data), IndicatorEngine(), RiskEngine(risk_parameters))
    smart = SignalEngine(FakeMarketEngine(data), IndicatorEngine(), RiskEngine(risk_parameters))
    smart.set_intelligence(IntelligentDecisionEngine())
    base = await plain.generate("TEST/USDT", ["1d", "4h", "1h"])
    enriched = await smart.generate("TEST/USDT", ["1d", "4h", "1h"])
    assert base.direction == SignalDirection.LONG
    assert base.intelligence is None or base.intelligence == {}
    intel = enriched.intelligence
    assert intel and intel["decision"] in ("TRADE", "NO_TRADE")
    assert intel["technical_confidence"] == base.confidence
    if intel["decision"] == "TRADE":
        assert enriched.direction == SignalDirection.LONG
        assert enriched.confidence == intel["final_confidence"]
    assert eligibility_confidence(enriched) == base.confidence
    assert "intelligence" in enriched.to_dict()


# ---------------------------------------------------------------------------
# بک‌تست: بدون look-ahead، هزینه‌ها، معیارها، walk-forward
# ---------------------------------------------------------------------------
def test_resample_keeps_only_complete_buckets():
    base = _candles(14, step=300, t0=3600 * 1000)  # ۱۴ کندل ۵ دقیقه
    hourly = resample(base, "5m", "1h")
    assert len(hourly) == 1
    assert hourly[0].open == base[0].open and hourly[0].close == base[11].close


def test_historical_market_never_leaks_future_candles():
    base = _candles(200, step=300, t0=3600 * 1000)
    market = HistoricalMarket("5m")
    market.add_symbol("X/USDT", base, ["5m", "15m", "1h"])
    now = base[100].timestamp  # لحظهٔ باز شدن کندل ۱۰۰
    market.set_time(now)
    for timeframe, step in (("5m", 300), ("15m", 900), ("1h", 3600)):
        visible = asyncio.run(market.get_candles("X/USDT", timeframe, 500))
        assert visible, timeframe
        # کندل در حال شکل‌گیری فقط از کندل‌های پایهٔ بسته‌شده ساخته می‌شود
        assert all(c.timestamp < now for c in visible)
        closed = market.candle_source("X/USDT", timeframe, 500)
        assert all(c.timestamp + step <= now for c in closed)
    last_5m = asyncio.run(market.get_candles("X/USDT", "5m", 1))[-1]
    assert last_5m.timestamp == base[99].timestamp


def test_simulated_trade_charges_costs_and_is_pessimistic():
    future = [Candle(i * 300, 100, 103, 98, 101, 1) for i in range(5)]  # هر دو SL و TP در یک کندل
    trade = simulate_trade(symbol="X", direction="LONG", signal_time=0, stop_loss=99.0,
                           take_profits=[102.0, 104.0, 106.0], future=future,
                           model=ExecutionModel(), max_bars=5)
    assert trade is not None and trade.exit_reason == "stop" and trade.r_multiple < -1.0
    free = ExecutionModel(fee_percent=0, spread_percent=0, slippage_percent=0)
    clean = [Candle(0, 100, 100.5, 99.5, 100, 1)] + [Candle(i * 300, 101, 106.5, 100.5, 106, 1) for i in range(1, 4)]
    win = simulate_trade(symbol="X", direction="LONG", signal_time=0, stop_loss=99.0,
                         take_profits=[102.0, 104.0, 106.0], future=clean, model=free, max_bars=5)
    assert win.exit_reason == "target" and win.targets_hit == 3 and win.r_multiple == pytest.approx(4.0)
    costly = simulate_trade(symbol="X", direction="LONG", signal_time=0, stop_loss=99.0,
                            take_profits=[102.0, 104.0, 106.0], future=clean, model=ExecutionModel(), max_bars=5)
    assert costly.r_multiple < win.r_multiple


def test_entry_refused_when_open_already_past_stop():
    future = [Candle(0, 98.5, 99, 98, 98.7, 1)]
    assert simulate_trade(symbol="X", direction="LONG", signal_time=0, stop_loss=99.0,
                          take_profits=[102.0], future=future, model=ExecutionModel(), max_bars=5) is None


def _trade(r: float, t: int, **meta) -> TradeResult:
    return TradeResult("X", "LONG", t, t, t + 1, 100.0, 99.0, "target" if r > 0 else "stop", r, r, 0.12, 3, -0.5, 0.8,
                       1 if r > 0 else 0, meta=meta)


def test_metrics_summary_profit_factor_and_drawdown():
    trades = [_trade(2.0, 1), _trade(-1.0, 2), _trade(-1.0, 3), _trade(2.0, 4)]
    s = summarize(trades)
    assert s["trades"] == 4 and s["win_rate"] == 50.0
    assert s["profit_factor"] == pytest.approx(2.0)
    assert s["expectancy_r"] == pytest.approx(0.5)
    assert s["total_r"] == pytest.approx(2.0)
    assert s["max_drawdown_percent"] > 0
    assert summarize([])["trades"] == 0


def test_calibration_and_grouping_keys():
    trades = [_trade(1.0 if i % 3 else -1.0, i, final_confidence=60 + (i % 3) * 10, quality="NORMAL") for i in range(40)]
    cal = calibration(trades)
    assert cal["samples"] == 40 and cal["brier"] is not None and "roughly_monotonic" in cal
    assert set(by_key(trades, "quality")) == {"NORMAL"}


def test_walk_forward_test_windows_do_not_overlap():
    day = 86_400
    folds = make_folds(0, 20 * day, train_days=8, val_days=4, test_days=2)
    assert len(folds) >= 3
    for fold in folds:
        assert fold.train[1] == fold.validation[0] and fold.validation[1] == fold.test[0]
    tests = [f.test for f in folds]
    assert all(a[1] <= b[0] for a, b in zip(tests, tests[1:]))


# ---------------------------------------------------------------------------
# اسکالپ: جهت فقط از مومنتوم نیست
# ---------------------------------------------------------------------------
def _scalp(direction: str = "LONG") -> ScalpCandidate:
    return ScalpCandidate(symbol="X/USDT", price=100.0, score=80.0, direction=direction,
                          volatility_5m=0.5, turnover_24h=5e7, spread_percent=0.02, momentum=0.4)


def test_scalp_direction_follows_multi_timeframe_evidence():
    down = {tf: _candles(80, drift=-0.003, step=s) for tf, s in (("5m", 300), ("15m", 900), ("1h", 3600))}
    candidate = apply_direction_evidence(_scalp("LONG"), down)
    assert candidate.direction == "SHORT"
    assert candidate.direction_source == "evidence" and candidate.evidence


def test_scalp_without_evidence_is_kept_and_marked_low_conviction():
    candidate = apply_direction_evidence(_scalp("LONG"), {})
    assert candidate.direction == "LONG"
    assert candidate.direction_source == "momentum_low_conviction"
    assert candidate.score == pytest.approx(56.0)


# ---------------------------------------------------------------------------
# دروازهٔ اعتبارسنجی
# ---------------------------------------------------------------------------
_GOOD_REPORT = {
    "full_period": {
        "new": {"trades": 400, "profit_factor": 1.4, "expectancy_r": 0.12, "max_drawdown_percent": 9.0},
        "calibration_new_final": {"brier": 0.23, "roughly_monotonic": True},
    },
    "walk_forward": {"p1": {"folds": [{}, {}, {}], "test_total": {"new_tuned_learning": {
        "trades": 90, "profit_factor": 1.2, "total_r": 6.0}}}},
}
_GOOD_PAPER = {"trades": 150, "profit_factor": 1.3, "max_drawdown_percent": 6.0}
_GOOD_LEARNER = {"records": 150, "status": "ok"}
_GOOD_RISK = {"max_loss_set": True, "daily_limit_set": True}


def test_gate_is_locked_by_default(tmp_path):
    gate = ValidationGate(tmp_path / "gate.json")
    allowed, reason = gate.live_allowed()
    assert not allowed and "backtest" in reason


def test_gate_passes_only_with_all_evidence(tmp_path):
    gate = ValidationGate(tmp_path / "gate.json")
    gate.record_backtest_report(_GOOD_REPORT)
    status = gate.evaluate(paper=_GOOD_PAPER, learner=_GOOD_LEARNER, risk=_GOOD_RISK)
    assert status.passed, status.reason
    # شواهد ذخیره می‌شوند و پس از ساخت دوباره هم هستند
    reloaded = ValidationGate(tmp_path / "gate.json")
    assert reloaded.evaluate(paper=_GOOD_PAPER, learner=_GOOD_LEARNER, risk=_GOOD_RISK).passed
    for broken in ({"paper": {"trades": 20, "profit_factor": 2.0, "max_drawdown_percent": 1.0}},
                   {"learner": {"records": 10, "status": "learning"}},
                   {"risk": {"max_loss_set": True}}):
        kwargs = {"paper": _GOOD_PAPER, "learner": _GOOD_LEARNER, "risk": _GOOD_RISK, **broken}
        assert not gate.evaluate(**kwargs).passed


def test_gate_corrupt_file_stays_locked(tmp_path):
    path = tmp_path / "gate.json"
    path.write_text("{not json", encoding="utf-8")
    assert not ValidationGate(path).evaluate(paper=_GOOD_PAPER, learner=_GOOD_LEARNER, risk=_GOOD_RISK).passed


def test_summarize_pnls_drawdown():
    stats = summarize_pnls([10.0, -20.0, 5.0])
    assert stats["trades"] == 3 and stats["max_drawdown_percent"] > 0


# ---------------------------------------------------------------------------
# معامله‌گر خودکار: قفل live → ثبت کاغذی؛ ضریب اندازه
# ---------------------------------------------------------------------------
class _Repo:
    def __init__(self):
        self.rows = []

    def open_trade(self, **kwargs):
        row = dict(kwargs, id=len(self.rows) + 1, status="open")
        self.rows.append(row)
        return row

    def close_trade(self, tid, *, exit_price, fee, **kwargs):
        row = self.rows[tid - 1]
        row.update(status="closed", exit_price=exit_price, pnl=0.0)
        return row

    def open_trades(self, _user_id=None):
        return [r for r in self.rows if r["status"] == "open"]

    def update_live_pnl(self, *_a, **_k):
        pass

    def update_protection(self, *_a, **_k):
        pass


class _Gateway:
    def __init__(self):
        self.opened = []
        self.closed = []

    async def open_position(self, **kwargs):
        self.opened.append(kwargs)
        return {"ok": True}

    async def close_position(self, **kwargs):
        self.closed.append(kwargs)
        return {"ok": True}


def _auto(gate, *, live=True, repo=None, gateway=None):
    async def price(_symbol):
        return 100.0

    def portfolio():
        return {"balance": 1000.0, "used_margin": 0.0, "available_margin": 1000.0, "open_count": 0}

    config = AutoTradeConfig(
        engine_mode="ultra", margin_per_trade=10, leverage=10, target_profit=2, max_loss=2,
        max_concurrent=10, fee_rate=0.0006, slippage_percent=0, min_liquidity=0,
        max_total_margin_percent=100, daily_loss_limit=10_000,
        mode="live" if live else "paper",
        live_confirmation=LIVE_CONFIRMATION_PHRASE if live else "",
    )
    return AutoTrader(config=config, price_source=price, repository=repo or _Repo(),
                      gateway=gateway, portfolio_source=portfolio, live_gate=gate)


def _cand(symbol="A/USDT", **extra):
    return NS(symbol=symbol, direction="LONG", score=80.0, price=100.0, take_profit=0.0, stop_loss=0.0,
              observed_at=time.time(), **extra)


async def test_locked_gate_records_paper_and_never_calls_gateway():
    repo, gateway = _Repo(), _Gateway()
    trader = _auto(lambda: (False, "backtest: not validated"), repo=repo, gateway=gateway)
    trade = await trader.open_trade(_cand())
    assert trade is not None and trade.mode == "paper"
    assert repo.rows[0]["mode"] == "paper"
    assert gateway.opened == []
    assert "backtest" in trader.live_gate_reason
    await trader.close_trade(trade, "manual")
    assert gateway.closed == []  # بستن ورود کاغذی هرگز سفارش واقعی نمی‌فرستد


async def test_gate_error_counts_as_locked():
    def broken():
        raise RuntimeError("boom")

    trader = _auto(broken, gateway=_Gateway())
    assert trader.live_execution_allowed() is False
    assert "boom" in trader.live_gate_reason


async def test_open_gate_allows_live_path():
    gateway = _Gateway()
    trader = _auto(lambda: (True, ""), gateway=gateway)
    assert trader.live_execution_allowed() is True
    trade = await trader.open_trade(_cand())
    assert trade is not None and trade.mode == "live" and len(gateway.opened) == 1


async def test_paper_mode_ignores_gate_entirely():
    calls = []
    trader = _auto(lambda: calls.append(1) or (True, ""), live=False)
    assert trader.live_execution_allowed() is False and calls == []


async def test_size_multiplier_scales_margin_and_is_clamped():
    repo = _Repo()
    trader = _auto(None, live=False, repo=repo)
    full = await trader.open_trade(_cand("A/USDT"))
    half = await trader.open_trade(_cand("B/USDT", size_multiplier=0.5, quality="WEAK", intelligence={"quality": "WEAK"}))
    tiny = await trader.open_trade(_cand("C/USDT", size_multiplier=0.01))
    assert full and half and tiny
    q = {r["symbol"]: r["quantity"] for r in repo.rows}
    assert q["B/USDT"] == pytest.approx(q["A/USDT"] * 0.5, rel=0.02)
    assert q["C/USDT"] == pytest.approx(q["A/USDT"] * 0.25, rel=0.02)
    extra = repo.rows[1].get("extra") or {}
    assert extra.get("quality") == "WEAK" and extra.get("size_multiplier") == 0.5


# ---------------------------------------------------------------------------
# منبع نامزد: صلاحیت با اطمینان فنی، امتیاز با نهایی
# ---------------------------------------------------------------------------
def test_confidence_candidate_carries_quality_fields():
    from trading.confidence_source import ConfidenceCandidate

    names = set(ConfidenceCandidate.__dataclass_fields__)
    assert {"quality", "size_multiplier", "intelligence"} <= names


# ---------------------------------------------------------------------------
# داشبورد کیفیت سیگنال (UI)
# ---------------------------------------------------------------------------
_INTEL = {
    "decision": "TRADE", "quality": "WEAK", "base_direction": "LONG", "technical_confidence": 68,
    "final_confidence": 52, "prediction_probability": 41, "mtf_alignment": 30, "regime": "range",
    "regime_score": 45, "historical_edge": 50, "historical_samples": 4, "size_multiplier": 0.5,
    "weak_reason": "prediction: bearish 59%",
}


def test_quality_rows_show_all_fields_and_weak_reason():
    pytest.importorskip("PySide6")
    from localization import Translator
    from ui.dialogs.signal_detail_dialog import quality_rows

    rows = quality_rows({"direction": "LONG", "risk_reward": 2.1}, _INTEL, Translator("en"))
    text = {label: value for label, value, _tone in rows}
    assert text["Technical confidence"] == "68%" and text["Final confidence"] == "52%"
    assert text["Prediction probability"] == "41%" and text["R/R"] == "2.10"
    assert text["Quality"] == "WEAK" and "bearish" in text["Why weak"]
    assert text["Position size"] == "×0.50"


def test_detail_dialog_builds_quality_card(qt_application):
    from PySide6.QtWidgets import QFrame

    from localization import Translator
    from ui.dialogs.signal_detail_dialog import SignalDetailDialog

    signal = {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 52, "entry_price": 100.0,
              "stop_loss": 98.0, "take_profits": [104.0], "risk_reward": 2.0, "intelligence": _INTEL}
    dialog = SignalDetailDialog(signal, Translator("fa"))
    assert dialog.findChild(QFrame, "signalQualityCard") is not None
    dialog.deleteLater()
    plain = SignalDetailDialog({k: v for k, v in signal.items() if k != "intelligence"}, Translator("fa"))
    assert plain.findChild(QFrame, "signalQualityCard") is None  # سیگنال قدیمی بدون تغییر
    plain.deleteLater()


def test_share_text_includes_quality():
    from ui.signal_share import format_signal_text

    text = format_signal_text({"symbol": "BTC/USDT", "direction": "LONG", "confidence": 52, "intelligence": _INTEL})
    assert "WEAK" in text and "68" in text


def test_quality_keys_exist_in_both_languages():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "localization"
    fa = json.loads((root / "fa" / "signals.json").read_text(encoding="utf-8"))["quality"]
    en = json.loads((root / "en" / "signals.json").read_text(encoding="utf-8"))["quality"]
    assert set(fa) == set(en) and "weak_reason" in fa
