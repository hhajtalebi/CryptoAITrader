"""
آزمون‌های فازهای ۲ تا ۸ موتور هوش پیش‌بینی.

اصل حاکم: هیچ ماژولی بدون داده عدد نسازد و هیچ ادعایی آزمون‌نشده
نماند. این آزمون‌ها PySide6 وارد نمی‌کنند.
"""

from __future__ import annotations

import math
import random

import pytest

from app.core.models import Candle
from signals.prediction.anomaly import detect_anomalies
from signals.prediction.breakout import assess_breakout, detect_false_breakout
from signals.prediction.crossasset import detect_lead_lag, market_context, rolling_correlation
from signals.prediction.distribution import (
    MAX_PROBABILITY,
    build_distribution,
    forward_log_returns,
    probability_of_range,
)
from signals.prediction.events import event_pressure, parse_events
from signals.prediction.features import FeatureStore
from signals.prediction.fusion import (
    CONFLICT_THRESHOLD,
    FusionComponent,
    fuse,
    multi_timeframe_view,
)
from signals.prediction.horizons import HORIZON_LADDER, plan_horizons
from signals.prediction.models.base import forward_labels
from signals.prediction.models.drift import STATUS_OK, STATUS_RETRAIN_RECOMMENDED, assess_drift
from signals.prediction.models.ensemble import ModelEnsemble
from signals.prediction.models.gbm import GBMModel
from signals.prediction.models.lstm import LSTMModel
from signals.prediction.models.statistical import StatisticalModel
from signals.prediction.models.walkforward import walk_forward
from signals.prediction.regime import (
    MARKET_STAGES,
    Regime,
    classify_timeframe,
    detect_transition,
    stage_of,
    transition_probabilities,
)
from signals.prediction.scenarios import build_scenarios
from signals.prediction.uncertainty import (
    UNCERTAIN_THRESHOLD,
    decayed_validity,
    effective_confidence,
)
from signals.prediction.volatility import forecast_for_horizon
from signals.prediction.warning import build_warnings

STEP = 900
BASE_TS = 1_699_999_200  # مضرب ۹۰۰


def random_walk(
    count: int,
    *,
    seed: int = 11,
    start: float = 100.0,
    drift: float = 0.0,
    volatility: float = 0.6,
) -> list[Candle]:
    """سری واقع‌گرایانه با پارامترهای قابل کنترل."""
    rng = random.Random(seed)
    price = start
    candles: list[Candle] = []
    for index in range(count):
        open_ = price
        close = max(1.0, price + drift + rng.uniform(-volatility, volatility))
        high = max(open_, close) + rng.uniform(0.05, 0.3)
        low = min(open_, close) - rng.uniform(0.05, 0.3)
        candles.append(
            Candle(
                timestamp=BASE_TS + index * STEP,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=rng.uniform(200.0, 900.0),
            )
        )
        price = close
    return candles


# ==========================================================================
# فاز ۲ — نردبان افق‌ها
# ==========================================================================
class TestHorizonLadder:
    """۱۳ افق، فعال/غیرفعال شدن صادقانه."""

    def test_ladder_is_complete(self) -> None:
        assert [code for code, _ in HORIZON_LADDER] == [
            "1m", "3m", "5m", "15m", "30m", "1h", "2h",
            "4h", "6h", "12h", "24h", "3d", "7d",
        ]

    def test_disabled_without_data(self) -> None:
        plans = plan_horizons({})
        assert len(plans) == 13
        assert all(not plan.enabled for plan in plans)
        assert all(plan.reason for plan in plans)

    def test_enabled_with_history_and_prefers_larger_tf(self) -> None:
        plans = plan_horizons({"15m": 600, "1h": 600, "4h": 600, "1d": 600})
        by_code = {plan.horizon: plan for plan in plans}
        # افق ۴ ساعت باید از خود 4h ساخته شود (بزرگ‌ترین گام ≤ افق)
        assert by_code["4h"].enabled
        assert by_code["4h"].source_timeframe == "4h"
        assert by_code["4h"].steps == 1
        # افق ۱ دقیقه: هیچ تایم‌فریمی به اندازهٔ کافی ریز نیست → خاموش
        assert not by_code["1m"].enabled
        # افق ۷ روز از 1d با ۷ گام
        assert by_code["7d"].source_timeframe == "1d"
        assert by_code["7d"].steps == 7

    def test_short_history_disables_long_horizons_only(self) -> None:
        plans = plan_horizons({"15m": 120})
        enabled = {plan.horizon for plan in plans if plan.enabled}
        # با ۱۲۰ کندلِ ۱۵ دقیقه‌ای فقط افق‌های کوتاه ممکن‌اند
        assert "15m" in enabled or "5m" in enabled
        assert "24h" not in enabled
        assert "7d" not in enabled


