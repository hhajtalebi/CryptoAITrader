"""
آزمون پیگیری نتیجهٔ واقعی سیگنال‌ها (مورد ۱.۵ نقشهٔ راه).

تا پیش از این، برنامه سیگنال می‌داد و هیچ‌وقت نمی‌فهمید درست بوده یا نه.
این آزمون‌ها روی همان چیزی تمرکز دارند که اگر بشکند، آمار **دروغ**
می‌گوید — و آمار دروغ از نبود آمار بدتر است، چون کاربر بر پایه‌اش پول
واقعی به خطر می‌اندازد:

    • حد ضرر باید بر هدف مقدم باشد (بدبینانه، نه خوش‌بینانه)
    • جهت فروش باید علامت سود و زیانش وارونه شود
    • سیگنال بسته‌شده نباید با قیمت‌های بعدی بازنویسی شود
    • اهرم نباید وارد درصد شود
    • نرخ برد نباید سیگنال‌های باز را بشمارد
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.constants import (
    AnalysisStatus,
    MarketStructureType,
    SignalDirection,
    TrendDirection,
)
from app.core.models import TradingSignal
from app.database.repositories.outcome_repository import SignalOutcomeRepository
from app.database.repositories.signal_repository import SignalRepository
from localization import Translator
from signals.outcome_tracker import (
    CLOSED_STATUSES,
    DEFAULT_EXPIRY_HOURS,
    EXPIRY_HOURS,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_STOP,
    STATUS_TARGET,
    OutcomeState,
    PriceWindow,
    confidence_buckets,
    expiry_for,
    group_by,
    percent_change,
    summarize,
    update_outcome,
)

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)


def make_state(
    *,
    direction: str = "LONG",
    entry: float = 60000.0,
    stop: float = 58800.0,
    targets: tuple[float, ...] = (61200.0, 62400.0, 63600.0),
    **kwargs,
) -> OutcomeState:
    """وضعیت پیگیری نمونه با نسبت ریسک به سود ۱:۳."""
    return OutcomeState(
        symbol="BTC/USDT",
        direction=direction,
        entry_price=entry,
        stop_loss=stop,
        take_profits=targets,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# منطق پایه
# ---------------------------------------------------------------------------
class TestPercentChange:
    """درصد تغییر باید از دید خودِ سیگنال حساب شود."""

    def test_long_profits_when_price_rises(self) -> None:
        """خرید با بالا رفتن قیمت سود می‌کند."""
        assert percent_change(100.0, 110.0, is_long=True) == pytest.approx(10.0)

    def test_short_profits_when_price_falls(self) -> None:
        """
        فروش با **افت** قیمت سود می‌کند.

        بدون وارونه‌کردن علامت، تمام آمار شورت‌ها برعکس ثبت می‌شد.
        """
        assert percent_change(100.0, 90.0, is_long=False) == pytest.approx(10.0)

    def test_short_loses_when_price_rises(self) -> None:
        """فروش با بالا رفتن قیمت زیان می‌دهد."""
        assert percent_change(100.0, 110.0, is_long=False) == pytest.approx(-10.0)

    def test_zero_entry_is_not_a_division_error(self) -> None:
        """ورودی صفر نباید برنامه را بشکند."""
        assert percent_change(0.0, 100.0, is_long=True) == 0.0


class TestStopBeatsTarget:
    """اگر هم هدف و هم حد ضرر در بازه باشند، حد ضرر برنده است."""

    def test_a_window_touching_both_is_recorded_as_a_loss(self) -> None:
        """
        با یک کندل که هم سقف هدف را زده و هم کف حد ضرر را، نمی‌توان
        فهمید کدام زودتر لمس شده. فرض خوش‌بینانه آمار را نظام‌مند بهتر
        از واقعیت نشان می‌دهد؛ پس بدبینانه حساب می‌کنیم.
        """
        state = make_state()
        update_outcome(state, PriceWindow(last=61000, high=63700, low=58700), now=NOW)

        assert state.status == STATUS_STOP
        assert state.result_percent < 0

    def test_target_alone_still_wins(self) -> None:
        """وقتی حد ضرر لمس نشده، هدف طبیعتاً ثبت می‌شود."""
        state = make_state()
        update_outcome(state, PriceWindow(last=63700, high=63700, low=59900), now=NOW)

        assert state.status == STATUS_TARGET


class TestTargets:
    """هدف‌های پله‌ای."""

    def test_first_target_counts_but_does_not_close(self) -> None:
        """
        معامله‌گر واقعی پله‌ای خارج می‌شود؛ رسیدن به هدف اول پایان کار
        نیست.
        """
        state = make_state()
        update_outcome(state, PriceWindow(last=61300, high=61300, low=60000), now=NOW)

        assert state.targets_hit == 1
        assert state.status == STATUS_PENDING

    def test_last_target_closes_the_signal(self) -> None:
        """رسیدن به آخرین هدف یعنی کار تمام است."""
        state = make_state()
        update_outcome(state, PriceWindow(last=63700, high=63700, low=60000), now=NOW)

        assert state.targets_hit == 3
        assert state.status == STATUS_TARGET
        assert state.closed_at is not None

    def test_targets_are_counted_in_order(self) -> None:
        """
        هدف دوم بدون هدف اول شمرده نمی‌شود.

        قیمت برای رسیدن به هدف دوم ناچار از هدف اول گذشته است؛ شمارش
        باید پیوسته بماند.
        """
        state = make_state()
        update_outcome(state, PriceWindow(last=62500, high=62500, low=60000), now=NOW)

        assert state.targets_hit == 2

    def test_short_targets_are_below_entry(self) -> None:
        """در فروش، هدف پایین‌تر از ورود است."""
        state = make_state(
            direction="SHORT", entry=60000, stop=61200, targets=(58800.0,)
        )
        update_outcome(state, PriceWindow(last=58700, high=60100, low=58700), now=NOW)

        assert state.status == STATUS_TARGET
        assert state.result_percent == pytest.approx(2.0)


class TestRMultiple:
    """واحد R، تنها معیار قابل مقایسه میان نمادها."""

    def test_full_target_run_equals_the_risk_reward(self) -> None:
        """ورود ۶۰۰۰۰، حد ضرر ۵۸۸۰۰، هدف ۶۳۶۰۰ ⇒ دقیقاً ۳R."""
        state = make_state()
        update_outcome(state, PriceWindow(last=63600, high=63600, low=60000), now=NOW)

        assert state.realized_r == pytest.approx(3.0)

    def test_a_stop_is_exactly_minus_one_r(self) -> None:
        """حد ضرر طبق تعریف یعنی از دست دادن یک واحد ریسک."""
        state = make_state()
        update_outcome(state, PriceWindow(last=58800, high=60000, low=58800), now=NOW)

        assert state.realized_r == pytest.approx(-1.0)

    def test_zero_risk_distance_does_not_divide_by_zero(self) -> None:
        """حد ضرر برابر ورود نباید استثنا بدهد."""
        state = make_state(stop=60000.0)
        update_outcome(state, PriceWindow(last=61300, high=61300, low=60000), now=NOW)

        assert state.realized_r == 0.0


class TestLeverageIsExcluded:
    """اهرم انتخاب کاربر است، نه ویژگی سیگنال."""

    def test_result_percent_is_unleveraged(self) -> None:
        """
        اگر اهرم وارد درصد می‌شد، آمار به تنظیمات لحظه‌ای کاربر وابسته
        می‌شد و مقایسهٔ دو سیگنال بی‌معنا.
        """
        state = make_state()
        update_outcome(state, PriceWindow(last=63600, high=63600, low=60000), now=NOW)

        # حرکت خام قیمت ۶٪ است؛ با اهرم ۵ می‌شد ۳۰٪
        assert state.result_percent == pytest.approx(6.0)


class TestExcursions:
    """بیشترین سود و زیان شناور."""

    def test_favorable_and_adverse_are_tracked(self) -> None:
        """هر دو لبهٔ حرکت ثبت می‌شود، نه فقط قیمت پایانی."""
        state = make_state()
        update_outcome(state, PriceWindow(last=60100, high=61000, low=59400), now=NOW)

        assert state.max_favorable_percent == pytest.approx(1.6667, abs=1e-3)
        assert state.max_adverse_percent == pytest.approx(-1.0)

    def test_extremes_never_shrink(self) -> None:
        """رکورد بیشترین سود با یک کندل آرام پاک نمی‌شود."""
        state = make_state()
        update_outcome(state, PriceWindow(last=60900, high=61000, low=59400), now=NOW)
        update_outcome(state, PriceWindow(last=60050, high=60100, low=60000), now=NOW)

        assert state.max_favorable_percent == pytest.approx(1.6667, abs=1e-3)
        assert state.max_adverse_percent == pytest.approx(-1.0)


class TestClosedSignalsAreFrozen:
    """سیگنال بسته‌شده تاریخ است و بازنویسی نمی‌شود."""

    def test_further_prices_do_not_change_a_closed_outcome(self) -> None:
        """
        بدون این قفل، قیمت‌های فردا نتیجهٔ دیروز را عوض می‌کردند و آمار
        گذشته بی‌معنا می‌شد.
        """
        state = make_state()
        update_outcome(state, PriceWindow(last=58800, high=60000, low=58800), now=NOW)
        recorded = state.result_percent

        update_outcome(state, PriceWindow(last=70000, high=70000, low=69000), now=NOW)

        assert state.status == STATUS_STOP
        assert state.result_percent == recorded


class TestExpiry:
    """مهلت پیگیری."""

    def test_expiry_depends_on_the_timeframe(self) -> None:
        """سیگنال ۱۵ دقیقه‌ای نباید به اندازهٔ سیگنال روزانه باز بماند."""
        created = NOW
        assert expiry_for("15m", created_at=created) < expiry_for("1d", created_at=created)

    def test_unknown_timeframe_falls_back_to_a_week(self) -> None:
        """تایم‌فریم ناشناخته نباید بی‌نهایت پیگیری شود."""
        created = NOW
        assert expiry_for("nonsense", created_at=created) == created + timedelta(
            hours=DEFAULT_EXPIRY_HOURS
        )

    def test_every_known_timeframe_has_a_positive_window(self) -> None:
        """هیچ تایم‌فریمی نباید مهلت صفر یا منفی داشته باشد."""
        assert all(hours > 0 for hours in EXPIRY_HOURS.values())

    def test_passing_the_deadline_closes_as_expired(self) -> None:
        """پس از مهلت، سیگنال نه برد است نه باخت — منقضی است."""
        state = make_state(expires_at=NOW - timedelta(hours=1))
        update_outcome(state, PriceWindow(last=60100, high=60200, low=59900), now=NOW)

        assert state.status == STATUS_EXPIRED

    def test_a_target_hit_beats_an_expiry_in_the_same_window(self) -> None:
        """
        اگر در همان لحظه هم هدف خورده و هم مهلت تمام شده، نتیجهٔ واقعی
        معامله مهم‌تر از ساعت است.
        """
        state = make_state(expires_at=NOW - timedelta(hours=1))
        update_outcome(state, PriceWindow(last=63700, high=63700, low=60000), now=NOW)

        assert state.status == STATUS_TARGET

    def test_naive_deadline_does_not_raise(self) -> None:
        """
        پایگاه داده تاریخ بی‌منطقهٔ زمانی می‌دهد ولی منطق با زمان آگاه
        کار می‌کند؛ مقایسه‌شان نباید `TypeError` بدهد.
        """
        state = make_state(expires_at=datetime(2026, 9, 14, 11, 0))
        update_outcome(state, PriceWindow(last=60100, high=60200, low=59900), now=NOW)

        assert state.status == STATUS_EXPIRED


class TestPriceWindow:
    """بازهٔ قیمتی."""

    def test_a_single_price_fills_all_three_bounds(self) -> None:
        """وقتی فقط قیمت لحظه‌ای هست، سقف و کف همان است."""
        window = PriceWindow(last=100.0)

        assert window.ceiling == 100.0
        assert window.floor == 100.0

    def test_zero_low_is_ignored(self) -> None:
        """کف صفر یعنی «داده نداریم»، نه «قیمت صفر شد»."""
        window = PriceWindow(last=100.0, high=110.0, low=0.0)

        assert window.floor == 100.0


# ---------------------------------------------------------------------------
# آمار
# ---------------------------------------------------------------------------
class FakeOutcome:
    """رکورد ساختگی برای آزمون آمار."""

    def __init__(
        self,
        status: str,
        result: float = 0.0,
        r: float = 0.0,
        confidence: int = 60,
        symbol: str = "BTC/USDT",
        timeframe: str = "4h",
    ) -> None:
        self.status = status
        self.result_percent = result
        self.realized_r = r
        self.confidence = confidence
        self.symbol = symbol
        self.primary_timeframe = timeframe


class TestSummary:
    """خلاصهٔ عملکرد."""

    def test_open_signals_do_not_dilute_the_win_rate(self) -> None:
        """
        نرخ برد فقط روی معاملات **تصمیم‌شده** معنا دارد. شمردن
        سیگنال‌های باز، نرخ را مصنوعی پایین می‌آورد.
        """
        stats = summarize(
            [
                FakeOutcome(STATUS_TARGET, 5.0, 2.0),
                FakeOutcome(STATUS_STOP, -2.0, -1.0),
                FakeOutcome(STATUS_PENDING),
                FakeOutcome(STATUS_PENDING),
            ]
        )

        assert stats["decided"] == 2
        assert stats["win_rate"] == 50.0
        assert stats["pending"] == 2

    def test_expired_signals_are_counted_separately(self) -> None:
        """منقضی نه برد است نه باخت و نباید نرخ برد را جابه‌جا کند."""
        stats = summarize(
            [
                FakeOutcome(STATUS_TARGET, 5.0, 2.0),
                FakeOutcome(STATUS_EXPIRED, 0.2, 0.1),
            ]
        )

        assert stats["expired"] == 1
        assert stats["decided"] == 1
        assert stats["win_rate"] == 100.0

    def test_profit_factor_divides_gains_by_losses(self) -> None:
        """ضریب سود بالای ۱ یعنی مجموعاً سودده."""
        stats = summarize(
            [
                FakeOutcome(STATUS_TARGET, 6.0, 3.0),
                FakeOutcome(STATUS_STOP, -2.0, -1.0),
                FakeOutcome(STATUS_STOP, -1.0, -0.5),
            ]
        )

        assert stats["profit_factor"] == pytest.approx(2.0)

    def test_an_empty_history_is_safe(self) -> None:
        """آمار خالی نباید تقسیم بر صفر بدهد."""
        stats = summarize([])

        assert stats["total"] == 0
        assert stats["win_rate"] == 0.0
        assert stats["average_r"] == 0.0


class TestGrouping:
    """تفکیک آمار."""

    def test_confidence_buckets_are_ten_wide(self) -> None:
        """بازه‌های ده‌تایی، همان چیزی که روی نمودار خوانا می‌ماند."""
        buckets = confidence_buckets(
            [
                FakeOutcome(STATUS_TARGET, 5.0, 2.0, confidence=72),
                FakeOutcome(STATUS_TARGET, 4.0, 1.5, confidence=75),
                FakeOutcome(STATUS_STOP, -2.0, -1.0, confidence=41),
            ]
        )

        assert set(buckets) == {"70-79", "40-49"}
        assert buckets["70-79"]["total"] == 2

    def test_confidence_bucket_answers_the_key_question(self) -> None:
        """
        مهم‌ترین سنجش کل سیستم: آیا ضریب اطمینان بالاتر واقعاً نرخ برد
        بالاتری دارد؟ اگر این تفکیک درست کار نکند، هیچ راهی برای ردّ یا
        اثبات ادعای موتور نمی‌ماند.
        """
        buckets = confidence_buckets(
            [
                FakeOutcome(STATUS_TARGET, 5.0, 2.0, confidence=75),
                FakeOutcome(STATUS_TARGET, 5.0, 2.0, confidence=78),
                FakeOutcome(STATUS_STOP, -2.0, -1.0, confidence=45),
                FakeOutcome(STATUS_STOP, -2.0, -1.0, confidence=42),
            ]
        )

        assert buckets["70-79"]["win_rate"] == 100.0
        assert buckets["40-49"]["win_rate"] == 0.0

    def test_grouping_by_symbol_and_timeframe(self) -> None:
        """تفکیک نماد و تایم‌فریم برای یافتن نقطهٔ قوت موتور."""
        rows = [
            FakeOutcome(STATUS_TARGET, 5.0, 2.0, symbol="BTC/USDT", timeframe="4h"),
            FakeOutcome(STATUS_STOP, -2.0, -1.0, symbol="ETH/USDT", timeframe="1h"),
        ]

        assert set(group_by(rows, "symbol")) == {"BTC/USDT", "ETH/USDT"}
        assert set(group_by(rows, "primary_timeframe")) == {"4h", "1h"}

    def test_missing_attribute_becomes_a_dash(self) -> None:
        """مقدار خالی نباید کلید تهی بسازد."""
        rows = [FakeOutcome(STATUS_TARGET, 5.0, 2.0, timeframe="")]

        assert "—" in group_by(rows, "primary_timeframe")


# ---------------------------------------------------------------------------
# مخزن
# ---------------------------------------------------------------------------
@pytest.fixture()
def repos(database):  # noqa: ANN001, ANN201
    """مخزن سیگنال و نتیجه روی پایگاه دادهٔ موقت."""
    return SignalRepository(database), SignalOutcomeRepository(database)


def make_signal(
    direction: SignalDirection = SignalDirection.LONG,
    *,
    confidence: int = 70,
    stop: float | None = 58800.0,
    symbol: str = "BTC/USDT",
) -> TradingSignal:
    """سیگنال نمونه برای ذخیره در پایگاه داده."""
    return TradingSignal(
        symbol=symbol,
        exchange="lbank",
        direction=direction,
        entry_min=59800.0,
        entry_max=60200.0,
        stop_loss=stop,
        take_profits=[61200.0, 62400.0, 63600.0],
        risk_reward=3.0,
        leverage=5,
        confidence=confidence,
        trend=TrendDirection.BULLISH,
        market_structure=MarketStructureType.BULLISH,
        timeframes=["4h", "1h"],
        indicators_used=["rsi"],
        reason="test",
        invalidation="test",
        status=AnalysisStatus.OK,
    )


class TestRepository:
    """ثبت و به‌روزرسانی نتیجه در پایگاه داده."""

    def test_entry_price_is_the_middle_of_the_range(self, repos) -> None:  # noqa: ANN001
        """
        سیگنال یک بازهٔ ورود می‌دهد نه یک عدد؛ میانه منصفانه‌ترین مرجع
        است، نه لبهٔ خوش‌بینانه.
        """
        signals, outcomes = repos
        signal_id = signals.save_signal(make_signal())
        outcomes.track_signal(signal_id)

        record = outcomes.get_by_signal(signal_id)
        assert record.entry_price == pytest.approx(60000.0)

    def test_tracking_is_idempotent(self, repos) -> None:  # noqa: ANN001
        """
        ثبت دوبارهٔ یک سیگنال نباید ردیف تکراری بسازد، وگرنه همان
        معامله دو بار در آمار شمرده می‌شود.
        """
        signals, outcomes = repos
        signal_id = signals.save_signal(make_signal())

        first = outcomes.track_signal(signal_id)
        second = outcomes.track_signal(signal_id)

        assert first == second
        assert outcomes.count() == 1

    def test_wait_signals_are_not_tracked(self, repos) -> None:  # noqa: ANN001
        """«انتظار» معامله‌ای نیست که نتیجه‌ای داشته باشد."""
        signals, outcomes = repos
        signal_id = signals.save_signal(make_signal(SignalDirection.WAIT))

        assert outcomes.track_signal(signal_id) is None

    def test_a_signal_without_a_stop_is_not_tracked(self, repos) -> None:  # noqa: ANN001
        """بدون حد ضرر، نه R معنا دارد نه باخت قابل تشخیص است."""
        signals, outcomes = repos
        signal_id = signals.save_signal(make_signal(stop=None))

        assert outcomes.track_signal(signal_id) is None

    def test_unknown_signal_is_handled(self, repos) -> None:  # noqa: ANN001
        """شناسهٔ ناموجود نباید استثنا بدهد."""
        _signals, outcomes = repos

        assert outcomes.track_signal(9999) is None

    def test_state_round_trip(self, repos) -> None:  # noqa: ANN001
        """وضعیت محاسبه‌شده باید سالم در پایگاه داده بنشیند و برگردد."""
        signals, outcomes = repos
        signal_id = signals.save_signal(make_signal())
        outcome_id = outcomes.track_signal(signal_id)

        record = outcomes.get_by_signal(signal_id)
        state = outcomes.to_state(record)
        update_outcome(state, PriceWindow(last=63700, high=63700, low=60000))
        outcomes.apply_state(outcome_id, state)

        stored = outcomes.get_by_signal(signal_id)
        assert stored.status == STATUS_TARGET
        assert stored.result_percent == pytest.approx(6.0)
        assert stored.realized_r == pytest.approx(3.0)
        assert stored.closed_at is not None

    def test_open_outcomes_exclude_closed_ones(self, repos) -> None:  # noqa: ANN001
        """سیگنال بسته‌شده نباید دوباره قیمت بگیرد."""
        signals, outcomes = repos
        open_id = signals.save_signal(make_signal())
        closed_id = signals.save_signal(make_signal(symbol="ETH/USDT"))
        outcomes.track_signal(open_id)
        outcome_id = outcomes.track_signal(closed_id)

        record = outcomes.get_by_signal(closed_id)
        state = outcomes.to_state(record)
        update_outcome(state, PriceWindow(last=63700, high=63700, low=60000))
        outcomes.apply_state(outcome_id, state)

        remaining = [item.signal_id for item in outcomes.open_outcomes()]
        assert remaining == [open_id]
        assert outcomes.pending_count() == 1

    def test_open_symbols_are_unique(self, repos) -> None:  # noqa: ANN001
        """نماد تکراری نباید دو بار قیمت بگیرد."""
        signals, outcomes = repos
        for _ in range(3):
            outcomes.track_signal(signals.save_signal(make_signal()))

        assert outcomes.open_symbols() == ["BTC/USDT"]

    def test_cancel_marks_the_outcome_manual(self, repos) -> None:  # noqa: ANN001
        """لغو دستی باید از نتیجهٔ خودکار قابل تشخیص باشد."""
        signals, outcomes = repos
        signal_id = signals.save_signal(make_signal())
        outcome_id = outcomes.track_signal(signal_id)

        assert outcomes.cancel(outcome_id, note="manual") is True

        record = outcomes.get_by_signal(signal_id)
        assert record.status in CLOSED_STATUSES
        assert record.manual is True

    def test_backfill_picks_up_untracked_signals(self, repos) -> None:  # noqa: ANN001
        """
        کاربری که پیش از این نسخه سیگنال ساخته، نباید صفحهٔ عملکرد
        خالی ببیند.
        """
        signals, outcomes = repos
        signals.save_signal(make_signal())
        signals.save_signal(make_signal(symbol="ETH/USDT"))
        signals.save_signal(make_signal(SignalDirection.WAIT))

        assert outcomes.backfill() == 2
        # اجرای دوباره نباید چیز تازه‌ای اضافه کند
        assert outcomes.backfill() == 0

    def test_history_filters_by_confidence(self, repos) -> None:  # noqa: ANN001
        """فیلتر ضریب اطمینان برای صفحهٔ عملکرد."""
        signals, outcomes = repos
        outcomes.track_signal(signals.save_signal(make_signal(confidence=80)))
        outcomes.track_signal(
            signals.save_signal(make_signal(confidence=40, symbol="ETH/USDT"))
        )

        high = outcomes.history(min_confidence=70)
        assert [item.confidence for item in high] == [80]

    def test_performance_report_has_every_breakdown(self, repos) -> None:  # noqa: ANN001
        """گزارش باید هر چهار تفکیک را بدهد تا صفحه کامل پر شود."""
        signals, outcomes = repos
        outcomes.track_signal(signals.save_signal(make_signal()))

        report = outcomes.performance()
        assert set(report) == {
            "summary",
            "by_symbol",
            "by_timeframe",
            "by_confidence",
            "by_direction",
        }


# ---------------------------------------------------------------------------
# رابط کاربری
# ---------------------------------------------------------------------------
@pytest.fixture()
def view(qt_application):  # noqa: ANN001, ANN201
    """نمای عملکرد با مترجم فارسی."""
    from ui.widgets.performance_view import PerformanceView

    return PerformanceView(Translator("fa"))


SAMPLE_REPORT = {
    "summary": {
        "total": 10, "pending": 2, "wins": 5, "losses": 3, "expired": 0,
        "decided": 8, "win_rate": 62.5, "total_percent": 12.0,
        "average_percent": 1.5, "total_r": 4.0, "average_r": 0.5,
        "best_percent": 6.0, "worst_percent": -2.5,
        "average_win": 4.0, "average_loss": 2.0, "profit_factor": 1.8,
    },
    "by_confidence": {
        "40-49": {"total": 3, "decided": 3, "wins": 0, "losses": 3,
                  "win_rate": 0.0, "average_r": -1.0, "total_percent": -6.0},
        "70-79": {"total": 5, "decided": 5, "wins": 5, "losses": 0,
                  "win_rate": 100.0, "average_r": 2.0, "total_percent": 18.0},
    },
    "by_symbol": {}, "by_timeframe": {}, "by_direction": {},
}


class TestPerformanceView:
    """نمای عملکرد."""

    def test_report_fills_the_breakdown_table(self, view) -> None:  # noqa: ANN001
        """گزارش باید ردیف‌های تفکیک را بسازد."""
        view.set_performance(SAMPLE_REPORT)

        assert view.breakdown_table.rowCount() == 2

    def test_wins_and_losses_keep_their_order_in_rtl(self, view) -> None:  # noqa: ANN001
        """
        نقص واقعی که در بازبینی چشمی پیدا شد: «۲ / ۴» در چیدمان
        راست‌به‌چپ وارونه دیده می‌شد و کاربر باخت را برد می‌خواند.
        نشانگر چپ‌به‌راست جلوی این را می‌گیرد.
        """
        view.set_performance(SAMPLE_REPORT)
        cell = view.breakdown_table.item(0, 3).text()

        assert cell.startswith("\u200e")
        digits = Translator("fa").to_latin_digits(cell)
        assert digits.replace("\u200e", "") == "0 / 3"

    def test_negative_numbers_keep_the_minus_in_front(self, view) -> None:  # noqa: ANN001
        """بدون مهار دوسویه، «-۶.۰۰%» به «۶.۰۰%-» تبدیل می‌شد."""
        view.set_performance(SAMPLE_REPORT)
        cell = view.breakdown_table.item(0, 5).text()

        assert cell.startswith("\u200e-")

    def test_win_rate_card_reports_the_sample_size(self, view) -> None:  # noqa: ANN001
        """
        «۱۰۰٪» از یک معامله گمراه‌کننده است؛ تعداد همیشه باید کنارش
        باشد.
        """
        view.set_performance(SAMPLE_REPORT)

        assert view._stat_cards["win_rate"].caption_label.text().strip()  # noqa: SLF001

    def test_an_empty_report_is_safe(self, view) -> None:  # noqa: ANN001
        """گزارش خالی نباید استثنا بدهد یا عدد جعلی نشان دهد."""
        view.set_performance({"summary": {}, "by_confidence": {}})

        assert view.breakdown_table.rowCount() == 0
        assert view._stat_cards["win_rate"].value_label.text() == "—"  # noqa: SLF001

    def test_history_shows_the_empty_state(self, view) -> None:  # noqa: ANN001
        """بدون داده، کاربر باید توضیح ببیند نه جدول خالی."""
        view.set_history([])

        assert view.empty_label.isVisible() or not view.history_table.isVisible()

    def test_history_rows_are_rendered(self, view) -> None:  # noqa: ANN001
        """هر نتیجه یک ردیف می‌گیرد."""
        view.set_history(
            [
                {"symbol": "BTC/USDT", "direction": "LONG", "status": "TARGET",
                 "confidence": 74, "timeframe": "4h", "result_percent": 6.0,
                 "realized_r": 3.0, "targets_hit": 3},
            ]
        )

        assert view.history_table.rowCount() == 1
        assert "BTC/USDT" in view.history_table.item(0, 0).text()

    def test_symbol_is_never_rtl_mangled(self, view) -> None:  # noqa: ANN001
        """`BTC/USDT` باید دقیقاً به همین شکل خوانده شود."""
        view.set_history(
            [
                {"symbol": "BTC/USDT", "direction": "LONG", "status": "TARGET",
                 "confidence": 74, "timeframe": "4h", "result_percent": 6.0,
                 "realized_r": 3.0, "targets_hit": 3},
            ]
        )
        text = view.history_table.item(0, 0).text()

        assert text.replace("\u200e", "") == "BTC/USDT"

    def test_period_selection_reports_days(self, view) -> None:  # noqa: ANN001
        """بازهٔ انتخابی باید به روز تبدیل شود."""
        view.period_control.set_current("7", emit=False)

        assert view.selected_period() == 7

    def test_all_period_means_no_limit(self, view) -> None:  # noqa: ANN001
        """«همه» یعنی بدون محدودیت زمانی (صفر روز)."""
        view.period_control.set_current("all", emit=False)

        assert view.selected_period() == 0

    def test_infinite_profit_factor_is_readable(self, view) -> None:  # noqa: ANN001
        """
        وقتی هیچ باختی نبوده، ریاضی «بی‌نهایت» می‌دهد؛ نمایش `inf` به
        کاربر بی‌معناست.
        """
        assert view._format_factor(float("inf")) == "∞"  # noqa: SLF001

    def test_theme_key_string_does_not_crash_colouring(self, view) -> None:  # noqa: ANN001
        """
        اگر به‌جای شیء توکن، کلید رشته‌ای پوسته فرستاده شود نباید
        `AttributeError` بدهد.
        """
        view.apply_theme("glass_dark")
        view.set_history(
            [
                {"symbol": "BTC/USDT", "direction": "LONG", "status": "STOP",
                 "confidence": 50, "timeframe": "1h", "result_percent": -2.0,
                 "realized_r": -1.0, "targets_hit": 0},
            ]
        )

        assert view.history_table.rowCount() == 1

    def test_retranslate_switches_language(self, qt_application) -> None:  # noqa: ANN001, ARG002
        """تغییر زبان نباید رشتهٔ ترجمه‌نشده باقی بگذارد."""
        from ui.widgets.performance_view import PerformanceView

        widget = PerformanceView(Translator("en"))
        widget.set_performance(SAMPLE_REPORT)
        widget.retranslate()

        assert widget.history_card.title_label.text() == "Outcome history"


class TestReportsPageTabs:
    """یکپارچگی با صفحهٔ گزارش‌ها."""

    def test_performance_is_a_tab_of_the_reports_page(self, qt_application) -> None:  # noqa: ANN001, ARG002
        """
        صفحهٔ یازدهم ساخته نشد: نوار کناری ده جا دارد و میان‌برهایش
        `Ctrl+1` تا `Ctrl+0` است.
        """
        from ui.pages.reports_page import ReportsPage

        page = ReportsPage(Translator("fa"))

        # از ۱.۹.۱۹ زبانهٔ سوم «دفترچهٔ نتیجه» هم اضافه شده؛ چیزی که
        # این آزمون تضمین می‌کند این است که «عملکرد» یک زبانه بماند و
        # صفحهٔ یازدهمِ نوار کناری نشود.
        assert page.tabs.count() >= 2
        assert page.performance is not None
        titles = [page.tabs.tabText(index) for index in range(page.tabs.count())]
        assert any(page.tr_.tr("performance.title") == title for title in titles)

    def test_the_export_tab_still_works(self, qt_application) -> None:  # noqa: ANN001, ARG002
        """قابلیت قبلی نباید با افزودن زبانه از بین رفته باشد."""
        from ui.pages.reports_page import ReportsPage

        page = ReportsPage(Translator("fa"))

        assert page.generate_button is not None
        assert page.selected_format() == "csv"
        page.set_summary({"total": 3, "by_direction": {"LONG": 3}, "average_confidence": 60})
        assert page.preview_table is not None

    def test_show_performance_opens_the_right_tab(self, qt_application) -> None:  # noqa: ANN001, ARG002
        """پیوند مستقیم به عملکرد باید زبانهٔ درست را باز کند."""
        from ui.pages.reports_page import ReportsPage

        page = ReportsPage(Translator("fa"))
        page.show_performance()

        assert page.tabs.currentIndex() == 1


# ---------------------------------------------------------------------------
# بومی‌سازی
# ---------------------------------------------------------------------------
class TestLocalization:
    """هیچ رشتهٔ سخت‌کدشده‌ای نباید بماند."""

    @pytest.mark.parametrize("language", ["fa", "en"])
    def test_every_performance_key_exists(self, language: str) -> None:
        """کلید جامانده روی صفحه به‌صورت خام دیده می‌شود."""
        translator = Translator(language)
        keys = [
            "performance.title", "performance.period", "performance.period_all",
            "performance.refresh", "performance.win_rate", "performance.total_r",
            "performance.profit_factor", "performance.pending",
            "performance.breakdown", "performance.group", "performance.history",
            "performance.empty", "performance.confidence_hint",
            "performance.group_confidence", "performance.group_symbol",
            "performance.group_timeframe", "performance.group_direction",
            "performance.status_pending", "performance.status_target",
            "performance.status_stop", "performance.status_expired",
            "performance.status_cancelled", "performance.wins_losses",
            "performance.average_r", "performance.total_percent",
            "performance.timeframe", "performance.status", "performance.result",
            "performance.r_value", "performance.targets", "performance.total",
            "reports.tab_export", "signals.outcome.closed_toast",
            "signals.outcome.checking", "signals.outcome.error",
        ]
        for key in keys:
            assert translator.tr(key) != key, f"{language}: {key}"

    @pytest.mark.parametrize(
        ("key", "kwargs"),
        [
            ("performance.period_days", {"days": "۷"}),
            ("performance.decided_count", {"count": "۵"}),
            ("signals.outcome.closed_toast", {"wins": "۲", "losses": "۱"}),
        ],
    )
    def test_placeholders_are_filled(self, key: str, kwargs: dict) -> None:
        """جای‌نگهدار پرنشده یعنی «{count}» روی صفحه."""
        for language in ("fa", "en"):
            text = Translator(language).tr(key, **kwargs)
            assert "{" not in text, f"{language}: {key} -> {text}"


# ---------------------------------------------------------------------------
# تنظیمات
# ---------------------------------------------------------------------------
class TestSettings:
    """کلیدهای تنظیمات پیگیری."""

    def test_tracking_is_on_by_default(self) -> None:
        """
        برخلاف پویش خودکار، پیگیری نتیجه پیش‌فرض روشن است: هزینه‌اش
        ناچیز است و بدون آن هیچ آماری شکل نمی‌گیرد.
        """
        from app.config.defaults import DEFAULT_SETTINGS

        assert DEFAULT_SETTINGS["signals.track_outcomes"] is True

    def test_interval_and_batch_have_sane_defaults(self) -> None:
        """فاصلهٔ بررسی نباید آن‌قدر کوتاه باشد که صرافی را اذیت کند."""
        from app.config.defaults import DEFAULT_SETTINGS

        assert DEFAULT_SETTINGS["signals.track_interval"] >= 60
        assert DEFAULT_SETTINGS["signals.track_batch"] > 0

    def test_keys_are_registered_in_the_signals_group(self) -> None:
        """کلید ثبت‌نشده در گروه، در پشتیبان‌گیری و بازیابی جا می‌ماند."""
        from app.config.defaults import SETTING_CATEGORIES

        group = SETTING_CATEGORIES["signals"]
        assert "signals.track_outcomes" in group
        assert "signals.track_interval" in group
