"""
آزمون‌های ۲٫۷٫۲ — چرا نرخ برد ۲٪ نشان داده می‌شد و چرا دیگر نمی‌شود.

سه نقص که با هم آمار سیگنال‌ها را نظام‌مند وارونه می‌کردند:

۱. پنجرهٔ قیمتِ پیگیری از `high_24h`/`low_24h` تیکر ساخته می‌شد، در حالی
   که `update_outcome` آن را «از آخرین بررسی تا حالا» می‌خواند. بازهٔ ۲۴
   ساعته تقریباً همیشه حد ضرر را در بر می‌گیرد، پس تقریباً هر سیگنال در
   نخستین بررسی «حد ضرر خورده» اعلام می‌شد — حتی اگر بعد از ورود قیمت
   اصلاً به سمت حد ضرر نرفته بود. این باگ در گزارش کاربر «۵۸ بسته: ۱ برد
   و ۵۷ باخت» دقیقاً همین اثر را داشت.

۲. «برد» فقط رسیدن به آخرین هدف (۴R) حساب می‌شد؛ سیگنالی که به هدف اول
   و دوم رسیده و بعد با سود جزئی بسته شده «باخت» بود.

۳. خروج پله‌ای در حسابداری R نبود: حد ضررِ بعد از هدف اول، «-۱R» ثبت
   می‌شد در حالی که معامله‌گر بخشی را با سود بسته است.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from signals.outcome_tracker import (
    STATUS_PENDING,
    STATUS_STOP,
    STATUS_TARGET,
    OutcomeState,
    PriceWindow,
    ladder_exit,
    summarize,
    update_outcome,
    window_from_ticks,
)


# ---------------------------------------------------------------------------
# ۱) پنجرهٔ قیمت باید «از آخرین بررسی» باشد، نه ۲۴ ساعت اخیر
# ---------------------------------------------------------------------------


class TestWindowIsIntervalScoped:
    """پنجره هرگز نباید قیمت‌های پیش از بازه را وارد تصمیم کند."""

    def test_ticks_before_the_interval_are_ignored(self) -> None:
        """
        بازتولید باگِ گزارش‌شده.

        سیگنال LONG روی ۱۰۰ با حد ضرر ۹۵. در ۲۴ ساعت اخیر قیمت تا ۹۴
        هم پایین رفته (همان نوسانی که ساختار حد ضرر از آن ساخته شده)،
        اما **بعد از ورود** قیمت هرگز زیر ۹۵ نیامده است.
        """
        entry_moment = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
        since_ms = entry_moment.timestamp() * 1000.0

        # تیک‌های قدیمی (پیش از ورود) — قیمت تا ۹۴ پایین رفته بود
        old_ticks = [(since_ms - 3_600_000, 94.0), (since_ms - 1_800_000, 97.0)]
        # تیک‌های بعد از ورود — فقط بالای حد ضرر
        new_ticks = [(since_ms + 60_000, 100.5), (since_ms + 120_000, 101.0)]

        # رفتار قدیمی: high/low بیست‌وچهار ساعته (۹۴..۱۰۱) — فوراً STOP
        buggy = PriceWindow(last=100.0, high=101.0, low=94.0)
        state = _long_state(entry=100.0, stop=95.0)
        update_outcome(state, buggy, now=entry_moment + timedelta(minutes=3))
        assert state.status == STATUS_STOP, "رفتار قدیمی باید واقعاً STOP می‌داد"

        # رفتار اصلاح‌شده: فقط تیک‌های بعد از ورود
        state = _long_state(entry=100.0, stop=95.0)
        window = window_from_ticks(old_ticks + new_ticks, last=100.0, since_ms=since_ms)
        assert window.low >= 100.0, f"قیمتِ پیش از بازه نشت کرد: {window}"
        update_outcome(state, window, now=entry_moment + timedelta(minutes=3))
        assert state.status == STATUS_PENDING, "سیگنال سالم نباید حد ضرر خورده اعلام شود"

    def test_no_ticks_in_interval_falls_back_to_last_price_only(self) -> None:
        """بدون تیک در بازه، فقط قیمت لحظه‌ای — کم‌دقت ولی منصفانه."""
        window = window_from_ticks([], last=42.0, since_ms=123.0)
        assert window.last == 42.0
        assert window.high == 0.0 and window.low == 0.0
        assert window.ceiling == 42.0 and window.floor == 42.0

    def test_interval_extremes_are_the_real_deal(self) -> None:
        """وقتی تیک در بازه هست، افراطِ واقعیِ بازه باید بیاید."""
        window = window_from_ticks(
            [(500.0, 10.0), (600.0, 12.0), (700.0, 9.0), (800.0, 11.0)],
            last=11.0,
            since_ms=550.0,
        )
        assert window.high == 12.0
        assert window.low == 9.0

    def test_a_stop_inside_the_interval_is_still_caught(self) -> None:
        """اصلاح نباید کور باشد: لمسِ واقعیِ حد ضرر در بازه همچنان ثبت می‌شود."""
        state = _long_state(entry=100.0, stop=95.0)
        window = window_from_ticks(
            [(1_000.0, 100.0), (2_000.0, 94.5)], last=96.0, since_ms=0.0
        )
        update_outcome(state, window)
        assert state.status == STATUS_STOP


# ---------------------------------------------------------------------------
# ۲ و ۳) حسابداری خروجِ پله‌ای
# ---------------------------------------------------------------------------


class TestLadderAccounting:
    """خروج پله‌ای باید در آمار منعکس شود، نه فقط قیمت نهایی.

    سیاست حسابداری: سهم‌های مساوی (یک‌سوم) روی هر هدف، باقی‌مانده روی
    قیمت نهایی. عمداً **بدون** فرضِ «حد ضرر را سربه‌سر می‌کنیم»: این
    کفِ محافظه‌کارانه است و هرگز بهتر از واقعیت نشان نمی‌دهد.
    """

    def test_a_stop_after_the_first_target_is_a_small_loss_not_a_full_one(self) -> None:
        """
        هدف اول با ۱٫۵R لمس شده (یک‌سوم بانک شده)، بعد حد ضرر خورده.
        حسابداری قدیمی این را «-۱R» کامل ثبت می‌کرد؛ اکنون ‎-0.167R‎ است.
        (با سیاستِ سربه‌سر کردنِ حد ضرر پس از هدف اول، همین معامله سود
        می‌شد — ولی آن سیاست را به‌جای کاربر فرض نمی‌کنیم.)
        """
        state = _long_state(
            entry=100.0,
            stop=95.0,
            targets=(107.5, 112.5, 120.0),
            targets_hit=1,
            status=STATUS_STOP,
            exit_price=95.0,
        )
        _percent, r_value = ladder_exit(state)
        # دقیقاً: (1.5 + (-1) + (-1)) / 3 = -0.167
        assert r_value == round((1.5 - 1 - 1) / 3, 3)
        assert r_value > -1.0, "نباید دیگر -۱R کامل ثبت شود"

    def test_a_stop_after_the_second_target_is_a_win(self) -> None:
        """دو هدف بانک شده و بعد حد ضرر: معامله‌ای سودده — و باید برد حساب شود."""
        state = _long_state(
            entry=100.0,
            stop=95.0,
            targets=(107.5, 112.5, 120.0),
            targets_hit=2,
            status=STATUS_STOP,
            exit_price=95.0,
        )
        _percent, r_value = ladder_exit(state)
        # (1.5 + 2.5 - 1) / 3 = +1R
        assert r_value == round((1.5 + 2.5 - 1) / 3, 3)
        assert r_value > 0

    def test_a_stop_without_any_target_is_exactly_minus_one_r(self) -> None:
        """بدون هیچ هدفی، همه چیز روی حد ضرر: دقیقاً -۱R."""
        state = _long_state(
            entry=100.0, stop=95.0, targets=(107.5, 112.5, 120.0),
            targets_hit=0, status=STATUS_STOP, exit_price=95.0,
        )
        assert ladder_exit(state)[1] == -1.0

    def test_a_full_run_realizes_the_average_of_the_targets(self) -> None:
        """خروج کامل: میانگین R اهداف، نه فقط هدف آخر."""
        state = _long_state(
            entry=100.0, stop=95.0, targets=(107.5, 112.5, 120.0),
            targets_hit=3, status=STATUS_TARGET, exit_price=120.0,
        )
        # (1.5 + 2.5 + 4) / 3
        assert ladder_exit(state)[1] == round((1.5 + 2.5 + 4.0) / 3, 3)

    def test_short_ladder_flips_the_sign(self) -> None:
        """برای شورت، افت قیمت سود است."""
        state = OutcomeState(
            symbol="BTC/USDT",
            direction="SHORT",
            entry_price=100.0,
            stop_loss=105.0,
            take_profits=(92.5, 87.5, 80.0),
            status=STATUS_STOP,
            targets_hit=2,
            exit_price=105.0,
        )
        assert ladder_exit(state)[1] == round((1.5 + 2.5 - 1) / 3, 3)

    def test_open_signals_fall_back_to_the_price_path(self) -> None:
        """سیگنال باز: همان مقادیر مسیر قیمت."""
        state = _long_state(entry=100.0, stop=95.0, targets=(107.5, 112.5, 120.0))
        state.result_percent = 1.25
        state.realized_r = 0.25
        assert ladder_exit(state) == (1.25, 0.25)

    def test_dict_records_also_work(self) -> None:
        """`summarize` روی رکوردهای دیکشنری/پایگاه داده هم کار کند."""
        item = {
            "direction": "LONG",
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profits": [107.5, 112.5, 120.0],
            "targets_hit": 2,
            "status": STATUS_STOP,
            "exit_price": 95.0,
        }
        assert ladder_exit(item)[1] == round((1.5 + 2.5 - 1) / 3, 3)


# ---------------------------------------------------------------------------
# نرخ بردِ صادقانه در summarize
# ---------------------------------------------------------------------------


class TestSummarizeHonesty:
    """«برد» یعنی معاملهٔ سودده با خروجِ پله‌ای — نه فقط رسیدن به هدف سوم."""

    def test_a_stop_after_two_targets_counts_as_a_win(self) -> None:
        items = [
            _closed_item(status=STATUS_STOP, targets_hit=2, exit=95.0),
            _closed_item(status=STATUS_STOP, targets_hit=0, exit=95.0),
        ]
        summary = summarize(items)
        assert summary["wins"] == 1
        assert summary["losses"] == 1
        assert summary["win_rate"] == 50.0
        # وضعیت‌های خام هم شفاف می‌آیند
        assert summary["targets_full"] == 0
        assert summary["stops_hit"] == 2

    def test_a_stop_after_one_target_is_a_small_loss(self) -> None:
        """هدف اول و بعد حد ضرر: با سیاستِ بدون‌سربه‌سر، زیان کوچک است — نه برد."""
        items = [_closed_item(status=STATUS_STOP, targets_hit=1, exit=95.0)]
        summary = summarize(items)
        assert summary["wins"] == 0
        assert summary["losses"] == 1
        assert -1.0 < summary["average_r"] < 0.0

    def test_tp1_rate_is_reported(self) -> None:
        items = [
            _closed_item(status=STATUS_STOP, targets_hit=1, exit=95.0),
            _closed_item(status=STATUS_STOP, targets_hit=0, exit=95.0),
            _closed_item(status=STATUS_STOP, targets_hit=0, exit=95.0),
            _closed_item(status=STATUS_STOP, targets_hit=0, exit=95.0),
        ]
        summary = summarize(items)
        assert summary["tp1_reached"] == 1
        assert summary["tp1_rate"] == 25.0

    def test_a_full_target_run_is_still_a_win(self) -> None:
        items = [_closed_item(status=STATUS_TARGET, targets_hit=3, exit=120.0)]
        summary = summarize(items)
        assert summary["wins"] == 1
        assert summary["targets_full"] == 1
        assert summary["full_target_rate"] == 100.0

    def test_expectancy_r_uses_the_ladder(self) -> None:
        items = [
            _closed_item(status=STATUS_STOP, targets_hit=2, exit=95.0),
            _closed_item(status=STATUS_STOP, targets_hit=0, exit=95.0),
        ]
        summary = summarize(items)
        # میانگینِ (‎+1R‎ ، ‎-1R‎) = صفر
        assert summary["average_r"] == 0.0


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------


def _long_state(
    *,
    entry: float = 100.0,
    stop: float = 95.0,
    targets: tuple[float, ...] = (107.5, 112.5, 120.0),
    targets_hit: int = 0,
    status: str = STATUS_PENDING,
    exit_price: float | None = None,
) -> OutcomeState:
    return OutcomeState(
        symbol="BTC/USDT",
        direction="LONG",
        entry_price=entry,
        stop_loss=stop,
        take_profits=targets,
        status=status,
        targets_hit=targets_hit,
        exit_price=exit_price,
    )


def _closed_item(
    *, status: str, targets_hit: int, exit: float
) -> dict:
    return {
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profits": [107.5, 112.5, 120.0],
        "targets_hit": targets_hit,
        "status": status,
        "exit_price": exit,
        "result_percent": 0.0,
        "realized_r": 0.0,
    }