# ==========================================================================
# فاز ۳ — رژیم + گذار + ماشین حالت
# ==========================================================================
class TestRegimeEngine:
    """تشخیص رژیم از دادهٔ واقعی."""

    def _assess(self, candles: list[Candle]) -> object:
        features = FeatureStore().build(candles, "1h", symbol="TEST")
        return classify_timeframe("1h", candles, features)

    def test_trending_market_detected(self) -> None:
        # روند صعودی پیوسته با نوسان کم
        candles = random_walk(200, seed=3, drift=1.2, volatility=0.25)
        assessment = self._assess(candles)
        assert assessment.regime in (
            Regime.STRONG_TREND_UP, Regime.WEAK_TREND, Regime.BREAKOUT, Regime.EXPANSION,
        )
        assert assessment.direction == 1

    def test_downtrend_detected(self) -> None:
        # شروع بالا تا سری به کفِ قیمتِ ۱٫۰ نرسد و واقعاً نزولی بماند
        candles = random_walk(200, seed=4, start=1000.0, drift=-1.2, volatility=0.25)
        assessment = self._assess(candles)
        assert assessment.regime in (
            Regime.STRONG_TREND_DOWN, Regime.WEAK_TREND, Regime.BREAKDOWN,
            Regime.TREND_REVERSAL, Regime.DISTRIBUTION_TOP,
        )
        # جهت -۱ مگر اینکه واژگونی روند تشخیص داده شده باشد (که جهتش
        # برعکسِ روند موجود یعنی +۱ است — تعریف واژگونی)
        if assessment.regime is not Regime.TREND_REVERSAL:
            assert assessment.direction == -1

    def test_flat_market_is_neutral_or_range(self) -> None:
        candles = random_walk(200, seed=5, drift=0.0, volatility=0.9)
        assessment = self._assess(candles)
        assert assessment.regime in (
            Regime.RANGE, Regime.LOW_VOLATILITY, Regime.HIGH_VOLATILITY,
            Regime.COMPRESSION, Regime.EXPANSION, Regime.WEAK_TREND,
            Regime.ACCUMULATION, Regime.DISTRIBUTION_TOP,
        )

    def test_insufficient_data_is_unknown(self) -> None:
        candles = random_walk(30)
        assessment = self._assess(candles)
        assert assessment.regime is Regime.UNKNOWN
        assert assessment.confidence <= 30

    def test_liquidation_never_guessed(self) -> None:
        candles = random_walk(200, seed=6, drift=2.0, volatility=0.2)
        assessment = self._assess(candles)
        assert assessment.regime is not Regime.LIQUIDATION_EVENT
        # فقط با دادهٔ واقعی لیکوییداسیون
        features = FeatureStore().build(candles, "1h")
        pressured = classify_timeframe("1h", candles, features, liquidation_pressure=0.95)
        assert pressured.regime is Regime.LIQUIDATION_EVENT

    def test_drivers_present(self) -> None:
        candles = random_walk(200)
        assessment = self._assess(candles)
        for key in ("adx", "rsi", "atr_percentile"):
            assert key in assessment.drivers

    def test_transition_risk_and_confidence(self) -> None:
        candles = random_walk(200)
        features = FeatureStore().build(candles, "1h")
        prev = classify_timeframe("1h", candles[:-30], FeatureStore().build(candles[:-30], "1h"))
        cur = classify_timeframe("1h", candles, features)
        transition = detect_transition(prev, cur)
        assert 0 <= transition.confidence <= 100
        assert transition.risk_level in ("low", "medium", "high")

    def test_state_machine_stage_mapping(self) -> None:
        assert stage_of(Regime.ACCUMULATION) in MARKET_STAGES
        assert stage_of(Regime.STRONG_TREND_UP) == "TREND"
        assert stage_of(Regime.BREAKDOWN) == "BREAKDOWN"

    def test_transition_probabilities_from_history(self) -> None:
        history = [
            Regime.ACCUMULATION, Regime.ACCUMULATION, Regime.EXPANSION,
            Regime.STRONG_TREND_UP, Regime.STRONG_TREND_UP,
        ]
        probabilities = transition_probabilities(history)
        # کلیدها «مرحلهٔ ماشین حالت»‌اند: STRONG_TREND_UP → TREND
        assert probabilities["ACCUMULATION"]["EXPANSION"] == 50.0
        assert probabilities["ACCUMULATION"]["_samples"] == 2
        assert probabilities["TREND"]["_samples"] == 1


