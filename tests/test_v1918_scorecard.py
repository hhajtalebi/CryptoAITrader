"""
آزمون‌های دفترچهٔ نتیجهٔ پیش‌بینی‌ها.

`score_forecast()` در نسخهٔ ۱.۹.۱۷ ساخته شد ولی هیچ‌چیز صدایش نمی‌زد.
این آزمون‌ها تضمین می‌کنند که حالا واقعاً اجرا می‌شود و حکمش درست است.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest

from signals.scorecard import (
    ACCEPTABLE_DRIFT,
    MIN_SAMPLES_FOR_VERDICT,
    TARGET_HIT_RATE,
    build_report,
    horizon_is_due,
)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


def _forecast(horizon: str, lower: float, upper: float) -> dict:
    """یک ردیف پیش‌بینی ساختگی."""
    return {"horizon": horizon, "lower": lower, "upper": upper, "probability": 60}


def _signal(created: datetime, *rows: dict, symbol: str = "BTC/USDT") -> dict:
    """یک سیگنال ساختگی با پیش‌بینی."""
    return {"symbol": symbol, "created_at": created, "forecast": list(rows)}


class TestHorizonDue:
    """افقی که زمانش نرسیده نباید قضاوت شود."""

    def test_matured_horizon_is_due(self) -> None:
        """یک ساعت پس از ساخت، افق ۱ ساعته سررسید شده است."""
        assert horizon_is_due(NOW - timedelta(hours=2), "1h", now=NOW)

    def test_immature_horizon_is_not_due(self) -> None:
        """افق ۴ ساعته پس از ۲ ساعت هنوز سررسید نشده."""
        assert not horizon_is_due(NOW - timedelta(hours=2), "4h", now=NOW)

    def test_exactly_at_boundary_counts_as_due(self) -> None:
        """دقیقاً سر وقت، سررسید شده حساب می‌شود."""
        assert horizon_is_due(NOW - timedelta(hours=1), "1h", now=NOW)

    def test_unknown_horizon_is_never_due(self) -> None:
        """افق ناشناخته نباید باعث استثنا یا شمارش اشتباه شود."""
        assert not horizon_is_due(NOW - timedelta(days=400), "17y", now=NOW)

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        """تاریخ بدون منطقهٔ زمانی نباید خطا بدهد."""
        naive = (NOW - timedelta(hours=5)).replace(tzinfo=None)
        assert horizon_is_due(naive, "1h", now=NOW)


class TestBuildReport:
    """ساخت گزارش از سیگنال‌های ذخیره‌شده."""

    def test_empty_input_is_safe(self) -> None:
        """بدون داده نباید استثنا بدهد."""
        report = build_report([], {}, now=NOW)
        assert report.checked == 0
        assert report.hit_rate == 0.0
        assert report.verdict == "insufficient_data"

    def test_price_inside_band_counts_as_hit(self) -> None:
        """قیمت داخل بازه یعنی اصابت."""
        signals = [_signal(NOW - timedelta(hours=3), _forecast("1h", 100, 110))]
        report = build_report(signals, {("BTC/USDT", "1h"): 105.0}, now=NOW)
        assert report.checked == 1
        assert report.hits == 1
        assert report.hit_rate == 100.0

    def test_price_outside_band_counts_as_miss(self) -> None:
        """قیمت بیرون بازه یعنی خطا، و فاصله ثبت می‌شود."""
        signals = [_signal(NOW - timedelta(hours=3), _forecast("1h", 100, 110))]
        report = build_report(signals, {("BTC/USDT", "1h"): 130.0}, now=NOW)
        assert report.hits == 0
        assert report.rows[0].average_miss == 20.0

    def test_immature_horizon_is_pending_not_counted(self) -> None:
        """
        مهم‌ترین قاعدهٔ صداقت آماری.

        افق نرسیده نه «درست» است نه «غلط» — اصلاً نباید شمرده شود.
        """
        signals = [_signal(NOW - timedelta(minutes=10), _forecast("4h", 100, 110))]
        report = build_report(signals, {("BTC/USDT", "4h"): 105.0}, now=NOW)
        assert report.checked == 0
        assert report.pending == 1

    def test_missing_price_is_pending_not_a_miss(self) -> None:
        """نبودِ قیمت واقعی نباید به‌عنوان خطا ثبت شود."""
        signals = [_signal(NOW - timedelta(hours=3), _forecast("1h", 100, 110))]
        report = build_report(signals, {}, now=NOW)
        assert report.checked == 0
        assert report.pending == 1

    def test_rows_are_grouped_by_horizon(self) -> None:
        """هر افق ردیف خودش را دارد."""
        signals = [
            _signal(
                NOW - timedelta(hours=30),
                _forecast("1h", 100, 110),
                _forecast("4h", 90, 120),
            )
        ]
        prices = {("BTC/USDT", "1h"): 105.0, ("BTC/USDT", "4h"): 200.0}
        report = build_report(signals, prices, now=NOW)
        assert [row.horizon for row in report.rows] == ["1h", "4h"]
        assert report.rows[0].hits == 1
        assert report.rows[1].hits == 0

    def test_rows_keep_a_stable_order(self) -> None:
        """ترتیب ردیف‌ها باید ثابت باشد، نه تصادفی."""
        signals = [
            _signal(
                NOW - timedelta(days=3),
                _forecast("1d", 1, 2),
                _forecast("15m", 1, 2),
                _forecast("1h", 1, 2),
            )
        ]
        prices = {
            ("BTC/USDT", "1d"): 1.5,
            ("BTC/USDT", "15m"): 1.5,
            ("BTC/USDT", "1h"): 1.5,
        }
        report = build_report(signals, prices, now=NOW)
        assert [row.horizon for row in report.rows] == ["15m", "1h", "1d"]

    def test_signal_without_forecast_is_skipped(self) -> None:
        """سیگنال بدون پیش‌بینی نباید در آمار بیاید."""
        report = build_report(
            [{"symbol": "BTC/USDT", "created_at": NOW, "forecast": []}], {}, now=NOW
        )
        assert report.signals_examined == 0

    def test_malformed_rows_do_not_crash(self) -> None:
        """دادهٔ خراب نباید کل گزارش را از کار بیندازد."""
        signals = [
            {
                "symbol": "BTC/USDT",
                "created_at": NOW - timedelta(hours=3),
                "forecast": ["nonsense", {"horizon": ""}, _forecast("1h", 100, 110)],
            }
        ]
        report = build_report(signals, {("BTC/USDT", "1h"): 105.0}, now=NOW)
        assert report.hits == 1

    def test_multiple_symbols_are_kept_separate(self) -> None:
        """قیمت یک نماد نباید به نماد دیگر نسبت داده شود."""
        signals = [
            _signal(NOW - timedelta(hours=3), _forecast("1h", 100, 110)),
            _signal(NOW - timedelta(hours=3), _forecast("1h", 1, 2), symbol="ETH/USDT"),
        ]
        prices = {("BTC/USDT", "1h"): 105.0, ("ETH/USDT", "1h"): 50.0}
        report = build_report(signals, prices, now=NOW)
        assert report.checked == 2
        assert report.hits == 1


class TestVerdict:
    """حکم باید با واقعیت آماری بخواند."""

    def _report_with(self, hits: int, total: int):
        """گزارشی با نرخ اصابت دلخواه."""
        signals = []
        for index in range(total):
            inside = index < hits
            signals.append(
                _signal(NOW - timedelta(hours=3), _forecast("1h", 100, 110))
            )
            signals[-1]["symbol"] = f"S{index}/USDT"
        prices = {
            (f"S{index}/USDT", "1h"): (105.0 if index < hits else 500.0)
            for index in range(total)
        }
        return build_report(signals, prices, now=NOW)

    def test_small_sample_gives_no_verdict(self) -> None:
        """
        با نمونهٔ کم هیچ حکمی صادر نمی‌شود.

        تغییر ضریب بر پایهٔ سه نمونه، تنظیم را خراب می‌کند.
        """
        report = self._report_with(1, 3)
        assert report.verdict == "insufficient_data"
        assert report.suggested_sigma_shift == 0.0

    def test_low_hit_rate_means_bands_too_narrow(self) -> None:
        """نرخ اصابت خیلی پایین ⇒ بازه‌ها تنگ‌اند."""
        report = self._report_with(10, 40)
        assert report.checked >= MIN_SAMPLES_FOR_VERDICT
        assert report.verdict == "too_narrow"
        assert report.suggested_sigma_shift > 0

    def test_perfect_hit_rate_means_bands_too_wide(self) -> None:
        """نرخ اصابت ۱۰۰٪ ⇒ بازه‌ها آن‌قدر پهن‌اند که بی‌فایده‌اند."""
        report = self._report_with(40, 40)
        assert report.verdict == "too_wide"
        assert report.suggested_sigma_shift < 0

    def test_on_target_is_calibrated(self) -> None:
        """نزدیک هدف ۸۰٪ ⇒ تنظیم درست است."""
        report = self._report_with(32, 40)
        assert report.hit_rate == TARGET_HIT_RATE
        assert report.verdict == "calibrated"
        assert report.suggested_sigma_shift == 0.0

    def test_small_drift_is_tolerated(self) -> None:
        """انحراف کوچک نباید باعث تغییر ضریب شود."""
        report = self._report_with(30, 40)
        assert abs(report.hit_rate - TARGET_HIT_RATE) < ACCEPTABLE_DRIFT
        assert report.verdict == "calibrated"

    def test_sigma_shift_is_capped(self) -> None:
        """پیشنهاد تغییر نباید پرش بزرگ بدهد."""
        report = self._report_with(0, 40)
        assert 0 < report.suggested_sigma_shift <= 0.2


class TestApplicationWiring:
    """تابع باید واقعاً از برنامه قابل فراخوانی باشد."""

    def test_application_exposes_score_forecasts(self) -> None:
        """متد باید روی `Application` باشد."""
        from app.application import Application

        assert hasattr(Application, "score_forecasts")
        assert inspect.iscoroutinefunction(Application.score_forecasts)

    def test_it_uses_historical_candles_not_current_price(self) -> None:
        """
        پیش‌بینیِ «یک ساعت بعد» باید با قیمت همان یک ساعت بعد سنجیده
        شود، نه با قیمت امروز.
        """
        from app.application import Application

        source = inspect.getsource(Application.score_forecasts)
        assert "get_candles" in source
        assert "get_current_price" not in source

    def test_controller_can_refresh_the_scorecard(self) -> None:
        """کنترلر باید دکمهٔ صفحه را به تابع وصل کرده باشد."""
        from ui.controllers.main_controller import MainController

        assert hasattr(MainController, "refresh_scorecard")
        source = inspect.getsource(MainController.refresh_scorecard)
        assert "score_forecasts" in source


@pytest.mark.usefixtures("qt_application")
class TestScorecardPage:
    """زبانهٔ دفترچهٔ نتیجه روی صفحهٔ گزارش‌ها."""

    def _page(self):
        from localization import Translator
        from ui.pages.reports_page import ReportsPage

        return ReportsPage(Translator("fa"))

    def test_reports_page_has_three_tabs(self) -> None:
        """زبانهٔ تازه باید اضافه شده باشد بدون حذف زبانه‌های قبلی."""
        assert self._page().tabs.count() == 3

    def test_table_renders_rows(self) -> None:
        """ردیف‌ها باید روی جدول بنشینند."""
        page = self._page()
        page.set_scorecard(
            {
                "rows": [
                    {
                        "horizon": "1h",
                        "checked": 40,
                        "hits": 26,
                        "hit_rate": 65.0,
                        "average_miss": 12.5,
                    }
                ],
                "checked": 40,
                "hit_rate": 65.0,
                "target_rate": 80.0,
                "verdict": "too_narrow",
                "pending": 3,
            }
        )
        assert page.scorecard_table.rowCount() == 1
        assert page.scorecard_table.item(0, 0).text() == "1h"
        assert "65.0%" in page.scorecard_table.item(0, 3).text()

    def test_empty_report_shows_guidance(self) -> None:
        """گزارش خالی باید پیام روشن بدهد، نه جدول خالی و بی‌توضیح."""
        page = self._page()
        page.set_scorecard({})
        assert page.scorecard_verdict_label.text().strip()

    def test_no_untranslated_keys(self) -> None:
        """هیچ کلید ترجمه‌نشده‌ای نباید دیده شود."""
        page = self._page()
        page.set_scorecard(
            {"rows": [], "checked": 25, "hit_rate": 50.0, "verdict": "too_narrow",
             "target_rate": 80.0, "pending": 1}
        )
        assert "scorecard." not in page.scorecard_verdict_label.text()
        assert "scorecard." not in page.scorecard_note.text()

    def test_refresh_button_emits(self) -> None:
        """دکمه باید سیگنال بدهد تا کنترلر محاسبه کند."""
        page = self._page()
        seen: list[int] = []
        page.scorecard_refresh_requested.connect(lambda: seen.append(1))
        page.scorecard_refresh_button.click()
        assert seen == [1]
