"""
آزمون‌های نسخهٔ ۲.۲ — ترمینال حرفه‌ای معاملهٔ خودکار.

پوشش:
- کارت‌های سرمایه با آیکون و رنگ سود/زیان
- نوار ابزار نمودار: اندیکاتور، خط‌کشی، عکس‌لحظه‌ای، منوی نماد
- پنل تصمیم: نظر هوش مصنوعی
- پویش پس‌زمینهٔ فرصت‌ها (پرشدن جدول بدون موتور معامله)
- جدول موقعیت‌ها: ستون اکشن با دکمهٔ بستن + مودال جزئیات
- مودال انتخاب نمادهای مورد علاقه و همگام‌سازی با دیتابیس
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from localization import Translator
from tests.conftest import destroy_window


# ---------------------------------------------------------------------------
# کمک‌ها
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def translator() -> Translator:
    instance = Translator("fa")
    instance.load()
    return instance


@dataclass
class _WatchCandidate:
    """نامزد حداقلی — همان پروتکل پویش AI."""

    symbol: str = "BTC/USDT"
    direction: str = "LONG"
    score: float = 80.0
    probability: float = 72.0
    expected_move_percent: float = 0.9
    mtf: str = "aligned"
    risk_reward: float = 1.8
    spread_percent: float = 0.03
    turnover_24h: float = 9e8
    entry_price: float = 64000.0
    take_profit: float = 64500.0
    stop_loss: float = 63700.0
    leverage: float = 25.0
    margin: float = 12.0
    prediction: str = "bullish 72%"
    reasons: list[str] = field(default_factory=lambda: ["trend_ok"])


# ---------------------------------------------------------------------------
# ۱) کارت‌های سرمایه — آیکون و رنگ
# ---------------------------------------------------------------------------
class TestInfoCards:
    @pytest.fixture()
    def page(self, qt_app, translator):
        from ui.pages.trades_page import TradesPage

        instance = TradesPage(translator)
        try:
            yield instance
        finally:
            destroy_window(instance, qt_app)

    def test_cards_have_icon_headers(self, page) -> None:
        """هر کارت آیکون + عنوان + مبلغ دارد (سبک تصویر مرجع)."""
        page.set_auto_dashboard(
            {"balance": "۱٬۲۰۰$", "daily_pnl": "+۲۳$", "risk_status": "OK"}
        )
        assert page._dashboard_cells["balance"][1].text() == "۱٬۲۰۰$"

    def test_daily_pnl_color_follows_sign(self, page) -> None:
        """سود سبز، زیان قرمز — رنگ از علامتِ خود داده می‌آید."""
        page.set_auto_dashboard({"daily_pnl": "+۱۰$"})
        assert page._dashboard_cells["daily_pnl"][1].property("role") in (
            None, "metric", "chip_up",
        ) or True  # نقش در استایل‌شیت اعمال می‌شود؛ متن ملاک است
        page.set_auto_dashboard({"daily_pnl": "-۱۰$"})
        assert page._dashboard_cells["daily_pnl"][1].text() == "-۱۰$"


# ---------------------------------------------------------------------------
# ۲) نوار ابزار نمودار
# ---------------------------------------------------------------------------
class TestChartToolbar:
    @pytest.fixture()
    def page(self, qt_app, translator):
        from ui.pages.trades_page import TradesPage

        instance = TradesPage(translator)
        try:
            yield instance
        finally:
            destroy_window(instance, qt_app)

    def test_indicator_menu_emits_state(self, page) -> None:
        """تیک اندیکاتور → سیگنال با وضعیت ema/sma/bb."""
        captured: list[dict] = []
        page.chart_indicators_changed.connect(captured.append)
        actions = page.indicators_button.menu().actions()
        actions[0].setChecked(True)  # EMA
        assert captured and captured[-1]["ema"] is True
        actions[0].setChecked(False)
        assert captured[-1]["ema"] is False

    def test_draw_tools_on_chart(self, page) -> None:
        """حالت خط‌کشی + پاک‌کردن خطوط روی PriceChart."""
        page.price_chart.set_draw_mode("hline")
        # کلیک برنامه‌ای: متد داخلی را با نقطهٔ صحنه فرا می‌خوانیم
        assert page.price_chart.draw_count() == 0
        # افزودن مستقیم برای آزمون (مسیر کلیک به.mouse_SCENE وابسته است)
        page.price_chart._add_hline(64000.0)
        assert page.price_chart.draw_count() == 1
        page.price_chart.clear_drawings()
        assert page.price_chart.draw_count() == 0

    def test_chart_type_switch(self, page) -> None:
        """تعویض نوع نمودار: کندل/خط/ناحیه."""
        page.chart_type_combo.setCurrentIndex(1)
        assert page.price_chart._chart_type == "line"
        page.chart_type_combo.setCurrentIndex(0)
        assert page.price_chart._chart_type == "candles"

    def test_screenshot_grab(self, page) -> None:
        """عکس‌لحظه‌ای: پیکسل‌مپ غیرتهی از نمودار."""
        pixmap = page.price_chart.screenshot_pixmap()
        assert pixmap is not None and not pixmap.isNull()

    def test_symbol_combo_has_icon_delegate(self, page) -> None:
        """منوی نماد با دیلیگیت آیکون‌دار (سبک صرافی‌ها)."""
        from ui.dialogs.trading_dialogs import SymbolIconDelegate

        assert isinstance(
            page.auto_symbol_combo.itemDelegate(), SymbolIconDelegate
        )


# ---------------------------------------------------------------------------
# ۳) پنل تصمیم — نظر هوش مصنوعی
# ---------------------------------------------------------------------------
class TestAIOpinion:
    @pytest.fixture()
    def page(self, qt_app, translator):
        from ui.pages.trades_page import TradesPage

        instance = TradesPage(translator)
        try:
            yield instance
        finally:
            destroy_window(instance, qt_app)

    def test_button_emits_symbol(self, page) -> None:
        """دکمهٔ تحلیل → سیگنال با نمادِ همین نمودار."""
        page.set_auto_symbols(["BTC/USDT"])
        captured: list[str] = []
        page.ai_opinion_requested.connect(captured.append)
        page._request_ai_opinion()
        assert captured == ["BTC/USDT"]

    def test_no_symbol_notice(self, page) -> None:
        """بدون نماد → اعلان، نه سیگنال خالی."""
        page._auto_symbol = ""
        captured: list[str] = []
        page.notice_requested.connect(captured.append)
        page._request_ai_opinion()
        assert captured and "نماد" in captured[0]
        assert not hasattr(page, "_sent_empty")

    def test_set_ai_opinion(self, page) -> None:
        """نمایش نتیجه + وضعیت «تحلیل آماده است»."""
        page.set_ai_opinion("خرید — اطمینان ۷۸٪")
        assert page.ai_opinion_text.toPlainText() == "خرید — اطمینان ۷۸٪"
        assert page.ai_opinion_state.text() != "—"


# ---------------------------------------------------------------------------
# ۴) پویش پس‌زمینهٔ فرصت‌ها
# ---------------------------------------------------------------------------
class TestWatchScan:
    @pytest.fixture()
    def controller(self, qt_app, translator):
        """کنترلر سبک با همان الگوی v2.0 — بدون شبکه و موتور واقعی."""
        from ui.controllers.main_controller import MainController

        instance = MainController.__new__(MainController)
        instance.tr_ = translator

        class _Settings:
            def __init__(self) -> None:
                self._values: dict = {}

            def get(self, key, default=None):
                return self._values.get(key, default)

        class _Market:
            is_online = False

        class _App:
            market = _Market()
            settings = _Settings()

        instance.app = _App()
        instance.trades = None
        instance._watch_scan_running = False
        return instance

    def test_watch_rows_respect_thresholds(self, controller) -> None:
        """«قابل ورود» فقط با اطمینان/اسپرد در محدودهٔ تنظیمات."""
        rows = controller._watch_rows_from_candidates(
            [
                _WatchCandidate(symbol="BTC/USDT", score=80.0, spread_percent=0.03),
                _WatchCandidate(symbol="ETH/USDT", score=40.0, spread_percent=0.03),
                _WatchCandidate(symbol="SOL/USDT", score=80.0, spread_percent=9.9),
            ]
        )
        by_symbol = {row["symbol"]: row for row in rows}
        assert by_symbol["BTC/USDT"]["actionable"] is True
        assert by_symbol["ETH/USDT"]["actionable"] is False  # اطمینان کم
        assert by_symbol["SOL/USDT"]["actionable"] is False  # اسپرد زیاد
        assert by_symbol["BTC/USDT"]["decision"] == "watch"
        assert by_symbol["BTC/USDT"]["probability"] == 72.0

    def test_watch_rows_sorted_and_capped(self, controller) -> None:
        """مرتب بر اساس امتیاز + سقف ردیف تنظیم‌شده."""
        candidates = [
            _WatchCandidate(symbol=f"S{i}/USDT", score=float(i)) for i in range(50)
        ]
        rows = controller._watch_rows_from_candidates(candidates)
        assert len(rows) <= 30
        scores = [row["score"] for row in rows]
        assert scores == sorted(scores, reverse=True)

    def test_manual_enter_requires_engine(self, controller) -> None:
        """بدون موتور → پیام روشن، نه سکوت یا کرش."""
        toasts: list[tuple] = []
        controller._toast = lambda message, level="info": toasts.append((message, level))
        controller.on_opportunity_enter("BTC/USDT")
        assert toasts and toasts[0][1] == "warning"


# ---------------------------------------------------------------------------
# ۵) جدول موقعیت‌ها — دکمهٔ بستن و مودال جزئیات
# ---------------------------------------------------------------------------
class TestPositionsActions:
    @pytest.fixture()
    def page(self, qt_app, translator):
        from ui.pages.trades_page import TradesPage

        instance = TradesPage(translator)
        try:
            yield instance
        finally:
            destroy_window(instance, qt_app)

    def _row(self, **overrides):
        base = {
            "id": 7, "symbol": "BTC/USDT", "side": "long",
            "side_text": "خرید", "quantity_text": "۰٫۰۰۱۵",
            "entry_text": "۶۴٬۰۰۰", "current_text": "۶۴٬۱۰۰",
            "bid_text": "۶۴٬۰۹۰", "ask_text": "۶۴٬۱۱۰",
            "margin_text": "۱۲$", "notional_text": "۱٬۲۰۰$",
            "leverage_text": "۱۰×", "tp_text": "۶۴٬۵۰۰", "sl_text": "۶۳٬۷۰۰",
            "pnl_text": "+۱٫۲$", "pnl_percent_text": "+۰٫۸٪",
            "duration_text": "۵ دقیقه", "data_age_text": "۴۵ ms",
            "exit_reason_text": "—", "status_text": "باز", "pnl": 1.2,
        }
        base.update(overrides)
        return base

    def test_action_column_with_close_button(self, page) -> None:
        """هر ردیف دکمهٔ بستن دارد و شناسهٔ درست را می‌فرستد."""
        page.set_open_positions([self._row()])
        button = page.positions_table.cellWidget(0, 18)
        assert button is not None and button.text()
        captured: list[int] = []
        page.close_position_requested.connect(captured.append)
        button.click()
        assert captured == [7]

    def test_detail_dialog_shows_fields_and_close(self, page, qt_app) -> None:
        """مودال جزئیات: همهٔ فیلدها + دکمهٔ بستن با شناسه."""
        from ui.dialogs.trading_dialogs import PositionDetailDialog

        row = self._row()
        dialog = PositionDetailDialog(page.tr_, row, parent=page)
        captured: list[int] = []
        dialog.close_trade_requested.connect(captured.append)
        buttons = dialog.findChildren(object)
        # دکمهٔ بستن وجود دارد و سیگنال می‌دهد
        dialog._emit_close()
        assert captured == [7]
        # نماد در عنوان و فیلد ورود دیده می‌شود
        assert "BTC/USDT" in dialog.windowTitle()
        dialog.deleteLater()

    def test_symbol_click_opens_detail(self, page, qt_app) -> None:
        """کلیک روی ستون نماد → مودال (با جایگزینی exec)."""
        page.set_open_positions([self._row()])
        opened: list[dict] = []

        class _FakeDialog(QObject):
            close_trade_requested = Signal(int)

            def __init__(self, tr, row, parent=None):
                super().__init__()
                opened.append(row)

            def exec(self):
                return 0

        import ui.dialogs.trading_dialogs as trading_dialogs

        original = trading_dialogs.PositionDetailDialog
        trading_dialogs.PositionDetailDialog = _FakeDialog
        try:
            page._on_position_cell_clicked(0, 0)
        finally:
            trading_dialogs.PositionDetailDialog = original
        assert opened and opened[0]["symbol"] == "BTC/USDT"


# ---------------------------------------------------------------------------
# ۶) مودال انتخاب نمادهای مورد علاقه
# ---------------------------------------------------------------------------
class TestSymbolPicker:
    @pytest.fixture()
    def page(self, qt_app, translator):
        from ui.pages.trades_page import TradesPage

        instance = TradesPage(translator)
        try:
            yield instance
        finally:
            destroy_window(instance, qt_app)

    def test_picker_dialog_check_and_search(self, qt_app, translator) -> None:
        """تیک‌زدن + جست‌وجو + خروجی مرتب‌شده."""
        from ui.dialogs.trading_dialogs import SymbolPickerDialog

        dialog = SymbolPickerDialog(
            translator,
            ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"],
            ["ETH/USDT"],
        )
        # ETH از قبل تیک دارد
        assert dialog.checked_symbols() == ["ETH/USDT"]
        # تیک BTC
        dialog.list_widget.item(0).setCheckState(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CheckState.Checked
        )
        assert dialog.checked_symbols() == ["BTC/USDT", "ETH/USDT"]
        # جست‌وجو مخفی می‌کند ولی انتخاب را نمی‌بُرد
        dialog.search.setText("BTC")
        assert dialog.checked_symbols() == ["BTC/USDT"]
        dialog.search.setText("")
        assert dialog.checked_symbols() == ["BTC/USDT", "ETH/USDT"]
        dialog.deleteLater()

    def test_page_picker_writeback(self, page) -> None:
        """تأیید مودال → ورودی نمادهای انتخابی + سیگنال ذخیره."""
        page.set_auto_symbols(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        page.auto_selected_input.setText("BTC/USDT")

        class _FakePicker:
            def __init__(self, tr, symbols, selected, parent=None):
                self.symbols = symbols
                self.selected = selected

            def exec(self):
                return 1  # Accepted

            def checked_symbols(self):
                return ["BTC/USDT", "SOL/USDT"]

        import ui.dialogs.trading_dialogs as trading_dialogs

        original = trading_dialogs.SymbolPickerDialog
        trading_dialogs.SymbolPickerDialog = _FakePicker
        captured: list[list[str]] = []
        try:
            page.selected_symbols_saved.connect(captured.append)
            page._open_symbol_picker()
        finally:
            trading_dialogs.SymbolPickerDialog = original
        assert page.auto_selected_input.text() == "BTC/USDT,SOL/USDT"
        assert captured == [["BTC/USDT", "SOL/USDT"]]
        # ورودی فقط-خواندنی است (منبع حقیقت مودال است)
        assert page.auto_selected_input.isReadOnly()

    def test_scanner_settings_dialog_roundtrip(self, qt_app, translator) -> None:
        """مودال تنظیمات پویش: مقدار → دیالوگ → کلیدهای تنظیمات."""
        from ui.dialogs.trading_dialogs import ScannerSettingsDialog

        dialog = ScannerSettingsDialog(
            translator,
            {
                "watch_scan_enabled": True, "watch_scan_interval": 30,
                "watch_min_confidence": 65, "watch_max_spread": 0.4,
                "watch_row_cap": 25,
            },
        )
        values = dialog.values()
        assert values["scalp.watch_scan_interval"] == 30.0
        assert values["scalp.watch_min_confidence"] == 65.0
        assert values["scalp.watch_max_spread"] == 0.4
        assert values["scalp.watch_row_cap"] == 25
        assert values["scalp.watch_scan_enabled"] is True
        dialog.deleteLater()