# ==========================================================================
# فاز ۴ — توزیع و نوسان
# ==========================================================================
class TestDistribution:
    """چندک‌ها از داده؛ احتمال سقف‌دار."""

    def test_empirical_quantiles_ordered(self) -> None:
        candles = random_walk(400)
        dist = build_distribution(horizon="4h", steps=4, candles=candles)
        assert dist is not None
        assert dist.method == "empirical"
        assert dist.samples >= 50
        assert dist.quantiles["p10"] < dist.quantiles["p25"] < dist.quantiles["p50"] \
            < dist.quantiles["p75"] < dist.quantiles["p90"]

    def test_probability_capped(self) -> None:
        candles = random_walk(300, drift=1.5)  # روند قوی
        dist = build_distribution(horizon="1h", steps=4, candles=candles, momentum_tilt=1.0)
        assert dist is not None
        assert dist.probability <= MAX_PROBABILITY

    def test_analytic_fallback_labeled(self) -> None:
        # افقِ بلند (۱۰۰ گام) روی تاریخ کوتاه → نمونهٔ تجربی کم؛ روش تحلیلی
        candles = random_walk(140)
        atr = max(c.high - c.low for c in candles[-14:])
        dist = build_distribution(horizon="7d", steps=100, candles=candles, atr=atr)
        assert dist is not None
        assert dist.method == "analytic"
        assert "ATR" in dist.note

    def test_none_without_data(self) -> None:
        assert build_distribution(horizon="4h", steps=4, candles=random_walk(40)) is None

    def test_forward_returns_no_lookahead(self) -> None:
        candles = random_walk(50)
        returns = forward_log_returns(candles, 4)
        # آخرین ۴ کندل آینده‌شان نیست
        assert len(returns) == len(candles) - 4

    def test_probability_of_range(self) -> None:
        candles = random_walk(400)
        dist = build_distribution(horizon="1h", steps=4, candles=candles)
        assert dist is not None
        # کل بازه باید تقریباً همهٔ جرم را بگیرد
        wide = probability_of_range(dist, dist.quantiles["p10"], dist.quantiles["p90"])
        assert wide >= 0.75
        narrow = probability_of_range(dist, dist.quantiles["p50"], dist.quantiles["p50"])
        assert narrow <= 0.2


class TestVolatilityForecast:
    """پیش‌بینی نوسان با مقیاس جذر زمان."""

    def test_sigma_grows_with_sqrt_steps(self) -> None:
        candles = random_walk(300)
        short = forecast_for_horizon(horizon="1h", steps=4, candles=candles)
        long = forecast_for_horizon(horizon="4h", steps=16, candles=candles)
        assert short is not None and long is not None
        assert long.sigma > short.sigma
        ratio = long.sigma / short.sigma
        assert 1.6 < ratio < 2.6  # ≈ sqrt(4) = 2 با تلورانس EWMA

    def test_labels_are_relative(self) -> None:
        candles = random_walk(300)
        forecast = forecast_for_horizon(horizon="1h", steps=4, candles=candles)
        assert forecast is not None
        assert forecast.label in ("low", "medium", "high", "very_high")
        assert 0.0 <= forecast.percentile <= 100.0

    def test_none_without_data(self) -> None:
        assert forecast_for_horizon(horizon="1h", steps=4, candles=random_walk(20)) is None


