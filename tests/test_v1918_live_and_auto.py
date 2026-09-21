"""
آزمون‌های نسخهٔ ۱.۹.۱۸.

شش ایراد تازهٔ کاربر را پوشش می‌دهد:

1. هوش مصنوعی در بخش «تولید سیگنال» بالای صفحه کار نمی‌کرد (کند بود).
2. بخش پویش سریع بود ولی بخش بالا نه.
4. معاملهٔ خودکار اضافه نشده بود (موتور بود، ولی هیچ دکمه‌ای نداشت).
5. نمودار بخش تحلیل باید زنده و شبیه تریدینگ‌ویو باشد.
6. روی سیگنالِ ساخته‌شده نمی‌شد دوباره تحلیل گرفت.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from ai.agent.autonomous_agent import AutonomousAgent
from app.database.repositories.signal_repository import SignalRepository


# ---------------------------------------------------------------------------
# ۱ و ۲ — سرعت بخش بالای صفحه
# ---------------------------------------------------------------------------
class TestAgentPreload:
    """شواهد باید موازی و پیش از حلقه گرفته شوند، نه یکی‌یکی از مدل."""

    def test_preload_helper_exists(self) -> None:
        """متد پیش‌بارگذاری باید وجود داشته باشد."""
        assert hasattr(AutonomousAgent, "_preload_evidence")
        assert inspect.iscoroutinefunction(AutonomousAgent._preload_evidence)

    def test_preload_runs_tools_in_parallel(self) -> None:
        """
        باید از `asyncio.gather` استفاده کند.

        اجرای پشت‌سرهم همان کندی قبلی را برمی‌گرداند؛ روی کارت گرافیک
        ضعیف کاربر هر فراخوانی ده‌ها ثانیه است.
        """
        source = inspect.getsource(AutonomousAgent._preload_evidence)
        assert "gather" in source

    def test_preload_collects_the_three_core_tools(self) -> None:
        """قیمت لحظه‌ای، چند تایم‌فریم و اندیکاتورها باید از پیش آماده شوند."""
        source = inspect.getsource(AutonomousAgent._preload_evidence)
        for tool in (
            "get_ticker",
            "get_multi_timeframe_data",
            "calculate_multiple_indicators",
        ):
            assert tool in source, tool

    def test_loop_injects_preloaded_evidence(self) -> None:
        """حلقه باید شواهد آماده را به پیام کاربر بدهد."""
        source = inspect.getsource(AutonomousAgent._loop)
        assert "_preload_evidence" in source

    def test_render_tool_data_truncates(self) -> None:
        """متن طولانی باید کوتاه شود تا پنجرهٔ متن مدل پر نشود."""
        rendered = AutonomousAgent._render_tool_data({"x": "y" * 9000}, limit=300)
        assert len(rendered) <= 320

    def test_render_tool_data_handles_empty(self) -> None:
        """دادهٔ خالی نباید استثنا بدهد."""
        assert isinstance(AutonomousAgent._render_tool_data(None), str)
        assert isinstance(AutonomousAgent._render_tool_data({}), str)


class TestDeadlineGuard:
    """مدل کند نباید کاربر را با «انتظار ۰٪» رها کند."""

    def test_loop_tracks_elapsed_time(self) -> None:
        """حلقه باید زمان سپری‌شده را بسنجد، نه فقط شمار گام را."""
        source = inspect.getsource(AutonomousAgent._loop)
        assert "monotonic" in source

    def test_loop_forces_a_final_answer_before_timeout(self) -> None:
        """پیش از پایان مهلت باید یک جمع‌بندی اجباری خواسته شود."""
        source = inspect.getsource(AutonomousAgent._loop)
        assert "TIME IS UP" in source


# ---------------------------------------------------------------------------
# ۶ — تحلیل دوباره روی سیگنال موجود
# ---------------------------------------------------------------------------
class TestRerunAnalysis:
    """کاربر باید از کارت و از جدول سابقه تحلیل بگیرد."""

    def test_repository_exposes_flat_payload(self) -> None:
        """`analysis_payload` باید دیکشنری بدهد، نه تاپل."""
        assert hasattr(SignalRepository, "analysis_payload")

    def test_repository_can_update_analysis(self) -> None:
        """متن تازه باید قابل ذخیره باشد."""
        assert hasattr(SignalRepository, "update_analysis")

    def test_get_with_analysis_still_returns_tuple(self) -> None:
        """
        رفتار قدیمی نباید عوض شود.

        دلیل وجود `analysis_payload` همین است: کد قدیمی تاپل را با `**`
        باز می‌کرد و `TypeError` می‌گرفت.
        """
        source = inspect.getsource(SignalRepository.get_with_analysis)
        assert "return record, record.analysis" in source

    def test_controller_no_longer_unpacks_tuple(self) -> None:
        """کنترلر نباید دوباره تاپل را مثل دیکشنری باز کند."""
        from ui.controllers.main_controller import MainController

        source = inspect.getsource(MainController.show_signal_analysis)
        # فراخوانی واقعی را بررسی می‌کنیم، نه صرف حضور نام در متن؛
        # وگرنه یک توضیح فارسی هم آزمون را رد می‌کند.
        assert "signal_repository.get_with_analysis(" not in source
        assert "signal_repository.analysis_payload(" in source

    def test_controller_has_rerun_handler(self) -> None:
        """هندلر تحلیل دوباره باید وجود داشته باشد."""
        from ui.controllers.main_controller import MainController

        assert hasattr(MainController, "_rerun_signal_analysis")

    def test_rerun_persists_result(self) -> None:
        """نتیجهٔ تحلیل تازه باید ذخیره شود تا با بستن پنجره از بین نرود."""
        from ui.controllers.main_controller import MainController

        source = inspect.getsource(MainController._rerun_signal_analysis)
        assert "update_analysis" in source

    def test_application_keeps_last_signal_id(self) -> None:
        """
        بدون نگه‌داشتن شناسه، دکمهٔ تحلیلِ کارت هرگز فعال نمی‌شود.

        `TradingSignal.to_dict()` شناسه ندارد چون کلاس اسلات‌محور است.
        """
        from app.application import Application

        source = inspect.getsource(Application.generate_signal)
        assert "_last_signal_id" in source


@pytest.mark.usefixtures("qt_application")
class TestRerunDialog:
    """پنجرهٔ تحلیل باید دکمهٔ اجرای دوباره داشته باشد."""

    def _dialog(self, payload: dict[str, Any] | None = None) -> Any:
        from localization import Translator
        from ui.dialogs.analysis_dialog import AnalysisDialog

        return AnalysisDialog(payload or {"symbol": "BTC/USDT"}, Translator("fa"))

    def test_dialog_has_rerun_button(self) -> None:
        """دکمه باید ساخته شود."""
        assert hasattr(self._dialog(), "rerun_button")

    def test_rerun_emits_signal_with_payload(self) -> None:
        """کلیک باید سیگنال را با دادهٔ سیگنال بفرستد."""
        dialog = self._dialog({"symbol": "ETH/USDT", "id": 7})
        seen: list[dict[str, Any]] = []
        dialog.rerun_requested.connect(seen.append)
        dialog.rerun_button.click()
        assert seen and seen[0]["symbol"] == "ETH/USDT"

    def test_button_locks_while_running(self) -> None:
        """در حین تحلیل نباید بتوان دوباره کلیک کرد."""
        dialog = self._dialog()
        dialog.rerun_button.click()
        assert not dialog.rerun_button.isEnabled()

    def test_new_text_replaces_viewer_content(self) -> None:
        """متن تازه باید در همان پنجره بنشیند."""
        dialog = self._dialog()
        dialog.set_analysis_text("تحلیل تازه")
        assert "تحلیل تازه" in dialog.viewer.toPlainText()
        assert dialog.rerun_button.isEnabled()

    def test_empty_analysis_shows_guidance_not_blank(self) -> None:
        """سیگنال بدون تحلیل نباید پنجرهٔ خالی بدهد."""
        dialog = self._dialog({"symbol": "BTC/USDT", "analysis_text": ""})
        assert dialog.viewer.toPlainText().strip()


# ---------------------------------------------------------------------------
# ۵ — نمودار زنده شبیه تریدینگ‌ویو
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("qt_application")
class TestLiveChart:
    """نمودار باید زنده، قابل زوم و چندحالته باشد."""

    def _chart(self) -> Any:
        from localization import Translator
        from ui.charts.price_chart import PriceChart

        return PriceChart(Translator("fa"))

    def _candles(self, count: int = 40) -> list[Any]:
        from app.core.models import Candle

        base = 1_700_000_000
        out = []
        for index in range(count):
            price = 100.0 + index
            out.append(
                Candle(
                    timestamp=base + index * 900,
                    open=price,
                    high=price + 2,
                    low=price - 2,
                    close=price + 1,
                    volume=10.0 + index,
                )
            )
        return out

    def test_chart_supports_three_types(self) -> None:
        """کندل، خطی و ناحیه‌ای."""
        chart = self._chart()
        chart.set_candles(self._candles(), "15m", "BTC/USDT")

        chart.set_chart_type("line")
        assert not chart.candles_item.isVisible()

        chart.set_chart_type("area")
        assert chart._line_curve.isVisible()

        chart.set_chart_type("candles")
        assert chart.candles_item.isVisible()

    def test_unknown_type_falls_back_to_candles(self) -> None:
        """نوع ناشناخته نباید نمودار را خالی کند."""
        chart = self._chart()
        chart.set_candles(self._candles(), "15m")
        chart.set_chart_type("nonsense")
        assert chart.candles_item.isVisible()

    def test_live_price_line_appears(self) -> None:
        """خط قیمت زنده باید دیده شود."""
        chart = self._chart()
        chart.set_candles(self._candles(), "15m")
        chart.set_live_price(123.45)
        assert chart._price_line.isVisible()
        assert "123" in chart._price_tag.toPlainText()

    def test_live_price_ignores_invalid_values(self) -> None:
        """قیمت صفر یا منفی نباید خط بکشد."""
        chart = self._chart()
        chart.set_candles(self._candles(), "15m")
        chart.set_live_price(0)
        assert not chart._price_line.isVisible()

    def test_manual_zoom_survives_a_refresh(self) -> None:
        """
        مهم‌ترین رفتار تریدینگ‌ویو.

        نمودار هر چند ثانیه تازه می‌شود؛ اگر زوم کاربر پاک شود، کار
        کردن با نمودار ممکن نیست.
        """
        chart = self._chart()
        candles = self._candles()
        chart.set_candles(candles, "15m")
        chart._on_manual_range()
        chart.price_plot.setXRange(candles[10].timestamp, candles[20].timestamp)
        before = chart.price_plot.viewRange()[0]
        chart.set_candles(candles, "15m")
        after = chart.price_plot.viewRange()[0]
        assert [round(v) for v in before] == [round(v) for v in after]

    def test_fit_button_restores_auto_range(self) -> None:
        """«تناسب صفحه» باید حالت خودکار را برگرداند."""
        chart = self._chart()
        chart.set_candles(self._candles(), "15m")
        chart._on_manual_range()
        assert chart._user_zoomed
        chart.reset_zoom()
        assert not chart._user_zoomed

    def test_analysis_page_exposes_chart_tools(self) -> None:
        """نوار ابزار نمودار باید روی صفحهٔ تحلیل باشد."""
        from localization import Translator
        from ui.pages.analysis_page import AnalysisPage

        page = AnalysisPage(Translator("fa"))
        assert hasattr(page, "chart_type_combo")
        assert hasattr(page, "fit_button")
        assert hasattr(page, "live_price_label")
        assert page.chart_type_combo.count() == 3

    def test_analysis_page_updates_live_price(self) -> None:
        """عدد قیمت زنده باید روی صفحه بنشیند."""
        from localization import Translator
        from ui.pages.analysis_page import AnalysisPage

        page = AnalysisPage(Translator("fa"))
        page.set_live_price(64000.0, change_percent=1.5)
        assert "64,000" in page.live_price_label.text()
        assert "+1.50%" in page.live_price_label.text()

    def test_controller_has_a_separate_price_ticker(self) -> None:
        """قیمت زنده باید تیک سبک خودش را داشته باشد."""
        from ui.controllers.main_controller import LIVE_PRICE_TICK_MS, MainController

        assert LIVE_PRICE_TICK_MS < 15_000
        assert hasattr(MainController, "_live_price_tick")


# ---------------------------------------------------------------------------
# ۴ — معاملهٔ خودکار باید دیده شود
# ---------------------------------------------------------------------------
@pytest.mark.usefixtures("qt_application")
class TestAutoTradingVisible:
    """موتور از قبل بود؛ چیزی که نبود، راهی برای روشن‌کردنش بود."""

    def _page(self) -> Any:
        from localization import Translator
        from ui.pages.trades_page import TradesPage

        return TradesPage(Translator("fa"))

    def test_trades_page_has_auto_panel(self) -> None:
        """پنل معاملهٔ خودکار باید روی صفحه باشد."""
        page = self._page()
        assert hasattr(page, "auto_toggle_button")
        assert hasattr(page, "auto_state_label")
        assert hasattr(page, "auto_config_label")

    def test_toggle_emits_start_then_stop(self) -> None:
        """دکمه باید بین شروع و توقف جابه‌جا شود."""
        page = self._page()
        seen: list[bool] = []
        page.auto_trade_toggled.connect(seen.append)

        page.auto_toggle_button.click()
        assert seen == [True]

        page.set_auto_state(True)
        page.auto_toggle_button.click()
        assert seen == [True, False]

    def test_state_label_reflects_engine(self) -> None:
        """برچسب وضعیت باید با موتور هماهنگ باشد."""
        page = self._page()
        page.set_auto_state(True, "در حال اجرا • 1 / 3")
        assert page.auto_state_label.text()
        assert "1 / 3" in page.auto_status_label.text()

    def test_no_untranslated_keys_on_screen(self) -> None:
        """هیچ کلید ترجمه‌نشده‌ای نباید به کاربر نشان داده شود."""
        page = self._page()
        for text in (
            page.auto_toggle_button.text(),
            page.auto_state_label.text(),
            page.auto_status_label.text(),
        ):
            assert "trades.auto" not in text

    def test_controller_wires_the_engine(self) -> None:
        """کنترلر باید موتور واقعی را بسازد و روشن/خاموش کند."""
        from ui.controllers.main_controller import MainController

        assert hasattr(MainController, "toggle_auto_trading")
        assert hasattr(MainController, "_auto_trader")
        source = inspect.getsource(MainController._auto_trader)
        assert "AutoTrader" in source

    def test_controller_uses_user_settings_not_hardcoded_numbers(self) -> None:
        """
        عددها باید از تنظیمات کاربر بیایند.

        کاربر صریح گفت هدف سود، حد ضرر و اهرم را خودش تعیین می‌کند.
        """
        from ui.controllers.main_controller import MainController

        source = inspect.getsource(MainController._auto_trader)
        assert "build_trader_config" in source

    def test_engine_defaults_to_paper(self) -> None:
        """حالت پیش‌فرض باید کاغذی باشد، نه پول واقعی."""
        from trading.auto_trader import AutoTradeConfig

        config = AutoTradeConfig(10, 2, 3, 10).validated()
        assert config.mode == "paper"
        assert not config.is_live
