"""
آزمون چرخهٔ عمر پیش‌بینی: ثبت → حل → امتیاز → تایم‌لاین → موتور کامل.

قانون حیاتی ۵ همین است: پیش‌بینی ذخیره شود، با واقعیت سنجیده شود و
آمار از رکوردهای «حل‌شده» بیاید — نه از ادعا. این آزمون‌ها روی
پایگاه دادهٔ موقت واقعی (SQLite) اجرا می‌شوند و PySide6 وارد نمی‌کنند.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest

from app.database.repositories.prediction_repository import PredictionRepository
from app.core.models import Candle
from signals.prediction.engine import PredictiveIntelligenceEngine
from signals.prediction.scoring import (
    accuracy_summary,
    brier_score,
    calibration_buckets,
    model_health,
)
from signals.prediction.store import PredictionStore, price_lookup_from_candles
from signals.prediction.timeline import prediction_timeline, what_changed

STEP = 900
BASE_TS = 1_699_999_200


def make_candles(count: int, *, seed: int = 7, step: int = STEP, start: float = 500.0):
    """سری واقع‌گرایانه با روند ملایم صعودی."""
    rng = random.Random(seed)
    price = start
    candles: list[Candle] = []
    for index in range(count):
        open_ = price
        close = price + rng.uniform(-1.0, 1.3)
        high = max(open_, close) + rng.uniform(0.1, 0.4)
        low = min(open_, close) - rng.uniform(0.1, 0.4)
        candles.append(
            Candle(BASE_TS + index * step, open_, high, low, close, rng.uniform(200, 900))
        )
        price = close
    return candles


@pytest.fixture()
def repo(database) -> PredictionRepository:  # noqa: ANN001
    """مخزن پیش‌بینی روی پایگاه موقت."""
    return PredictionRepository(database)


class TestRecordAndResolve:
    """ثبت، سرآمدن، و حل با قیمت واقعی."""

    def test_record_and_due(self, repo: PredictionRepository) -> None:
        now = datetime.now(UTC)
        store = PredictionStore(repo)
        store.save_horizon(
            symbol="BTC/USDT", horizon="15m", horizon_minutes=15,
            direction="bullish", probability=65, confidence_effective=60,
            quantiles={"p10": 95, "p25": 98, "p50": 100, "p75": 102, "p90": 105},
            last_price=100.0, method="empirical", regime="weak_trend",
            model_agreement=0.8,
            created_at=now,
        )
        # هنوز سر نیامده
        assert repo.due_for_resolution(now=now) == []
        # ۲۰ دقیقه بعد: سر آمده
        due = repo.due_for_resolution(now=now + timedelta(minutes=20))
        assert len(due) == 1
        assert due[0].horizon == "15m"

    def test_resolve_bullish_correct(self, repo: PredictionRepository) -> None:
        now = datetime.now(UTC)
        candles = make_candles(50)
        store = PredictionStore(repo, price_lookup=price_lookup_from_candles(candles))
        store.save_horizon(
            symbol="BTC/USDT", horizon="1h", horizon_minutes=60,
            direction="bullish", probability=70, confidence_effective=65,
            quantiles={"p10": 480, "p25": 495, "p50": 500, "p75": 510, "p90": 520},
            last_price=500.0, method="empirical", regime="strong_trend_up",
            model_agreement=0.9,
            created_at=now - timedelta(minutes=90),
        )
        stats = store.resolve_due(now=now)
        assert stats["due"] == 1
        assert stats["resolved"] == 1
        resolved = repo.resolved(symbol="BTC/USDT")
        assert len(resolved) == 1
        record = resolved[0]
        # قیمت لحظهٔ سرآمدن از کندل‌ها آمده — نه جعل
        assert record.actual_price == pytest.approx(price_lookup_from_candles(candles)(
            "BTC/USDT", now - timedelta(minutes=30)
        ))
        assert record.direction_correct is (record.actual_price > 500.0)
        assert isinstance(record.range_correct, bool)

    def test_resolve_skips_without_price(self, repo: PredictionRepository) -> None:
        now = datetime.now(UTC)
        store = PredictionStore(repo)  # بدون price_lookup
        store.save_horizon(
            symbol="BTC/USDT", horizon="15m", horizon_minutes=15,
            direction="neutral", probability=50, confidence_effective=40,
            quantiles={"p10": 9, "p25": 9.5, "p50": 10, "p75": 10.5, "p90": 11},
            last_price=10.0, method="analytic", regime="range",
            model_agreement=0.5, created_at=now - timedelta(minutes=30),
        )
        stats = store.resolve_due(now=now)
        assert stats["skipped_no_price"] == 1
        assert stats["resolved"] == 0
        # رکورد open می‌ماند تا بعداً با قیمت واقعی حل شود
        assert repo.due_for_resolution(now=now)

    def test_neutral_judged_by_range(self, repo: PredictionRepository) -> None:
        now = datetime.now(UTC)
        # قیمت سرآمدن دقیقاً وسط بازه → neutral درست
        flat = [
            Candle(BASE_TS + i * STEP, 100.0, 100.4, 99.6, 100.0, 500.0)
            for i in range(40)
        ]
        store = PredictionStore(repo, price_lookup=price_lookup_from_candles(flat))
        store.save_horizon(
            symbol="X/USDT", horizon="1h", horizon_minutes=60,
            direction="neutral", probability=50, confidence_effective=45,
            quantiles={"p10": 99, "p25": 99.5, "p50": 100, "p75": 100.5, "p90": 101},
            last_price=100.0, method="empirical", regime="range",
            model_agreement=0.6, created_at=now - timedelta(minutes=61),
        )
        stats = store.resolve_due(now=now)
        assert stats["resolved"] == 1
        record = repo.resolved(symbol="X/USDT")[0]
        assert record.direction_correct is True  # قیمت ثابت ماند


class TestScoring:
    """دقت، بریر و کالیبراسیون از رکوردهای حل‌شده."""

    def _record(self, **overrides):
        from app.database.models import PredictionRecord

        defaults = dict(
            symbol="BTC/USDT", horizon="1h", horizon_minutes=60,
            direction="bullish", probability=70, confidence_effective=65,
            p10=95, p25=98, p50=100, p75=102, p90=105, last_price=100.0,
            method="empirical", regime="weak_trend", model_agreement=0.8,
            models=[], contributors=[], status="resolved",
            actual_price=103.0, direction_correct=True, range_correct=True,
        )
        defaults.update(overrides)
        return PredictionRecord(**defaults)

    def test_accuracy_summary(self) -> None:
        records = [self._record() for _ in range(6)] + [
            self._record(direction_correct=False) for _ in range(4)
        ]
        summary = accuracy_summary(records)
        assert summary["resolved"] == 10
        assert summary["direction_accuracy"] == 60.0
        assert summary["brier"] is not None
        assert 0 <= summary["brier"] <= 1

    def test_brier_of_perfect_forecast(self) -> None:
        records = [self._record(probability=100, actual_price=110.0) for _ in range(10)]
        assert brier_score(records) == pytest.approx(0.0, abs=0.01)

    def test_brier_of_chance_forecast(self) -> None:
        records = [self._record(probability=50, actual_price=110.0) for _ in range(10)]
        assert brier_score(records) == pytest.approx(0.25, abs=0.01)

    def test_calibration_buckets_shape(self) -> None:
        records = [self._record(probability=70) for _ in range(8)]
        buckets = calibration_buckets(records)
        assert "70-80" in buckets
        bucket = buckets["70-80"]
        assert bucket["samples"] == 8
        assert bucket["actual_rate"] == 100.0
        assert bucket["calibrated"] is False  # ۱۰۰٪ واقعی در برابر ادعای ۷۵

    def test_model_health_from_models_json(self) -> None:
        records = [
            self._record(
                models=[
                    {"name": "statistical", "prob_up": 0.9},
                    {"name": "gbm", "prob_up": 0.4},
                ],
                actual_price=110.0,  # واقعاً بالا رفت
            )
            for _ in range(10)
        ]
        health = model_health(records)
        assert health["statistical"]["accuracy"] == 100.0
        assert health["statistical"]["status"] == "good"
        assert health["gbm"]["accuracy"] == 0.0
        assert health["gbm"]["status"] == "retraining_suggested"


class TestTimeline:
    """تایم‌لاین و What-Changed."""

    def test_timeline_ordered(self) -> None:
        records = []
        base = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
        for index in range(5):
            record = self._fake(
                created_at=base + timedelta(minutes=15 * index),
                probability=55 + index,
            )
            records.append(record)
        timeline = prediction_timeline(records)
        assert len(timeline) == 5
        assert timeline[0]["probability"] == 55
        assert timeline[-1]["probability"] == 59

    def test_what_changed_detects_shift(self) -> None:
        earlier = self._fake(
            direction="bullish", probability=71,
            contributors=[{"name": "ensemble", "contribution": 15.0},
                          {"name": "volume", "contribution": 8.0}],
        )
        later = self._fake(
            direction="bullish", probability=56,
            contributors=[{"name": "ensemble", "contribution": 4.0},
                          {"name": "volume", "contribution": -6.0}],
        )
        changed = what_changed(earlier, later)
        assert changed is not None
        assert changed["probability_delta"] == -15
        assert changed["direction_changed"] is False
        factors = {f["name"]: f for f in changed["changed_factors"]}
        assert factors["ensemble"]["direction"] == "down"
        assert factors["volume"]["after"] == -6.0

    def test_what_changed_none_when_stable(self) -> None:
        record = self._fake(direction="neutral", probability=52, contributors=[])
        assert what_changed(record, self._fake(direction="neutral", probability=52,
                                               contributors=[])) is None

    @staticmethod
    def _fake(**overrides):
        from datetime import datetime as dt
        from types import SimpleNamespace

        defaults = dict(
            created_at=dt(2026, 9, 22, 10, 0), horizon="4h",
            direction="bullish", probability=65, confidence_effective=60,
            contributors=[],
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)


class TestEngineEndToEnd:
    """موتور کامل: از کندل تا گزارش + ثبت در DB."""

    @pytest.mark.asyncio
    async def test_full_assessment(self, repo: PredictionRepository) -> None:
        candle_sets = {
            "15m": make_candles(600, seed=1, step=900),
            "1h": make_candles(600, seed=2, step=3600),
            "4h": make_candles(600, seed=3, step=14400),
            "1d": make_candles(600, seed=4, step=86400),
        }

        def source(symbol: str, timeframe: str, limit: int = 600):
            return candle_sets.get(timeframe, [])

        store = PredictionStore(
            repo, price_lookup=price_lookup_from_candles(candle_sets["1h"])
        )
        engine = PredictiveIntelligenceEngine(source, store=store, include_dl=False)
        report = await engine.assess("BTC/USDT")

        assert report is not None
        assert report.last_price > 0
        # همهٔ اجزای خواستهٔ ۵۰ حاضرند
        assert report.horizons, "حداقل یک افق فعال"
        assert report.regimes and len(report.regimes) == 4
        assert report.market_stage
        assert report.multi_timeframe["per_timeframe"]
        assert report.data_quality
        assert report.contributors
        # هر افق ساختار کامل دارد (خواستهٔ ۱)
        for horizon in report.horizons:
            payload = horizon.to_dict()
            assert payload["direction"] in ("bullish", "bearish", "neutral", "uncertain")
            assert 0 <= payload["probability"] <= 100
            assert payload["quantiles"]["p10"] < payload["quantiles"]["p90"]
            assert payload["scenarios"]["scenarios"]
            assert payload["volatility"] is not None
        # افق‌های خاموش با دلیل گزارش شده‌اند
        assert report.disabled_horizons
        assert all("reason" in item for item in report.disabled_horizons)
        # ثبت در DB انجام شده (خواستهٔ ۲۳)
        records = repo.recent(symbol="BTC/USDT")
        assert records, "پیش‌بینی‌ها باید ثبت شوند"
        saved_horizons = {record.horizon for record in records}
        assert saved_horizons == {h.horizon for h in report.horizons}

        # فراخوانی دوم از کش می‌آید (فاز ۱۴ — debounce)
        cached = await engine.assess("BTC/USDT")
        assert cached is report

        # to_dict قابل serialize به JSON است (مسیر عامل AI)
        import json

        payload = report.to_dict()
        json.dumps(payload)  # نباید exception بدهد

    @pytest.mark.asyncio
    async def test_engine_returns_none_without_data(self, repo) -> None:  # noqa: ANN001
        engine = PredictiveIntelligenceEngine(
            lambda symbol, timeframe, limit=600: [], store=PredictionStore(repo),
            include_dl=False,
        )
        assert await engine.assess("EMPTY/USDT") is None

    @pytest.mark.asyncio
    async def test_no_duplicate_spam_records(self, repo: PredictionRepository) -> None:
        candle_sets = {"15m": make_candles(300, seed=5, step=900),
                       "1h": make_candles(300, seed=6, step=3600)}
        engine = PredictiveIntelligenceEngine(
            lambda symbol, timeframe, limit=600: candle_sets.get(timeframe, []),
            store=PredictionStore(repo), include_dl=False,
        )
        await engine.assess("SPAM/USDT")
        first_count = len(repo.recent(symbol="SPAM/USDT"))
        await engine.assess("SPAM/USDT", force=True)
        second_count = len(repo.recent(symbol="SPAM/USDT"))
        # نظر تغییر نکرده → نباید رکورد تکراری بگیرد
        assert second_count == first_count