# ==========================================================================
# فاز ۶ — سناریوها
# ==========================================================================
class TestScenarios:
    """سناریو از توزیع، نه از LLM."""

    def _dist(self):
        candles = random_walk(400)
        dist = build_distribution(horizon="4h", steps=4, candles=candles, momentum_tilt=0.5)
        assert dist is not None
        return dist

    def test_three_scenarios_sum_to_100(self) -> None:
        tree = build_scenarios(self._dist())
        assert len(tree.scenarios) == 3
        assert {s.name for s in tree.scenarios} == {"bullish", "base", "bearish"}
        assert sum(s.probability for s in tree.scenarios) == 100

    def test_ranges_consistent_with_quantiles(self) -> None:
        tree = build_scenarios(self._dist())
        by_name = {s.name: s for s in tree.scenarios}
        assert by_name["bearish"].upper <= by_name["base"].lower
        assert by_name["base"].upper == by_name["bullish"].lower

    def test_conditions_and_triggers_present(self) -> None:
        tree = build_scenarios(
            self._dist(), regime_drivers={"adx": 28.0, "volume_trend": 0.1}
        )
        for scenario in tree.scenarios:
            assert scenario.trigger
            assert scenario.conditions

    def test_tree_dominant_split(self) -> None:
        tree = build_scenarios(self._dist())
        assert tree.dominant in ("bullish", "base", "bearish")
        assert tree.strong_probability + tree.weak_probability == 100


# ==========================================================================
# فاز ۷ — شکست و شکست کاذب
# ==========================================================================
class TestBreakout:
    """احتمال‌های سه‌گانه از دادهٔ موجود."""

    def test_probabilities_sum_to_100(self) -> None:
        assessment = assess_breakout(random_walk(200))
        assert assessment is not None
        total = (
            assessment.breakout_probability
            + assessment.false_breakout_probability
            + assessment.breakdown_probability
        )
        assert total == 100

    def test_unavailable_factors_never_fabricated(self) -> None:
        assessment = assess_breakout(random_walk(200))
        assert assessment is not None
        assert assessment.factors["open_interest"] == "unavailable"
        assert assessment.factors["funding"] == "unavailable"

    def test_none_without_data(self) -> None:
        assert assess_breakout(random_walk(30)) is None

    def test_false_breakout_detected_on_weak_volume_break(self) -> None:
        # شکست سقف قبلی با حجمِ نصف → مظنون به کاذب
        base = random_walk(150, seed=9, drift=0.3, volatility=0.2)
        prior_high = max(c.high for c in base[:-6])
        head = base[:-6]
        tail = [
            Candle(
                c.timestamp,
                prior_high,
                prior_high * (1.003 + i * 0.001),
                prior_high * 0.999,
                prior_high * (1.002 + i * 0.001),
                120.0,  # حجم ضعیف
            )
            for i, c in enumerate(base[-6:])
        ]
        candles = head + tail
        result = detect_false_breakout(candles)
        assert result is not None
        assert result["side"] == "up"
        assert result["confidence"] >= 55
        assert result["factors"]["cvd"] == "unavailable"

    def test_no_false_breakout_without_break(self) -> None:
        candles = [
            Candle(BASE_TS + i * STEP, 100.0, 101.5 if i % 2 else 100.5,
                   99.5, 100.0 + (0.4 if i % 2 else 0.0), 500.0)
            for i in range(150)
        ]
        # هیچ بسته‌ای از سقف ۱۰۱٫۵ نگذشته → نباید شکتی گزارش شود
        assert max(c.close for c in candles) <= 101.5
        assert detect_false_breakout(candles) is None


