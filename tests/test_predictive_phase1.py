"""
آزمون‌های فاز ۱ موتور هوش پیش‌بینی: کیفیت داده + خزانهٔ فیچر.

اصل حاکم (قانون‌های حیاتی ۲ و ۳ سند docs/PREDICTIVE_ENGINE_FA.md):
    • دادهٔ خراب باید **دیده** شود، نه اینکه بی‌صدا وارد مدل شود.
    • هیچ فیچری حق ندارد زودتر از «زمان بسته‌شدن کندلش» قابل مصرف باشد.
    • ردیف ناقص حذف می‌شود، هرگز با عدد ساختگی پر نمی‌شود.

این آزمون‌ها عمداً PySide6 import نمی‌کنند (قاعدهٔ پروژه).
"""

from __future__ import annotations

import math
import random

import pytest

from app.core.models import Candle
from market.quality import (
    CLOCK_SKEW_TOLERANCE,
    IssueKind,
    Severity,
    clean_candles,
    inspect_candles,
)
from signals.prediction.features import FeatureStore, FeatureVector

STEP = 900  # 15m
# مضرب ۹۰۰ تا همهٔ کندل‌های استاندارد روی شبکهٔ تایم‌فریم تراز باشند
BASE_TS = 1_699_999_200


def make_candle(
    index: int,
    price: float = 100.0,
    *,
    spread: float = 1.0,
    volume: float = 500.0,
    timestamp: int | None = None,
) -> Candle:
    """کندل سالم استاندارد؛ انحراف‌ها با آرگومان اعمال می‌شوند."""
    ts = BASE_TS + index * STEP if timestamp is None else timestamp
    return Candle(
        timestamp=ts,
        open=price,
        high=price + spread,
        low=price - spread,
        close=price,
        volume=volume,
    )