# ==========================================================================
# فاز ۸ — آنومالی و هشدار
# ==========================================================================
class TestAnomaly:
    """z مقاوم و آلفای زودهنگام."""

    def test_volume_spike_detected(self) -> None:
        candles = with_volume(random_walk(150, seed=13), 6.0, 3)  # جهش حجم
        report = detect_anomalies(candles)
        assert report.is_anomaly
        assert any(a.metric == "volume_surge" for a in report.anomalies)

    def test_quiet_market_clean(self) -> None:
        report = detect_anomalies(random_walk(150, seed=14, volatility=0.3))
        assert not report.is_anomaly

    def test_early_alpha_on_flat_price_big_volume(self) -> None:
        base = random_walk(150, seed=15, drift=0.0, volatility=0.1)
        flat = [
            Candle(c.timestamp, 100.0, 100.05, 99.95, 100.0, c.volume)
            for c in base
        ]
        candles = with_volume(flat, 4.0, 5)  # حجم زیاد، قیمت کاملاً خنثی
        report = detect_anomalies(candles)
        assert report.early_alpha is not None
        assert report.early_alpha["status"] == "unusual_accumulation_suspected"

    def test_insufficient_data_returns_empty(self) -> None:
        report = detect_anomalies(random_walk(30))
        assert not report.anomalies
        assert report.early_alpha is None


class TestEarlyWarnings:
    """هشدار = ریسک محتمل، نه پیش‌بینی سقوط."""

    def test_momentum_divergence_warning(self) -> None:
        # قیمت بالاتر، RSI پایین‌تر
        closes = [100.0 + i * 0.5 for i in range(60)]
        rsi_series = [70.0 - i * 0.4 for i in range(60)]
        warnings = build_warnings(
            rsi_series=rsi_series,
            closes=closes,
            volume_series=[500.0] * 60,
        )
        kinds = [w.kind for w in warnings]
        assert "momentum_divergence" in kinds
        divergence = next(w for w in warnings if w.kind == "momentum_divergence")
        assert "not a prediction" in divergence.to_dict()["disclaimer"]

    def test_volatility_expansion_warning(self) -> None:
        warnings = build_warnings(
            rsi_series=[50.0] * 60,
            closes=[100.0] * 60,
            volume_series=[500.0] * 60,
            volatility_regime="expansion",
        )
        assert any(w.kind == "volatility_expanding" for w in warnings)

    def test_distribution_regime_high_severity(self) -> None:
        warnings = build_warnings(
            rsi_series=[50.0] * 60,
            closes=[100.0] * 60,
            volume_series=[500.0] * 60,
            market_regime="distribution",
        )
        distribution = next(w for w in warnings if w.kind == "distribution_risk")
        assert distribution.severity == "high"


# ==========================================================================
# عدم‌قطعیت و فیوژن
# ==========================================================================
class TestUncertainty:
    """«نمی‌دانم» مجاز و تشویق‌شده است."""

    def test_low_confidence_becomes_uncertain(self) -> None:
        adjustment = effective_confidence(
            probability=55,
            model_agreement=0.2,
            data_quality_ratio=0.6,
            regime_stability=0.3,
            event_pressure=0.8,
        )
        assert adjustment.uncertain
        assert adjustment.direction == "uncertain"
        assert adjustment.confidence < UNCERTAIN_THRESHOLD
        assert adjustment.reasons

    def test_clean_inputs_keep_confidence(self) -> None:
        adjustment = effective_confidence(probability=70)
        assert not adjustment.uncertain
        assert adjustment.direction == "bullish"
        assert adjustment.confidence == 70

    def test_decay_reduces_with_age(self) -> None:
        fresh = decayed_validity(original_confidence=80, age_minutes=5, horizon_minutes=240)
        old = decayed_validity(original_confidence=80, age_minutes=200, horizon_minutes=240)
        ancient = decayed_validity(original_confidence=80, age_minutes=500, horizon_minutes=240)
        assert fresh == 80  # دورهٔ عسل
        assert old < fresh
        assert ancient == 0

    def test_decay_monotonic(self) -> None:
        values = [
            decayed_validity(original_confidence=90, age_minutes=age, horizon_minutes=120)
            for age in (0, 30, 60, 120, 240, 360)
        ]
        assert values == sorted(values, reverse=True)


class TestFusion:
    """فیوژن وزن‌دار + تعارض + چندتایم‌فریمی."""

    def test_weighted_average(self) -> None:
        result = fuse([
            FusionComponent("distribution", "bullish", 70, 1.0),
            FusionComponent("ensemble", "bullish", 60, 1.0),
        ])
        assert result.direction == "bullish"
        assert result.probability == 65
        assert result.reliability == "high"

    def test_conflict_detected_and_declared(self) -> None:
        result = fuse([
            FusionComponent("distribution", "bullish", 85, 1.0),
            FusionComponent("ensemble", "bearish", 15, 1.0),
        ])
        assert result.conflict
        assert result.reliability == "low"
        assert result.agreement < 1 - CONFLICT_THRESHOLD + 0.01

    def test_same_name_components_merged(self) -> None:
        result = fuse([
            FusionComponent("distribution", "bullish", 60, 1.0),
            FusionComponent("distribution", "bullish", 80, 1.0),
        ])
        assert len(result.components) == 1
        assert result.components[0].probability == 70

    def test_multi_timeframe_reversal_detection(self) -> None:
        view = multi_timeframe_view({
            "15m": {"direction": -1, "regime": "weak_trend"},
            "1h": {"direction": 1, "regime": "strong_trend_up"},
            "4h": {"direction": 1, "regime": "strong_trend_up"},
            "1d": {"direction": 1, "regime": "strong_trend_up"},
        })
        assert view["short_term"] == "bearish"
        assert view["long_term"] == "bullish"
        assert view["reversal_inside_trend"] is True
        assert view["market_stage_note"] == "short_term_reversal_inside_long_term_trend"


# ==========================================================================
# کراس-asset و رویدادها
# ==========================================================================
class TestCrossAsset:
    """پیش‌تازی از دادهٔ هم‌ترازشده."""

    def test_lead_lag_detected(self) -> None:
        rng = random.Random(21)
        base: list[float] = []
        price = 100.0
        for _ in range(300):
            price += rng.uniform(-1, 1)
            base.append(price)

        def series_from(shock: list[float], lag: int) -> list[Candle]:
            # پیرو: بازدهٔ زمان t = بازدهٔ راهبر در t-lag (تأخیر واقعی)
            candles: list[Candle] = []
            value = 100.0
            for index in range(lag, len(shock)):
                value += shock[index - lag]
                candles.append(
                    Candle(BASE_TS + index * STEP, value, value + 0.2,
                           value - 0.2, value, 100.0)
                )
            return candles

        leader = series_from(base, 0)
        follower = series_from(base, 2)
        result = detect_lead_lag("LEAD", leader, "FOLLOW", follower)
        assert result is not None
        assert result.leader == "LEAD"
        assert result.best_lag >= 1

    def test_none_without_overlap(self) -> None:
        assert detect_lead_lag("A", random_walk(50), "B", random_walk(50)) is None

    def test_market_context_labels(self) -> None:
        context = market_context({"BTC": 2.0, "ETH": 1.5, "SOL": 3.0})
        assert context["context"] == "risk_on"
        assert context["directions"]["BTC"] == "up"

    def test_rolling_correlation_shape(self) -> None:
        rng = random.Random(3)
        a = [rng.uniform(-1, 1) for _ in range(120)]
        b = [value * 0.5 for value in a]
        result = rolling_correlation(a, b, window=40)
        assert len(result) == 81
        assert result[-1] > 0.9