def random_walk(count: int, *, seed: int = 7, start: float = 100.0) -> list[Candle]:
    """سری واقع‌گرایانه با حرکت تصادفی — برای فیچرها بهتر از سری صاف است."""
    rng = random.Random(seed)
    price = start
    candles: list[Candle] = []
    for i in range(count):
        drift = rng.uniform(-0.6, 0.6)
        open_ = price
        close = max(1.0, price + drift)
        high = max(open_, close) + rng.uniform(0.05, 0.4)
        low = min(open_, close) - rng.uniform(0.05, 0.4)
        candles.append(
            Candle(
                timestamp=BASE_TS + i * STEP,
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
# موتور کیفیت داده
# ==========================================================================
class TestDataQualityDetectsProblems:
    """هر عیب رایج باید کشف و شمرده شود."""

    def test_empty_input_is_critical(self) -> None:
        report = inspect_candles([], "15m")
        assert not report.usable
        assert report.issues[0].kind is IssueKind.EMPTY
        assert report.issues[0].severity is Severity.CRITICAL

    def test_duplicate_timestamps_counted(self) -> None:
        candles = [make_candle(i) for i in range(10)]
        candles.append(make_candle(3, price=111.0))  # تکراری با قیمت متفاوت
        report = inspect_candles(candles, "15m")
        assert report.duplicates == 1
        assert report.checked == 11

    def test_gap_between_candles_detected(self) -> None:
        candles = [make_candle(i) for i in range(10)]
        candles += [make_candle(i) for i in range(13, 20)]  # سه کندل گم
        report = inspect_candles(candles, "15m")
        assert report.missing == 3
        assert report.gap_ranges[0]["missing"] == 3

    def test_invalid_ohlc_flagged(self) -> None:
        bad = Candle(timestamp=BASE_TS, open=100, high=99, low=98, close=99.5, volume=1)
        report = inspect_candles([make_candle(0), bad, make_candle(1)], "15m")
        assert report.invalid == 1
        assert any(i.kind is IssueKind.INVALID_OHLC for i in report.issues)

    def test_future_candle_rejected_within_tolerance(self) -> None:
        now = BASE_TS + 5 * STEP
        skew = Candle(
            timestamp=now + CLOCK_SKEW_TOLERANCE - 1,  # داخل تلورانس کجی ساعت
            open=1, high=2, low=0.5, close=1.5, volume=1,
        )
        future = Candle(
            timestamp=now + STEP * 10,  # آشکارا در آینده
            open=1, high=2, low=0.5, close=1.5, volume=1,
        )
        report = inspect_candles([make_candle(i) for i in range(5)] + [skew, future], "15m", now=now)
        assert report.future == 1  # فقط کندلِ آشکارا آینده

    def test_suspicious_spike_kept_but_warned(self) -> None:
        spike = Candle(timestamp=BASE_TS, open=100, high=160, low=99, close=155, volume=10)
        report = inspect_candles([spike], "15m")
        assert report.suspicious == 1
        assert report.invalid == 0  # جهش ممکن است؛ حذف نمی‌شود

    def test_misaligned_timestamp_warned(self) -> None:
        off = Candle(timestamp=BASE_TS + 17, open=1, high=2, low=0.5, close=1.5, volume=1)
        report = inspect_candles([make_candle(0), off], "15m")
        assert report.misaligned == 1

    def test_unordered_input_reported(self) -> None:
        candles = [make_candle(i) for i in range(6)]
        report = inspect_candles(list(reversed(candles)), "15m")
        assert report.unordered is True


class TestDataCleaning:
    """پاک‌سازی: حذف فقط ردیف‌های به‌صراحت نامعتبر."""

    def test_clean_removes_invalid_and_sorts_and_dedupes(self) -> None:
        # مهر زمانی جدا برای کندل خراب تا با کندل سالم تداخل تکراری نسازد
        bad_ohlc = Candle(timestamp=BASE_TS + 7 * STEP, open=100, high=90, low=95, close=97, volume=5)
        candles = [make_candle(i) for i in range(5)]
        candles.append(make_candle(1, price=222.0))  # تکراری
        candles.insert(0, bad_ohlc)
        cleaned, report = clean_candles(candles, "15m")

        assert len(cleaned) == 5
        stamps = [c.timestamp for c in cleaned]
        assert stamps == sorted(stamps)
        assert len(set(stamps)) == len(stamps)
        assert report.invalid == 1
        assert report.duplicates == 1

    def test_clean_never_fills_gaps(self) -> None:
        candles = [make_candle(i) for i in range(3)] + [make_candle(i) for i in range(6, 9)]
        cleaned, report = clean_candles(candles, "15m")
        assert len(cleaned) == 6  # همان شش کندل واقعی — سه تای گم ساخته نمی‌شود
        assert report.missing == 3

    def test_duplicate_keeps_last_occurrence(self) -> None:
        first = make_candle(0, price=100.0)
        last = make_candle(0, price=130.0)
        cleaned, _ = clean_candles([first, last], "15m")
        assert len(cleaned) == 1
        assert cleaned[0].close == pytest.approx(130.0)

    def test_usable_threshold(self) -> None:
        candles = [make_candle(i) for i in range(10)]
        # شش ردیف از ده خراب → نسبت سالم ۰٫۴ < ۰٫۸ → غیرقابل اتکا
        for i in range(6):
            candles[i] = Candle(timestamp=candles[i].timestamp, open=0, high=0, low=0, close=0, volume=1)
        _, report = clean_candles(candles, "15m")
        assert not report.usable


# ==========================================================================
# خزانهٔ فیچر
# ==========================================================================
class TestFeatureStoreBasics:
    """ساخت فیچر از کندل بسته‌شده و کیفیت ساختار خروجی."""

    def test_minimal_history_returns_empty(self) -> None:
        store = FeatureStore()
        features = store.build([make_candle(0)], "15m", symbol="BTC/USDT")
        assert len(features) == 0
        assert features.available == ()

    def test_vectors_carry_close_time(self) -> None:
        candles = random_walk(80)
        now = candles[-1].timestamp + STEP  # همه بسته‌شده
        features = FeatureStore().build(candles, "15m", now=now, symbol="BTC/USDT")
        assert len(features) == 79  # کندل اول هیچ فیچری ندارد
        # اولین بردار متعلق به کندل دوم است (بازده از کندل دوم شروع می‌شود)
        assert features.vectors[0].close_time == candles[1].timestamp + STEP
        assert features.vectors[-1].close_time == candles[-1].timestamp + STEP

    def test_last_forming_candle_dropped_by_default(self) -> None:
        candles = random_walk(80)
        # now نمی‌دهیم: آخرین کندل «در حال شکل‌گیری» فرض و حذف می‌شود
        features = FeatureStore().build(candles, "15m", symbol="BTC/USDT")
        assert len(features) == 78
        assert features.vectors[-1].close_time == candles[-2].timestamp + STEP

    def test_base_features_available_on_realistic_data(self) -> None:
        candles = random_walk(120)
        now = candles[-1].timestamp + STEP
        features = FeatureStore().build(candles, "15m", now=now)
        for name in ("price_returns", "volume_change", "rsi", "macd", "atr", "ema_distance"):
            assert name in features.available, f"فیچر {name} باید موجود باشد"

    def test_rsi_within_bounds(self) -> None:
        candles = random_walk(120)
        now = candles[-1].timestamp + STEP
        features = FeatureStore().build(candles, "15m", now=now)
        values = [v.get("rsi") for v in features.vectors if v.get("rsi") is not None]
        assert values, "RSI باید مقدار داشته باشد"
        assert all(0.0 <= value <= 100.0 for value in values)

    def test_extra_features_attached_and_aligned(self) -> None:
        candles = random_walk(60)
        now = candles[-1].timestamp + STEP
        closed = [c for c in candles if c.timestamp + STEP <= now]
        oi = [float(i) for i in range(len(candles))]  # هم‌طول با ورودی
        features = FeatureStore().build(candles, "15m", now=now, extra={"oi_change": oi})
        assert "oi_change" in features.available
        latest = features.latest()
        assert latest is not None
        assert latest.get("oi_change") == pytest.approx(float(len(closed) - 1))


class TestNoLookAhead:
    """قانون حیاتی ۳: فیچر نباید از آینده تغذیه شود."""

    def test_truncated_build_matches_full_prefix(self) -> None:
        candles = random_walk(140)
        cut = 90
        now_partial = candles[cut - 1].timestamp + STEP  # فقط ۹۰ کندل اول بسته‌اند

        partial = FeatureStore().build(candles[:cut], "15m", now=now_partial)
        full = FeatureStore().build(candles, "15m", now=now_partial)

        # مقدار RSI در «لحظهٔ مشترک» نباید به کندل‌های بعدی وابسته باشد
        common = partial.vectors[-1].close_time
        full_at_common = next(v for v in full.vectors if v.close_time == common)
        assert partial.vectors[-1].get("rsi") == pytest.approx(full_at_common.get("rsi"))

    def test_now_hides_unclosed_candles(self) -> None:
        candles = random_walk(50)
        # «الان» وسط کندل دهم است: فقط ۹ کندل بسته‌شده دیده می‌شوند
        now = candles[9].timestamp + STEP // 2
        features = FeatureStore().build(candles, "15m", now=now)
        assert len(features) == 8
        assert features.vectors[-1].close_time == candles[8].timestamp + STEP


class TestFeatureMatrix:
    """ماتریس مدل: ردیف ناقص حذف می‌شود، نه پر کردن با عدد."""

    def test_matrix_drops_incomplete_rows(self) -> None:
        candles = random_walk(140)
        now = candles[-1].timestamp + STEP
        features = FeatureStore().build(candles, "15m", now=now)

        names = ["price_returns", "rsi", "atr"]
        times, rows = features.matrix(names)
        assert len(times) == len(rows)
        assert rows, "باید ردیف کامل داشته باشیم"
        for row in rows:
            assert len(row) == len(names)
            assert all(math.isfinite(value) for value in row)
        # گرم‌شدن RSI (۱۴ دوره) یعنی چند ردیف اول حتماً حذف شده‌اند
        assert len(rows) < len(features)

    def test_matrix_never_imputes(self) -> None:
        candles = random_walk(140)
        now = candles[-1].timestamp + STEP
        features = FeatureStore().build(candles, "15m", now=now)

        # فیچر ساختگی که فقط برای چند ردیف آخر مقدار دارد
        for vector in features.vectors[:-3]:
            vector.values.pop("rsi", None)
        times, rows = features.matrix(["rsi", "atr"])
        assert len(rows) <= 3  # بقیه حذف — نه میانگین، نه صفر

    def test_to_dict_shape(self) -> None:
        candles = random_walk(80)
        features = FeatureStore().build(candles, "15m", symbol="BTC/USDT")
        payload = features.to_dict()
        assert payload["symbol"] == "BTC/USDT"
        assert payload["timeframe"] == "15m"
        assert payload["count"] == len(features)
        assert payload["latest"] is not None


class TestFeatureVectorDataclass:
    """قرارداد خود بردار فیچر."""

    def test_get_default(self) -> None:
        vector = FeatureVector(close_time=1, values={"rsi": 55.0})
        assert vector.get("rsi") == pytest.approx(55.0)
        assert vector.get("oi_change") is None
        assert vector.get("oi_change", 0.0) == pytest.approx(0.0)