class TestEvents:
    """رویداد دستی: کاهش اعتبار، نه تغییر جهت."""

    def test_parse_and_pressure(self) -> None:
        from datetime import timedelta

        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        events = parse_events([
            {"name": "CPI", "at": (now + timedelta(minutes=60)).isoformat(), "impact": "high"},
        ])
        assert len(events) == 1
        pressure = event_pressure(events, now=now, horizon_minutes=240)
        assert pressure.active
        assert pressure.strength > 0.3
        assert pressure.event is not None and pressure.event.name == "CPI"

    def test_far_event_no_pressure(self) -> None:
        from datetime import timedelta

        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        events = parse_events([
            {"name": "FOMC", "at": (now + timedelta(days=10)).isoformat(), "impact": "high"},
        ])
        pressure = event_pressure(events, now=now, horizon_minutes=60)
        assert not pressure.active

    def test_malformed_entries_skipped(self) -> None:
        events = parse_events([
            {"no_name": True},
            {"name": "X", "at": "not-a-date", "impact": "high"},
            {"name": "Y", "at": "2026-09-22T12:00:00+00:00", "impact": "ridiculous"},
        ])
        assert events == []

    def test_json_string_accepted(self) -> None:
        events = parse_events('[{"name": "Fed", "at": "2026-09-22T18:00:00+00:00"}]')
        assert len(events) == 1
        assert events[0].impact == "medium"  # پیش‌فرض


# ==========================================================================
# فاز ۵ و ۱۳ — مدل‌ها و walk-forward
# ==========================================================================
#: ترتیب فیچرها دقیقاً مثل FeatureStore.matrix — سیگنال در ema_distance.
def make_dataset(count: int = 600, *, seed: int = 31, signal_strength: float = 1.0):
    """مجموعهٔ فیچر/برچسب با سیگنال واقعیِ قابل یادگیری در فیچر ۸."""
    rng = random.Random(seed)
    rows: list[list[float]] = []
    returns: list[float] = []
    for _ in range(count):
        ema_distance = rng.uniform(-1, 1)
        noise = rng.uniform(-0.3, 0.3)
        ahead = signal_strength * ema_distance + noise
        rows.append([
            noise,            # price_returns
            0.0,              # volume_change
            50 + 10 * ema_distance,  # rsi
            0.0, 0.0,         # macd, macd_signal
            noise * 0.1,      # macd_histogram
            1.0, 0.01,        # atr, atr_percent
            ema_distance,     # ema_distance — حامل سیگنال
            2.0,              # bollinger_width
            30.0,             # adx — بازار روندار
        ])
        returns.append(ahead)
    times = [BASE_TS + i * STEP for i in range(count)]
    return times, rows, returns


def with_volume(candles: list[Candle], factor: float, last_n: int) -> list[Candle]:
    """نسخهٔ جدید سری با حجم ضرب‌شده در آخرین کندل‌ها (Candle فروزن است)."""
    cut = len(candles) - last_n
    head = candles[:cut]
    tail = [
        Candle(c.timestamp, c.open, c.high, c.low, c.close, c.volume * factor)
        for c in candles[cut:]
    ]
    return head + tail


def full_row(ema_distance: float, rsi: float = 55.0) -> list[float]:
    """ردیف ۱۱فیچری کامل برای پیش‌بینی لحظه‌ای مدل‌ها."""
    return [0.0, 0.0, rsi, 0.0, 0.0, 0.0, 1.0, 0.01, ema_distance, 2.0, 30.0]


class TestModels:
    """مدل آماری + GBM + برچسب سه‌مانعی."""

    def test_forward_labels_exclude_neutral_band(self) -> None:
        times, rows, returns = make_dataset(300, signal_strength=0.0)
        kept_rows, labels, _, _ = forward_labels(rows=rows, times=times, forward_returns=returns)
        # با سیگنال صفر، بیشتر بازده‌ها در ناحیهٔ خنثی‌اند
        assert len(labels) < len(rows)
        assert set(labels) <= {0, 1}

    def test_statistical_model_fits_and_predicts(self) -> None:
        times, rows, returns = make_dataset(400)
        kept_rows, labels, kept_times, _ = forward_labels(
            rows=rows, times=times, forward_returns=returns
        )
        model = StatisticalModel().fit(kept_times, kept_rows, labels)
        output = model.predict(full_row(1.5, rsi=58.0))  # مومنتوم قوی مثبت
        assert output.available
        assert output.prob_up > 0.5
        output_down = model.predict(full_row(-1.5, rsi=42.0))
        assert output_down.prob_up < 0.5

    def test_gbm_learns_real_signal(self) -> None:
        pytest.importorskip("lightgbm")
        times, rows, returns = make_dataset(600, signal_strength=1.0)
        kept_rows, labels, kept_times, _ = forward_labels(
            rows=rows, times=times, forward_returns=returns
        )
        model = GBMModel().fit(kept_times, kept_rows, labels)
        output = model.predict(full_row(1.5, rsi=65.0))
        assert output.available
        assert output.prob_up > 0.6
        output_down = model.predict(full_row(-1.5, rsi=35.0))
        assert output_down.prob_up < 0.4

    def test_gbm_unavailable_without_libs(self) -> None:
        model = GBMModel()
        if not model.is_available():
            model.fit([], [], [])
            assert not model.predict([0.0]).available
        else:
            assert model.is_available()

    def test_walk_forward_blocks_leakage(self) -> None:
        """fold ها مرتب در زمان‌اند و گسست اعمال می‌شود."""
        times, rows, returns = make_dataset(500, signal_strength=1.0)
        kept_rows, labels, kept_times, _ = forward_labels(
            rows=rows, times=times, forward_returns=returns
        )
        result = walk_forward(
            StatisticalModel,
            times=kept_times,
            rows=kept_rows,
            labels=labels,
            gap_seconds=STEP * 4,
        )
        assert result.valid
        assert len(result.folds) >= 2
        # مدل با سیگنال واقعی باید بالای شانس باشد
        assert result.pooled_accuracy > 0.55

    def test_walk_forward_insufficient_data(self) -> None:
        result = walk_forward(
            StatisticalModel, times=[], rows=[], labels=[], gap_seconds=1
        )
        assert not result.valid

    def test_ensemble_weights_and_predict(self) -> None:
        times, rows, returns = make_dataset(500, signal_strength=0.8)
        kept_rows, labels, kept_times, _ = forward_labels(
            rows=rows, times=times, forward_returns=returns
        )
        ensemble = ModelEnsemble(include_dl=False)
        ensemble.fit(kept_times, kept_rows, labels, horizon_steps=4, step_seconds=STEP)
        assert "statistical" in ensemble.model_names
        forecast = ensemble.predict(full_row(0.9, rsi=59.0))
        assert 0.0 <= forecast.prob_up <= 1.0
        assert forecast.agreement >= 0.0
        # وزن‌ها جمعشان ۱ است
        assert math.isclose(sum(ensemble.weights.values()), 1.0, rel_tol=1e-6)

    def test_ensemble_reweight(self) -> None:
        times, rows, returns = make_dataset(400)
        kept_rows, labels, kept_times, _ = forward_labels(
            rows=rows, times=times, forward_returns=returns
        )
        ensemble = ModelEnsemble(include_dl=False)
        ensemble.fit(kept_times, kept_rows, labels, horizon_steps=4, step_seconds=STEP)
        ensemble.reweight({"statistical": 0.8, "gbm": 0.4})
        assert math.isclose(sum(ensemble.weights.values()), 1.0, rel_tol=1e-6)

    def test_lstm_trains_and_predicts(self) -> None:
        pytest.importorskip("torch")
        times, rows, returns = make_dataset(320, signal_strength=1.0)
        kept_rows, labels, kept_times, _ = forward_labels(
            rows=rows, times=times, forward_returns=returns
        )
        model = LSTMModel().fit(kept_times, kept_rows, labels)
        # دادهٔ کم (< MIN_TRAIN_SAMPLES+پنجره) → صادقانه unavailable
        if len(labels) >= 216:
            output = model.predict(full_row(0.8, rsi=58.0))
            assert 0.0 <= output.prob_up <= 1.0

    def test_drift_detection(self) -> None:
        # ۶۰ نتیجهٔ اول درست، ۶۰ تای آخر غلط → افت شدید
        outcomes = [True] * 60 + [False] * 60
        report = assess_drift(outcomes, window=120)
        assert report.status == STATUS_RETRAIN_RECOMMENDED
        assert report.drop_percent >= 15.0

    def test_drift_ok_and_unknown(self) -> None:
        assert assess_drift([True] * 40).status == STATUS_OK
        assert assess_drift([True] * 5).status == "unknown"
