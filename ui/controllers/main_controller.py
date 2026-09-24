"""
کنترلر اصلی رابط گرافیکی.

این لایه، صفحات را به موتورهای برنامه وصل می‌کند. صفحات هیچ چیزی درباره
موتور بازار، موتور سیگنال یا پایگاه داده نمی‌دانند و موتورها هیچ چیزی
درباره Qt نمی‌دانند؛ همه هماهنگی اینجا انجام می‌شود.

قاعده‌ای که در سراسر این فایل رعایت شده: هر کاری که ممکن است طول بکشد
(شبکه، محاسبه، فایل) از راه `AsyncRunner` روی نخ پس‌زمینه می‌رود و فقط
نتیجه‌اش به ویجت‌ها داده می‌شود.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from ai.recommendation import parse_recommendation, strip_recommendation_line
from app.application import Application
from app.config.defaults import SettingKey
from app.core.constants import APP_VERSION, MIN_CANDLES_FOR_ANALYSIS, SignalDirection
from app.core.timeutil import format_datetime, format_time, now_local, set_display_timezone
from app.core.models import Candle, TradingSignal
from app.logging import get_logger
from indicators.support_resistance import analyze_market_structure, find_support_resistance
from localization import Translator
from ui.charts.price_chart import OVERLAY_COLORS  # noqa: F401 - نگهداشت سازگاری رنگ‌ها
from ui.controllers.async_runner import AsyncRunner
from ui.dialogs.analysis_dialog import AnalysisDialog
from ui.dialogs.coin_detail_dialog import CoinDetailDialog
from ui.dialogs.signal_detail_dialog import SignalDetailDialog
from ui.themes import ThemeManager
from ui.themes.catalog import DEFAULT_THEME
from ui.themes.custom import CustomThemeStore
from ui.themes.fonts import DEFAULT_FONT_KEY
from ui.windows import MainWindow

try:  # pragma: no cover - وابسته به بسته‌بندی PySide6
    from shiboken6 import isValid as _shiboken_is_valid
except ImportError:  # pragma: no cover
    _shiboken_is_valid = None


def _dialog_alive(dialog: Any) -> bool:
    """
    آیا این پنجره هنوز زنده است؟

    پس از بسته‌شدن پنجره، شیء ++C نابود می‌شود ولی ارجاع پایتونی ممکن
    است هنوز در بستارِ یک کار پس‌زمینه باقی باشد. تماس با چنین شیئی
    برنامه را با «Internal C++ object already deleted» می‌بندد — همان
    کرشی که کاربر هنگام بستن مدال بازار گزارش کرد.
    """
    if dialog is None:
        return False
    if _shiboken_is_valid is not None and not _shiboken_is_valid(dialog):
        return False
    return True

logger = get_logger(__name__)

#: اندیکاتورهایی که به‌صورت خط روی نمودار قیمت کشیده می‌شوند
CHART_OVERLAYS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("EMA", {"period": 21}),
    ("SMA", {"period": 50}),
)

#: اندیکاتورهایی که در جدول تحلیل نمایش داده می‌شوند
ANALYSIS_INDICATORS: tuple[str, ...] = (
    "RSI", "MACD", "ADX", "ATR", "STOCH", "CCI", "MFI", "BBANDS", "OBV", "VWAP",
)

#: بیشینه تعداد نماد در جدول بازارها (فهرست کامل صرافی هزاران ردیف است)
MARKET_ROW_LIMIT = 300

#: تعداد نقطهٔ نگه‌داشته‌شده برای نمودار کوچک ستون «روند»
PRICE_HISTORY_POINTS = 24

#: فاصله زمانی به‌روزرسانی قیمت‌های زنده روی صفحه (میلی‌ثانیه)
LIVE_UI_INTERVAL = 500

#: فاصله زمانی تازه‌سازی نرخ تومان (میلی‌ثانیه)
FIAT_REFRESH_INTERVAL = 300_000

#: شناسهٔ پوستهٔ موقتِ پیش‌نمایش ویرایشگر. ثابت است تا هر بار یک ورودی
#: تازه در فهرست پوسته‌ها ساخته نشود.
PREVIEW_THEME_KEY = "custom__preview"

#: فاصله زمانی بررسی وضعیت هوش مصنوعی (میلی‌ثانیه) — سه دقیقه.
#: کوتاه‌تر از این برای سرویس ابری یعنی درخواست بی‌مورد و برای مدل
#: محلی یعنی بیدارکردن بیهودهٔ مدل.
AI_STATUS_INTERVAL = 180_000

#: تیک زمان‌بند پویش خودکار. کوتاه است تا شمارش معکوس روی صفحه زنده
#: بماند و تغییر تنظیمات بی‌درنگ اثر کند؛ خودِ پویش طبق فاصلهٔ کاربر
#: اجرا می‌شود نه هر تیک.
AUTO_SCAN_TICK_MS = 15_000

#: ۲.۴.۱ — سهم CPU پویش پس‌زمینهٔ خودکار (رجوع: signals.scanner)
from signals.scanner import BACKGROUND_CPU_DUTY  # noqa: E402

#: تیک بررسی نتیجهٔ سیگنال‌ها. برخلاف پویش، اینجا فقط قیمت خوانده
#: می‌شود و هزینه‌اش ناچیز است؛ ولی فاصلهٔ واقعی را کاربر تعیین می‌کند
#: و این تیک صرفاً موعد را می‌سنجد.
OUTCOME_TICK_MS = 30_000
# فاصلهٔ پایش معاملات باز. قیمت از کش خوانده می‌شود؛ REST فقط وقتی
# کش کهنه باشد. دو ثانیه برای بستن سریع اسکالپ کافی است.
TRADE_MONITOR_TICK_MS = 2_000

#: فاصلهٔ تازه‌سازی داشبورد ترمینال معاملهٔ خودکار (v2.0). خروج
#: موقعیت‌ها تیک‌محور است؛ این تایمر فقط «نمایش» را تازه می‌کند.
TERMINAL_UI_INTERVAL_MS = 1_000

#: فاصلهٔ نوسازی Bid/Ask از دفتر سفارش (REST). تیک وب‌سوکت Bid/Ask
#: ندارد؛ دفتر باید جداگانه بخواند و روی کش تیک لایه شود.
ORDERBOOK_REFRESH_MS = 5_000
# تازه‌سازی کندل‌ها. قیمت لحظه‌ای جداگانه و بدون redraw کامل می‌آید.
LIVE_CHART_TICK_MS = 8_000

#: تیک قیمت زنده — سبک و پرتکرار، فقط یک عدد می‌گیرد
LIVE_PRICE_TICK_MS = 1_000

#: نگه داشتن اتصال و تلاش دوبارهٔ سوکت
KEEPALIVE_TICK_MS = 15_000


def summarise_market(tickers: Any, *, liquid_count: int = 200, movers: int = 5) -> dict[str, Any]:
    """
    پهنای بازار و بیشترین رشد/افت، فقط روی بازارهای نقدشونده.

    بازار کم‌گردش با یک معامله ۴۰٪ جابه‌جا می‌شود؛ رتبه‌بندی بر پایهٔ آن
    گمراه‌کننده است. پس ابتدا `liquid_count` بازار پرگردش انتخاب می‌شوند.
    """
    items = []
    for ticker in tickers or []:
        try:
            price = float(getattr(ticker, "last_price", 0) or 0)
            turnover = float(getattr(ticker, "turnover_24h", 0) or 0)
            change = float(getattr(ticker, "change_percent", 0) or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0 or turnover <= 0 or change != change:
            continue
        items.append({"symbol": str(ticker.symbol), "price": price,
                      "change_percent": change, "turnover": turnover})
    items.sort(key=lambda row: row["turnover"], reverse=True)
    liquid = items[:liquid_count]
    if not liquid:
        return {"total": 0, "gainers": [], "losers": []}
    up = sum(1 for row in liquid if row["change_percent"] > 0.05)
    down = sum(1 for row in liquid if row["change_percent"] < -0.05)
    ranked = sorted(liquid, key=lambda row: row["change_percent"], reverse=True)
    return {
        "total": len(liquid),
        "up": up,
        "down": down,
        "flat": len(liquid) - up - down,
        "avg_change": sum(row["change_percent"] for row in liquid) / len(liquid),
        "gainers": [row for row in ranked[:movers] if row["change_percent"] > 0],
        "losers": [row for row in reversed(ranked[-movers:]) if row["change_percent"] < 0],
    }

#: دفترچهٔ نتیجه، فقط اگر کاربر خودش خودکار را روشن کرده باشد
SCORECARD_TICK_MS = 3_600_000


class MainController(QObject):
    """
    هماهنگ‌کننده رابط گرافیکی و موتورهای برنامه.

    مثال:
        controller = MainController(application, window, translator, themes, qt_app)
        controller.start()
    """

    #: تکه‌های پاسخ جریانی چت. سیگنال است نه فراخوان مستقیم، چون از نخ
    #: شبکه می‌آید و Qt تحویل امن به نخ رابط کاربری را تضمین می‌کند؛
    #: دست‌زدن مستقیم به ویجت از نخ دیگر برنامه را می‌کشد.
    chat_stream_delta = Signal(str, bool)

    #: پیشرفت پویش بازار (انجام‌شده، کل، نماد، یافته‌شده). مثل بالا،
    #: سیگنال است چون پس‌فراخوانِ پویشگر روی نخ شبکه اجرا می‌شود.
    scan_progress_changed = Signal(int, int, str, int)
    #: نسخهٔ ۲.۴.۰ — هر سیگنالِ پذیرفته‌شده در میانهٔ پویش دستی (نخ شبکه → UI)
    scan_partial_found = Signal(object)
    #: نسخهٔ ۲.۴.۰ — سیگنال/پیشرفتِ پویش خودکار (نخ شبکه → UI)
    auto_scan_signal_found = Signal(object)
    auto_scan_progress = Signal(int, int)
    #: رویداد موتور معاملهٔ خودکار (نخ شبکه → نخ رابط کاربری)
    auto_trade_event = Signal(str, dict)

    #: شروع اجرای یک ابزار چت (نام، آرگومان‌ها). از نخ شبکه می‌آید.
    chat_tool_started = Signal(str, dict)

    #: پایان اجرای یک ابزار چت (نام، موفق؟، نتیجه، آرگومان‌ها).
    chat_tool_finished = Signal(str, bool, str, dict)

    def __init__(
        self,
        application: Application,
        window: MainWindow,
        translator: Translator,
        theme_manager: ThemeManager,
        qt_app: QApplication,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app = application
        self.window = window
        self.tr_ = translator
        self.themes = theme_manager
        self.qt_app = qt_app
        self.runner = AsyncRunner(self)

        # پوسته‌های سفارشی کاربر کنار داده‌های او ذخیره می‌شوند و در
        # همان آغاز ثبت می‌گردند تا اگر پوستهٔ فعالش سفارشی باشد،
        # برنامه با همان بالا بیاید نه با پوستهٔ پیش‌فرض.
        self.custom_themes = CustomThemeStore(self.app.paths.data_dir)
        self.custom_themes.load_all()
        self._editor_base_key: str = ""
        self._editor_overrides: dict = {}

        self._symbols: list[str] = []
        #: تاریخچهٔ کوتاه قیمت هر نماد، برای نمودار کوچک ستون «روند».
        #: گرفتن کندل برای ۳۰۰ نماد کند است، پس تاریخچه را از همان
        #: تازه‌سازی‌های پی‌درپی خودمان می‌سازیم.
        self._price_history: dict[str, list[float]] = {}
        # قیمت دارایی‌های کیف پول که هنگام همگام‌سازی گرفته شده‌اند؛ جدول
        # بازارها همیشه بارگذاری نشده و بدون این، ستون «ارزش» خط تیره می‌ماند.
        self._asset_prices: dict[str, float] = {}
        self._last_signal: TradingSignal | None = None
        #: آخرین نتیجهٔ پویش بازار — برای تحلیل هوشمند ردیف‌ها لازم است
        self._last_scan: Any = None
        self._started = False

        # ---- سرویس‌های زنده ----
        self._live_feed: Any = None
        self._connection_supervisor: Any = None
        self._fiat: Any = None
        self._toman_rate: float | None = None
        self._toman_source: str = ""
        #: به‌روزرسانی‌های رسیده از نخ شبکه، منتظر نمایش روی صفحه
        self._pending_updates: dict[str, dict[str, Any]] = {}
        self._last_signal_rows: list[dict[str, Any]] = []
        #: شناسهٔ گفت‌وگوی فعال چت؛ صفر یعنی هنوز ساخته نشده
        self._conversation_id: int = 0

        self.dashboard = window.pages["nav.dashboard"]
        self.markets = window.pages["nav.markets"]
        self.analysis = window.pages["nav.analysis"]
        self.signals = window.pages["nav.signals"]
        self.prediction = window.pages["nav.prediction"]
        self.chat = window.pages["nav.chat"]
        self.reports = window.pages["nav.reports"]
        #: نمای عملکرد، زبانهٔ دوم صفحهٔ گزارش‌ها
        self.performance = getattr(self.reports, "performance", None)
        self.trades = window.pages["nav.trades"]
        self.wallet = window.pages["nav.wallet"]
        self.settings_page = window.pages["nav.settings"]

        #: ۲.۴.۲ — تازه‌سازی تنبل صفحهٔ عملکرد
        self._outcome_view_stale = True
        self._outcome_watch_installed = False
        self._stall_watchdog = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self.refresh_dashboard)

        # تایمر نمایش زنده: داده از نخ شبکه می‌آید ولی **فقط اینجا** روی
        # ویجت‌ها می‌نشیند. دست‌زدن به ویجت از نخ دیگر، برنامه را می‌کشد.
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(LIVE_UI_INTERVAL)
        self._live_timer.timeout.connect(self._flush_live_updates)

        self._fiat_timer = QTimer(self)
        self._fiat_timer.setInterval(FIAT_REFRESH_INTERVAL)
        self._fiat_timer.timeout.connect(self.refresh_fiat_rate)

        # وضعیت هوش مصنوعی هر سه دقیقه تازه می‌شود (خواستهٔ کاربر).
        # سرویس می‌تواند بدون دخالت کاربر قطع شود — اولامای محلی بسته
        # می‌شود یا سهمیهٔ سرویس ابری تمام می‌شود — و کارت نباید وضعیت
        # کهنه نشان دهد.
        self._ai_status_timer = QTimer(self)
        self._ai_status_timer.setInterval(AI_STATUS_INTERVAL)
        self._ai_status_timer.timeout.connect(self.refresh_ai_status)

        self._connect()

    # ------------------------------------------------------------------
    # راه‌اندازی
    # ------------------------------------------------------------------
    def _connect(self) -> None:
        """اتصال دکمه‌های صفحات به کنش‌ها."""
        self.prediction.refresh_requested.connect(self.run_prediction_report)
        self.analysis.symbol_combo.currentTextChanged.connect(
            self._sync_prediction_symbol
        )
        self.dashboard.refresh_button.clicked.connect(self.refresh_dashboard)
        self.markets.refresh_button.clicked.connect(self.refresh_markets)
        self.markets.watchlist_button.clicked.connect(self.add_to_watchlist)
        self.markets.watchlist_toggled.connect(self._on_watchlist_toggled)

        panel = self.markets.watchlist_panel
        panel.list_selected.connect(self._on_watchlist_list_selected)
        panel.list_created.connect(self._create_watchlist)
        panel.list_renamed.connect(self._rename_watchlist)
        panel.list_deleted.connect(self._delete_watchlist)
        panel.symbol_moved.connect(self._move_watchlist_symbol)
        panel.symbol_removed.connect(self._remove_watchlist_symbol)
        panel.note_changed.connect(self._save_watchlist_note)
        panel.symbol_activated.connect(self._open_watchlist_symbol)
        self.markets.table.itemDoubleClicked.connect(self._on_market_double_clicked)

        # کلیک روی سیگنال در داشبورد، پنجرهٔ جزئیات را باز می‌کند
        self.dashboard.signals_table.cellClicked.connect(self._on_signal_cell_clicked)
        self.signals.history_table.cellDoubleClicked.connect(self._on_history_double_clicked)

        # تعویض صرافی و سرویس هوش مصنوعی در تنظیمات
        self.settings_page.exchange_changed.connect(self._on_exchange_selected)
        self.settings_page.ai_provider_changed.connect(self._on_ai_provider_selected)
        self.settings_page.test_ai_button.clicked.connect(self.test_ai_connection)
        self.settings_page.doctor_button.clicked.connect(self.run_ollama_doctor)
        self.settings_page.check_update_button.clicked.connect(self.check_for_update)
        self.settings_page.install_update_button.clicked.connect(self.install_update)
        # تغییر پوسته باید بی‌درنگ دیده شود، نه پس از زدن «ذخیره»
        self.settings_page.theme_preview_requested.connect(self.change_theme)
        self.settings_page.font_scale_changed.connect(self._on_font_scale_changed)
        self.settings_page.compact_mode_changed.connect(self._on_compact_mode_changed)
        self.settings_page.font_family_changed.connect(self.change_font_family)
        # ویرایشگر پیشرفتهٔ ظاهر
        self.settings_page.theme_tokens_changed.connect(self.preview_theme_tokens)
        self.settings_page.custom_theme_save_requested.connect(self.save_custom_theme)
        self.settings_page.custom_theme_delete_requested.connect(self.delete_custom_theme)
        self.settings_page.theme_combo.currentIndexChanged.connect(
            self._on_theme_combo_changed
        )
        self.settings_page.load_models_button.clicked.connect(self.load_ai_models)
        # ---- چت با هوش مصنوعی ----
        self.chat.message_sent.connect(self.send_chat_message)
        # اتصال صف‌شده: تکه از نخ شبکه می‌آید و باید در نخ رابط کاربری
        # اجرا شود. Qt این را خودش مدیریت می‌کند.
        self.chat_stream_delta.connect(self.chat.stream_delta)
        # گام‌های ابزار هم از نخ شبکه می‌آیند و همان مسیر امن را می‌روند
        self.chat_tool_started.connect(self._on_chat_tool_started)
        self.chat_tool_finished.connect(self._on_chat_tool_finished)
        self.scan_progress_changed.connect(self.signals.set_scan_progress)
        self.scan_partial_found.connect(self._on_scan_partial_signal)
        self.auto_scan_signal_found.connect(self._on_auto_partial_signal)
        self.auto_scan_progress.connect(self._on_auto_scan_progress)
        self.auto_trade_event.connect(self._handle_auto_trade_event)
        self.chat.action_requested.connect(self._on_chat_action)
        self.chat.chat_cleared.connect(self._on_chat_cleared)
        self.chat.conversation_selected.connect(self.open_conversation)
        self.chat.conversation_deleted.connect(self.delete_conversation)
        self.chat.new_conversation_requested.connect(self.start_new_conversation)
        self.chat.conversation_renamed.connect(self.rename_conversation)
        # کلیک روی نام ارز در داشبورد و بازارها → مدال جزئیات
        self.dashboard.coin_activated.connect(self.show_coin_details)
        self.markets.coin_activated.connect(self.show_coin_details)
        # کلیک روی دکمهٔ تحلیل در جدول سابقهٔ سیگنال‌ها
        self.signals.analysis_requested.connect(self.show_signal_analysis)
        # چیدمان دلخواه کاربر در داشبورد
        self.dashboard.layout_changed.connect(self.save_dashboard_layout)
        # کلیک روی کارت وضعیت هوش مصنوعی در نوار کناری
        ai_card = getattr(self.window.sidebar, "ai_status", None)
        if ai_card is not None:
            ai_card.clicked.connect(self.open_ai_settings)

        self.analysis.run_button.clicked.connect(self.run_analysis)
        self.analysis.indicator_toggled.connect(self._on_indicator_toggled)
        self.signals.generate_button.clicked.connect(self.generate_signal)
        self.signals.scan_requested.connect(self.scan_market)
        self.signals.auto_scan_changed.connect(self.save_auto_scan_config)
        self.signals.scan_settings_changed.connect(self.save_scan_settings)
        self.signals.auto_scan_run_now.connect(self.run_auto_scan_now)
        self.signals.scan_stop_requested.connect(self.stop_market_scan)
        self.signals.scan_ai_requested.connect(self.analyze_scanned_symbol)
        self.signals.scan_detail_requested.connect(self.show_scanned_signal_detail)
        self.signals.copy_notice.connect(lambda message: self._toast(message, level="success"))
        self.reports.generate_button.clicked.connect(self.generate_report)
        if self.performance is not None:
            self.performance.refresh_requested.connect(self.refresh_outcomes_now)
            self.performance.period_changed.connect(
                lambda _days: self._refresh_outcome_view()
            )
        self.reports.scorecard_refresh_requested.connect(self.refresh_scorecard)
        if hasattr(self.reports, "scorecard_auto_changed"):
            self.reports.scorecard_auto_changed.connect(self.save_scorecard_auto)
        self.settings_page.save_button.clicked.connect(self.save_settings)
        self.settings_page.backup_button.clicked.connect(self.create_backup)
        self.settings_page.restore_button.clicked.connect(self.restore_backup)

        # ---- تاریخچهٔ معاملات و کیف پول ----
        self.trades.filters_changed.connect(lambda _f: self.refresh_trades())
        self.trades.refresh_requested.connect(self.refresh_trades)
        self.trades.close_requested.connect(self.close_paper_trade)
        self.trades.close_blocked.connect(
            lambda: self._toast(
                self.tr_.tr("trades.no_open_trade_selected"), level="warning"
            )
        )
        self.trades.auto_trade_toggled.connect(self.toggle_auto_trading)
        self.trades.auto_settings_changed.connect(self.save_auto_trade_settings)
        # ---- ترمینال معاملهٔ خودکار (v2.0) ----
        self.trades.auto_mode_changed.connect(self.change_auto_engine_mode)
        self.trades.auto_symbol_changed.connect(self.on_auto_symbol_selected)
        self.trades.close_position_requested.connect(self.close_auto_position)
        self.trades.close_position_blocked.connect(
            lambda: self._toast(
                self.tr_.tr("trades.no_open_trade_selected"), level="warning"
            )
        )
        self.trades.emergency_exit_requested.connect(self.emergency_exit_positions)
        # v2.1 — ترمینال حرفه‌ای
        self.trades.auto_timeframe_changed.connect(self.on_auto_timeframe_changed)
        self.trades.opportunity_enter_requested.connect(self.on_opportunity_enter)
        # v2.2 — ترمینال حرفه‌ای
        self.trades.chart_indicators_changed.connect(self.on_chart_indicators_changed)
        self.trades.scanner_settings_saved.connect(self.on_scanner_settings_saved)
        self.trades.selected_symbols_saved.connect(self.on_selected_symbols_saved)
        self.trades.ai_opinion_requested.connect(self.on_ai_opinion_requested)
        self.trades.notice_requested.connect(
            lambda message: self._toast(message)
        )
        self._terminal_timer = QTimer(self.window)
        self._terminal_timer.setInterval(TERMINAL_UI_INTERVAL_MS)
        self._terminal_timer.timeout.connect(self._terminal_timer_tick)
        self._terminal_timer.start()
        self._terminal_stats_tick = 0
        # پنل باید از همان ابتدا تنظیم‌های واقعی کاربر را نشان دهد،
        # نه خط تیره؛ وگرنه معلوم نیست با چه هدفی معامله می‌شود.
        QTimer.singleShot(0, self._refresh_auto_trade_panel)
        self.trades.export_requested.connect(self.export_trades)
        self.trades.clear_requested.connect(self.clear_trade_history)
        self.markets.alert_requested.connect(self.create_price_alert)
        self.wallet.sync_requested.connect(self.sync_wallet)
        self.wallet.range_changed.connect(lambda _r: self.refresh_wallet())

        # ---- حساب کاربری و حساب‌های صرافی ----
        self.window.login_requested.connect(self.show_auth_dialog)
        self.window.logout_requested.connect(self.logout)
        self.settings_page.account_add_requested.connect(self.add_exchange_account)
        self.settings_page.account_test_requested.connect(self.test_exchange_account)
        self.settings_page.account_remove_requested.connect(self.remove_exchange_account)
        self.settings_page.account_activate_requested.connect(self.activate_exchange_account)
        self.settings_page.account_selection_blocked.connect(
            lambda: self._toast(
                self.tr_.tr("settings.accounts.no_account_selected"), level="warning"
            )
        )
        self.settings_page.profile_save_requested.connect(self.save_profile)
        self.settings_page.email_save_requested.connect(self.save_email_settings)
        self.settings_page.email_test_requested.connect(self.test_email_connection)
        self.settings_page.password_change_requested.connect(self.change_password)
        self.settings_page.session_revoke_requested.connect(self.revoke_session)
        self.settings_page.session_revoke_blocked.connect(
            lambda: self._toast(
                self.tr_.tr("settings.security.no_session_selected"), level="warning"
            )
        )
        self.settings_page.revoke_others_requested.connect(self.revoke_other_sessions)

        # ---- نوار بالا ----
        self.window.search_requested.connect(self.global_search)
        self.window.search_suggestion_activated.connect(self._on_search_suggestion)
        self.window.refresh_requested.connect(self.refresh_current_page)
        self.window.language_change_requested.connect(self.change_language)
        self.window.theme_change_requested.connect(self.change_theme)

    def start(self) -> None:
        """راه‌اندازی موتورها و بارگذاری داده اولیه."""
        if self._started:
            return
        self._started = True
        self.runner.start()
        # نسخهٔ ۲.۴.۲: هر «هنگ» نخ رابط با پشتهٔ دقیق در لاگ ثبت می‌شود
        try:
            from ui.responsiveness import UiStallWatchdog

            self._stall_watchdog = UiStallWatchdog(self)
            self._stall_watchdog.start()
        except Exception:  # noqa: BLE001 - فقط ابزار تشخیص است
            logger.debug("UI stall watchdog unavailable", exc_info=True)
        self.analysis.apply_chart_palette(self.themes.palette)
        self.trades.apply_chart_palette(self.themes.palette)
        self._populate_indicator_catalog()
        # کاربر گزارش کرد «اندیکاتورها در بخش اندیکاتورها نیستند». پنل
        # فهرست درست پر می‌شد، ولی جدول مقادیر تا وقتی دکمهٔ «تحلیل»
        # زده نمی‌شد خالی می‌ماند و صفحه بی‌استفاده به نظر می‌رسید.
        # حالا اولین ورود به صفحه، خودش تحلیل را اجرا می‌کند.
        self.analysis.on_activated = self._on_analysis_activated
        self.settings_page.load_values(self.app.settings.export_all())
        self.apply_display_preferences()
        self._sync_user_chrome()
        self.refresh_accounts()
        self.refresh_security()
        self._load_signal_history()
        self.refresh_trades()
        self.refresh_wallet()
        self.status(self.tr_.tr("common.loading"))

        self.runner.submit(
            "start-engines",
            self.app.start(),
            on_success=lambda _: self._on_engines_ready(),
            on_error=self._on_error,
        )

    def shutdown(self) -> None:
        """توقف تمیز هنگام بستن پنجره."""
        self._refresh_timer.stop()
        self._live_timer.stop()
        self._fiat_timer.stop()
        self._ai_status_timer.stop()
        outcome_timer = getattr(self, "_outcome_timer", None)
        if outcome_timer is not None:
            outcome_timer.stop()

        # جریان زنده باید در همان حلقه‌ای بسته شود که باز شده است
        if self._live_feed is not None and self.runner.running:
            import asyncio

            loop = self.runner._loop  # noqa: SLF001 - دسترسی عمدی برای خاموشی
            if loop is not None:
                try:
                    if self._connection_supervisor is not None:
                        asyncio.run_coroutine_threadsafe(
                            self._connection_supervisor.stop(), loop
                        ).result(timeout=5)
                    asyncio.run_coroutine_threadsafe(self._live_feed.stop(), loop).result(timeout=5)
                except Exception:  # noqa: BLE001 - خاموشی نباید خطا بدهد
                    logger.warning("Live feed did not stop cleanly")
        if self.runner.running:
            # `app.stop()` ناهمگام است و باید در همان حلقه‌ای بسته شود که
            # اتصال‌ها در آن باز شده‌اند، وگرنه سوکت‌ها رها می‌شوند.
            import asyncio

            loop = self.runner._loop  # noqa: SLF001 - دسترسی عمدی برای خاموشی
            if loop is not None:
                future = asyncio.run_coroutine_threadsafe(self.app.stop(), loop)
                try:
                    future.result(timeout=8)
                except Exception:  # noqa: BLE001 - خاموشی هرگز نباید خطا بدهد
                    logger.warning("Engine shutdown did not finish cleanly")
        self.runner.stop()
        # کارگرهای استخر محاسبه (۲.۴.۲) حتی اگر app.stop به موقع تمام نشد
        pool = getattr(self.app, "_compute_pool", None)
        if pool is not None:
            try:
                pool.shutdown()
            except Exception:  # noqa: BLE001
                pass
        stall_watchdog = getattr(self, "_stall_watchdog", None)
        if stall_watchdog is not None:
            stall_watchdog.stop()
        logger.info("Controller shut down")

    def _on_engines_ready(self) -> None:
        """
        پس از آماده شدن موتور بازار.

        اینجا جریان قیمت زنده هم راه می‌افتد. پیش از این، برنامه فقط یک
        بار داده می‌گرفت و بعد ساکت می‌شد — همان چیزی که کاربر آن را
        «آفلاین شدن پس از بارگذاری» دید.
        """
        self._apply_timezone_setting()
        self._apply_performance_settings()
        self._apply_display_settings()
        self.load_conversations()
        self.status(self.tr_.tr("common.online"))
        self.dashboard.set_connection_status(self.tr_.tr("common.online"), "bullish")
        self.window.set_connection_indicator(True)
        self.markets.set_palette(self.themes.palette)

        self._start_live_feed()
        self.refresh_markets()
        self.refresh_dashboard()
        self.refresh_fiat_rate()
        self.restore_dashboard_layout()
        self.refresh_ai_status()
        self.start_auto_scanner()
        self.start_outcome_tracker()
        self.start_trade_monitor()
        self.start_live_chart()
        self.start_connection_keepalive()
        self.start_scorecard_timer()
        if hasattr(self.reports, "set_scorecard_auto"):
            self.reports.set_scorecard_auto(
                self.app.settings.get_bool("signals.scorecard_auto", False)
            )
        self.refresh_watchlist_panel(keep_selection=False)
        self._refresh_outcome_view(quiet=True)
        self._refresh_timer.start()
        self._live_timer.start()
        self._fiat_timer.start()
        self._ai_status_timer.start()

    # ------------------------------------------------------------------
    # جریان قیمت زنده
    # ------------------------------------------------------------------
    def _start_live_feed(self) -> None:
        """
        راه‌اندازی سرویس قیمت زنده.

        سرویس ترکیبی است: وب‌سوکت برای نمادهای تحت نظر (نوسان لحظه‌ای) و
        نظرسنجی REST برای کل بازار. اگر وب‌سوکت بیفتد، REST همچنان کار
        می‌کند و برنامه آنلاین می‌ماند.
        """
        if self._live_feed is not None or self.app.market is None:
            return

        from market.live_feed import LivePriceFeed
        from market.resilience import ConnectionSupervisor

        bound_market = self.app.market
        self._live_feed = LivePriceFeed(bound_market)
        self._live_feed.add_listener(
            lambda updates: self._on_price_update(updates) if self.app.market is bound_market else None
        )

        self.runner.submit(
            "live-feed",
            self._live_feed.start(),
            on_success=lambda _: self._update_streamed_symbols(),
            on_error=lambda message, exc=None: logger.warning("Live feed failed: %s", message),
        )
        logger.info("Live price feed starting")

        # نگهبان اتصال: اگر وظیفهٔ فید به دلیلی بمیرد، خودش زنده‌اش
        # می‌کند و وضعیت سه‌حالته صادقانه می‌دهد — قلب «همیشه آنلاین».
        self._connection_supervisor = ConnectionSupervisor(
            self._live_feed, event_bus=getattr(self.app, "events", None)
        )
        self.runner.submit(
            "connection-supervisor",
            self._connection_supervisor.start(),
            on_error=lambda message, exc=None: logger.warning("Connection supervisor failed: %s", message),
        )

    def _update_streamed_symbols(self) -> None:
        """
        تعیین نمادهایی که از وب‌سوکت دنبال می‌شوند.

        این متد ناهمگام است، پس باید در حلقه پس‌زمینه اجرا شود؛ صدا زدن
        مستقیم آن فقط یک coroutine بی‌استفاده می‌سازد.
        """
        if self._live_feed is None and self.app.market is None:
            return
        symbols = self._stream_symbols()
        symbol = ""
        timeframe = ""
        try:
            symbol = self.analysis.symbol_combo.currentText().strip().upper()
            timeframe = self.analysis.timeframe_combo.currentText().strip()
        except Exception:  # noqa: BLE001 - نبود ویجت نباید جریان را بشکند
            symbol = ""
        self.runner.submit(
            "streamed-symbols",
            self._sync_streams(symbols, symbol, timeframe),
            on_error=lambda message, exc=None: logger.debug("Streaming update failed: %s", message),
        )

    def _stream_symbols(self) -> list[str]:
        """نماد تحلیل، فهرست پیگیری و معامله‌های باز — برای سوکت."""
        symbols: list[str] = []
        try:
            current = self.analysis.symbol_combo.currentText().strip().upper()
        except Exception:  # noqa: BLE001
            current = ""
        if current:
            symbols.append(current)
        symbols.extend(self._watchlist_symbols())
        engine = getattr(self, "_auto_trader_engine", None)
        if engine is not None:
            for trade in getattr(engine, "open_trades", []) or []:
                symbol = str(getattr(trade, "symbol", "") or "").strip().upper()
                if symbol:
                    symbols.append(symbol)
        # نماد پنل پیش‌بینیِ ترمینال + نمادهای حالت Selected (v2.0):
        # بدون تیک این نمادها، نردبان و پایش فرصت کور می‌شود.
        auto_symbol = str(getattr(self, "_auto_prediction_symbol", "") or "").strip().upper()
        if auto_symbol:
            symbols.append(auto_symbol)
        try:
            selected = str(
                self.app.settings.get("scalp.selected_symbols", "") or ""
            ).upper()
            symbols.extend(
                item.strip() for item in selected.replace(";", ",").split(",") if item.strip()
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            for row in self.app.trade_repository.open_trades(self.app.auth.user_id):
                symbol = str((row or {}).get("symbol") or "").strip().upper()
                if symbol:
                    symbols.append(symbol)
        except Exception:  # noqa: BLE001
            logger.debug("Open-trade symbols unavailable", exc_info=True)
        priority = []
        if engine is not None:
            priority.extend(t.symbol for t in engine.open_trades)
        try:
            priority.extend(r["symbol"] for r in self.app.trade_repository.open_trades(self.app.auth.user_id))
        except Exception:
            pass
        return list(dict.fromkeys(item for item in priority + symbols if item))

    async def _sync_streams(
        self,
        symbols: list[str],
        symbol: str,
        timeframe: str,
    ) -> None:
        """به‌روزرسانی اشتراک سوکت. ویجت‌ها را لمس نمی‌کند."""
        if self._live_feed is not None:
            await self._live_feed.set_streamed_symbols(symbols)
        market = self.app.market
        if market is None or not symbol or not hasattr(market, "subscribe_symbol"):
            return
        await market.subscribe_symbol(symbol, timeframe or None)

    def _on_price_update(self, updates: Any) -> None:
        """
        دریافت به‌روزرسانی قیمت از نخ شبکه.

        اینجا **هیچ ویجتی لمس نمی‌شود**؛ فقط داده در صف می‌نشیند و تایمر
        رابط کاربری آن را روی صفحه می‌آورد. دست‌زدن به Qt از نخ asyncio
        باعث فروپاشی برنامه می‌شود.
        """
        try:
            # سرویس، نگاشت «نماد به به‌روزرسانی» می‌فرستد
            items = updates.values() if isinstance(updates, dict) else updates
            for update in items:
                ticks = getattr(self, "_tick_engine", None)
                if ticks is not None and getattr(update, "source", "") == "rest":
                    ticks.record(update.symbol, update.price, source="rest",
                                 exchange_ts=getattr(update, "exchange_ts", None),
                                 received_at_ms=update.updated_at.timestamp() * 1000)
                if not getattr(update, "changed", True):
                    continue
                self._pending_updates[update.symbol] = {
                    "price": update.price,
                    "change_percent": update.change_percent,
                    "tick_direction": update.tick_direction,
                }
        except Exception:  # noqa: BLE001 - داده بد نباید جریان را قطع کند
            logger.debug("Malformed price update ignored", exc_info=True)

    def _flush_live_updates(self) -> None:
        """
        نمایش به‌روزرسانی‌های انباشته روی صفحه.

        هر ثانیه یک بار اجرا می‌شود؛ بیشتر از این، هم بی‌فایده است و هم
        جدول را غیرقابل خواندن می‌کند.
        """
        if not self._pending_updates:
            self._refresh_connection_indicator()
            return

        updates = dict(self._pending_updates)
        self._pending_updates.clear()

        self.markets.apply_price_updates(updates)
        self._apply_dashboard_prices(updates)
        self._refresh_connection_indicator()

        if self._live_feed is not None:
            self.dashboard.set_status_value("last_update", format_time(now_local()))

    def _apply_dashboard_prices(self, updates: dict[str, dict[str, Any]]) -> None:
        """به‌روزرسانی جدول کوچک بازار در داشبورد."""
        table = self.dashboard.market_table
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is None:
                continue
            update = updates.get(item.text())
            if update is None:
                continue
            price_item = table.item(row, 1)
            if price_item is not None:
                price_item.setText(self.tr_.format_number(update["price"], 2))
            change = update.get("change_percent")
            change_item = table.item(row, 2)
            if change_item is not None and change is not None:
                change_item.setText(f"{float(change):+.2f}%")

    def _refresh_connection_indicator(self) -> None:
        """
        همگام‌سازی نشانگر اتصال با وضعیت واقعی.

        ملاک «آنلاین بودن» تازه بودن داده است، نه صرفاً برقرار بودن
        وب‌سوکت؛ افتادن وب‌سوکت تا وقتی REST جواب می‌دهد یعنی هنوز آنلاین.
        """
        online = False
        state = ""
        # نگهبان اتصال وضعیت سه‌حالتهٔ صادقانه می‌دهد؛ فقط وقتی نیست که
        # فید هنوز راه نیفتاده باشد (fallback همان منطق قبلی است).
        if self._connection_supervisor is not None:
            state = str(getattr(self._connection_supervisor.state, "value", "online"))
            online = state == "online"
        elif self._live_feed is not None:
            online = bool(self._live_feed.is_fresh)
        elif self.app.market is not None:
            online = bool(self.app.market.is_online)

        cooldown = 0.0
        if self.app.market is not None and hasattr(self.app.market, "rest_cooldown_remaining"):
            cooldown = float(self.app.market.rest_cooldown_remaining or 0.0)
        if state != "online" and cooldown > 0:
            # صرافی موقتاً درخواست‌ها را محدود کرده؛ اینترنت قطع نیست.
            label = self.tr_.tr("dashboard.command.rate_limited")
            role = "neutral"
        elif state == "degraded":
            # حلقه‌ها زنده‌اند ولی داده کهنه است — در حال بازاتصال، نه آفلاین
            label = self.tr_.tr("common.reconnecting")
            role = "neutral"
        else:
            label = self.tr_.tr("common.online") if online else self.tr_.tr("common.offline")
            role = "bullish" if online else "bearish"
        if online:
            self._note_market_online()
        self.dashboard.set_connection_status(label, role)
        self.dashboard.set_status_value("connection", label, role)
        self.window.set_connection_indicator(online)

        # کارت اتصالِ نوار کناری تا امروز هیچ‌وقت پر نمی‌شد و به‌صورت یک
        # مستطیل خالی دیده می‌شد؛ همان داده‌ای که نوار پایین دارد باید
        # اینجا هم بنشیند.
        market = self.app.market
        exchange = str(getattr(market, "exchange_name", "") or "")
        count = len(getattr(self, "_symbols", ()) or ())
        detail = ""
        if count > 0:
            detail = self.tr_.tr("markets.count", count=count)
        self.window.set_connection_card(
            connected=online, exchange=exchange, detail=detail
        )
        self._refresh_command_center()

    def _refresh_command_center(self, *, force: bool = False) -> None:
        """
        کاشی‌های مرکز فرمان داشبورد (2.3.1).

        فقط از داده‌ای که همین حالا در حافظه/DB است؛ هیچ درخواست شبکه‌ای
        نمی‌زند. وضعیت اتصال هر ۳ ثانیه و پرسش‌های DB هر ۱۰ ثانیه (یا پس از
        تازه‌سازی داشبورد) اجرا می‌شوند.
        """
        dashboard = getattr(self, "dashboard", None)
        if dashboard is None or not hasattr(dashboard, "set_connection_health"):
            return
        now = time.monotonic()
        if not force and now - getattr(self, "_command_center_at", 0.0) < 3.0:
            return
        self._command_center_at = now
        try:
            market = self.app.market
            supervisor = getattr(self, "_connection_supervisor", None)
            feed = getattr(self, "_live_feed", None)
            state = "starting"
            if supervisor is not None:
                state = str(getattr(supervisor.state, "value", "offline"))
            elif market is not None and market.is_online:
                state = "online"
            dashboard.set_connection_health({
                "state": state,
                "exchange": getattr(market, "exchange_name", "") if market is not None else "",
                "data_age": getattr(feed, "data_age_seconds", None) if feed is not None else None,
                "streams": getattr(market, "stream_stats", {}) if market is not None else {},
                "rest": market.rest_health() if market is not None and hasattr(market, "rest_health") else {},
            })

            engine = getattr(self, "_auto_trader_engine", None)
            config = engine.config if engine is not None else self._auto_trade_config()
            dashboard.set_engine_status({
                "exists": engine is not None,
                "running": bool(engine is not None and engine.is_running),
                "halted": bool(engine is not None and getattr(engine, "_halted_reason", "")),
                "open": len(engine.open_trades) if engine is not None else 0,
                "max": int(getattr(config, "max_concurrent", 0) or 0),
                "live": str(getattr(config, "mode", "paper")).lower() == "live",
                "daily_limit": float(getattr(config, "daily_loss_limit", 0) or 0),
            })

            if not force and now - getattr(self, "_command_db_at", 0.0) < 10.0:
                return
            self._command_db_at = now
            repo = self.app.trade_repository
            user_id = self.app.auth.user_id
            records = list(repo.open_trades(user_id) or [])
            marked = [r for r in records if r.get("last_price")]
            margin = 0.0
            for record in records:
                leverage = float(record.get("leverage") or 1.0) or 1.0
                margin += float(record.get("quantity") or 0.0) * float(record.get("entry_price") or 0.0) / leverage
            realised = repo.daily_realised_pnl(user_id) if hasattr(repo, "daily_realised_pnl") else None
            statistics = repo.statistics(user_id=user_id)
            dashboard.set_portfolio({
                "open_count": len(records),
                "unrealised": sum(float(r.get("pnl") or 0.0) for r in marked) if marked else None,
                "realised_today": float(realised) if realised is not None else None,
                "margin": margin if records else None,
                "win_rate": float(statistics.get("win_rate", 0.0)) if statistics.get("closed", statistics.get("total", 0)) else None,
            })
        except Exception:  # noqa: BLE001 - داشبورد نباید برنامه را بخواباند
            logger.debug("Command center refresh failed", exc_info=True)

    # ------------------------------------------------------------------
    # وضعیت هوش مصنوعی
    # ------------------------------------------------------------------
    def save_dashboard_layout(self, state: str) -> None:
        """
        ذخیرهٔ چیدمان دلخواه کاربر در داشبورد.

        در ترجیحات کاربر می‌نشیند نه در تنظیمات سراسری، تا هر کاربر
        چیدمان خودش را داشته باشد.
        """
        self.app.auth.set_preference("ui.dashboard_layout", str(state or ""))
        self.status(self.tr_.tr("layout.saved"))
        self._toast(self.tr_.tr("layout.saved"), level="success")

    def restore_dashboard_layout(self) -> None:
        """اعمال چیدمان ذخیره‌شده هنگام راه‌اندازی."""
        state = str(self.app.settings.get("ui.dashboard_layout", "") or "")
        if state:
            self.dashboard.apply_layout_state(state)

    def open_ai_settings(self) -> None:
        """کلیک روی کارت هوش مصنوعی → زبانهٔ هوش مصنوعی در تنظیمات."""
        self._go_to("nav.settings")
        self.settings_page.open_tab("settings.ai")

    def refresh_ai_status(self) -> None:
        """
        بررسی زندهٔ سرویس هوش مصنوعی و به‌روزرسانی کارت نوار کناری.

        بررسی واقعی است، نه خواندن تنظیمات: سرویس ممکن است پیکربندی
        شده ولی خاموش باشد. اگر هوش مصنوعی غیرفعال باشد اصلاً درخواستی
        فرستاده نمی‌شود — نه معطلی، نه توکن سوخته.
        """
        card = getattr(self.window.sidebar, "ai_status", None)
        if card is None:
            return

        if not self.app.ai_enabled():
            card.set_status(
                state="unknown",
                title=self.tr_.tr("sidebar.ai_title"),
                detail=self.tr_.tr("sidebar.ai_off"),
            )
            return

        provider = str(self.app.settings.get("ai.provider", "") or "")
        model = str(self.app.settings.get("ai.model", "") or "")

        async def probe() -> tuple[bool, str]:
            """پرسش از خود سرویس که آیا پاسخ می‌دهد."""
            agent = self.app.autonomous_agent()
            if agent is None:
                return False, self.tr_.tr("sidebar.ai_off")
            return await agent.health_check()

        def apply(result: tuple[bool, str]) -> None:
            """نشاندن نتیجه روی کارت (نخ رابط کاربری)."""
            if not _dialog_alive(card):
                return
            ok, detail = result
            card.set_status(
                state="connected" if ok else "disconnected",
                title=self.tr_.tr("sidebar.ai_title"),
                provider=provider,
                model=model,
                detail="" if ok else str(detail or "")[:80],
            )

        def failed(message: str, exc: Exception | None = None) -> None:
            """شکست بررسی هم یک وضعیت است و باید دیده شود."""
            if not _dialog_alive(card):
                return
            card.set_status(
                state="disconnected",
                title=self.tr_.tr("sidebar.ai_title"),
                provider=provider,
                model=model,
                detail=str(message or "")[:80],
            )

        card.set_checking(self.tr_.tr("sidebar.ai_checking"))
        self.runner.submit(
            "ai-status",
            probe(),
            on_success=apply,
            on_error=failed,
        )

    # ------------------------------------------------------------------
    # نرخ تومان
    # ------------------------------------------------------------------
    def refresh_fiat_rate(self) -> None:
        """
        دریافت نرخ تتر به تومان.

        منبع اول صرافی‌های ایرانی است؛ اگر در دسترس نبودند، نرخ دستی
        کاربر به کار می‌رود — همان چیزی که کاربر خواسته بود.
        """
        if self._fiat is None:
            from market.fiat_rates import FiatRateService

            manual = self.app.settings.get_float("market.manual_toman_rate", 0.0)
            self._fiat = FiatRateService(manual_rate=manual or None)

        async def fetch() -> Any:
            """دریافت نرخ در نخ پس‌زمینه."""
            return await self._fiat.get_rate()

        def apply(rate: Any) -> None:
            """اعمال نرخ روی صفحه بازارها."""
            if rate is None:
                self.markets.set_toman_rate(None)
                return
            self._toman_rate = rate.toman
            self._toman_source = rate.source
            self.markets.set_toman_rate(rate.toman, rate.source)

        self.runner.submit(
            "fiat-rate",
            fetch(),
            on_success=apply,
            on_error=lambda message, exc=None: logger.info("Toman rate unavailable: %s", message),
        )

    def _apply_timezone_setting(self) -> None:
        """اعمال منطقه زمانی انتخابی کاربر روی نمایش زمان‌ها."""
        name = str(self.app.settings.get("ui.timezone", "system") or "system")
        set_display_timezone(name)

    # ------------------------------------------------------------------
    # داشبورد
    # ------------------------------------------------------------------
    def refresh_dashboard(self) -> None:
        """به‌روزرسانی کارت‌های وضعیت و جدول‌های داشبورد."""
        if self.app.market is None:
            return

        watchlist = self._watchlist_symbols()

        async def collect() -> dict[str, Any]:
            """گردآوری داده داشبورد در یک رفت‌وبرگشت."""
            rows: list[dict[str, Any]] = []
            wanted = set(watchlist)

            # تلاش اول: یک درخواست دسته‌ای برای همه نمادها.
            # این روش به‌جای N درخواست جدا، فقط یک رفت‌وبرگشت شبکه دارد.
            try:
                tickers = await self.app.market.get_all_tickers()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Bulk ticker fetch failed, falling back: %s", exc)
                tickers = []

            found: dict[str, Any] = {
                t.symbol: t for t in tickers if t.symbol in wanted
            }

            # اگر نمادی در پاسخ دسته‌ای نبود، فقط همان‌ها را موازی می‌گیریم.
            missing = [s for s in watchlist if s not in found]
            if missing:
                fetched = await asyncio.gather(
                    *(self.app.market.get_ticker(s) for s in missing),
                    return_exceptions=True,
                )
                for symbol, ticker in zip(missing, fetched, strict=True):
                    if isinstance(ticker, BaseException):
                        logger.debug("Ticker failed for %s: %s", symbol, ticker)
                        continue
                    found[symbol] = ticker

            # ترتیب واچ‌لیست کاربر حفظ می‌شود.
            for symbol in watchlist:
                ticker = found.get(symbol)
                if ticker is None:
                    continue
                rows.append(
                    {
                        "symbol": ticker.symbol,
                        "price": ticker.last_price,
                        "change_percent": ticker.change_percent,
                        "volume": ticker.volume_24h,
                    }
                )
            return {
                "market_rows": rows,
                "market_summary": summarise_market(tickers),
                "online": self.app.market.is_online,
                "exchange": self.app.market.exchange_name,
                "websocket": self.app.market.websocket_status,
            }

        def apply(payload: dict[str, Any]) -> None:
            """نمایش داده گردآوری‌شده."""
            rows = payload["market_rows"]
            self.dashboard.set_market_rows(rows)
            summary = payload.get("market_summary") or {}
            if summary.get("total"):
                self.dashboard.set_breadth(summary)
                self.dashboard.set_movers(summary.get("gainers", []), summary.get("losers", []))
            self._refresh_command_center(force=True)
            self.dashboard.set_ticker_items(
                [
                    {
                        "symbol": row.get("symbol", ""),
                        "price": self.tr_.format_number(row.get("price", 0.0), 2),
                        "change": row.get("change_percent", 0.0) or 0.0,
                    }
                    for row in rows[:8]
                ]
            )
            self._update_dashboard_stats(rows)
            self.dashboard.set_status_value("exchange", str(payload["exchange"]).upper())
            # زمان به وقت محلی کاربر، نه UTC
            self.dashboard.set_status_value("last_update", format_time(now_local()))

            provider = (
                str(self.app.settings.get("ai.provider", "—"))
                if self.app.ai_enabled()
                else self.tr_.tr("common.disabled")
            )
            self.dashboard.set_status_value("ai_provider", provider)

            self._refresh_connection_indicator()
            self._load_signal_history()

        self.dashboard.refresh_button.start_busy()
        self.runner.submit(
            "dashboard",
            collect(),
            on_success=apply,
            on_error=self._on_error,
            on_finished=lambda: self.dashboard.refresh_button.finish_busy(),
        )

    # ------------------------------------------------------------------
    # بازارها
    # ------------------------------------------------------------------
    def refresh_markets(self) -> None:
        """دریافت فهرست بازارها و پر کردن جدول و فهرست نمادها."""
        if self.app.market is None:
            return
        self.status(self.tr_.tr("markets.loading"))

        async def collect() -> tuple[list[dict[str, Any]], list[str]]:
            """دریافت تیکرها و نمادها."""
            tickers = await self.app.market.get_all_tickers()
            rows = [
                {
                    "symbol": ticker.symbol,
                    "price": ticker.last_price,
                    "change_percent": ticker.change_percent,
                    "high": ticker.high_24h,
                    "volume": ticker.volume_24h,
                }
                for ticker in tickers
            ]
            self._remember_prices(rows)
            # پرگردش‌ترین بازارها بالا؛ فهرست کامل صرافی برای جدول زیاد است
            rows.sort(key=lambda row: row.get("volume") or 0.0, reverse=True)
            symbols = [row["symbol"] for row in rows]
            return rows[:MARKET_ROW_LIMIT], symbols

        def apply(payload: tuple[list[dict[str, Any]], list[str]]) -> None:
            """نمایش بازارها و پر کردن همه فهرست‌های نماد."""
            rows, symbols = payload
            self._symbols = symbols
            self.markets.set_palette(self.themes.palette)
            # ستاره‌ها باید پیش از ترسیم ردیف‌ها شناخته شده باشند
            self.markets.set_watchlist(self.app.symbol_repository.get_watchlist())
            self.markets.set_rows(rows)
            if self._toman_rate:
                self.markets.set_toman_rate(self._toman_rate, self._toman_source)

            self._refresh_search_suggestions()

            # فهرست **کامل** نمادها در تحلیل و سیگنال. قبلاً فقط ۱۰۰ نماد
            # نخست داده می‌شد و کاربر نمی‌توانست بقیه را انتخاب کند.
            preferred = self._watchlist_symbols()
            unique = list(dict.fromkeys(preferred + symbols))
            self.analysis.set_symbols(unique)
            self.signals.set_symbols(unique)
            self.chat.set_symbols(unique)
            # ترمینال معامله — با انتخاب نخستین نماد، نمودار و
            # پیش‌بینی همان لحظه بار می‌شوند (سیگنال از خود کمبو).
            self.trades.set_auto_symbols(unique)

            self._update_streamed_symbols()

            # شمارندهٔ نوار پایین تا امروز هیچ‌وقت مقدار نمی‌گرفت
            self.window.set_market_count(len(symbols))
            self._refresh_connection_indicator()

            self.status(self.tr_.tr("markets.count", count=len(symbols)))

        self.markets.refresh_button.start_busy()
        self.runner.submit(
            "markets",
            collect(),
            on_success=apply,
            on_error=self._on_error,
            on_finished=lambda: self.markets.refresh_button.finish_busy(),
        )

    def add_to_watchlist(self) -> None:
        """افزودن نماد انتخاب‌شده به فهرست پیگیری."""
        symbol = self.markets.selected_symbol()
        if not symbol:
            self.status(self.tr_.tr("markets.select_symbol_first"))
            return
        exchange = self.app.settings.active_exchange
        added = self.app.symbol_repository.add_to_watchlist(symbol, exchange)
        key = "markets.added_to_watchlist" if added else "markets.already_in_watchlist"
        self.status(self.tr_.tr(key, symbol=symbol))
        self.refresh_dashboard()

    def _on_watchlist_toggled(self, symbol: str, added: bool) -> None:
        """
        کلیک روی ستارهٔ جدول بازارها.

        صفحه پیش از ارسال سیگنال، ستاره را جابه‌جا کرده است؛ اینجا فقط
        پایگاه داده را هم‌راستا می‌کنیم و اگر ذخیره شکست خورد، ستاره را
        به وضعیت واقعی برمی‌گردانیم.
        """
        exchange = self.app.settings.active_exchange
        try:
            if added:
                self.app.symbol_repository.add_to_watchlist(symbol, exchange)
                key = "markets.added_to_watchlist"
            else:
                self.app.symbol_repository.remove_from_watchlist(symbol, exchange)
                key = "markets.removed_from_watchlist"
            self.status(self.tr_.tr(key, symbol=symbol))
        except Exception:  # noqa: BLE001 - نباید جدول را بشکند
            logger.exception("Watchlist toggle failed for %s", symbol)
        self.markets.set_watchlist(self.app.symbol_repository.get_watchlist())
        self.refresh_watchlist_panel()
        self.refresh_dashboard()

    # ------------------------------------------------------------------
    # فهرست‌های دیده‌بانی (مورد ۵.۳)
    # ------------------------------------------------------------------
    def refresh_watchlist_panel(self, *, keep_selection: bool = True) -> None:
        """
        تازه‌سازی پنل مدیریت فهرست‌ها از روی پایگاه داده.

        تنها نقطه‌ای است که پنل داده می‌گیرد؛ هر تغییری (افزودن، حذف،
        جابه‌جایی) به همین‌جا ختم می‌شود تا نما و پایگاه داده از هم جدا
        نیفتند.
        """
        panel = getattr(self.markets, "watchlist_panel", None)
        if panel is None:
            return
        repo = self.app.symbol_repository
        try:
            names = repo.watchlist_names()
            counts = repo.watchlist_counts()
            current = panel.current_list() if keep_selection else repo.DEFAULT_LIST
            if current not in names:
                current = repo.DEFAULT_LIST
            panel.set_lists(names, counts)
            panel.list_combo.setCurrentIndex(max(0, panel.list_combo.findData(current)))
            panel.set_items(repo.watchlist_details(current))
        except Exception:  # noqa: BLE001 - پنل نباید برنامه را بشکند
            logger.exception("Could not refresh the watchlist panel")

    def _on_watchlist_list_selected(self, name: str) -> None:
        """کاربر فهرست دیگری را برگزید."""
        panel = self.markets.watchlist_panel
        panel.set_items(self.app.symbol_repository.watchlist_details(name))

    def _create_watchlist(self, name: str) -> None:
        """ساخت فهرست تازه و انتخاب فوری آن."""
        repo = self.app.symbol_repository
        if not repo.create_watchlist(name):
            self.status(self.tr_.tr("watchlist.create_failed"))
            return
        # فهرست خالی ردیفی در پایگاه داده ندارد، پس تا افزودن اولین
        # نماد فقط در همین نشست دیده می‌شود.
        panel = self.markets.watchlist_panel
        counts = repo.watchlist_counts()
        counts[name] = 0
        panel.set_lists([*repo.watchlist_names(), name], counts)
        panel.list_combo.setCurrentIndex(max(0, panel.list_combo.findData(name)))
        panel.set_items([])
        self.status(self.tr_.tr("watchlist.created", name=name))

    def _rename_watchlist(self, old_name: str, new_name: str) -> None:
        """تغییر نام فهرست."""
        if self.app.symbol_repository.rename_watchlist(old_name, new_name):
            self.refresh_watchlist_panel(keep_selection=False)
            panel = self.markets.watchlist_panel
            panel.list_combo.setCurrentIndex(max(0, panel.list_combo.findData(new_name)))
            self.status(self.tr_.tr("watchlist.renamed", name=new_name))
        else:
            self.status(self.tr_.tr("watchlist.rename_failed"))

    def _delete_watchlist(self, name: str) -> None:
        """
        حذف فهرست پس از تأیید.

        تأیید اینجا گرفته می‌شود نه در پنل، تا ویجت به پنجرهٔ پیام
        وابسته نباشد و در آزمون بدون مداخلهٔ کاربر آزمودنی بماند.
        """
        repo = self.app.symbol_repository
        count = len(repo.watchlist_details(name))
        answer = QMessageBox.question(
            self.window,
            self.tr_.tr("watchlist.delete"),
            self.tr_.tr(
                "watchlist.delete_confirm",
                name=name,
                count=self.tr_.format_number(count, 0),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        repo.delete_watchlist(name)
        self.refresh_watchlist_panel(keep_selection=False)
        self.status(self.tr_.tr("watchlist.deleted", name=name))
        self._toast(self.tr_.tr("watchlist.deleted", name=name), level="success")
        self.refresh_dashboard()

    def _move_watchlist_symbol(self, list_name: str, symbol: str, delta: int) -> None:
        """جابه‌جایی یک نماد در ترتیب فهرست."""
        if self.app.symbol_repository.move_in_watchlist(list_name, symbol, int(delta)):
            panel = self.markets.watchlist_panel
            panel.set_items(self.app.symbol_repository.watchlist_details(list_name))
            # انتخاب روی همان نماد می‌ماند تا بتوان پشت سر هم جابه‌جا کرد
            panel.select_symbol(symbol)
            self.status(self.tr_.tr("watchlist.moved"))

    def _remove_watchlist_symbol(self, list_name: str, symbol: str) -> None:
        """حذف یک نماد از فهرست."""
        exchange = self.app.settings.active_exchange
        self.app.symbol_repository.remove_from_watchlist(symbol, exchange, list_name)
        self.refresh_watchlist_panel()
        self.markets.set_watchlist(self.app.symbol_repository.get_watchlist())
        self.status(self.tr_.tr("watchlist.removed", symbol=symbol))
        self.refresh_dashboard()

    def _save_watchlist_note(self, list_name: str, symbol: str, note: str) -> None:
        """ثبت یادداشت روی یک عضو فهرست."""
        exchange = self.app.settings.active_exchange
        if self.app.symbol_repository.set_watchlist_note(
            symbol, exchange, note, list_name
        ):
            panel = self.markets.watchlist_panel
            panel.set_items(self.app.symbol_repository.watchlist_details(list_name))
            panel.select_symbol(symbol)
            self.status(self.tr_.tr("watchlist.note_saved"))

    def _open_watchlist_symbol(self, symbol: str) -> None:
        """دوبار کلیک روی نماد فهرست، آن را در صفحهٔ تحلیل باز می‌کند."""
        if not symbol:
            return
        self.analysis.symbol_combo.setCurrentText(symbol)
        self.window.go_to_page(self.window.page_index("nav.analysis"))
        self.run_analysis()

    def _on_market_double_clicked(self, *_: Any) -> None:
        """دوبار کلیک روی یک بازار، آن را در صفحه تحلیل باز می‌کند."""
        symbol = self.markets.selected_symbol()
        if not symbol:
            return
        self.analysis.symbol_combo.setCurrentText(symbol)
        self.window.go_to_page(2)
        self.run_analysis()

    def _watchlist_symbols(self) -> list[str]:
        """
        نمادهای فهرست پیگیری، یا چند نماد پیش‌فرض اگر خالی باشد.

        داشبورد خالی در اولین اجرا تجربه بدی است.
        """
        exchange = self.app.settings.active_exchange
        watchlist = self.app.symbol_repository.get_watchlist()
        if watchlist:
            return watchlist
        defaults = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"]
        return [s for s in defaults if not self._symbols or s in self._symbols] or defaults[:3]

    # ------------------------------------------------------------------
    # تحلیل
    # ------------------------------------------------------------------
    def _populate_indicator_catalog(self) -> None:
        """
        پر کردن پنل اندیکاتورهای صفحهٔ تحلیل از روی رجیستری واقعی.

        توضیح هر اندیکاتور به زبان جاری نمایش داده می‌شود و وضعیت روشن
        بودن از تنظیمات کاربر خوانده می‌گردد.
        """
        language = self.tr_.language
        entries: list[dict[str, Any]] = []
        for name in self.app.indicators.available_indicators():
            try:
                meta = self.app.indicators.get_metadata(name)
            except Exception:  # noqa: BLE001 - یک اندیکاتور خراب نباید پنل را بشکند
                logger.exception("Indicator metadata failed for %s", name)
                continue
            description = meta.get("description_fa" if language == "fa" else "description_en")
            entries.append({"name": name, "label": name, "description": description or ""})

        saved = self.app.settings.get_list(SettingKey.ANALYSIS_ENABLED_INDICATORS, [])
        enabled = [str(item) for item in saved] or list(ANALYSIS_INDICATORS)
        # اندیکاتورهایی که دیگر ثبت نشده‌اند کنار گذاشته می‌شوند
        known = {entry["name"] for entry in entries}
        enabled = [name for name in enabled if name in known]
        self.analysis.set_indicator_catalog(entries, enabled)
        self.analysis.apply_theme(self.themes.tokens)

    def _on_analysis_activated(self) -> None:
        """
        اجرای خودکار تحلیل در نخستین ورود به صفحه.

        فقط یک بار؛ بعد از آن کاربر خودش تصمیم می‌گیرد کِی دوباره
        تحلیل کند و نمودار زنده هم کار خودش را می‌کند.
        """
        if getattr(self, "_analysis_auto_ran", False):
            return
        if self.app.market is None:
            return
        symbol = self.analysis.symbol_combo.currentText().strip()
        if not symbol:
            return
        self._analysis_auto_ran = True
        self.run_analysis()

    def _on_indicator_toggled(self, name: str, checked: bool) -> None:  # noqa: ARG002
        """ذخیرهٔ فهرست اندیکاتورهای روشن در تنظیمات کاربر."""
        self.app.settings.set(
            SettingKey.ANALYSIS_ENABLED_INDICATORS, self.analysis.enabled_indicators()
        )

    def run_analysis(self) -> None:
        """اجرای تحلیل تکنیکال روی نماد و تایم‌فریم انتخاب‌شده."""
        symbol = self.analysis.symbol_combo.currentText().strip().upper()
        timeframe = self.analysis.timeframe_combo.currentText()
        if not symbol:
            self.status(self.tr_.tr("markets.select_symbol_first"))
            return
        if self.app.market is None:
            self.status(self.tr_.tr("errors.not_connected"))
            return

        # اندیکاتورهای روشن در پنل کناری؛ اگر هیچ‌کدام روشن نباشد فهرست
        # پیش‌فرض به کار می‌رود تا جدول تحلیل هرگز خالی نماند.
        selected_indicators = self.analysis.enabled_indicators() or list(ANALYSIS_INDICATORS)

        self.analysis.set_busy(True)
        self.status(self.tr_.tr("analysis.running"))

        async def analyse() -> dict[str, Any]:
            """دریافت کندل‌ها و محاسبه اندیکاتورها و سطوح."""
            candles = await self.app.market.get_candles(symbol, timeframe, limit=300)
            if len(candles) < MIN_CANDLES_FOR_ANALYSIS:
                return {"candles": candles, "insufficient": True}

            names = list(selected_indicators) + [name for name, _ in CHART_OVERLAYS]
            parameters = dict(CHART_OVERLAYS)
            results = self.app.indicators.calculate_many(
                names, candles, timeframe, symbol=symbol, parameters=parameters
            )
            levels = find_support_resistance(candles)
            structure = analyze_market_structure(candles, timeframe=timeframe)
            return {
                "candles": candles,
                "results": results,
                "levels": levels,
                "structure": structure,
                "insufficient": False,
            }

        def apply(payload: dict[str, Any]) -> None:
            """نمایش نتیجه تحلیل."""
            candles: list[Candle] = payload["candles"]
            self.analysis.set_chart_data(candles, timeframe, symbol)

            if payload.get("insufficient"):
                self.analysis.set_indicator_rows([])
                self.analysis.set_level_rows([])
                self.status(
                    self.tr_.tr("errors.insufficient_data", symbol=symbol, timeframe=timeframe)
                )
                return

            results = payload["results"]
            timestamps = [float(candle.timestamp) for candle in candles]
            for name, params in CHART_OVERLAYS:
                result = results.get(name)
                if result is None:
                    continue
                series = self._overlay_series(result)
                label = f"{name}({params.get('period', '')})"
                if series:
                    self.analysis.set_chart_overlay(label, timestamps, series)

            rows = [
                {
                    "name": result.name,
                    "timeframe": result.timeframe or timeframe,
                    "value": self._format_latest(result.latest),
                    "signal": self.tr_.tr(f"analysis.{str(result.signal).lower()}", str(result.signal)),
                }
                for result in results.values()
                if result.name in selected_indicators
            ]
            self.analysis.set_indicator_rows(rows)

            levels = payload["levels"]
            self.analysis.set_level_rows(
                [
                    {
                        "price": level.price,
                        "type": level.kind,
                        "strength": level.strength,
                        "distance_percent": level.distance_percent,
                    }
                    for level in levels
                ]
            )
            self.analysis.set_chart_levels(levels)

            self.status(self.tr_.tr("analysis.done", symbol=symbol, timeframe=timeframe))

            # پس از تحلیل موتور، عامل هوش مصنوعی هم نظر می‌دهد
            if self.analysis.use_ai_checkbox.isChecked():
                self._run_ai_analysis(symbol, timeframe)
            else:
                self.analysis.set_ai_text(self.tr_.tr("signals.engine_only"))

        self.runner.submit(
            "analysis",
            analyse(),
            on_success=apply,
            on_error=self._on_error,
            on_finished=lambda: self.analysis.set_busy(False),
        )

    def _sync_prediction_symbol(self, symbol: str) -> None:
        """نماد صفحهٔ پیش‌بینی همگام با نماد تحلیل بماند."""
        self.prediction.set_symbol((symbol or "").strip().upper())

    def run_prediction_report(self) -> None:
        """
        اجرای موتور هوش پیش‌بینی روی نماد فعلی.

        گزارش کامل (نردبان ۱۳ افق، رژیم‌ها، سناریوها، دقت) در نخِ
        پس‌زمینه ساخته می‌شود و فقط نتیجه روی صفحه می‌نشیند.
        """
        symbol = self.analysis.symbol_combo.currentText().strip().upper()
        if not symbol:
            self.status(self.tr_.tr("markets.select_symbol_first"))
            return
        if self.app.market is None:
            self.status(self.tr_.tr("errors.not_connected"))
            return

        self.prediction.set_symbol(symbol)
        self.prediction.set_busy(True)
        self.status(self.tr_.tr("prediction.computing"))

        async def compute() -> dict[str, Any] | None:
            """ساخت گزارش در حلقهٔ ناهمگام — هیچ عددی در UI ساخته نمی‌شود."""
            engine = self.app.prediction_engine
            if engine is None:
                return None
            report = await engine.assess(symbol)
            return report.to_dict() if report is not None else None

        def apply(payload: dict[str, Any] | None) -> None:
            """نمایش گزارش یا اعلام صادقانهٔ نبودِ داده."""
            self.prediction.update_report(payload)
            if payload is None:
                self.status(self.tr_.tr("prediction.no_data"))
            else:
                self.status(
                    "{} — {}".format(
                        symbol, self.tr_.tr("prediction.horizons_title")
                    )
                )

        self.runner.submit(
            "prediction",
            compute(),
            on_success=apply,
            on_error=self._on_error,
            on_finished=lambda: self.prediction.set_busy(False),
        )

    def _run_ai_analysis(self, symbol: str, timeframe: str) -> None:
        """
        اجرای عامل خودمختار روی نماد انتخاب‌شده.

        اگر هوش مصنوعی پیکربندی نشده باشد، پیام روشنی نشان داده می‌شود
        به‌جای اینکه زبانهٔ تحلیل خالی بماند.
        """
        agent = self.app.autonomous_agent()
        if agent is None:
            self.analysis.set_ai_text(self.tr_.tr("analysis.ai_disabled"))
            return

        self.analysis.set_ai_text(self.tr_.tr("analysis.ai_running", symbol=symbol))

        def apply(outcome: Any) -> None:
            """نمایش نتیجه عامل."""
            self.analysis.set_ai_text(self._format_agent_outcome(outcome))
            if outcome.succeeded:
                self.status(self.tr_.tr("analysis.ai_done"))

        def failed(message: str, exception: Exception | None = None) -> None:
            """گزارش شکست بدون خراب کردن بقیه تحلیل."""
            self.analysis.set_ai_text(self.tr_.tr("analysis.ai_failed", error=message))
            logger.warning("AI analysis failed: %s", message)

        self.runner.submit(
            "ai-analysis",
            agent.run(symbol, timeframe=timeframe),
            on_success=apply,
            on_error=failed,
        )

    def _format_agent_outcome(self, outcome: Any) -> str:
        """
        تبدیل نتیجه عامل به متن خوانا.

        مسیر تصمیم‌گیری هم نشان داده می‌شود تا کاربر ببیند عامل بر پایه
        چه داده‌ای نتیجه گرفته — نه اینکه فقط یک حکم بی‌پشتوانه ببیند.
        """
        lines: list[str] = []
        direction = self.tr_.tr(f"signals.{outcome.direction.lower()}", outcome.direction)
        lines.append(f"{direction} — {self.tr_.tr('signals.confidence')}: {outcome.confidence}%")

        decision = outcome.decision or {}
        if decision.get("reason"):
            lines.append("")
            lines.append(str(decision["reason"]))
        if outcome.narrative and outcome.narrative != decision.get("reason"):
            lines.append("")
            lines.append(outcome.narrative)
        if decision.get("invalidation"):
            lines.append("")
            lines.append(f"{self.tr_.tr('signals.invalidation')}: {decision['invalidation']}")

        if outcome.steps:
            lines.append("")
            lines.append(self.tr_.tr("analysis.ai_steps") + ":")
            for step in outcome.steps:
                if step.tool:
                    mark = "✓" if step.ok else "✗"
                    lines.append(f"  {mark} {step.tool}")

        if outcome.provider:
            lines.append("")
            lines.append(f"{outcome.provider} · {outcome.model}")
        if outcome.errors:
            lines.append("")
            lines.append("⚠ " + "; ".join(outcome.errors))
        return "\n".join(lines)

    @staticmethod
    def _overlay_series(result: Any) -> list[float | None]:
        """
        استخراج سری عددی یک اندیکاتور برای ترسیم.

        برخی اندیکاتورها چند سری برمی‌گردانند (مثل باندها)؛ برای نمودار
        اولین سری عددی کافی است.
        """
        values = getattr(result, "values", None)
        if isinstance(values, dict):
            for series in values.values():
                if isinstance(series, list) and series:
                    return series
            return []
        if isinstance(values, list):
            return values
        return []

    @staticmethod
    def _format_latest(latest: Any) -> str:
        """قالب‌بندی آخرین مقدار اندیکاتور برای جدول."""
        if isinstance(latest, dict):
            return "  ".join(
                f"{key}={value:,.4g}" if isinstance(value, int | float) else f"{key}={value}"
                for key, value in list(latest.items())[:3]
            )
        if isinstance(latest, int | float):
            return f"{latest:,.4g}"
        return str(latest) if latest is not None else "—"

    # ------------------------------------------------------------------
    # سیگنال‌ها
    # ------------------------------------------------------------------
    def generate_signal(self) -> None:
        """
        تولید سیگنال برای نماد و تایم‌فریم انتخاب‌شده.

        اگر کاربر هوش مصنوعی را خواسته باشد، عامل خودمختار تصمیم‌گیر
        اصلی است و موتور سیگنال نقش پشتیبان را دارد؛ در غیر این صورت
        فقط موتور کار می‌کند.
        """
        symbol = self.signals.symbol_combo.currentText().strip().upper()
        if not symbol:
            self.status(self.tr_.tr("markets.select_symbol_first"))
            return
        if self.app.signals is None:
            self.status(self.tr_.tr("errors.not_connected"))
            return

        timeframe = self.signals.timeframe_combo.currentData() or "4h"
        # تایم‌فریم‌های انتخابی کاربر. پیش‌تر این انتخاب خوانده نمی‌شد و
        # موتور همیشه فهرست تنظیمات را می‌گرفت، پس تغییر آن در صفحه هیچ
        # اثری نداشت.
        frames = self.signals.selected_timeframes()
        # تایم‌فریم اصلی باید حتماً میان فهرست باشد وگرنه موتور آن را
        # نادیده می‌گیرد و نتیجه با انتظار کاربر نمی‌خواند.
        if str(timeframe) not in frames:
            frames = [str(timeframe), *frames]

        if self.signals.use_ai_checkbox.isChecked() and self.app.ai_enabled():
            self._generate_ai_signal(symbol, str(timeframe), frames)
            return

        self.signals.set_busy(True)
        self.status(self.tr_.tr("signals.generating"))

        def apply(signal: TradingSignal) -> None:
            """نمایش سیگنال و به‌روزرسانی سابقه."""
            self._last_signal = signal
            # شناسهٔ ذخیره‌شده را به کارت می‌دهیم تا دکمهٔ «تحلیل دوباره»
            # فعال شود؛ `to_dict()` خودش شناسه ندارد.
            payload = signal.to_dict()
            payload["id"] = int(getattr(self.app, "_last_signal_id", 0) or 0)
            self.signals.show_signal(payload)
            self.check_signal_alerts(payload)
            self._load_signal_history()

            direction = signal.direction
            if direction is SignalDirection.WAIT:
                self.status(self.tr_.tr("signals.wait_result", symbol=symbol))
            else:
                self.status(
                    self.tr_.tr(
                        "signals.result",
                        symbol=symbol,
                        direction=self.tr_.tr(f"signals.{direction.value.lower()}"),
                        confidence=signal.confidence,
                    )
                )

            # اگر همان نماد روی نمودار باز است، سطوح سیگنال را علامت بزن
            if self.analysis.symbol_combo.currentText().strip().upper() == symbol:
                self.analysis.chart.mark_signal(
                    signal.entry_min, signal.stop_loss, signal.take_profits
                )

        self.runner.submit(
            "signal",
            self.app.generate_signal(symbol, frames),
            on_success=apply,
            on_error=self._on_error,
            on_finished=lambda: self.signals.set_busy(False),
        )

    def scan_market(self) -> None:
        """
        پویش همهٔ نمادهای پرگردش با موتور ریاضی.

        کاربر خواست یک دکمه همهٔ نمادها را یکی‌یکی بررسی کند و بهترین‌ها
        بالا بیایند. این کار **هیچ توکن هوش مصنوعی مصرف نمی‌کند**؛
        تحلیل هوشمند دکمهٔ جداگانه در هر ردیف دارد.
        """
        if self.app.signals is None:
            self.status(self.tr_.tr("errors.not_connected"))
            return

        options = self.signals.scan_options()
        universe = self.signals.scan_universe_options()
        frames = self.signals.selected_timeframes()
        self.save_scan_settings(self.signals.scan_settings())

        # نتیجه‌های زنده: هر سیگنال همان لحظه در جدول می‌نشیند و اگر
        # کاربر پویشِ طولانیِ کل بازار را متوقف کند، از دست نمی‌رود.
        self._scan_live_signals = []
        self._scan_live_dirty = False
        self._scan_live_active = True
        self.signals.set_scanning(True)
        self.signals.set_scan_status(self.tr_.tr("signals.scan_running"))

        def on_signal(signal: Any) -> None:
            """سیگنال پذیرفته‌شده از نخ شبکه → سیگنال Qt → نخ رابط کاربری."""
            self.scan_partial_found.emit(signal)

        last_progress = [0.0]

        def on_progress(progress: Any) -> None:
            """گزارش پیشرفت از نخ شبکه → سیگنال Qt → نخ رابط کاربری."""
            # ۲.۴.۱: در پویش کل بازار صدها گزارش در ثانیه صف رابط را پر می‌کرد؛
            # حداکثر ~۷ بار در ثانیه کافی است (گزارش پایانی همیشه می‌رود).
            now = time.monotonic()
            if int(progress.done) < int(progress.total) and now - last_progress[0] < 0.15:
                return
            last_progress[0] = now
            self.scan_progress_changed.emit(
                int(progress.done), int(progress.total),
                str(progress.symbol), int(progress.found),
            )

        def apply(result: Any) -> None:
            """نمایش نتیجهٔ پویش."""
            self._scan_live_active = False
            self._stop_live_flush()
            self._scan_live_signals = []
            rows = self._apply_stale_filter(
                self._decorate_validity([signal.to_dict() for signal in result.signals])
            )
            self.signals.set_scan_results(rows)
            self._last_scan = result
            self._seed_auto_focus(list(result.signals))
            if rows:
                message = self.tr_.tr(
                    "signals.scan_done",
                    found=len(rows),
                    scanned=result.scanned,
                    seconds=f"{result.duration_seconds:.0f}",
                )
            else:
                message = self.tr_.tr("signals.scan_empty")
            self.signals.set_scan_status(message)
            self.status(message)
            # سیگنال‌های تازه در پایگاه داده ذخیره شده‌اند، پس سابقه هم
            # باید تازه شود وگرنه کاربر دو فهرست ناهماهنگ می‌بیند.
            self._load_signal_history()

        def on_error(name: str, error: Exception) -> None:
            """خطای پویش نباید صفحه را در حالت «در حال پویش» رها کند."""
            self._scan_live_active = False
            self._stop_live_flush()
            self.signals.set_scan_status(self.tr_.tr("signals.scan_failed"))
            self._on_error(name, error)

        self.runner.submit(
            "market-scan",
            self.app.scan_market(
                None,
                frames,
                limit=options["limit"],
                min_confidence=options["min_confidence"],
                include_wait=options["include_wait"],
                on_progress=on_progress,
                universe=universe["universe"],
                min_turnover=universe["min_turnover"],
                smart_filter=universe["smart_filter"],
                on_signal=on_signal,
            ),
            on_success=apply,
            on_error=on_error,
            on_finished=lambda: self.signals.set_scanning(False),
        )

    # ------------------------------------------------------------------
    # نسخهٔ ۲.۴.۰ — نتیجهٔ زندهٔ پویش و تنظیمات پایدار آن
    # ------------------------------------------------------------------
    #: فاصلهٔ تازه‌سازی جدول هنگام رسیدن سیگنال‌های زنده (میلی‌ثانیه).
    #: رسم دوبارهٔ جدول به ازای هر سیگنال، روی پویش ۱۰۰۰+ نماد رابط را
    #: کند می‌کرد؛ دسته‌کردن تا ۸۰۰ms هم زنده است و هم سبک.
    SCAN_LIVE_FLUSH_MS = 800

    def save_scan_settings(self, values: dict) -> None:
        """ذخیرهٔ دامنه/تعداد/پالایش پویش دستی."""
        for key, value in (values or {}).items():
            try:
                self.app.settings.set(key, value)
            except Exception as error:  # noqa: BLE001 - ذخیره نباید پویش را بشکند
                logger.debug("Could not persist %s: %s", key, error)

    def _load_scan_settings(self) -> None:
        """نشاندن تنظیمات ذخیره‌شدهٔ پویش دستی در صفحه."""
        keys = (
            "signals.scan_universe",
            "signals.scan_limit",
            "signals.scan_min_turnover",
            "signals.scan_smart_filter",
        )
        try:
            self.signals.set_scan_settings({key: self.app.settings.get(key) for key in keys})
        except Exception as error:  # noqa: BLE001
            logger.debug("Could not load scan settings: %s", error)

    def _on_scan_partial_signal(self, signal: Any) -> None:
        """یک سیگنال زنده رسید؛ جدول با تأخیر کوتاه و دسته‌ای تازه می‌شود."""
        if not getattr(self, "_scan_live_active", False):
            # پویش متوقف شده؛ سیگنال‌های دیررسیده جدول را عوض نکنند
            return
        live = getattr(self, "_scan_live_signals", None)
        if live is None:
            live = self._scan_live_signals = []
        live.append(signal)
        self._scan_live_dirty = True
        timer = getattr(self, "_scan_live_timer", None)
        if timer is None:
            timer = self._scan_live_timer = QTimer(self.window)
            timer.setSingleShot(True)
            timer.setInterval(self.SCAN_LIVE_FLUSH_MS)
            timer.timeout.connect(self._flush_scan_live)
        if not timer.isActive():
            timer.start()

    def _flush_scan_live(self) -> None:
        """نمایش سیگنال‌های زندهٔ انباشته، مرتب بر پایهٔ ضریب اطمینان."""
        if not getattr(self, "_scan_live_dirty", False):
            return
        self._scan_live_dirty = False
        signals = sorted(
            list(getattr(self, "_scan_live_signals", []) or []),
            key=lambda item: float(getattr(item, "confidence", 0) or 0),
            reverse=True,
        )
        if not signals:
            return
        started = time.monotonic()
        rows = self._apply_stale_filter(
            self._decorate_validity([signal.to_dict() for signal in signals])
        )
        self.signals.set_scan_results(rows)
        # تازه‌سازی تطبیقی (۲.۴.۱): اگر رسم جدول طول کشید، دفعهٔ بعد دیرتر؛
        # رابط کاربری هیچ‌وقت بیش از ~۱۰٪ وقتش را صرف این جدول نمی‌کند.
        elapsed_ms = (time.monotonic() - started) * 1000.0
        timer = getattr(self, "_scan_live_timer", None)
        if timer is not None:
            timer.setInterval(int(min(5000, max(self.SCAN_LIVE_FLUSH_MS, elapsed_ms * 10))))
        from types import SimpleNamespace

        # تا پایان پویش، دکمهٔ تحلیل هوشمند/جزئیات روی همین نتایج کار کند
        self._last_scan = SimpleNamespace(signals=signals)

    def _stop_live_flush(self) -> None:
        timer = getattr(self, "_scan_live_timer", None)
        if timer is not None:
            timer.stop()
        self._scan_live_dirty = False

    def _seed_auto_focus(self, signals: list) -> None:
        """
        نتیجهٔ پویش دستی → فهرست تمرکز سیگنال‌گیر خودکار.

        در حالت «فقط سیگنال‌های پیداشده» فهرست با همین نتایج جایگزین
        می‌شود؛ در حالت‌های دیگر به بالای فهرست افزوده می‌شود.
        """
        scheduler = getattr(self, "_auto_scheduler", None)
        if scheduler is None or not signals:
            return
        from signals.auto_scanner import SOURCE_FOUND, normalize_source

        replace = normalize_source(scheduler.config.source) == SOURCE_FOUND
        try:
            scheduler.seed_focus(signals, replace=replace)
        except Exception as error:  # noqa: BLE001
            logger.debug("Could not seed auto focus: %s", error)
            return
        self._refresh_auto_scan_status()

    def _on_auto_partial_signal(self, signal: Any) -> None:
        """سیگنال قوی در میانهٔ چرخش کامل: همان لحظه وارد فهرست تمرکز شود."""
        scheduler = getattr(self, "_auto_scheduler", None)
        if scheduler is None:
            return
        try:
            scheduler.seed_focus([signal])
        except Exception as error:  # noqa: BLE001
            logger.debug("Could not seed auto focus: %s", error)

    def _on_auto_scan_progress(self, done: int, total: int) -> None:
        """نمایش «X از Y» برای چرخش کامل خودکار."""
        scheduler = getattr(self, "_auto_scheduler", None)
        if scheduler is None or not scheduler.running:
            return
        self.signals.set_auto_scan_status(
            self.tr_.tr(
                "signals.auto.status_progress",
                done=self.tr_.format_number(int(done), 0),
                total=self.tr_.format_number(int(total), 0),
            ),
            focus=scheduler.focus_symbols,
        )

    # ------------------------------------------------------------------
    # سیگنال‌گیری خودکار
    # ------------------------------------------------------------------
    def start_auto_scanner(self) -> None:
        """
        راه‌اندازی زمان‌بند سیگنال‌گیری خودکار.

        تیک تایمر عمداً کوتاه (۱۵ ثانیه) است ولی خودِ پویش طبق فاصله‌ای
        که کاربر گفته اجرا می‌شود؛ تیک کوتاه فقط باعث می‌شود شمارش معکوس
        روی صفحه زنده بماند و تغییر تنظیمات فوراً اثر کند.
        """
        from signals.auto_scanner import AutoScanConfig, AutoScanScheduler

        self._auto_scheduler = AutoScanScheduler(
            AutoScanConfig.from_settings(self.app.settings)
        )
        self.signals.set_auto_scan_options(
            {
                key: self.app.settings.get(key)
                for key in (
                    "signals.auto_scan_enabled",
                    "signals.auto_scan_interval",
                    "signals.auto_scan_full_sweep",
                    "signals.auto_scan_full_interval",
                    "signals.auto_scan_focus_size",
                    "signals.auto_scan_min_confidence",
                    "signals.auto_scan_notify",
                    "signals.auto_scan_source",
                    "signals.auto_scan_universe",
                    "signals.auto_scan_sweep_limit",
                    "signals.auto_scan_min_turnover",
                    "signals.auto_scan_smart_filter",
                )
            }
        )
        self._load_scan_settings()

        self._auto_timer = QTimer(self.window)
        self._auto_timer.setInterval(AUTO_SCAN_TICK_MS)
        self._auto_timer.timeout.connect(self._auto_scan_tick)
        self._auto_timer.start()
        self._refresh_auto_scan_status()

    def save_auto_scan_config(self, values: dict) -> None:
        """ذخیرهٔ تنظیمات خودکار و اعمال فوری روی زمان‌بند."""
        from signals.auto_scanner import AutoScanConfig

        for key, value in values.items():
            self.app.settings.set(key, value)

        scheduler = getattr(self, "_auto_scheduler", None)
        if scheduler is not None:
            scheduler.apply_config(AutoScanConfig.from_settings(self.app.settings))
            self._refresh_auto_scan_status()

    def run_auto_scan_now(self) -> None:
        """
        اجرای فوری یک چرخهٔ خودکار بدون منتظر ماندن.

        نوع چرخه را خود زمان‌بند تعیین می‌کند؛ اگر فهرست تمرکز خالی باشد
        چرخش کامل اجرا می‌شود.
        """
        scheduler = getattr(self, "_auto_scheduler", None)
        if scheduler is None or scheduler.running:
            return
        from signals.auto_scanner import ScanJob

        from signals.auto_scanner import SOURCE_MARKET, normalize_source

        source = normalize_source(scheduler.config.source)
        if scheduler.focus_symbols and source != SOURCE_MARKET:
            job = ScanJob(
                kind="focus",
                symbols=tuple(scheduler.focus_symbols[: scheduler.config.focus_size]),
                reason="auto.reason_focus",
            )
        elif scheduler.config.sweep_active or (
            not scheduler.focus_symbols and source != "found"
        ):
            job = ScanJob(kind="full", symbols=(), reason="auto.reason_bootstrap")
        else:
            # «فقط سیگنال‌های پیداشده» و هنوز چیزی پیدا نشده
            self.signals.set_auto_scan_status(self.tr_.tr("signals.auto.status_need_scan"))
            return
        self._execute_auto_job(job)

    def _auto_scan_tick(self) -> None:
        """بررسی دوره‌ای: آیا نوبت پویشی رسیده است؟"""
        scheduler = getattr(self, "_auto_scheduler", None)
        if scheduler is None:
            return

        # پویش دستی در جریان باشد، خودکار مزاحمش نمی‌شود
        # پویش دستی یا خودکارِ در جریان نباید با نوبت تازه تداخل کند
        if {"market-scan", "auto-scan"} & set(self.runner.active_keys()):
            self._refresh_auto_scan_status()
            return

        job = scheduler.due()
        if job is None:
            self._refresh_auto_scan_status()
            return
        self._execute_auto_job(job)

    def _execute_auto_job(self, job: Any) -> None:
        """اجرای یک نوبت پویش خودکار."""
        scheduler = self._auto_scheduler
        if self.app.signals is None:
            return

        scheduler.start(job)
        frames = self.signals.selected_timeframes()
        symbols = list(job.symbols) or None
        config = scheduler.config
        universe = str(getattr(config, "universe", "top") or "top")
        full = symbols is None
        # چرخش کامل روی «کل صرافی» سقف تعداد ندارد؛ فقط حالت «پرگردش‌ترین‌ها»
        # به `sweep_limit` محدود می‌شود.
        if full:
            limit = config.sweep_limit if universe == "top" else None
        else:
            limit = None

        def on_signal(signal: Any) -> None:
            self.auto_scan_signal_found.emit(signal)

        last_auto_progress = [0.0]

        def on_progress(progress: Any) -> None:
            now = time.monotonic()
            if int(progress.done) < int(progress.total) and now - last_auto_progress[0] < 0.5:
                return
            last_auto_progress[0] = now
            self.auto_scan_progress.emit(int(progress.done), int(progress.total))

        scan_kwargs: dict[str, Any] = {}
        if full:
            scan_kwargs = {
                "universe": universe,
                "min_turnover": float(getattr(config, "min_turnover", 0.0) or 0.0),
                "smart_filter": bool(getattr(config, "smart_filter", True)),
                "on_signal": on_signal,
                "on_progress": on_progress,
            }

        self.signals.set_auto_scan_status(
            self.tr_.tr(
                "signals.auto.status_running_focus"
                if job.kind == "focus"
                else "signals.auto.status_running_full"
            ),
            focus=scheduler.focus_symbols,
        )

        def apply(result: Any) -> None:
            """ثبت نتیجه، تازه‌سازی فهرست تمرکز و نمایش سیگنال‌ها."""
            signals = list(getattr(result, "signals", []) or [])
            scheduler.complete(job, signals)

            rows = [signal.to_dict() for signal in signals]
            if rows:
                # نتیجهٔ خودکار در همان جدول پویش می‌نشیند تا کاربر دو
                # جای متفاوت را دنبال نکند.
                self.signals.set_scan_results(rows)
                self._last_scan = result
                self._load_signal_history()

            self._notify_auto_signals(signals)
            self._refresh_auto_scan_status(
                last_count=len(rows), last_at=now_local()
            )

        def failed(name: str, error: Exception) -> None:
            scheduler.fail(job)
            logger.warning("Automatic scan failed: %s", error)
            self.signals.set_auto_scan_status(
                self.tr_.tr("signals.auto.status_failed"),
                focus=scheduler.focus_symbols,
            )

        self.runner.submit(
            "auto-scan",
            self.app.scan_market(
                symbols,
                frames,
                limit=limit,
                min_confidence=scheduler.config.focus_min_confidence,
                include_wait=False,
                cpu_duty=BACKGROUND_CPU_DUTY,
                **scan_kwargs,
            ),
            on_success=apply,
            on_error=failed,
        )

    def _notify_auto_signals(self, signals: list) -> None:
        """
        اطلاع‌رسانی سیگنال‌های تازه‌ای که قبلاً دیده نشده‌اند.

        بدون بررسی «قبلاً دیده شده»، هر چرخه همان نماد را دوباره اعلام
        می‌کند و کاربر اعلان‌ها را می‌بندد — یعنی قابلیت بی‌اثر می‌شود.
        """
        if not self.app.settings.get_bool("signals.auto_scan_notify", True):
            return

        seen = getattr(self, "_auto_notified", None)
        if seen is None:
            seen = self._auto_notified = {}

        for signal in signals[:3]:
            symbol = str(getattr(signal, "symbol", "") or "")
            confidence = int(getattr(signal, "confidence", 0) or 0)
            direction = str(getattr(getattr(signal, "direction", ""), "name", "") or "")
            if not symbol or direction.upper() == "WAIT":
                continue
            # همان نماد با همان جهت و ضریب نزدیک، خبر تازه نیست
            previous = seen.get(symbol)
            if previous and previous[0] == direction and abs(previous[1] - confidence) < 5:
                continue
            seen[symbol] = (direction, confidence)
            self._toast(
                self.tr_.tr(
                    "signals.auto.found",
                    symbol=symbol,
                    confidence=self.tr_.format_number(confidence, 0),
                ),
                level="success",
            )

    def _refresh_auto_scan_status(
        self, *, last_count: int | None = None, last_at: Any = None
    ) -> None:
        """به‌روزرسانی متن وضعیت زیر پنل خودکار."""
        scheduler = getattr(self, "_auto_scheduler", None)
        if scheduler is None:
            return

        if not scheduler.config.enabled:
            self.signals.set_auto_scan_status(self.tr_.tr("signals.auto.status_off"))
            return

        from signals.auto_scanner import SOURCE_FOUND, normalize_source

        if (
            last_count is None
            and not scheduler.running
            and normalize_source(scheduler.config.source) == SOURCE_FOUND
            and not scheduler.focus_symbols
        ):
            self.signals.set_auto_scan_status(self.tr_.tr("signals.auto.status_need_scan"))
            return

        if last_count is not None:
            text = self.tr_.tr(
                "signals.auto.status_done",
                time=format_time(last_at or now_local()),
                count=self.tr_.format_number(last_count, 0),
            )
        else:
            text = self.tr_.tr(
                "signals.auto.status_idle",
                time=self._format_duration(scheduler.seconds_until_next()),
            )
        self.signals.set_auto_scan_status(text, focus=scheduler.focus_symbols)

    def _format_duration(self, seconds: int) -> str:
        """قالب‌بندی «۴ دقیقه و ۲۰ ثانیه» برای شمارش معکوس."""
        seconds = max(0, int(seconds))
        minutes, rest = divmod(seconds, 60)
        if minutes and rest:
            return self.tr_.tr(
                "common.duration_minutes_seconds",
                minutes=self.tr_.format_number(minutes, 0),
                seconds=self.tr_.format_number(rest, 0),
            )
        if minutes:
            return self.tr_.tr(
                "common.duration_minutes", minutes=self.tr_.format_number(minutes, 0)
            )
        return self.tr_.tr(
            "common.duration_seconds", seconds=self.tr_.format_number(rest, 0)
        )

    # ------------------------------------------------------------------
    # پیگیری نتیجهٔ سیگنال‌ها
    # ------------------------------------------------------------------
    def _note_market_offline(self) -> None:
        """
        اطلاع‌رسانی یک‌بارهٔ قطع بودن بازار.

        کاربر گفت «همیشه بازار زنده نیست». سکوت در این حالت بدترین
        رفتار است: کاربر عددهای ثابت را می‌بیند و فکر می‌کند بازار
        آرام است، در حالی که برنامه اصلاً داده نمی‌گیرد.

        پیام فقط یک بار داده می‌شود؛ تکرارش هر ۱۰ ثانیه آزاردهنده است.
        """
        if getattr(self, "_offline_notified", False):
            return
        self._offline_notified = True
        self.status(self.tr_.tr("common.state.offline"))
        self._toast(self.tr_.tr("common.state.offline"), level="warning")

    def _note_market_online(self) -> None:
        """بازگشت بازار؛ اجازهٔ هشدار بعدی دوباره صادر می‌شود."""
        if getattr(self, "_offline_notified", False):
            self._offline_notified = False
            self._toast(self.tr_.tr("common.state.back_online"), level="success")

    def start_live_chart(self) -> None:
        """
        راه‌اندازی به‌روزرسانی زندهٔ نمودار تحلیل.

        کاربر گفت «نمودار باید زنده باشد». پیش‌تر نمودار فقط با فشردن
        دکمهٔ «تحلیل» عوض می‌شد و بعد از آن ثابت می‌ماند، پس عملاً یک
        عکس بود نه نمودار بازار.
        """
        self._chart_timer = QTimer(self.window)
        self._chart_timer.setInterval(LIVE_CHART_TICK_MS)
        self._chart_timer.timeout.connect(self._live_chart_tick)
        self._chart_timer.start()

        # قیمت زنده جدا و پرتکرارتر به‌روز می‌شود.
        #
        # کشیدن دوبارهٔ ۳۰۰ کندل هر ۳ ثانیه هم گران است هم روی صرافی
        # فشار می‌آورد؛ ولی گرفتن «آخرین قیمت» ارزان است و همان چیزی
        # است که کاربر انتظار دارد زنده تکان بخورد.
        self._price_timer = QTimer(self.window)
        self._price_timer.setInterval(LIVE_PRICE_TICK_MS)
        self._price_timer.timeout.connect(self._live_price_tick)
        self._price_timer.start()

    def _live_price_tick(self) -> None:
        """گرفتن آخرین قیمت و نشاندن آن روی نمودار، بدون redraw کندل‌ها."""
        if not self.app.settings.get_bool("analysis.live_chart", True):
            return
        if not self.analysis.isVisible() or self.app.market is None:
            return
        symbol = self.analysis.symbol_combo.currentText().strip().upper()
        if not symbol:
            return
        cached = self._cached_symbol_price(symbol, max_age=30.0)
        if cached > 0:
            self.analysis.set_live_price(cached)
            self._remember_price(symbol, cached)
        if self._cached_symbol_price(symbol, max_age=1.5) > 0:
            return
        if not self._market_reachable() or getattr(self, "_price_busy", False):
            if cached <= 0:
                self._note_market_offline()
            return
        self._price_busy = True

        async def fetch() -> float:
            """آخرین قیمت واقعی بازار."""
            return float(await self.app.market.get_current_price(symbol))

        def apply(price: float) -> None:
            """نشاندن قیمت تازه روی برچسب و خط قیمت."""
            if price > 0:
                self.analysis.set_live_price(price)
                self._remember_price(symbol, float(price))
                self._note_market_online()

        self.runner.submit(
            "live-price",
            fetch(),
            on_success=apply,
            on_error=lambda *_: None,
            on_finished=lambda: setattr(self, "_price_busy", False),
        )

    def _live_chart_tick(self) -> None:
        """تازه‌سازی کندل‌های نمودار اگر کاربر روی صفحهٔ تحلیل باشد."""
        if not self.app.settings.get_bool("analysis.live_chart", True):
            return
        # فقط وقتی صفحهٔ تحلیل دیده می‌شود؛ گرفتن کندل برای صفحه‌ای که
        # کاربر نمی‌بیند، هم پهنای باند است هم فشار بی‌دلیل روی صرافی.
        if not self.analysis.isVisible():
            return
        if getattr(self, "_chart_busy", False) or self.app.market is None:
            return
        symbol = self.analysis.symbol_combo.currentText().strip().upper()
        timeframe = self.analysis.timeframe_combo.currentText()
        if not symbol:
            return
        if not self._market_reachable():
            peeked = self._peek_chart(symbol, timeframe)
            if peeked:
                self.analysis.set_chart_data(peeked, timeframe, symbol)
                return
            self._note_market_offline()
            return
        self._chart_busy = True

        async def fetch() -> list[Any]:
            """گرفتن تازه‌ترین کندل‌ها. اگر REST نیامد، کش کافی است."""
            try:
                return await self.app.market.get_candles(symbol, timeframe, limit=300)
            except Exception:  # noqa: BLE001
                return self._peek_chart(symbol, timeframe)

        def apply(candles: list[Any]) -> None:
            """کشیدن دوبارهٔ نمودار بدون دست‌زدن به جدول اندیکاتورها."""
            if candles:
                self.analysis.set_chart_data(candles, timeframe, symbol)

        self.runner.submit(
            "live-chart",
            fetch(),
            on_success=apply,
            on_error=lambda *_: None,
            on_finished=lambda: setattr(self, "_chart_busy", False),
        )

    def start_trade_monitor(self) -> None:
        """
        راه‌اندازی پایش زندهٔ معاملات باز.

        کاربر گزارش کرد معاملهٔ باز هیچ‌وقت تغییر نمی‌کند و بسته نمی‌شود.
        علت این بود که هیچ چیزی معاملات باز را دنبال نمی‌کرد: `pnl` فقط
        هنگام بستن حساب می‌شد و حد ضرر/حد سود ذخیره می‌شدند ولی هرگز
        بررسی نمی‌گشتند.
        """
        self._live_prices: dict[str, float] = {}
        self._trade_timer = QTimer(self.window)
        self._trade_timer.setInterval(TRADE_MONITOR_TICK_MS)
        self._trade_timer.timeout.connect(self._trade_monitor_tick)
        self._trade_timer.start()
        QTimer.singleShot(3_000, self._trade_monitor_tick)

    def _trade_monitor_tick(self) -> None:
        """یک دور پایش معاملات باز با قیمت زنده."""
        if getattr(self, "_trade_monitor_busy", False):
            return
        # بازار همیشه زنده نیست. وقتی اتصال قطع است، قیمت قدیمی را
        # به‌عنوان قیمت روز جا نمی‌زنیم و معامله را هم با آن نمی‌بندیم:
        # بستن خودکار بر پایهٔ قیمت کهنه، ضرر واقعی می‌سازد.
        if self.app.market is None or not self._market_reachable():
            self._note_market_offline()
            return
        try:
            records = self.app.trade_repository.open_trades(self.app.auth.user_id)
        except Exception:  # noqa: BLE001 - پایش نباید برنامه را بشکند
            logger.debug("Reading open trades failed", exc_info=True)
            return
        if not records:
            return

        from trading.trade_monitor import evaluate, position_from_record

        engine = getattr(self, "_auto_trader_engine", None)
        managed_ids = {t.trade_id for t in engine.open_trades} if engine is not None else set()
        records = [r for r in records if r.get("id") not in managed_ids and r.get("mode") != "live"]
        positions = [p for p in (position_from_record(r) for r in records) if p is not None]
        if not positions:
            return
        symbols = sorted({p.symbol for p in positions})
        self._trade_monitor_busy = True
        ticks = self._ensure_tick_engine()
        config = self._auto_trade_config()

        async def fetch() -> dict[str, float]:
            """اول کش تازه، و فقط اگر کهنه بود REST."""
            prices: dict[str, float] = {}
            market = self.app.market
            for symbol in symbols:
                if market is None:
                    continue
                try:
                    if ticks.is_stale(symbol):
                        await asyncio.wait_for(market.refresh_execution_quote(symbol, ticks), timeout=5.0)
                    if not ticks.is_stale(symbol):
                        prices[symbol] = ticks.get(symbol).last
                except Exception:
                    continue
            return prices

        def apply(prices: dict[str, float]) -> None:
            """اعمال سود/زیان زنده و بستن خودکار در صورت لزوم."""
            if not prices:
                return
            self._live_prices.update({k.upper(): v for k, v in prices.items()})
            updates, closures = [], []
            for position in positions:
                if ticks.is_stale(position.symbol):
                    continue
                quote = ticks.get(position.symbol)
                price = quote.exit_price(position.side)
                price *= 1 - config.slippage_percent / 100 if position.is_long else 1 + config.slippage_percent / 100
                marks, exits = evaluate([position], {position.symbol: price})
                updates.extend(marks)
                closures.extend(exits)

            for item in updates:
                try:
                    self.app.trade_repository.update_live_pnl(
                        int(item["id"]),
                        price=float(item["price"]),
                        pnl=float(item["pnl"]),
                        pnl_percent=float(item["pnl_percent"]),
                    )
                except Exception:  # noqa: BLE001
                    logger.debug("Live PnL update failed", exc_info=True)

            for trade_id, price, reason in closures:
                try:
                    self.app.trade_repository.close_trade(
                        int(trade_id),
                        exit_price=float(price),
                        fee=self._exit_fee(next((r for r in records if r.get("id") == trade_id), None), price=float(price)),
                        note=reason,
                    )
                    self._toast(
                        self.tr_.tr(f"trades.closed_{reason}"), level="success"
                    )
                except Exception:  # noqa: BLE001
                    logger.warning("Auto-close failed for trade %s", trade_id)

            if updates or closures:
                self.refresh_trades()

        def finished() -> None:
            self._trade_monitor_busy = False

        self.runner.submit(
            "trade-monitor",
            fetch(),
            on_success=apply,
            on_error=lambda *_: None,
            on_finished=finished,
        )

    def start_outcome_tracker(self) -> None:
        """
        راه‌اندازی پیگیری خودکار نتیجهٔ سیگنال‌ها.

        هنگام شروع، سیگنال‌های قدیمیِ ثبت‌نشده هم وارد پیگیری می‌شوند
        (`backfill`) تا کاربری که پیش از این نسخه سیگنال ساخته، صفحهٔ
        عملکرد خالی نبیند.
        """
        if not self.app.settings.get_bool("signals.track_outcomes", True):
            return

        try:
            restored = self.app.outcome_repository.backfill()
            if restored:
                logger.info("Backfilled outcome tracking for %s signal(s)", restored)
        except Exception:  # noqa: BLE001 - پیگیری نباید راه‌اندازی را بشکند
            logger.debug("Outcome backfill failed", exc_info=True)

        self._outcome_timer = QTimer(self.window)
        self._outcome_timer.setInterval(OUTCOME_TICK_MS)
        self._outcome_timer.timeout.connect(self._outcome_tick)
        self._outcome_timer.start()
        # یک بررسی اولیه بلافاصله، تا کاربر برای دیدن اولین نتیجه
        # منتظر یک دورهٔ کامل نماند.
        QTimer.singleShot(5_000, self._run_outcome_check)

    def _outcome_tick(self) -> None:
        """آیا موعد بررسی دوباره رسیده است؟"""
        if not self.app.settings.get_bool("signals.track_outcomes", True):
            return
        interval = max(30, self.app.settings.get_int("signals.track_interval", 180) or 180)
        last = getattr(self, "_outcome_last_run", None)
        if last is not None and (now_local() - last).total_seconds() < interval:
            return
        self._run_outcome_check()
        self._run_alert_check()

    # ------------------------------------------------------------------
    # هشدارها
    # ------------------------------------------------------------------
    def _alert_book(self) -> Any:
        """خواندن هشدارهای کاربر از تنظیمات."""
        from signals.alerts import AlertBook

        return AlertBook.from_list(self.app.settings.get("alerts.items", []) or [])

    def _save_alert_book(self, book: Any) -> None:
        """
        ذخیرهٔ وضعیت هشدارها.

        لازم است چون هشدارِ فعال‌شده باید خاموش بماند؛ بدون ذخیره، با
        هر تیک دوباره فعال می‌شود و کاربر زیر بار اعلان دفن می‌شود.
        """
        self.app.settings.set("alerts.items", book.as_list())

    def create_price_alert(self, symbol: str) -> None:
        """
        ساخت هشدار قیمتی برای یک نماد.

        قیمت فعلی به‌عنوان پیش‌فرض پیشنهاد می‌شود تا کاربر عدد را از
        صفر تایپ نکند، و جهت هشدار از مقایسهٔ عدد واردشده با قیمت فعلی
        خودکار تشخیص داده می‌شود — کاربر لازم نیست «بالاتر/پایین‌تر» را
        هم انتخاب کند.
        """
        from PySide6.QtWidgets import QInputDialog

        from signals.alerts import ALERT_ABOVE, ALERT_BELOW, Alert

        symbol = str(symbol or "").strip().upper()
        if not symbol:
            return

        current = self._last_price(symbol)
        value, accepted = QInputDialog.getDouble(
            self.window,
            self.tr_.tr("alerts.add"),
            f"{symbol} — {self.tr_.tr('alerts.value')}",
            float(current or 0.0),
            0.0,
            1_000_000_000.0,
            8,
        )
        if not accepted:
            return

        book = self._alert_book()
        alert = Alert(
            symbol=symbol,
            value=float(value),
            direction=ALERT_ABOVE if float(value) >= float(current or 0) else ALERT_BELOW,
        )
        ok, reason = book.add(alert)
        if not ok:
            self._toast(self.tr_.tr("alerts.invalid", reason=reason), level="warning")
            return
        self._save_alert_book(book)
        self._toast(
            self.tr_.tr("alerts.added") + f"  {alert.describe()}", level="success"
        )

    def _run_alert_check(self) -> None:
        """
        بررسی هشدارهای قیمتی.

        فقط برای نمادهایی که هشدار مسلح دارند قیمت گرفته می‌شود، نه کل
        بازار؛ کاربر ممکن است دو هشدار داشته باشد و گرفتن ۱۳۰۰ قیمت
        برای آن، هدردادن پهنای باند است.
        """
        if not self.app.settings.get_bool("alerts.enabled", True):
            return
        if self.app.market is None or not self.app.market.is_online:
            return
        if "alert-check" in set(self.runner.active_keys()):
            return

        book = self._alert_book()
        symbols = book.active_symbols()
        if not symbols:
            return

        async def fetch() -> dict[str, float]:
            """گرفتن قیمت همان چند نماد."""
            import asyncio as _asyncio

            async def one(symbol: str) -> tuple[str, float]:
                try:
                    return symbol, float(
                        await self.app.market.get_current_price(symbol)
                    )
                except Exception:  # noqa: BLE001
                    return symbol, 0.0

            pairs = await _asyncio.gather(*(one(symbol) for symbol in symbols))
            return {symbol: price for symbol, price in pairs if price > 0}

        def apply(prices: dict[str, float]) -> None:
            """اعلام هشدارهای فعال‌شده."""
            hits = book.check_prices(prices)
            if not hits:
                return
            self._save_alert_book(book)
            for hit in hits:
                self._toast(
                    self.tr_.tr("alerts.fired", detail=hit.message),
                    level="warning",
                )

        self.runner.submit(
            "alert-check",
            fetch(),
            on_success=apply,
            on_error=lambda *_: None,
        )

    def check_signal_alerts(self, signal: dict[str, Any]) -> None:
        """
        بررسی هشدارهای سیگنالی روی یک سیگنال تازه.

        از مسیر تولید سیگنال صدا زده می‌شود تا کاربر لازم نباشد صفحه را
        باز نگه دارد.
        """
        if not self.app.settings.get_bool("alerts.enabled", True):
            return
        try:
            book = self._alert_book()
            hits = book.check_signal(signal or {})
            if not hits:
                return
            self._save_alert_book(book)
            for hit in hits:
                self._toast(
                    self.tr_.tr("alerts.fired", detail=hit.message),
                    level="success",
                )
        except Exception:  # noqa: BLE001
            logger.debug("Signal alert check failed", exc_info=True)

    def _run_outcome_check(self) -> None:
        """
        یک دور بررسی قیمت روی سیگنال‌های باز.

        اگر بررسی قبلی هنوز تمام نشده، این نوبت رد می‌شود؛ صف‌کردن
        بررسی‌ها روی هم فقط بار بی‌مورد می‌سازد.
        """
        if self.app.market is None or "outcome-track" in set(self.runner.active_keys()):
            return
        self._outcome_last_run = now_local()

        def apply(report: dict) -> None:
            """گزارش نتیجه و اطلاع‌رسانی سیگنال‌های بسته‌شده."""
            if not report or not report.get("closed"):
                self._refresh_outcome_view(quiet=True)
                return

            # سیگنالی بسته شد؛ حالا وقت درس‌گرفتن از آن است. در
            # پس‌زمینه و بی‌صدا، چون کاربر منتظرش نیست.
            self._run_signal_review()

            wins = int(report.get("wins", 0))
            losses = int(report.get("losses", 0))
            if wins or losses:
                self._toast(
                    self.tr_.tr(
                        "signals.outcome.closed_toast",
                        wins=self.tr_.format_number(wins, 0),
                        losses=self.tr_.format_number(losses, 0),
                    ),
                    level="success" if wins >= losses else "warning",
                )
            self._refresh_outcome_view(quiet=True)

        def failed(name: str, error: Exception) -> None:
            # شکست در پیگیری یک اتفاق عادی است (اینترنت قطع، صرافی کند)
            # و نباید به کاربر هشدار بدهد.
            logger.debug("Outcome tracking round failed: %s", error)

        self.runner.submit(
            "outcome-track",
            self.app.refresh_outcomes(),
            on_success=apply,
            on_error=failed,
        )

    def _run_signal_review(self) -> None:
        """
        بازبینی هوش مصنوعی روی سیگنال‌های تازه‌بسته‌شده.

        بی‌صدا اجرا می‌شود: کاربر برای آن دکمه‌ای نزده و شکستش (مثلاً
        خاموش‌بودن مدل محلی) هیچ هشداری لازم ندارد. نتیجه دفعهٔ بعد که
        سابقه را باز کند آنجاست.
        """
        if "signal-review" in set(self.runner.active_keys()):
            return
        if not self.app.settings.get_bool("ai.auto_review", True):
            return

        def done(report: dict) -> None:
            if report and int(report.get("reviewed", 0)):
                self._load_signal_history()

        def failed(name: str, error: Exception) -> None:
            logger.debug("Signal review round failed: %s", error)

        self.runner.submit(
            "signal-review",
            self.app.review_closed_signals(),
            on_success=done,
            on_error=failed,
        )

    def refresh_scorecard(self) -> None:
        """
        محاسبهٔ دفترچهٔ نتیجهٔ پیش‌بینی‌ها.

        کندل‌های تاریخی چند نماد گرفته می‌شود، پس ناهمگام اجرا می‌شود و
        دکمه تا پایان قفل می‌ماند تا کاربر چند بار پشت‌سرهم نزند.
        """
        button = getattr(self.reports, "scorecard_refresh_button", None)
        if button is not None:
            button.setEnabled(False)
        self.status(self.tr_.tr("scorecard.checking"))

        def apply(report: dict) -> None:
            """نشاندن گزارش روی جدول."""
            self.reports.set_scorecard(report or {})
            checked = int((report or {}).get("checked") or 0)
            self.status(
                self.tr_.tr("scorecard.title") + f" — {checked}"
                if checked else self.tr_.tr("scorecard.no_data")
            )

        def failed(name: str, error: Exception) -> None:
            """شکست محاسبه نباید صفحه را قفل رها کند."""
            self._on_error(name, error)

        def finished() -> None:
            if button is not None:
                button.setEnabled(True)

        self.runner.submit(
            "forecast-scorecard",
            self.app.score_forecasts(),
            on_success=apply,
            on_error=failed,
            on_finished=finished,
        )

    def refresh_outcomes_now(self) -> None:
        """بررسی فوری نتیجه‌ها به درخواست کاربر."""
        self.status(self.tr_.tr("signals.outcome.checking"))
        self._run_outcome_check()

    def _refresh_outcome_view(self, *, quiet: bool = False) -> None:
        """
        تازه‌سازی صفحهٔ عملکرد اگر ساخته شده باشد.

        نسخهٔ ۲.۴.۲: این متد هر ۳۰ ثانیه از تایمر پیگیری نتیجه صدا زده
        می‌شد و روی نخ رابط تا ۵۰۰۰ ردیف پایگاه داده می‌خواند و گروه‌بندی
        می‌کرد — یکی از علت‌های «هنگ» پس از چند ساعت. حالا:
            * وقتی صفحه پنهان است، فقط «کهنه» علامت می‌خورد و هنگام نمایش
              صفحه تازه می‌شود؛
            * پرس‌وجوها در نخ پس‌زمینه اجرا و فقط نتیجه روی رابط نشانده
              می‌شود.
        """
        page = getattr(self, "performance", None)
        if page is None:
            return
        if not self._outcome_watch_installed:
            self._outcome_watch_installed = True
            try:
                from ui.responsiveness import ShowWatcher

                self._outcome_show_watcher = ShowWatcher(page, self._on_outcome_view_shown)
            except Exception:  # noqa: BLE001
                logger.debug("Performance show watcher unavailable", exc_info=True)
        if quiet and not page.isVisible():
            self._outcome_view_stale = True
            return
        self._outcome_view_stale = False
        try:
            days = int(getattr(page, "selected_period", lambda: 0)() or 0)
        except Exception:  # noqa: BLE001
            days = 0
        repository = self.app.outcome_repository

        def load() -> tuple[Any, list[Any]]:
            report = repository.performance(days=days or None)
            records = list(repository.history(days=days or None, limit=300))
            return report, records

        def apply(result: tuple[Any, list[Any]]) -> None:
            report, records = result
            try:
                page.set_performance(report)
                page.set_history([self._outcome_row(record) for record in records])
            except Exception:  # noqa: BLE001
                logger.debug("Could not apply performance view", exc_info=True)
                if not quiet:
                    self.status(self.tr_.tr("signals.outcome.error"))

        def failed(_name: str, _error: Exception) -> None:
            logger.debug("Could not refresh performance view", exc_info=True)
            if not quiet:
                self.status(self.tr_.tr("signals.outcome.error"))

        if not self.runner.running:
            # پیش از راه‌اندازی حلقهٔ پس‌زمینه (و در آزمون‌ها): همان مسیر هم‌گام
            try:
                apply(load())
            except Exception as error:  # noqa: BLE001
                failed("outcome-view", error)
            return
        self.runner.run_blocking(
            "outcome-view", load, on_success=apply, on_error=failed
        )

    def _on_outcome_view_shown(self) -> None:
        """صفحهٔ عملکرد نمایش داده شد؛ اگر کهنه است تازه شود."""
        if self._outcome_view_stale:
            self._refresh_outcome_view(quiet=True)

    def _outcome_row(self, record: Any) -> dict:
        """تبدیل یک رکورد نتیجه به ردیف جدول."""
        return {
            "id": int(record.id),
            "signal_id": int(record.signal_id),
            "symbol": record.symbol,
            "direction": record.direction,
            "status": record.status,
            "confidence": int(record.confidence or 0),
            "timeframe": record.primary_timeframe,
            "entry_price": float(record.entry_price or 0),
            "exit_price": float(record.exit_price or 0),
            "last_price": float(record.last_price or 0),
            "result_percent": float(record.result_percent or 0),
            "realized_r": float(record.realized_r or 0),
            "targets_hit": int(record.targets_hit or 0),
            "created_at": record.created_at,
            "closed_at": record.closed_at,
        }

    def stop_market_scan(self) -> None:
        """توقف پویش در جریان."""
        self.runner.cancel("market-scan")
        self._scan_live_active = False
        self.signals.set_scanning(False)
        # نتیجه‌های زندهٔ تا این لحظه حفظ و نمایش داده می‌شوند
        self._scan_live_dirty = bool(getattr(self, "_scan_live_signals", None))
        self._flush_scan_live()
        self._stop_live_flush()
        partial = list(getattr(self, "_scan_live_signals", []) or [])
        if partial:
            self._seed_auto_focus(partial)
            message = self.tr_.tr("signals.scan_cancelled_partial", found=len(partial))
        else:
            message = self.tr_.tr("signals.scan_cancelled")
        self.signals.set_scan_status(message)
        self.status(message)

    def analyze_scanned_symbol(self, symbol: str) -> None:
        """
        تحلیل هوشمند روی یک نمادِ از پیش پویش‌شده.

        این همان «بعداً هرکدام را که خواستم جداگانه بدهم هوش مصنوعی
        تحلیل کند» است: پویش ارزان انجام شده و حالا فقط همین یک نماد
        هزینهٔ هوش مصنوعی دارد.
        """
        signal = None
        for candidate in getattr(getattr(self, "_last_scan", None), "signals", []) or []:
            if str(candidate.symbol).upper() == str(symbol).upper():
                signal = candidate
                break
        if signal is None:
            # نتیجهٔ پویش در دست نیست (مثلاً پس از تعویض صرافی)؛ به‌جای
            # پیام خطا، سیگنال را از نو می‌سازیم.
            self.signals.symbol_combo.setCurrentText(symbol)
            self.generate_signal()
            return

        # اگر هوش مصنوعی خاموش است، همان اول صادقانه بگو. پیش‌تر کاربر
        # دکمه را می‌زد، متن قالبی می‌گرفت و پیام «تحلیل انجام شد»
        # می‌دید — یعنی فکر می‌کرد هوش مصنوعی کار کرده ولی نکرده بود.
        if not self.app.ai_enabled():
            self.signals.set_scan_status(self.tr_.tr("signals.ai_disabled_hint"))
            self.status(self.tr_.tr("signals.ai_disabled_hint"))
            return

        self.signals.set_scan_status(self.tr_.tr("signals.scan_ai_running"))

        def apply(updated: Any) -> None:
            """
            نمایش سیگنال تحلیل‌شده.

            منبع تحلیل بررسی می‌شود: اگر هوش مصنوعی نتوانسته بنویسد،
            `NarrativeWriter` بی‌صدا متن قالبی برمی‌گرداند و ادعای
            «تحلیل هوشمند انجام شد» گمراه‌کننده است.
            """
            self._last_signal = updated
            payload = updated.to_dict()
            self.signals.show_signal(payload)

            if str(getattr(updated, "analysis_source", "")) == "ai":
                message = self.tr_.tr("signals.scan_ai_done", symbol=symbol)
            else:
                message = self.tr_.tr("signals.scan_ai_fallback", symbol=symbol)
            self.signals.set_scan_status(message)
            self.status(message)

            # نتیجه باید دیده شود. کاربر گزارش داد «تحلیل نمی‌کند» چون
            # متن فقط در کارت کوچک می‌نشست و خوانده نمی‌شد.
            dialog = AnalysisDialog(payload, self.tr_, self.window)
            dialog.pdf_requested.connect(
                lambda data: self._export_analysis_pdf(data, dialog)
            )
            dialog.exec()

            self._load_signal_history()

        self.runner.submit(
            f"scan-ai-{symbol}",
            self.app.analyze_scanned_signal(signal),
            on_success=apply,
            on_error=self._on_error,
        )

    def show_scanned_signal_detail(self, symbol: str) -> None:
        """
        باز کردن پنجرهٔ جزئیات یک ردیفِ نتیجهٔ پویش.

        کاربر گزارش داد کلیک روی نماد در جدول پویش کاری نمی‌کند. داده
        از `_last_scan` می‌آید که همان شیء سیگنال کامل است؛ اگر در دست
        نبود (مثلاً پس از تعویض صرافی) از ردیف جدول استفاده می‌شود تا
        پنجره دست‌کم خلاصه را نشان دهد و کاربر دست خالی نماند.
        """
        payload: dict[str, Any] = {}
        for candidate in getattr(getattr(self, "_last_scan", None), "signals", []) or []:
            if str(candidate.symbol).upper() == str(symbol).upper():
                payload = candidate.to_dict()
                break
        if not payload:
            payload = self.signals.scan_row(symbol)
        if not payload:
            return

        payload = self._decorate_validity([payload])[0]
        dialog = SignalDetailDialog(
            payload, self.tr_, self.window, theme=self.themes.tokens
        )
        self._prime_calculator(dialog)
        dialog.trade_requested.connect(self._on_trade_requested)
        # از همین پنجره هم باید بشود تحلیل هوشمند خواست؛ کاربر خواسته
        # بود بعد از پویش، هر نماد را جداگانه به هوش مصنوعی بسپارد.
        if hasattr(dialog, "ai_analysis_requested"):
            dialog.ai_analysis_requested.connect(
                lambda _=None, value=symbol: self.analyze_scanned_symbol(value)
            )
        dialog.exec()

    def _generate_ai_signal(
        self, symbol: str, timeframe: str, frames: list[str] | None = None
    ) -> None:
        """
        تولید سیگنال به‌وسیله عامل هوش مصنوعی.

        عامل خودش تصمیم می‌گیرد کدام تایم‌فریم‌ها و اندیکاتورها را
        بررسی کند؛ تایم‌فریم انتخابی کاربر تمرکز اصلی اوست.
        """
        frames = list(frames or [str(timeframe)])
        agent = self.app.autonomous_agent()
        if agent is None:
            # هوش مصنوعی در دسترس نیست: به‌جای شکست، موتور تحلیل کار کند
            self.status(self.tr_.tr("signals.ai_unavailable"))
            self.signals.use_ai_checkbox.setChecked(False)
            self.generate_signal()
            return

        self.signals.set_busy(True)
        self.signals.progress.show()
        self.signals.agent_trail.setText(self.tr_.tr("signals.ai_thinking"))
        self.signals.agent_trail.show()
        self.status(self.tr_.tr("signals.ai_generating"))

        # مسیر تصمیم عامل، زنده روی صفحه. چون از نخ شبکه می‌آید، فقط
        # متن جمع می‌شود و نمایشش با تایمر رابط کاربری انجام می‌گیرد.
        trail: list[str] = []

        def on_step(step: Any) -> None:
            """ثبت یک گام از کار عامل."""
            if step.tool:
                trail.append(("✓ " if step.ok else "✗ ") + step.tool)

        agent.set_progress_callback(on_step)

        def apply(outcome: Any) -> None:
            """نمایش تصمیم عامل و ذخیره آن."""
            self.signals.agent_trail.setText(" · ".join(trail[-8:]))

            # عامل شکست خورده است (مدل JSON نداد، مهلت تمام شد، یا سرویس
            # جواب نداد). در این حالت تصمیمِ عامل یک «صبر» توخالی با
            # اطمینان صفر است که هیچ اطلاعاتی به کاربر نمی‌دهد و دقیقاً
            # همان شکایتِ «با هوش مصنوعی همیشه صبر می‌دهد» را می‌سازد.
            # پس به‌جای نمایش آن، موتور ریاضی را اجرا می‌کنیم و دلیل
            # شکست هوش مصنوعی را هم صادقانه کنار نتیجه می‌گذاریم.
            if not self._agent_outcome_is_usable(outcome):
                self._fallback_to_engine_signal(symbol, timeframe, frames, outcome)
                return

            payload = self._agent_outcome_to_signal(outcome, symbol, timeframe)
            self.signals.show_signal(payload)
            self._save_agent_signal(outcome, symbol, timeframe)
            self._load_signal_history()

            if outcome.direction == "WAIT":
                self.status(self.tr_.tr("signals.wait_result", symbol=symbol))
            else:
                self.status(
                    self.tr_.tr(
                        "signals.result",
                        symbol=symbol,
                        direction=self.tr_.tr(f"signals.{outcome.direction.lower()}"),
                        confidence=outcome.confidence,
                    )
                )

        def finished() -> None:
            """پاک‌سازی وضعیت مشغول."""
            self.signals.set_busy(False)
            self.signals.progress.hide()

        async def analyse() -> Any:
            """
            اول موتور ریاضی، بعد عامل هوش مصنوعی.

            چرا ترتیب مهم است؟
                عامل پیش‌تر «کور» شروع می‌کرد: باید در چند گام محدود،
                کل تحلیل را از داده خام بازمی‌ساخت. مدل‌های کوچک‌تر در
                این وضعیت به امن‌ترین پاسخ ممکن پناه می‌برند، یعنی
                «انتظار با اطمینان صفر» — همان صفحه‌ای که کاربر گزارش
                کرد. حالا نتیجهٔ موتور به‌عنوان شاهدِ آماده به مدل داده
                می‌شود و کار مدل قضاوت دربارهٔ آن است، نه کشف دوباره‌اش.

            شکست موتور نباید جلوی هوش مصنوعی را بگیرد؛ در آن حالت عامل
            مثل قبل بدون شاهد اولیه کار می‌کند.
            """
            engine_signal = None
            try:
                engine_signal = await self.app.generate_signal(symbol, frames)
            except Exception as exc:  # noqa: BLE001 - شاهد اولیه اختیاری است
                logger.warning("Baseline engine signal failed for %s: %s", symbol, exc)
            outcome = await agent.run(symbol, timeframe=timeframe, baseline=engine_signal)
            # سیگنال موتور برای مسیر جایگزین نگه داشته می‌شود تا اگر
            # هوش مصنوعی نتیجهٔ قابل استفاده نداد، دوباره حساب نشود.
            setattr(outcome, "baseline_signal", engine_signal)
            return outcome

        self.runner.submit(
            "ai-signal",
            analyse(),
            on_success=apply,
            on_error=self._on_error,
            on_finished=finished,
        )

    # ------------------------------------------------------------------
    # چت با هوش مصنوعی
    # ------------------------------------------------------------------
    def _go_to(self, nav_key: str) -> None:
        """
        رفتن به یک صفحه با کلید ناوبری.

        `MainWindow.go_to_page` نمایه عددی می‌گیرد نه کلید؛ این پوشش کوچک
        باعث می‌شود جای صفحات در فهرست بدون شکستن اینجا قابل تغییر بماند.
        """
        for index, (key, _) in enumerate(self.window.PAGES):
            if key == nav_key:
                self.window.go_to_page(index)
                return
        logger.debug("Unknown nav key: %s", nav_key)

    def _streaming_chat_enabled(self) -> bool:
        """
        آیا پاسخ چت باید تکه‌تکه نمایش داده شود؟

        اگر سرویس فعال جریان ندهد، لایهٔ پایین خودش به حالت عادی
        برمی‌گردد؛ پس این فقط ترجیح کاربر است، نه ادعای توانایی.
        """
        return bool(self.app.settings.get_bool("ai.chat_streaming", True))

    def send_chat_message(self, message: str) -> None:
        """
        ارسال پیام کاربر به دستیار گفتگو.

        دستیار همان ابزارها و همان سرویس هوش مصنوعی تحلیل را به کار
        می‌گیرد، پس هر چه در تنظیمات عوض شود اینجا هم اثر می‌کند.
        """
        agent = self.app.chat_agent()
        if agent is None:
            self.chat.add_message(self.tr_.tr("chat.ai_disabled"), is_user=False)
            self.chat.set_status(self.tr_.tr("chat.no_provider"))
            return

        # پیام کاربر بی‌درنگ ذخیره می‌شود تا اگر پاسخ نرسید هم گم نشود
        self._store_chat_message("user", message)
        self.load_conversations()

        self.chat.begin_reply()

        # گام‌های ابزار روی حباب انتظار می‌نشینند. پس‌فراخوان روی نخ شبکه
        # اجرا می‌شود، پس فقط سیگنال می‌فرستیم؛ دست‌زدن مستقیم به ویجت از
        # آن نخ برنامه را می‌کشد.
        def on_tool(call: Any, *, running: bool = False) -> None:
            """اعلام شروع یا پایان اجرای یک ابزار به رابط کاربری."""
            arguments = dict(getattr(call, "arguments", {}) or {})
            if running:
                self.chat_tool_started.emit(str(call.name), arguments)
            else:
                self.chat_tool_finished.emit(
                    str(call.name),
                    bool(getattr(call, "ok", False)),
                    str(getattr(call, "observation", "") or ""),
                    arguments,
                )

        agent.set_progress_callback(on_tool)

        # پاسخ در حال تایپ. از نخ شبکه فقط سیگنال می‌فرستیم؛ نشستن متن
        # روی ویجت در نخ رابط کاربری انجام می‌شود.
        if self._streaming_chat_enabled():
            agent.set_stream_callback(
                lambda delta, replace=False: self.chat_stream_delta.emit(delta, replace)
            )
        else:
            agent.set_stream_callback(None)

        def apply(reply: Any) -> None:
            """نمایش پاسخ دستیار."""
            if reply.error and not reply.text:
                self.chat.fail_reply(self.tr_.tr("chat.failed", error=reply.error))
            else:
                tool_names = [call.summary() for call in reply.tool_calls]
                self.chat.finish_reply(reply.text, tool_names)
                self._store_chat_message(
                    "assistant",
                    reply.text,
                    tools=tool_names,
                    provider=str(reply.provider or ""),
                    model=str(reply.model or ""),
                )
                self.load_conversations()

            if reply.action:
                self.chat.show_action(reply.action.to_dict())
            if reply.provider:
                self.chat.set_status(
                    self.tr_.tr("chat.status_active", provider=reply.provider, model=reply.model)
                )

        self.runner.submit(
            "chat",
            agent.send(message, context=self.chat.current_context()),
            on_success=apply,
            on_error=lambda text, exc=None: self.chat.fail_reply(
                self.tr_.tr("chat.failed", error=text)
            ),
            on_finished=lambda: self.chat.set_busy(False),
            # پیام کاربر هرگز نباید با پیام بعدی لغو شود؛ هم‌ادغامی برای
            # تازه‌سازی‌های تکراری است، نه برای گفتگو.
            coalesce=False,
        )

    def _on_chat_action(self, action: dict[str, Any]) -> None:
        """
        اجرای اقدامی که دستیار پیشنهاد داده و کاربر تأیید کرده است.

        هیچ اقدامی خودکار اجرا نمی‌شود؛ این متد فقط پس از کلیک کاربر صدا
        زده می‌شود. نتیجه، رفتن به همان صفحه‌ای است که کار را انجام می‌دهد
        تا کاربر ببیند چه اتفاقی افتاد.
        """
        action_type = str(action.get("type") or "")
        symbol = str(action.get("symbol") or "").strip()
        timeframe = str(action.get("timeframe") or "4h").strip()

        if action_type == "generate_signal" and symbol:
            self.signals.symbol_combo.setCurrentText(symbol)
            index = self.signals.timeframe_combo.findData(timeframe)
            if index >= 0:
                self.signals.timeframe_combo.setCurrentIndex(index)
            self._go_to("nav.signals")
            self.generate_signal()
        elif action_type == "run_analysis" and symbol:
            self.analysis.symbol_combo.setCurrentText(symbol)
            index = self.analysis.timeframe_combo.findData(timeframe)
            if index >= 0:
                self.analysis.timeframe_combo.setCurrentIndex(index)
            self._go_to("nav.analysis")
            self.run_analysis()
        elif action_type == "open_paper_trade":
            if self._last_signal is None:
                self.status(self.tr_.tr("signals.no_signals"))
                return
            self._go_to("nav.signals")
            self._on_trade_requested(self._last_signal.to_dict())
        elif action_type == "show_markets":
            self._go_to("nav.markets")
        else:
            logger.info("Unknown chat action ignored: %s", action_type)
            return

        self.status(self.tr_.tr("chat.action_done"))

    def _on_chat_tool_started(self, name: str, arguments: dict) -> None:
        """نمایش ابزاری که تازه شروع به کار کرده (نخ رابط کاربری)."""
        self.chat.tool_started(name, dict(arguments or {}))

    def _on_chat_tool_finished(
        self, name: str, ok: bool, observation: str, arguments: dict
    ) -> None:
        """ثبت نتیجهٔ یک ابزار روی حباب انتظار (نخ رابط کاربری)."""
        self.chat.tool_finished(
            name, ok=bool(ok), observation=observation, arguments=dict(arguments or {})
        )

    def _on_chat_cleared(self) -> None:
        """شروع گفت‌وگوی تازه: حافظهٔ دستیار هم باید پاک شود."""
        agent = self.app.chat_agent()
        if agent is not None:
            agent.reset()
        # گفت‌وگوی بعدی رکورد تازه‌ای در پایگاه داده می‌گیرد؛ گفت‌وگوی
        # قبلی حذف نمی‌شود و در تاریخچه می‌ماند.
        self._conversation_id = 0
        logger.info("Chat conversation reset")

    # ------------------------------------------------------------------
    # تاریخچهٔ گفت‌وگو (مانند ChatGPT)
    # ------------------------------------------------------------------
    def load_conversations(self) -> None:
        """پر کردن ستون تاریخچه از پایگاه داده."""
        if self.app.chat_repository is None:
            return
        limit = self.app.settings.get_int("ai.chat_history_limit", 100) or 100
        try:
            conversations = self.app.chat_repository.list_conversations(limit)
        except Exception as exc:  # noqa: BLE001 - خطای تاریخچه نباید چت را بخواباند
            logger.warning("Could not load conversations: %s", exc)
            return
        self.chat.set_conversations(conversations)
        if self._conversation_id:
            self.chat.select_conversation(self._conversation_id)

    def start_new_conversation(self) -> None:
        """شروع گفت‌وگوی تازه؛ گفت‌وگوی قبلی در پایگاه داده می‌ماند."""
        self._conversation_id = 0
        agent = self.app.chat_agent()
        if agent is not None:
            agent.reset()
        self.chat.clear_conversation()
        self.load_conversations()

    def open_conversation(self, conversation_id: int) -> None:
        """باز کردن یک گفت‌وگوی ذخیره‌شده و نمایش پیام‌هایش."""
        if self.app.chat_repository is None:
            return
        data = self.app.chat_repository.get_conversation(int(conversation_id))
        if not data:
            return
        self._conversation_id = int(conversation_id)
        agent = self.app.chat_agent()
        if agent is not None:
            # حافظهٔ دستیار پاک می‌شود تا پاسخ‌های تازه بر پایهٔ همین
            # گفت‌وگو ساخته شوند و با گفت‌وگوی قبلی قاطی نشود.
            agent.reset()
        self.chat.load_messages(data.get("messages", []))
        self.chat.set_context(data.get("symbol", ""), data.get("timeframe", ""))
        self.chat.select_conversation(self._conversation_id)

    def delete_conversation(self, conversation_id: int) -> None:
        """حذف یک گفت‌وگو پس از گرفتن تأیید کاربر."""
        if self.app.chat_repository is None:
            return
        if self.app.settings.get_bool("ui.confirm_actions", True):
            answer = QMessageBox.question(
                self.window,
                self.tr_.tr("chat.delete"),
                self.tr_.tr("chat.delete_confirm"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.app.chat_repository.delete_conversation(int(conversation_id))
        if self._conversation_id == int(conversation_id):
            self._conversation_id = 0
            self.chat.clear_conversation()
        self.load_conversations()
        self.status(self.tr_.tr("chat.deleted"))
        self._toast(self.tr_.tr("chat.deleted"), level="success")

    def rename_conversation(self, conversation_id: int, title: str) -> None:
        """تغییر نام گفت‌وگو."""
        if self.app.chat_repository is None:
            return
        self.app.chat_repository.rename_conversation(int(conversation_id), title)
        self.load_conversations()

    def _ensure_conversation(self) -> int:
        """
        اطمینان از وجود یک گفت‌وگوی فعال.

        اگر کاربر بدون انتخاب گفت‌وگو پیام بفرستد، گفت‌وگوی تازه ساخته
        می‌شود. عنوان آن از نخستین پیام ساخته خواهد شد.
        """
        if self._conversation_id:
            return self._conversation_id
        if self.app.chat_repository is None:
            return 0
        context = self.chat.current_context()
        self._conversation_id = self.app.chat_repository.create_conversation(
            symbol=context.get("symbol", ""),
            timeframe=context.get("timeframe", ""),
        )
        return self._conversation_id

    def _store_chat_message(
        self,
        role: str,
        content: str,
        *,
        tools: list[str] | None = None,
        provider: str = "",
        model: str = "",
    ) -> None:
        """ذخیرهٔ یک پیام در پایگاه داده، اگر کاربر ذخیره‌سازی را خاموش نکرده باشد."""
        if not self.app.settings.get_bool("ai.save_chat_history", True):
            return
        if self.app.chat_repository is None:
            return
        conversation_id = self._ensure_conversation()
        if not conversation_id:
            return
        try:
            self.app.chat_repository.add_message(
                conversation_id,
                role=role,
                content=content,
                tools=tools or [],
                provider=provider,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not store chat message: %s", exc)

    # ------------------------------------------------------------------
    # مدال جزئیات ارز
    # ------------------------------------------------------------------
    def show_coin_details(self, symbol: str) -> None:
        """
        باز کردن مدال جزئیات یک ارز.

        پنجره بی‌درنگ با دادهٔ موجود در جدول باز می‌شود و جزئیات فنی در
        پس‌زمینه دریافت و اضافه می‌گردد؛ کاربر پشت پنجرهٔ خالی منتظر
        نمی‌ماند.
        """
        symbol = str(symbol or "").strip()
        if not symbol:
            return

        snapshot = self.markets.row_data(symbol) or self.dashboard.market_row_data(symbol)
        watchlist = self._watchlist_symbols()
        dialog = CoinDetailDialog(
            symbol,
            snapshot,
            self.tr_,
            self.window,
            in_watchlist=symbol in watchlist,
        )
        # اقدام‌ها باید اول مدال را ببندند. بدون این، کاربر روی «تحلیل»
        # می‌زند، برنامه پشت سرِ پنجرهٔ باز به صفحهٔ دیگری می‌رود و کار
        # سنگین را شروع می‌کند؛ مدال جلوی همه‌چیز می‌ماند و به نظر
        # «بسته نمی‌شود» می‌آید.
        def _act(handler, *args):
            """بستن مدال، سپس اجرای اقدام."""
            dialog.accept()
            handler(*args)

        dialog.analyze_requested.connect(lambda sym, tf: _act(self._coin_analyze, sym, tf))
        dialog.signal_requested.connect(lambda sym, tf: _act(self._coin_signal, sym, tf))
        dialog.chat_requested.connect(lambda sym, tf: _act(self._coin_chat, sym, tf))
        dialog.open_market_requested.connect(lambda sym: _act(self._coin_open_market, sym))
        dialog.watchlist_toggled.connect(self._coin_watchlist_toggled)

        self._load_coin_details(dialog, symbol)
        try:
            dialog.exec()
        finally:
            # کار پس‌زمینه‌ای که هنوز در راه است نباید به پنجرهٔ بسته دست بزند
            self.runner.cancel(f"coin-details-{symbol}")

    def _load_coin_details(self, dialog: Any, symbol: str) -> None:
        """دریافت اندیکاتورها و سطوح کلیدی برای مدال جزئیات."""
        if self.app.market is None:
            return
        timeframe = dialog.selected_timeframe()
        dialog.set_busy(True)

        async def collect() -> dict[str, Any]:
            """گردآوری موازی قیمت، کندل‌ها و اندیکاتورها."""
            ticker_task = self.app.market.get_ticker(symbol)
            candles_task = self.app.market.get_candles(symbol, timeframe, 200)
            ticker, candles = await asyncio.gather(
                ticker_task, candles_task, return_exceptions=True
            )
            payload: dict[str, Any] = {}
            if not isinstance(ticker, BaseException):
                payload["snapshot"] = {
                    "price": ticker.last_price,
                    "change_percent": ticker.change_percent,
                    "high": ticker.high_24h,
                    "low": ticker.low_24h,
                    "volume": ticker.volume_24h,
                }
            if not isinstance(candles, BaseException) and candles:
                payload["details"] = self._summarise_candles(candles)
            return payload

        def apply(payload: dict[str, Any]) -> None:
            """نمایش نتیجه در همان پنجره."""
            # اگر کاربر پنجره را بسته باشد، شیء ++C نابود شده و هر تماسی
            # با آن برنامه را با
            # «Internal C++ object already deleted» می‌بندد.
            if not _dialog_alive(dialog):
                return
            if payload.get("snapshot"):
                dialog.apply_snapshot(payload["snapshot"])
            if payload.get("details"):
                dialog.apply_details(payload["details"])
            else:
                dialog.set_details_error(self.tr_.tr("markets.details_failed"))
            dialog.set_busy(False)

        def _safe_details_error(target: Any) -> None:
            """نمایش خطا فقط وقتی پنجره هنوز باز است."""
            if not _dialog_alive(target):
                return
            target.set_details_error(self.tr_.tr("markets.details_failed"))
            target.set_busy(False)

        self.runner.submit(
            f"coin-details-{symbol}",
            collect(),
            on_success=apply,
            on_error=lambda text, exc=None: _safe_details_error(dialog),
        )

    def _summarise_candles(self, candles: list[Any]) -> dict[str, Any]:
        """محاسبهٔ خلاصهٔ فنی از روی کندل‌ها برای مدال جزئیات."""
        details: dict[str, Any] = {}
        try:
            structure = analyze_market_structure(candles)
            details["trend"] = str(getattr(structure, "trend", "") or "—")
            details["structure"] = str(getattr(structure, "structure", "") or "—")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Structure analysis failed: %s", exc)
        try:
            levels = find_support_resistance(candles)
            supports = getattr(levels, "supports", None) or []
            resistances = getattr(levels, "resistances", None) or []
            if supports:
                details["support"] = self.tr_.format_number(supports[0], 4)
            if resistances:
                details["resistance"] = self.tr_.format_number(resistances[0], 4)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Support/resistance failed: %s", exc)
        try:
            values = self.app.indicators.calculate_all(candles)
            for name in ("rsi", "macd", "ema", "atr"):
                raw = values.get(name)
                if isinstance(raw, dict):
                    raw = raw.get("value")
                if isinstance(raw, (int, float)):
                    details[name] = self.tr_.format_number(raw, 2)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Indicator summary failed: %s", exc)
        return details

    def _coin_analyze(self, symbol: str, timeframe: str) -> None:
        """از مدال: رفتن به صفحهٔ تحلیل و اجرای تحلیل همان ارز."""
        self.analysis.symbol_combo.setCurrentText(symbol)
        index = self.analysis.timeframe_combo.findData(timeframe)
        if index >= 0:
            self.analysis.timeframe_combo.setCurrentIndex(index)
        self._go_to("nav.analysis")
        self.run_analysis()

    def _coin_signal(self, symbol: str, timeframe: str) -> None:
        """از مدال: تولید سیگنال برای همان ارز."""
        self.signals.symbol_combo.setCurrentText(symbol)
        index = self.signals.timeframe_combo.findData(timeframe)
        if index >= 0:
            self.signals.timeframe_combo.setCurrentIndex(index)
        self._go_to("nav.signals")
        self.generate_signal()

    def _coin_chat(self, symbol: str, timeframe: str) -> None:
        """از مدال: گفت‌وگو دربارهٔ همان ارز."""
        self.chat.set_context(symbol, timeframe)
        self._go_to("nav.chat")

    def _coin_open_market(self, symbol: str) -> None:
        """از مدال: نمایش همان ارز در صفحهٔ بازارها."""
        self._go_to("nav.markets")
        self.markets.search_input.setText(symbol)

    def _coin_watchlist_toggled(self, symbol: str, added: bool) -> None:
        """افزودن یا برداشتن نماد از واچ‌لیست از داخل مدال."""
        try:
            if added:
                self.app.symbol_repository.add_to_watchlist(symbol)
                self.status(self.tr_.tr("markets.added_to_watchlist", symbol=symbol))
                self._toast(
                    self.tr_.tr("markets.added_to_watchlist", symbol=symbol),
                    level="success",
                )
            else:
                self.app.symbol_repository.remove_from_watchlist(symbol)
                self.status(self.tr_.tr("markets.remove_from_watchlist"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Watchlist update failed: %s", exc)
            return
        self.refresh_dashboard()

    # ------------------------------------------------------------------
    # تحلیل نوشتاری سیگنال و خروجی PDF
    # ------------------------------------------------------------------
    def show_signal_analysis(self, signal_id: int) -> None:
        """
        باز کردن مدال تحلیل نوشتاری یک سیگنال.

        اگر تحلیلی ذخیره نشده باشد پنجره خالی باز می‌شود ولی کاربر
        می‌تواند همان‌جا «تحلیل دوباره» بگیرد.
        """
        payload = self.signals.history_row(int(signal_id))
        if not payload.get("analysis_text"):
            # `get_with_analysis` تاپل می‌دهد نه دیکشنری؛ باز کردنش با
            # `**` خطا می‌داد و تحلیل ذخیره‌شده هرگز نمایش داده نمی‌شد.
            stored = self.app.signal_repository.analysis_payload(int(signal_id))
            if stored:
                payload = {**payload, **{k: v for k, v in stored.items() if v}}
        payload.setdefault("id", int(signal_id))

        dialog = AnalysisDialog(payload, self.tr_, self.window)
        dialog.pdf_requested.connect(lambda data: self._export_analysis_pdf(data, dialog))
        dialog.rerun_requested.connect(
            lambda data, dlg=dialog: self._rerun_signal_analysis(data, dlg)
        )
        dialog.exec()

    def _rerun_signal_analysis(self, payload: dict[str, Any], dialog: Any) -> None:
        """
        اجرای دوبارهٔ تحلیل هوش مصنوعی روی یک سیگنال موجود.

        کاربر گفت روی سیگنال ساخته‌شده نمی‌تواند دوباره تحلیل بگیرد.
        نتیجه هم روی همان پنجره می‌نشیند و هم در پایگاه داده ذخیره
        می‌شود تا دفعهٔ بعد بدون هزینهٔ دوباره دیده شود.
        """
        symbol = str(payload.get("symbol") or "")
        if not symbol:
            dialog.set_busy(False)
            dialog.set_status(self.tr_.tr("signals.rerun_failed", reason="—"))
            return

        agent = self.app.autonomous_agent()
        if agent is None:
            dialog.set_busy(False)
            dialog.set_status(
                self.tr_.tr("signals.rerun_failed", reason=self.tr_.tr("errors.ai_unavailable"))
            )
            return

        # تایم‌فریم خودِ سیگنال مبناست؛ اگر ذخیره نشده بود، انتخاب
        # فعلی کاربر در صفحهٔ سیگنال‌ها.
        frames = self.signals.selected_timeframes()
        timeframe = str(payload.get("timeframe") or "") or (frames[0] if frames else "1h")
        signal_id = int(payload.get("id") or 0)

        def done(outcome: Any) -> None:
            text = str(getattr(outcome, "analysis_text", "") or "")
            if not text:
                reason = "; ".join(getattr(outcome, "errors", []) or []) or "—"
                dialog.set_busy(False)
                dialog.set_status(self.tr_.tr("signals.rerun_failed", reason=reason))
                return
            saved = False
            if signal_id:
                try:
                    saved = self.app.signal_repository.update_analysis(signal_id, text)
                except Exception:  # noqa: BLE001
                    saved = False
            dialog.set_analysis_text(
                text,
                status=self.tr_.tr("signals.rerun_saved") if saved
                else self.tr_.tr("signals.rerun_done"),
            )
            if saved:
                self._load_signal_history()

        def failed(name: str, error: Exception) -> None:
            dialog.set_busy(False)
            dialog.set_status(self.tr_.tr("signals.rerun_failed", reason=str(error)))
            self._on_error(name, error)

        self.runner.submit(
            f"rerun-analysis-{signal_id}",
            agent.run(symbol, timeframe=timeframe),
            on_success=done,
            on_error=failed,
        )

    def _export_analysis_pdf(self, payload: dict[str, Any], dialog: Any = None) -> None:
        """
        ساخت خروجی PDF فارسی از تحلیل.

        قلم فارسی همراه برنامه است، پس متن درست و متصل چاپ می‌شود؛
        reportlab به‌تنهایی حروف فارسی را جدا و وارونه می‌نویسد.
        """
        symbol = str(payload.get("symbol", "signal")).replace("/", "-")
        default_name = f"analysis-{symbol}.pdf"
        export_dir = str(self.app.settings.get("reports.export_path", "") or "")
        start_path = str(Path(export_dir) / default_name) if export_dir else default_name

        path, _ = QFileDialog.getSaveFileName(
            self.window,
            self.tr_.tr("signals.export_pdf"),
            start_path,
            "PDF (*.pdf)",
        )
        if not path:
            return

        try:
            from reports.persian_pdf import build_analysis_pdf

            direction = str(payload.get("direction", "WAIT")).upper()
            facts: list[tuple[str, str]] = [
                (self.tr_.tr("signals.direction"), self.tr_.tr(f"signals.{direction.lower()}", direction)),
                (self.tr_.tr("signals.confidence"), f"{payload.get('confidence', 0)}%"),
            ]
            if payload.get("entry_min") and payload.get("entry_max"):
                facts.append((
                    self.tr_.tr("signals.entry_zone"),
                    f"{payload['entry_min']} — {payload['entry_max']}",
                ))
            if payload.get("stop_loss"):
                facts.append((self.tr_.tr("signals.stop_loss"), str(payload["stop_loss"])))
            if payload.get("risk_reward"):
                facts.append((self.tr_.tr("signals.risk_reward"), f"{payload['risk_reward']}"))

            sections = self._split_analysis_sections(str(payload.get("analysis_text", "")))
            build_analysis_pdf(
                path,
                title=self.tr_.tr("signals.analysis_title", symbol=str(payload.get("symbol", ""))),
                subtitle=str(payload.get("created_at", "")),
                facts=facts,
                sections=sections,
                footer="Crypto AI Trader — حسین حاج طالبی",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF export failed: %s", exc)
            message = self.tr_.tr("signals.pdf_failed")
            # ساخت PDF کند است؛ کاربر ممکن است در همین فاصله پنجره را
            # بسته باشد. `is not None` کافی نیست چون ارجاع پایتونی
            # می‌ماند ولی شیء ++C نابود شده است.
            if _dialog_alive(dialog):
                dialog.set_status(message)
            self.status(message)
            return

        message = self.tr_.tr("signals.pdf_saved", path=path)
        if _dialog_alive(dialog):
            dialog.set_status(message)
        self.status(message)

    @staticmethod
    def _split_analysis_sections(text: str) -> list[tuple[str, str]]:
        """
        تبدیل متن نشانه‌گذاری‌شده به فهرست (عنوان، متن) برای PDF.

        اگر متن عنوانی نداشته باشد، همه‌اش یک بخش بدون عنوان می‌شود.
        """
        raw = str(text or "").strip()
        if not raw:
            return []
        sections: list[tuple[str, str]] = []
        heading = ""
        body: list[str] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                if heading or body:
                    sections.append((heading, "\n".join(body).strip()))
                heading = stripped.lstrip("#").strip()
                body = []
            else:
                body.append(line)
        if heading or body:
            sections.append((heading, "\n".join(body).strip()))
        return [(h, b) for h, b in sections if b or h]

    @staticmethod
    def _agent_outcome_is_usable(outcome: Any) -> bool:
        """
        آیا تصمیم عامل واقعاً یک تحلیل است یا فقط اعلام شکست؟

        عامل خودمختار در دو حالت «صبر با اطمینان صفر» تولید می‌کند:
        وقتی مدل نتوانست JSON معتبر بدهد یا مهلتش تمام شد، و وقتی
        اعتبارسنج پیشنهادش را رد کرد. در هر دو حالت `succeeded` نادرست
        است و هیچ عددی (ورود، حد ضرر، هدف) وجود ندارد.

        چنین خروجی‌ای از دید کاربر با «تحلیل کردم و نتیجه گرفتم صبر کن»
        فرقی ندارد، و همین باعث شکایت «با تیک هوش مصنوعی همیشه صبر
        می‌دهد» شد. پس شکستِ عامل را شکست می‌شماریم، نه سیگنال.

        توجه: «صبر»ِ واقعیِ عامل (با اطمینان و دلیل) کاملاً معتبر است و
        باید نمایش داده شود؛ اینجا فقط خروجیِ توخالی رد می‌شود.
        """
        if outcome is None:
            return False
        confidence = int(getattr(outcome, "confidence", 0) or 0)
        direction = str(getattr(outcome, "direction", "WAIT")).upper()

        # «انتظار با اطمینان صفر» حتی وقتی عامل موفق بوده، یک تحلیل نیست.
        # مدل‌های کوچک‌تر این را به‌عنوان راه فرار برمی‌گردانند و کاربر
        # صفحه‌ای پر از «انتظار ۰٪» می‌بیند — همان چیزی که گزارش شد.
        # «انتظار» با اطمینان واقعی همچنان یک پاسخ معتبر است.
        if direction == "WAIT" and confidence <= 0:
            return False

        if getattr(outcome, "succeeded", False):
            return True
        # عامل موفق نبوده؛ اگر هیچ تصمیم عددی هم نساخته، چیزی برای
        # نشان‌دادن نیست.
        decision = dict(getattr(outcome, "decision", None) or {})
        has_numbers = any(
            decision.get(key) is not None
            for key in ("entry_min", "entry_max", "stop_loss")
        )
        return bool(has_numbers) and confidence > 0

    def _fallback_to_engine_signal(
        self, symbol: str, timeframe: str, frames: list[str], outcome: Any
    ) -> None:
        """
        اجرای موتور ریاضی وقتی عامل هوش مصنوعی شکست خورده است.

        کاربر تیک هوش مصنوعی را زده، پس انتظار **یک سیگنال** دارد، نه یک
        «صبر» توخالی. موتور سیگنال مستقل از هوش مصنوعی کار می‌کند و
        همیشه نتیجه‌ای دارد؛ همان را نشان می‌دهیم و شفاف می‌گوییم که
        هوش مصنوعی چرا کنار گذاشته شد.
        """
        reason = ""
        errors = list(getattr(outcome, "errors", None) or [])
        if errors:
            reason = str(errors[0])
        logger.warning("AI agent produced no usable signal for %s: %s", symbol, reason)

        self.signals.agent_trail.setText(
            self.tr_.tr("signals.ai_fell_back", reason=reason or "—")
        )
        self.signals.agent_trail.show()
        self.status(self.tr_.tr("signals.ai_fell_back", reason=reason or "—"))

        def apply(signal: TradingSignal) -> None:
            """نمایش سیگنال موتور به‌جای خروجی شکست‌خوردهٔ عامل."""
            self._last_signal = signal
            payload = signal.to_dict()
            # کاربر باید بداند این نتیجه از موتور آمده نه از هوش مصنوعی.
            note = self.tr_.tr("signals.ai_fell_back", reason=reason or "—")
            existing = str(payload.get("reason") or "").strip()
            payload["reason"] = f"{note}\n{existing}".strip()
            self.signals.show_signal(payload)
            self._load_signal_history()

            if signal.direction is SignalDirection.WAIT:
                self.status(self.tr_.tr("signals.wait_result", symbol=symbol))
            else:
                self.status(
                    self.tr_.tr(
                        "signals.result",
                        symbol=symbol,
                        direction=self.tr_.tr(f"signals.{signal.direction.value.lower()}"),
                        confidence=signal.confidence,
                    )
                )

        # سیگنال موتور معمولاً همین حالا به‌عنوان شاهد اولیه حساب شده؛
        # دوباره گرفتنش فقط کاربر را معطل می‌کند.
        ready = getattr(outcome, "baseline_signal", None)
        if ready is not None:
            apply(ready)
            self.signals.set_busy(False)
            self.signals.progress.hide()
            return

        self.runner.submit(
            "signal-fallback",
            self.app.generate_signal(symbol, frames),
            on_success=apply,
            on_error=self._on_error,
            on_finished=lambda: (
                self.signals.set_busy(False),
                self.signals.progress.hide(),
            ),
        )

    def _agent_outcome_to_signal(self, outcome: Any, symbol: str, timeframe: str) -> dict[str, Any]:
        """تبدیل خروجی عامل به قالبی که کارت سیگنال می‌فهمد."""
        decision = dict(outcome.decision or {})
        return {
            "symbol": symbol,
            "direction": outcome.direction,
            "confidence": outcome.confidence,
            "entry_min": decision.get("entry_min"),
            "entry_max": decision.get("entry_max"),
            "stop_loss": decision.get("stop_loss"),
            "take_profits": decision.get("take_profits") or [],
            "leverage": decision.get("leverage"),
            "risk_reward": decision.get("risk_reward"),
            "trend": decision.get("trend", ""),
            "market_structure": decision.get("market_structure", ""),
            "primary_timeframe": timeframe,
            "reason": decision.get("reason", ""),
            "invalidation": decision.get("invalidation", ""),
            **self._analysis_payload(outcome.narrative),
            "ai_provider": outcome.provider,
            "ai_model": outcome.model,
            "created_at": format_datetime(now_local()),
        }

    def _save_agent_signal(self, outcome: Any, symbol: str, timeframe: str) -> None:
        """
        ذخیره تصمیم عامل در پایگاه داده.

        شکست ذخیره‌سازی نباید مانع دیدن سیگنال شود، پس خطا فقط ثبت
        می‌شود و به کاربر پرتاب نمی‌گردد.
        """
        try:
            from app.core.models import TradingSignal

            decision = dict(outcome.decision or {})
            signal = TradingSignal(
                symbol=symbol,
                exchange=self.app.settings.active_exchange,
                direction=SignalDirection(outcome.direction),
                confidence=outcome.confidence,
                entry_min=decision.get("entry_min"),
                entry_max=decision.get("entry_max"),
                stop_loss=decision.get("stop_loss"),
                take_profits=list(decision.get("take_profits") or []),
                leverage=int(decision.get("leverage") or 1),
                risk_reward=decision.get("risk_reward"),
                timeframes=[timeframe],
                reason=str(decision.get("reason", ""))[:1000],
                invalidation=str(decision.get("invalidation", ""))[:500],
                ai_provider=outcome.provider,
                ai_model=outcome.model,
            )
            self.app.signal_repository.save_signal(signal, source="ai_agent")
        except Exception as exc:  # noqa: BLE001 - ذخیره نشدن نباید نمایش را خراب کند
            logger.warning("Could not save agent signal: %s", exc)

    def _decorate_validity(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        افزودن وضعیت اعتبار زنده به ردیف‌های سیگنال.

        چرا اینجا و نه در موتور سیگنال؟
            موتور، پنجرهٔ اعتبار را **هنگام ساخت** مهر می‌زند و آن
            تاریخ‌ها ثابت‌اند. ولی «سوخته بودن» یک وضعیت زنده است: به
            زمان حال و قیمت لحظه‌ای بستگی دارد و هر بار که کاربر جدول
            را می‌بیند باید دوباره حساب شود. سیگنالی که ده دقیقه پیش
            تازه بود، حالا ممکن است سوخته باشد.

        قیمت لحظه‌ای از کش بازار می‌آید، نه از درخواست تازه: این متد در
        مسیر نمایش اجرا می‌شود و نباید کند باشد. نبود قیمت هم مشکلی
        نیست — آن‌وقت فقط زمان سنجیده می‌شود.
        """
        from signals.validity import evaluate

        decorated: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            created = item.get("created_at_raw") or item.get("created_at")
            if not isinstance(created, datetime):
                # ردیف تازه‌ساخته‌شده هنوز در پایگاه داده نیست و زمان
                # خامش را ندارد؛ همین حالا ساخته شده است.
                created = datetime.now(UTC)

            # قیمت از جدول بازارها که همیشه در حافظه است — این متد در
            # مسیر نمایش اجرا می‌شود و نباید هیچ درخواست شبکه‌ای بزند.
            price = self._last_price(str(item.get("symbol") or ""))

            timeframes = item.get("timeframes") or (
                [item["primary_timeframe"]] if item.get("primary_timeframe") else []
            )
            window = evaluate(
                created_at=created,
                timeframes=list(timeframes),
                direction=str(item.get("direction") or ""),
                entry_min=item.get("entry_min"),
                entry_max=item.get("entry_max"),
                stop_loss=item.get("stop_loss"),
                take_profits=item.get("take_profits") or [],
                current_price=price or None,
            )
            item["freshness"] = window.freshness.value
            item["validity_reason"] = window.reason_key
            item["validity_args"] = dict(window.reason_args)
            item["effective_risk_reward"] = window.effective_risk_reward
            item["minutes_to_expiry"] = round(window.minutes_to_expiry, 1)
            decorated.append(item)
        return decorated

    def _apply_stale_filter(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        کنار گذاشتن سیگنال‌های سوخته وقتی کاربر خواسته است.

        تنظیم `signals.hide_stale` تا امروز ذخیره می‌شد ولی هیچ‌جا خوانده
        نمی‌شد — یعنی تیکی که هیچ کاری نمی‌کرد. بدترین نوع تنظیم همین
        است: کاربر فکر می‌کند چیزی را عوض کرده و نکرده.

        «سوخته» شامل منقضی، کهنه و باطل‌شده است؛ همان مجموعه‌ای که
        `signals.validity` برای «دیگر نباید وارد شد» تعریف کرده، تا دو
        تعریف موازی از یک مفهوم نداشته باشیم.
        """
        if not self.app.settings.get_bool(SettingKey.SIGNAL_HIDE_STALE, False):
            return rows
        from signals.validity import NOT_ENTERABLE

        blocked = {state.value for state in NOT_ENTERABLE}
        return [row for row in rows if str(row.get("freshness") or "") not in blocked]

    def _load_signal_history(self) -> None:
        """خواندن سابقه سیگنال‌ها از پایگاه داده."""
        records = self.app.signal_repository.get_latest(limit=100)
        rows = [
            {
                "id": record.id,
                "created_at": format_datetime(record.created_at) if record.created_at else "",
                "symbol": record.symbol,
                "direction": record.direction,
                "confidence": record.confidence,
                "risk_reward": record.risk_reward,
                "leverage": record.leverage,
                "created_at_raw": record.created_at,
                "primary_timeframe": getattr(record, "primary_timeframe", "") or "",
                "timeframes": list(getattr(record, "timeframes", None) or []),
                "entry_min": record.entry_min,
                "entry_max": record.entry_max,
                "stop_loss": record.stop_loss,
                "take_profits": list(record.take_profits or []),
                # پیش‌بینی ذخیره‌شده تا در پنجرهٔ جزئیات هم دیده شود.
                "forecast": list(getattr(record, "forecast", None) or []),
            }
            for record in records
        ]
        rows = self._apply_stale_filter(self._decorate_validity(rows))
        self._last_signal_rows = rows
        self.signals.set_history(rows)
        self.dashboard.set_signal_rows(rows[:10])
        statistics = self.app.signal_repository.get_statistics()
        self.dashboard.set_status_value("signals_today", str(statistics.get("total", 0)))

    # ------------------------------------------------------------------
    # جزئیات سیگنال و اقدام
    # ------------------------------------------------------------------
    def _on_signal_cell_clicked(self, row: int, _column: int) -> None:
        """کلیک روی ردیف سیگنال در داشبورد."""
        self._open_signal_detail(row)

    def _on_history_double_clicked(self, row: int, _column: int) -> None:
        """
        دوبار کلیک روی سابقه سیگنال‌ها.

        ۲.۴.۲: جدول سابقه ممکن است مرتب/گروه‌بندی شده باشد؛ ردیف جدول با
        شناسه به ردیف متناظر `_last_signal_rows` نگاشته می‌شود تا جزئیات
        همان سیگنالی باز شود که کاربر رویش کلیک کرده.
        """
        target = row
        getter = getattr(self.signals, "history_row_at", None)
        shown = getter(row) if callable(getter) else {}
        record_id = shown.get("id") if shown else None
        if record_id is not None:
            for index, candidate in enumerate(self._last_signal_rows):
                if candidate.get("id") == record_id:
                    target = index
                    break
        self._open_signal_detail(target)

    def _open_signal_detail(self, row: int) -> None:
        """
        باز کردن پنجرهٔ جزئیات یک سیگنال.

        داده کامل از پایگاه داده خوانده می‌شود، چون جدول فقط خلاصه را
        نگه می‌دارد و کاربر جزئیات کامل خواسته است.
        """
        if not 0 <= row < len(self._last_signal_rows):
            return
        summary = self._last_signal_rows[row]

        payload = dict(summary)
        record_id = summary.get("id")
        if record_id is not None:
            detail = self._load_signal_detail(record_id)
            if detail:
                payload.update(detail)

        # اعتبار باید همین حالا حساب شود، نه از روی مقدار ذخیره‌شدهٔ
        # جدول: کاربر ممکن است ساعتی بعد روی همان ردیف کلیک کند.
        payload = self._decorate_validity([payload])[0]

        dialog = SignalDetailDialog(
            payload, self.tr_, self.window, theme=self.themes.tokens
        )
        self._prime_calculator(dialog)
        dialog.trade_requested.connect(self._on_trade_requested)
        dialog.exec()

    def _prime_calculator(self, dialog: Any) -> None:
        """
        دادن سرمایه و درصد ریسک واقعی کاربر به ماشین‌حساب پنجرهٔ سیگنال.

        ماشین‌حساب پیش‌فرض ۱۰۰۰ دارد که فقط یک عدد نمونه است؛ با تنظیمات
        واقعی کاربر، حجم پیشنهادی هم واقعی می‌شود.
        """
        setter = getattr(dialog, "set_account_balance", None)
        if not callable(setter):
            return
        try:
            balance = float(self.app.settings.get("risk.account_balance", 0) or 0)
            risk = float(self.app.settings.get("risk.risk_percent", 0) or 0)
        except (TypeError, ValueError):
            return
        setter(balance, risk)

    def _load_signal_detail(self, record_id: Any) -> dict[str, Any]:
        """خواندن جزئیات کامل یک سیگنال از پایگاه داده."""
        try:
            found = self.app.signal_repository.get_with_analysis(int(record_id))
        except Exception:  # noqa: BLE001 - نبود جزئیات نباید پنجره را نبندد
            logger.debug("Could not load signal detail %s", record_id, exc_info=True)
            return {}
        if not found:
            return {}
        record, analysis = found

        # اهداف سود در یک ستون JSON ذخیره می‌شوند
        take_profits = record.take_profits if isinstance(record.take_profits, list) else []

        timeframes = record.timeframes if isinstance(record.timeframes, list) else []
        return {
            "symbol": record.symbol,
            "direction": record.direction,
            "confidence": record.confidence,
            "entry_min": record.entry_min,
            "entry_max": record.entry_max,
            "stop_loss": record.stop_loss,
            "take_profits": take_profits,
            "leverage": record.leverage,
            "risk_reward": record.risk_reward,
            "trend": record.trend or "",
            "market_structure": record.market_structure or "",
            "primary_timeframe": timeframes[0] if timeframes else "",
            "invalidation": record.invalidation or "",
            "reason": record.reason or "",
            **self._analysis_payload(
                getattr(analysis, "analysis_text", "") if analysis else ""
            ),
            "ai_provider": record.ai_provider or "",
            "ai_model": record.ai_model or "",
            "created_at": format_datetime(record.created_at) if record.created_at else "",
            "created_at_raw": record.created_at,
            "timeframes": list(timeframes),
            **self._review_payload(record_id),
        }

    def _analysis_payload(self, analysis_text: str) -> dict[str, Any]:
        """
        جداکردن توصیهٔ صریح از متن تحلیل ذخیره‌شده.

        توصیه هنگام تولید در انتهای متن به‌صورت یک خط ماشین‌خوان
        نوشته شده و همان‌طور ذخیره می‌شود. اینجا دوباره خوانده می‌شود
        تا سیگنال‌های قدیمیِ سابقه هم کارت توصیه داشته باشند، نه فقط
        تحلیل‌های تازه.

        خط ماشین‌خوان از متن نمایشی حذف می‌گردد؛ کاربر همان اطلاعات
        را در کارت با قالب درست می‌بیند.
        """
        text = str(analysis_text or "")
        if not text:
            return {"analysis_text": ""}

        recommendation = parse_recommendation(text)
        if recommendation is None:
            return {"analysis_text": text}
        return {
            "analysis_text": strip_recommendation_line(text),
            "recommendation": recommendation.to_dict(),
        }

    def _review_payload(self, record_id: Any) -> dict[str, Any]:
        """
        بازبینی هوش مصنوعی یک سیگنال، اگر ساخته شده باشد.

        دیکشنری خالی یعنی «هنوز بازبینی نشده»؛ پنجرهٔ جزئیات در آن حالت
        کارت بازبینی را اصلاً نمی‌سازد.
        """
        try:
            review = self.app.review_repository.for_signal(int(record_id))
        except Exception:  # noqa: BLE001 - نبود بازبینی نباید پنجره را ببندد
            logger.debug("Could not load review for %s", record_id, exc_info=True)
            return {}
        if review is None:
            return {}
        return {
            "review_text": review.review_text or "",
            "review_verdict": review.verdict or "",
            "review_lesson": review.lesson or "",
        }

    def _on_trade_requested(self, signal: dict[str, Any]) -> None:
        """
        اقدام روی یک سیگنال.

        معامله به‌صورت تمرینی ثبت می‌شود؛ سفارش واقعی روی صرافی ارسال
        نمی‌شود. این موضوع صریحاً به کاربر گفته می‌شود تا تصور نکند پول
        واقعی جابه‌جا شده است.
        """
        direction = str(signal.get("direction", "WAIT")).upper()
        if direction not in {"LONG", "SHORT"}:
            self.status(self.tr_.tr("signals.no_action_on_wait"))
            return

        trader = self._paper_trader()
        entry = trader._pick_entry(signal)  # noqa: SLF001 - محاسبه یکسان برای پیش‌نمایش
        confirm = QMessageBox.question(
            self.window,
            self.tr_.tr("signals.paper_trade_title"),
            self.tr_.tr(
                "signals.confirm_trade",
                direction=self.tr_.tr(f"signals.{direction.lower()}", direction),
                symbol=signal.get("symbol", ""),
                entry=self.tr_.format_number(entry or 0.0, 4),
                stop=self.tr_.format_number(signal.get("stop_loss") or 0.0, 4),
            )
            + "\n\n"
            + self.tr_.tr("signals.paper_trade_note"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        risk = self.app.risk_parameters()
        position = trader.open_from_signal(
            signal,
            balance=getattr(risk, "account_balance", 0.0),
            risk_percent=getattr(risk, "risk_percent", 1.0),
        )
        if position is None:
            self.status(self.tr_.tr("signals.paper_trade_failed"))
            return

        # `PaperTrader` معامله را در یک رشتهٔ JSON داخل تنظیمات نگه
        # می‌دارد، ولی صفحهٔ «معاملات» از `trade_repository` (پایگاه داده)
        # می‌خواند. تا پیش از این، دکمهٔ معامله فقط در آن حافظهٔ جداگانه
        # می‌نوشت، پس کاربر هیچ ردی از معامله‌اش در تاریخچه نمی‌دید —
        # همان گزارشِ «دکمهٔ معامله هیچ چیزی باز نمی‌کند». حالا در هر دو
        # جا ثبت می‌شود تا تاریخچه واقعاً معامله را نشان دهد.
        record = dict(signal)
        record["entry_price"] = position.entry
        self.record_paper_trade(record)

        message = self.tr_.tr(
            "signals.paper_trade_opened",
            direction=self.tr_.tr(f"signals.{position.direction.lower()}", position.direction),
            symbol=position.symbol,
            entry=self.tr_.format_number(position.entry, 4),
        )
        self.status(message)
        QMessageBox.information(self.window, self.tr_.tr("signals.paper_trade_title"), message)

    def _paper_trader(self) -> Any:
        """ساخت تنبل دفتر معاملهٔ تمرینی."""
        if getattr(self, "_paper_trader_instance", None) is None:
            from signals.paper_trader import PaperTrader

            self._paper_trader_instance = PaperTrader(self.app.settings)
        return self._paper_trader_instance

    # ------------------------------------------------------------------
    # گزارش‌ها
    # ------------------------------------------------------------------
    def generate_report(self) -> None:
        """ساخت گزارش و ذخیره آن در قالب انتخاب‌شده."""
        days = int(self.reports.days_spin.value())
        output_format = self.reports.selected_format()
        self.reports.generate_button.setEnabled(False)
        self.status(self.tr_.tr("reports.generating"))

        def build() -> tuple[Any, Path]:
            """ساخت داده گزارش و نوشتن فایل (کار دیسکی، در نخ پس‌زمینه)."""
            data = self.app.report_builder.build_signal_report(days=days)
            path = self.app.report_exporter.export(data, output_format)
            return data, path

        def apply(payload: tuple[Any, Path]) -> None:
            """نمایش خلاصه و مسیر فایل ساخته‌شده."""
            data, path = payload
            self.reports.set_summary(data.summary)
            self.reports.set_preview(data.rows)
            self.status(self.tr_.tr("reports.saved", path=str(path)))
            QMessageBox.information(
                self.window, self.tr_.tr("reports.title"), self.tr_.tr("reports.saved", path=str(path))
            )

        self.runner.run_blocking(
            "report",
            build,
            on_success=apply,
            on_error=self._on_error,
            on_finished=lambda: self.reports.generate_button.setEnabled(True),
        )

    # ------------------------------------------------------------------
    # تنظیمات، پشتیبان‌گیری
    # ------------------------------------------------------------------
    def _apply_performance_settings(self) -> None:
        """
        اعمال تنظیمات کارایی روی تایمرها.

        فاصلهٔ تازه‌سازی در تنظیمات بر حسب ثانیه است ولی QTimer میلی‌ثانیه
        می‌گیرد؛ تبدیل اینجا انجام می‌شود.
        """
        dashboard_seconds = self.app.settings.get_int("performance.dashboard_refresh_seconds", 30) or 30
        self._refresh_timer.setInterval(max(5, dashboard_seconds) * 1000)
        logger.info("Dashboard refresh interval set to %ss", dashboard_seconds)

    def _apply_display_settings(self) -> None:
        """اعمال تنظیمات نمایش روی صفحه‌ها."""
        sort_mode = str(self.app.settings.get("ui.markets_sort", "value") or "value")
        combo = getattr(self.markets, "sort_combo", None)
        if combo is not None:
            index = combo.findData(sort_mode)
            if index >= 0 and index != combo.currentIndex():
                combo.setCurrentIndex(index)

    def save_settings(self) -> None:
        """ذخیره تنظیمات کاربر و اعمال فوری آن‌ها."""
        values = self.settings_page.collect_values()
        self.app.settings.set_many(values)

        secrets = self.settings_page.collect_secrets()
        stored = 0
        for key, value in secrets.items():
            if value:
                self.app.secrets.set(key, value)
                stored += 1

        self.app.apply_risk_settings()
        # تنظیمات هوش مصنوعی عوض شده؛ نمونه‌های قبلی باید دور ریخته شوند
        # وگرنه تا اجرای بعدی برنامه، سرویس قدیمی استفاده می‌شد.
        self.app.reset_ai()
        self._apply_timezone_setting()
        # تنظیمات کارایی و نمایش بی‌درنگ اثر می‌کنند، بدون نیاز به
        # بستن و باز کردن برنامه.
        self._apply_performance_settings()
        self._apply_display_settings()

        manual_rate = self.app.settings.get_float("market.manual_toman_rate", 0.0)
        if self._fiat is not None and manual_rate:
            self._fiat.set_manual_rate(manual_rate)
            self.refresh_fiat_rate()

        language = values.get("ui.language")
        if language and language != self.tr_.language:
            self.change_language(language)
        theme = values.get("ui.theme")
        if theme:
            self.change_theme(theme)

        logger.info("Settings saved (%d secrets updated)", stored)
        # نوار وضعیت به‌تنهایی دیده نمی‌شود: کاربر گزارش کرد بعد از زدن
        # «ذخیره» هیچ واکنشی نمی‌بیند و نمی‌داند کارش انجام شده یا نه.
        # اعلان شناور بازخورد صریحی است که نمی‌شود از قلم انداخت.
        message = self.tr_.tr("settings.saved")
        self.status(message)
        self._toast(message, level="success")

        # صرافی باید بی‌درنگ عوض شود. پیش از این فقط مقدارش ذخیره می‌شد و
        # تا بسته‌شدن برنامه، داده‌ها از صرافی قبلی می‌آمد.
        selected_exchange = str(values.get("exchange.active") or "")
        if selected_exchange and self.app.market is not None:
            if selected_exchange != self.app.market.exchange_name:
                self.apply_exchange_switch(selected_exchange)

    def apply_exchange_switch(self, exchange: str) -> None:
        """
        تعویض صرافی فعال و تازه‌سازی همهٔ صفحه‌های وابسته.

        کار سنگین (اتصال شبکه) در نخ پس‌زمینه انجام می‌شود تا رابط کاربری
        قفل نشود.
        """
        engine = getattr(self, "_auto_trader_engine", None)
        pending = any(str(key).startswith(("auto-manual-enter-", "auto-trade-start", "auto-trade-stop")) for key in self.runner.active_keys())
        if pending or (engine is not None and engine.is_running) or self.app.trade_repository.open_trades(self.app.auth.user_id):
            self.app.settings.set("exchange.active", self.app.market.exchange_name)
            self._toast(self.tr_.tr("trades.auto.exchange_locked"), level="warning")
            return
        self._exchange_switching = True
        self.status(self.tr_.tr("settings.exchange_switching", exchange=exchange))

        async def switch():
            feed = self._live_feed
            supervisor = self._connection_supervisor
            if supervisor is not None:
                await supervisor.stop()
            if feed is not None:
                await feed.stop()
            try:
                return await self.app.switch_exchange(exchange)
            except Exception:
                if feed is not None:
                    await feed.start()
                if supervisor is not None:
                    await supervisor.start()
                raise

        def done(active: str) -> None:
            """پس از تعویض موفق، داده‌های همهٔ صفحه‌ها باید نو شوند."""
            # نمادها و قیمت‌های کش‌شده متعلق به صرافی قبلی بودند
            self._symbols = []
            self._asset_prices = {}
            self._auto_trader_engine = None
            self._exchange_switching = False
            self._live_feed = None
            self._connection_supervisor = None
            self._pending_updates.clear()
            self._watch_candidates = {}
            self._watch_rows = []
            self._auto_prediction_payload = None
            self._start_live_feed()
            ticks = getattr(self, "_tick_engine", None)
            if ticks is not None:
                if engine is not None:
                    ticks.remove_listener(engine._on_tick)
                ticks.clear()
                bound_market = self.app.market
                bound_market.add_ticker_listener(
                    lambda ticker: self._on_market_ticker(ticker) if self.app.market is bound_market else None
                )
            self._refresh_connection_indicator()
            self._toast(
                self.tr_.tr("settings.exchange_switched", exchange=active),
                level="success",
            )
            self.refresh_markets()
            self.refresh_dashboard()
            self.refresh_wallet()

        def failed(text: str, exc: Any = None) -> None:
            """شکست تعویض نباید بی‌صدا بماند."""
            self._exchange_switching = False
            if self.app.market is not None:
                self.app.settings.set("exchange.active", self.app.market.exchange_name)
            self._refresh_connection_indicator()
            self._on_error(self.tr_.tr("settings.exchange_switch_failed"), exc)

        self.runner.submit(
            "switch-exchange",
            switch(),
            on_success=done,
            on_error=failed,
        )

    def _on_exchange_selected(self, exchange: str) -> None:
        """
        نمایش کلیدهای ذخیره‌شده صرافی انتخاب‌شده.

        کلید در ورودی برگردانده نمی‌شود (رمز است)، ولی به کاربر گفته
        می‌شود که کلیدی ذخیره شده و نیازی به وارد کردن دوباره نیست.
        """
        api_key, api_secret = self.app.exchange_credentials(exchange)
        if api_key:
            self.settings_page.api_key_input.setPlaceholderText("••••••••")
        if api_secret:
            self.settings_page.api_secret_input.setPlaceholderText("••••••••")
        logger.info("Exchange selection changed to %s", exchange)

    def _on_ai_provider_selected(self, provider: str) -> None:
        """نمایش وضعیت کلید سرویس هوش مصنوعی انتخاب‌شده."""
        if self.app.secrets.get(f"ai.{provider}.api_key"):
            self.settings_page.ai_key_input.setPlaceholderText("••••••••")
        else:
            self.settings_page.ai_key_input.setPlaceholderText("")

    def test_ai_connection(self) -> None:
        """
        آزمایش اتصال به سرویس هوش مصنوعی.

        بدون این، کاربر تنها وقتی می‌فهمد پیکربندی‌اش غلط است که یک
        تحلیل شکست بخورد — و آن موقع علتش روشن نیست.
        """
        self.settings_page.set_ai_status(self.tr_.tr("settings.testing"))
        self.settings_page.test_ai_button.setEnabled(False)

        # تنظیمات جاری باید پیش از آزمایش ذخیره شوند وگرنه سرویس قبلی
        # آزمایش می‌شود، نه آنچه کاربر همین حالا انتخاب کرده است.
        self._persist_ai_settings()

        async def check() -> tuple[bool, str]:
            """بررسی در دسترس بودن سرویس."""
            agent = self.app.autonomous_agent()
            if agent is None:
                return False, self.tr_.tr("analysis.ai_disabled")
            return await agent.health_check()

        def apply(result: tuple[bool, str]) -> None:
            """نمایش نتیجه."""
            ok, detail = result
            key = "settings.connection_ok" if ok else "settings.connection_failed"
            self.settings_page.set_ai_status(self.tr_.tr(key, detail=detail), ok=ok)

        self.runner.submit(
            "ai-test",
            check(),
            on_success=apply,
            on_error=lambda message, exc=None: self.settings_page.set_ai_status(
                self.tr_.tr("settings.connection_failed", detail=message), ok=False
            ),
            on_finished=lambda: self.settings_page.test_ai_button.setEnabled(True),
        )

    def check_for_update(self) -> None:
        """
        بررسی وجود نسخهٔ تازه در منبعی که کاربر تعیین کرده.

        منبع می‌تواند پوشهٔ محلی باشد یا نشانی اینترنتی؛ پشتیبانی از
        پوشه عمدی است، چون کاربر ممکن است اینترنت پایدار نداشته باشد.
        """
        from app.core.updater import UpdateChecker

        source = self.settings_page.update_source_input.text().strip()
        if not source:
            self.settings_page.set_update_status(
                self.tr_.tr("settings.update.no_source"), ok=False
            )
            return

        self.settings_page.set_update_status(self.tr_.tr("settings.update.checking"))
        self.settings_page.check_update_button.setEnabled(False)

        def apply(info) -> None:  # noqa: ANN001
            """نمایش نتیجه و فعال‌کردن دکمهٔ نصب در صورت وجود نسخهٔ تازه."""
            if info is None:
                self._pending_update = None
                self.settings_page.install_update_button.setEnabled(False)
                self.settings_page.set_update_status(
                    self.tr_.tr("settings.update.up_to_date", version=APP_VERSION),
                    ok=True,
                )
                return
            self._pending_update = info
            self.settings_page.install_update_button.setEnabled(True)
            self.settings_page.set_update_status(
                self.tr_.tr("settings.update.available", version=info.version), ok=True
            )

        self.runner.submit(
            "update-check",
            UpdateChecker(source).check(),
            on_success=apply,
            on_error=lambda message, exc=None: self.settings_page.set_update_status(
                message, ok=False
            ),
            on_finished=lambda: self.settings_page.check_update_button.setEnabled(True),
        )

    def install_update(self) -> None:
        """
        دانلود نسخهٔ تازه و اجرای نصب‌کننده.

        نصب‌کننده خودش نسخهٔ قبلی را جایگزین می‌کند و میان‌برها را
        به‌روز نگه می‌دارد. دادهٔ کاربر بیرون از پوشهٔ برنامه است و
        دست‌نخورده می‌ماند.
        """
        from app.core.updater import UpdateChecker

        info = getattr(self, "_pending_update", None)
        if info is None:
            self.check_for_update()
            return

        source = self.settings_page.update_source_input.text().strip()
        self.settings_page.set_update_status(self.tr_.tr("settings.update.downloading"))
        self.settings_page.install_update_button.setEnabled(False)

        checker = UpdateChecker(source)
        # `AppSettings` صفت `data_dir` ندارد؛ مسیر داده از `app/core/paths`
        # می‌آید. فایل دانلودشده کنار دادهٔ کاربر می‌نشیند نه در پوشهٔ
        # برنامه، چون پوشهٔ برنامه ممکن است اجازهٔ نوشتن نداشته باشد.
        from app.core.paths import get_data_dir

        destination = get_data_dir() / "updates"

        def apply(path) -> None:  # noqa: ANN001
            """اجرای نصب‌کنندهٔ دانلودشده."""
            if path is None:
                self.settings_page.set_update_status(
                    self.tr_.tr("settings.update.download_failed"), ok=False
                )
                self.settings_page.install_update_button.setEnabled(True)
                return
            if checker.launch_installer(path):
                self.settings_page.set_update_status(
                    self.tr_.tr("settings.update.installing"), ok=True
                )
            else:
                self.settings_page.set_update_status(str(path), ok=True)
                self.settings_page.install_update_button.setEnabled(True)

        self.runner.submit(
            "update-download",
            checker.download(info, destination),
            on_success=apply,
            on_error=lambda message, exc=None: self.settings_page.set_update_status(
                message, ok=False
            ),
        )

    def run_ollama_doctor(self) -> None:
        """
        عیب‌یابی پله‌به‌پلهٔ اولاما روی دستگاه کاربر.

        چرا لازم شد؟ «آزمایش اتصال» فقط می‌گوید سرویس بالاست یا نه، و
        برای کاربری که مدلش در ترمینال کار می‌کند ولی در برنامه نه هیچ
        کمکی نمی‌کند. سه نسخه علت را از راه دور حدس زدم و هر بار بخشی
        را اشتباه فهمیدم؛ این دکمه به‌جای حدس، اندازه می‌گیرد.
        """
        from ai.ollama_doctor import run_diagnosis

        self.settings_page.set_ai_status(self.tr_.tr("settings.doctor.running"))
        self.settings_page.doctor_button.setEnabled(False)
        self._persist_ai_settings()

        # `ai.base_url` ممکن است نشانی سرویس دیگری باشد (مثلاً
        # OpenRouter)، چون کاربر می‌تواند سرویس فعال را عوض کند. عیب‌یاب
        # همیشه باید اولامای محلی را بیازماید، پس نشانی فقط وقتی پذیرفته
        # می‌شود که به نظر محلی بیاید.
        configured = str(self.app.settings.get("ai.base_url", "") or "").strip()
        local = any(host in configured for host in ("127.0.0.1", "localhost", "0.0.0.0"))
        base_url = configured if local else "http://127.0.0.1:11434"

        def apply(report) -> None:  # noqa: ANN001
            """تبدیل گزارش به متنی که کاربر بتواند کپی و ارسال کند."""
            lines: list[str] = []
            for step in report.steps:
                label = self.tr_.tr(f"settings.doctor.step_{step.key}")
                mark = (
                    self.tr_.tr("settings.doctor.ok")
                    if step.ok
                    else self.tr_.tr("settings.doctor.failed")
                )
                line = f"• {label}: {mark}"
                if not step.ok and step.detail:
                    line += f" — {step.detail[:160]}"
                lines.append(line)

            if report.cpu_offload_detected:
                lines.append(self.tr_.tr("settings.doctor.cpu_offload"))

            lines.append(self.tr_.tr(report.verdict_key))

            if report.verdict_key in {
                "settings.doctor.verdict_load_limit",
                "settings.doctor.verdict_broken_service",
            }:
                lines.append(self.tr_.tr("settings.doctor.advice_title"))
                lines.append(self.tr_.tr("settings.doctor.advice_cpu"))
                lines.append(self.tr_.tr("settings.doctor.advice_small"))

            healthy = report.verdict_key == "settings.doctor.verdict_healthy"
            self.settings_page.set_ai_status("\n".join(lines), ok=healthy)

        self.runner.submit(
            "ollama-doctor",
            run_diagnosis(base_url),
            on_success=apply,
            on_error=lambda message, exc=None: self.settings_page.set_ai_status(
                self.tr_.tr("settings.connection_failed", detail=message), ok=False
            ),
            on_finished=lambda: self.settings_page.doctor_button.setEnabled(True),
        )

    def load_ai_models(self) -> None:
        """دریافت زندهٔ فهرست مدل‌های سرویس انتخاب‌شده."""
        self.settings_page.set_ai_status(self.tr_.tr("settings.testing"))
        self.settings_page.load_models_button.setEnabled(False)
        self._persist_ai_settings()

        provider_key = str(self.settings_page.ai_provider_combo.currentData() or "")

        async def fetch() -> list[str]:
            """
            پرسیدن فهرست مدل‌ها از خود سرویس.

            مستقیم از `Application` پرسیده می‌شود، نه از تحلیل‌گر ساخته‌شده؛
            این‌طور حتی وقتی هوش مصنوعی غیرفعال است هم کاربر می‌تواند
            ببیند چه مدل‌هایی در دسترس‌اند و بعد تصمیم بگیرد.
            """
            return await self.app.list_ai_models(provider_key)

        def apply(models: list[str]) -> None:
            """
            نمایش مدل‌های یافت‌شده، با رایگان‌ها در صدر.

            اگر مدل انتخاب‌شده فعلی در فهرست نباشد، خودکار رایگان‌ترین
            گزینه انتخاب می‌شود — کاربر خواست بدون هزینه شروع کند.
            """
            if not models:
                self.settings_page.set_ai_status(self.tr_.tr("settings.models_failed"), ok=False)
                return

            self.settings_page.set_model_list(models)
            free_count = self.settings_page.free_model_count()

            if not self.settings_page.selected_model():
                chosen = self.settings_page.auto_pick_free_model()
                if chosen:
                    self.status(self.tr_.tr("settings.ai_model_auto", model=chosen))

            self.settings_page.set_ai_status(
                self.tr_.tr("settings.models_loaded_free", count=len(models), free=free_count),
                ok=True,
            )

        self.runner.submit(
            "ai-models",
            fetch(),
            on_success=apply,
            on_error=lambda message, exc=None: self.settings_page.set_ai_status(
                self.tr_.tr("settings.models_failed"), ok=False
            ),
            on_finished=lambda: self.settings_page.load_models_button.setEnabled(True),
        )

    def _persist_ai_settings(self) -> None:
        """ذخیره تنظیمات هوش مصنوعی و بازسازی نمونه‌ها."""
        values = self.settings_page.collect_values()
        ai_values = {k: v for k, v in values.items() if k.startswith("ai.")}
        self.app.settings.set_many(ai_values)

        for key, value in self.settings_page.collect_secrets().items():
            if value:
                self.app.secrets.set(key, value)
        self.app.reset_ai()

    def create_backup(self) -> None:
        """ساخت نسخه پشتیبان دستی."""

        def run() -> Any:
            """اجرای پشتیبان‌گیری روی دیسک."""
            return self.app.create_backup(note="manual backup from settings page")

        def apply(info: Any) -> None:
            """اعلام موفقیت."""
            message = self.tr_.tr("settings.backup_created", path=str(info.path))
            self.status(message)
            QMessageBox.information(self.window, self.tr_.tr("settings.backup"), message)

        self.runner.run_blocking("backup", run, on_success=apply, on_error=self._on_error)

    def restore_backup(self) -> None:
        """
        بازیابی از یک فایل پشتیبان.

        چون بازیابی، داده جاری را جایگزین می‌کند، تأیید صریح کاربر گرفته
        می‌شود و برنامه پس از آن باید دوباره اجرا شود.
        """
        selected, _ = QFileDialog.getOpenFileName(
            self.window,
            self.tr_.tr("settings.restore"),
            str(self.app.paths.backups_dir),
            "Backup archives (*.zip)",
        )
        if not selected:
            return

        confirm = QMessageBox.question(
            self.window,
            self.tr_.tr("settings.restore"),
            self.tr_.tr("settings.restore_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.app.backup.restore(Path(selected))
        except Exception as exc:  # noqa: BLE001 - پیام خطا باید به کاربر برسد
            self._on_error(str(exc), exc)
            return

        QMessageBox.information(
            self.window, self.tr_.tr("settings.restore"), self.tr_.tr("settings.restore_done")
        )
        self.status(self.tr_.tr("settings.restore_done"))

    # ------------------------------------------------------------------
    # زبان و پوسته
    # ------------------------------------------------------------------
    def change_language(self, code: str) -> None:
        """
        تغییر زبان در زمان اجرا و ذخیره انتخاب کاربر.

        فقط `retranslate` کافی نیست: جدول‌ها اعداد و برچسب‌ها را در زمان
        پر شدن قالب‌بندی می‌کنند، پس محتوای پویا باید دوباره ساخته شود،
        وگرنه پس از تعویض زبان، ارقام فارسی زیر عنوان‌های انگلیسی می‌مانند.
        """
        self.tr_.set_language(code)
        self.app.settings.set("ui.language", code)
        self.window.retranslate()
        self._rerender_dynamic_content()
        logger.info("Language changed to %s", code)

    def _rerender_dynamic_content(self) -> None:
        """بازسازی محتوای پویای جدول‌ها با زبان جاری."""
        self._load_signal_history()
        # توضیح اندیکاتورها دو زبانه است و باید دوباره ساخته شود
        self._populate_indicator_catalog()
        self._refresh_search_suggestions()
        self.markets.set_rows(getattr(self.markets, "_all_rows", []))
        online = bool(self.app.market and self.app.market.is_online)
        label = self.tr_.tr("common.online") if online else self.tr_.tr("common.offline")
        self.dashboard.set_connection_status(label, "bullish" if online else "bearish")
        self.dashboard.set_status_value("connection", label, "bullish" if online else "bearish")
        if self.app.market is not None:
            self.refresh_dashboard()
        if self._last_signal is not None:
            self.signals.show_signal(self._last_signal.to_dict())

    def _on_font_scale_changed(self, percent: int) -> None:
        """
        اعمال بی‌درنگ اندازهٔ قلم.

        مقدار همان لحظه ذخیره می‌شود تا پس از بستن برنامه هم بماند؛
        کاربر نباید برای دیدن اثرش «ذخیره» بزند.
        """
        self.themes.set_font_scale(int(percent), self.qt_app)
        self.app.settings.set("ui.font_scale", int(percent))
        self.window.apply_theme_tokens()

    def _on_compact_mode_changed(self, enabled: bool) -> None:
        """اعمال بی‌درنگ حالت فشرده."""
        self.themes.set_compact_mode(bool(enabled), self.qt_app)
        self.app.settings.set("ui.compact_mode", bool(enabled))
        self.window.apply_theme_tokens()

    def _on_theme_combo_changed(self, _index: int) -> None:
        """
        انتخاب پوسته از فهرست کشویی زبانهٔ عمومی.

        مثل کارت‌های زبانهٔ «ظاهر برنامه» بی‌درنگ اعمال می‌شود؛ اگر همان
        پوستهٔ فعلی باشد کاری نمی‌کنیم تا بی‌جهت بازرسم نشود.
        """
        key = self.settings_page.theme_combo.currentData()
        if key and key != self.themes.current:
            self.change_theme(str(key))

    def change_theme(self, name: str) -> None:
        """
        تغییر پوسته در زمان اجرا و ذخیره انتخاب کاربر.

        هیچ صفحه‌ای بازساخته نمی‌شود: برگه سبک دوباره اعمال می‌گردد و
        توکن‌ها به اجزای نقاشی‌شده (نمودارها) منتقل می‌شوند. به این ترتیب
        وضعیت صفحه‌ها — نماد انتخابی، متن‌های چت، ردیف‌های جدول — دست‌نخورده
        می‌ماند.
        """
        resolved = self.themes.apply(self.qt_app, name)
        # ترجیح برای کاربر واردشده ذخیره می‌شود و در حالت مهمان سراسری
        self.app.auth.set_preference("ui.theme", resolved)

        palette = self.themes.palette
        self.analysis.apply_chart_palette(palette)
        self.trades.apply_chart_palette(palette)
        self.markets.set_palette(palette)
        self.window.apply_theme_tokens()
        # کارت پوستهٔ فعال در تنظیمات علامت می‌خورد
        if hasattr(self.settings_page, "select_theme"):
            self.settings_page.select_theme(resolved)
        # ویرایشگر باید مقادیر همین پوسته را نشان دهد
        self._sync_theme_editor(resolved)
        self.window.set_connection_indicator(
            bool(self.app.market and self.app.market.is_online)
        )
        logger.info("Theme changed to %s (resolved: %s)", name, resolved)

    # ------------------------------------------------------------------
    # ویرایشگر پوسته و پوسته‌های سفارشی
    # ------------------------------------------------------------------
    def preview_theme_tokens(self, overrides: dict) -> None:
        """
        اعمال بی‌درنگ تغییرهای ویرایشگر روی کل برنامه.

        پوستهٔ موقتی با شناسهٔ ثابت `custom_preview_key()` ساخته و اعمال
        می‌شود؛ چیزی روی دیسک نوشته نمی‌شود تا تا وقتی کاربر «ذخیره»
        نزده، ترجیح ذخیره‌شده‌اش دست‌نخورده بماند.
        """
        from ui.themes.catalog import THEME_CATALOG
        from ui.themes.custom import build_tokens

        base_key = self._editor_base_key or self.themes.current
        self._editor_overrides = dict(overrides or {})

        if not self._editor_overrides:
            # بازگشت به پوستهٔ پایه؛ پوستهٔ موقت هم پاک می‌شود تا در
            # فهرست پوسته‌ها باقی نماند.
            THEME_CATALOG.pop(PREVIEW_THEME_KEY, None)
            self.change_theme(base_key)
            return

        base = self.themes.tokens_for(base_key)
        tokens = build_tokens(
            PREVIEW_THEME_KEY,
            base.name_fa,
            base.name_en,
            base_key,
            self._editor_overrides,
        )
        THEME_CATALOG[PREVIEW_THEME_KEY] = tokens
        self._apply_theme_tokens(PREVIEW_THEME_KEY, persist=False)

    def _apply_theme_tokens(self, key: str, *, persist: bool) -> None:
        """
        اعمال یک پوسته بدون ذخیرهٔ ترجیح.

        `change_theme` همیشه ترجیح کاربر را می‌نویسد؛ برای پیش‌نمایش
        زنده این کار نادرست است، چون هنوز چیزی انتخاب نشده.
        """
        self.themes.apply(self.qt_app, key)
        if persist:
            self.app.auth.set_preference("ui.theme", key)
        palette = self.themes.palette
        self.analysis.apply_chart_palette(palette)
        self.trades.apply_chart_palette(palette)
        self.markets.set_palette(palette)
        self.window.apply_theme_tokens()
        self.window.set_connection_indicator(
            bool(self.app.market and self.app.market.is_online)
        )

    def save_custom_theme(self) -> None:
        """
        ذخیرهٔ پوستهٔ ویرایش‌شده با نامی که کاربر می‌دهد.

        اگر هیچ تغییری نداده باشد، ذخیره بی‌معناست و به‌جای ساختن یک
        کپی بی‌فایده، به کاربر گفته می‌شود.
        """
        from PySide6.QtWidgets import QInputDialog

        if not self._editor_overrides:
            self.status(self.tr_.tr("settings.editor.nothing_to_save"))
            return

        name, accepted = QInputDialog.getText(
            self.window,
            self.tr_.tr("settings.editor.save_title"),
            self.tr_.tr("settings.editor.save_prompt"),
        )
        if not accepted or not str(name).strip():
            return

        base_key = self._editor_base_key or self.themes.current
        key = self.custom_themes.save(str(name).strip(), base_key, self._editor_overrides)

        # پوستهٔ موقت دیگر لازم نیست؛ ماندنش یعنی یک ورودی تکراری در
        # فهرست پوسته‌ها.
        from ui.themes.catalog import THEME_CATALOG

        THEME_CATALOG.pop(PREVIEW_THEME_KEY, None)

        self._editor_base_key = key
        self._editor_overrides = {}
        self.settings_page.refresh_theme_cards()
        self.change_theme(key)
        self.settings_page.set_custom_theme_active(True)
        self.status(self.tr_.tr("settings.editor.saved", name=str(name).strip()))

    def delete_custom_theme(self) -> None:
        """حذف پوستهٔ سفارشی فعال، پس از تأیید کاربر."""
        from PySide6.QtWidgets import QMessageBox

        from ui.themes.custom import is_custom

        key = self.themes.current
        if not is_custom(key):
            return

        name = self.themes.display_name(key, self.tr_.language)
        answer = QMessageBox.question(
            self.window,
            self.tr_.tr("settings.editor.delete"),
            self.tr_.tr("settings.editor.delete_confirm", name=name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.custom_themes.delete(key)
        self._editor_base_key = ""
        self._editor_overrides = {}
        self.settings_page.refresh_theme_cards()
        self.change_theme(DEFAULT_THEME)
        self.settings_page.set_custom_theme_active(False)
        self.status(self.tr_.tr("settings.editor.deleted"))
        self._toast(self.tr_.tr("settings.editor.deleted"), level="success")

    def _sync_theme_editor(self, key: str) -> None:
        """
        هم‌گام‌کردن ویرایشگر با پوستهٔ تازه انتخاب‌شده.

        وقتی کاربر پوستهٔ دیگری برمی‌گزیند، ویرایشگر باید مقادیر همان
        پوسته را نشان دهد، نه مقادیر پوستهٔ قبلی.
        """
        from ui.themes.custom import is_custom

        if key == PREVIEW_THEME_KEY:
            return

        self._editor_base_key = key
        stored = self.custom_themes.read(key) if is_custom(key) else {}
        self._editor_overrides = dict(stored.get("overrides") or {})

        base_key = str(stored.get("base") or key) if is_custom(key) else key
        self.settings_page.load_theme_editor(
            self.themes.tokens_for(base_key), self._editor_overrides
        )
        self.settings_page.set_custom_theme_active(is_custom(key))

    def change_font_family(self, key: str) -> None:
        """
        تغییر خانوادهٔ قلم در زمان اجرا و ذخیرهٔ ترجیح کاربر.

        مثل پوسته، هیچ صفحه‌ای بازساخته نمی‌شود: برگهٔ سبک با زنجیرهٔ قلم
        تازه دوباره ساخته می‌شود و وضعیت صفحه‌ها دست‌نخورده می‌ماند.
        """
        resolved = self.themes.set_font_family(key, self.qt_app)
        self.app.auth.set_preference("ui.font_family", resolved)
        self.window.apply_theme_tokens()
        if hasattr(self.settings_page, "select_font_family"):
            self.settings_page.select_font_family(resolved)
        logger.info("UI font changed to %s", resolved)

    def apply_display_preferences(self) -> None:
        """
        اعمال قلم، اندازهٔ قلم و حالت فشرده روی پوستهٔ جاری.

        این سه مستقل از نام پوسته‌اند و باید روی هر پوسته‌ای کار کنند.
        """
        # قلم پیش از اندازه می‌آید: هر دو برگهٔ سبک را بازمی‌سازند و این
        # ترتیب یعنی فقط یک بازسازی اضافه، نه دو تا با قلم غلط در میانه.
        self.themes.set_font_family(
            self.app.settings.get("ui.font_family", DEFAULT_FONT_KEY), self.qt_app
        )
        self.themes.set_font_scale(
            self.app.settings.get_int("ui.font_scale", 100), self.qt_app
        )
        self.themes.set_compact_mode(
            self.app.settings.get_bool("ui.compact_mode", False), self.qt_app
        )
        self.window.apply_theme_tokens()

    def _update_dashboard_stats(self, rows: list[dict[str, Any]]) -> None:
        """
        محاسبهٔ چهار کارت آمار داشبورد.

        ارقام از داده‌ای می‌آیند که همین حالا در دست است؛ درخواست شبکهٔ
        اضافه‌ای زده نمی‌شود تا داشبورد سبک بماند.
        """
        try:
            volume = sum(float(row.get("volume") or 0.0) for row in rows)
            self.dashboard.set_stat(
                "volume",
                self._compact_number(volume),
                series=[float(row.get("change_percent") or 0.0) for row in rows][:12],
            )

            gainers = [row for row in rows if float(row.get("change_percent") or 0.0) > 0]
            share = (len(gainers) / len(rows) * 100.0) if rows else 0.0
            self.dashboard.set_stat(
                "market_cap",
                self.tr_.format_number(share, 1) + "%",
                caption=self.tr_.tr("dashboard.stats.gainers_caption", ""),
                delta=share - 50.0,
            )

            statistics = self.app.signal_repository.get_statistics()
            self.dashboard.set_stat(
                "signals_today", self._digits(statistics.get("total", 0))
            )

            trades = self.app.trade_repository.statistics(user_id=self.app.auth.user_id)
            self.dashboard.set_stat(
                "win_rate", self.tr_.format_number(trades.get("win_rate", 0.0), 1) + "%"
            )
        except Exception:  # noqa: BLE001 - کارت آمار نباید داشبورد را بخواباند
            logger.exception("Dashboard statistics failed")

    def _compact_number(self, value: float) -> str:
        """
        کوتاه‌کردن عدد بزرگ به شکل خوانا (۲٫۴B).

        در کارت آمار جا محدود است و عدد کامل خوانده نمی‌شود.
        """
        for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
            if abs(value) >= limit:
                return self.tr_.format_number(value / limit, 2) + suffix
        return self.tr_.format_number(value, 0)

    # ------------------------------------------------------------------
    # حساب کاربری
    # ------------------------------------------------------------------
    def show_auth_dialog(self, *, register: bool = False) -> None:
        """باز کردن گفت‌وگوی ورود یا ثبت‌نام."""
        from ui.dialogs import AuthDialog

        dialog = AuthDialog(
            self.tr_,
            self.app.auth,
            self.window,
            register_mode=register,
            reset_service=getattr(self.app, "password_reset", None),
        )
        dialog.authenticated.connect(lambda _user: self._on_user_changed())
        dialog.exec()

    def logout(self) -> None:
        """خروج از حساب و بازگشت به حالت مهمان."""
        self.app.auth.logout()
        self._on_user_changed()
        self._toast(self.tr_.tr("auth.logout_success"))

    def _on_user_changed(self) -> None:
        """
        تازه‌سازی هر چیزی که به کاربر بستگی دارد.

        پوستهٔ ذخیره‌شدهٔ کاربر هم اینجا اعمال می‌شود؛ کاربر باید محیط
        خودش را ببیند نه محیط نفر قبلی.
        """
        self._sync_user_chrome()

        preferred = str(self.app.auth.preference("ui.theme", "") or "")
        if preferred and self.themes.resolve(preferred) != self.themes.current:
            self.change_theme(preferred)

        self.refresh_accounts()
        self.refresh_security()
        self.refresh_trades()
        self.refresh_wallet()

    # ------------------------------------------------------------------
    # حساب‌های صرافی
    # ------------------------------------------------------------------
    def refresh_accounts(self) -> None:
        """تازه‌سازی جدول حساب‌های صرافی در تنظیمات."""
        user_id = self.app.auth.user_id
        accounts = (
            self.app.exchange_accounts.list_accounts(user_id) if user_id is not None else []
        )
        for item in accounts:
            moment = item.get("last_sync_at")
            item["last_sync_at"] = self._localized_datetime(moment) if moment else None
        self.settings_page.set_accounts(accounts)

    # ------------------------------------------------------------------
    # امنیت حساب — پروفایل، رمز عبور و نشست‌ها
    # ------------------------------------------------------------------
    def refresh_security(self) -> None:
        """تازه‌سازی زبانهٔ امنیت با پروفایل و نشست‌های کاربر جاری."""
        auth = self.app.auth
        authenticated = bool(auth.is_authenticated)
        self.settings_page.set_security_enabled(authenticated)

        # تنظیمات ایمیل به کاربر وابسته نیست (مال خود دستگاه است) پس
        # حتی در حالت مهمان هم باید نشان داده شود؛ وگرنه کسی که رمزش را
        # فراموش کرده، نمی‌تواند پیش از ورود ایمیل را تنظیم کند.
        email_keys = (
            "email.preset",
            "email.smtp_host",
            "email.smtp_port",
            "email.smtp_username",
            "email.smtp_tls",
            "email.sender_name",
        )
        self.settings_page.set_email_settings(
            {key: self.app.settings.get(key) for key in email_keys},
            has_password=bool(self.app.email.configured),
        )
        if not authenticated:
            self.settings_page.set_profile("", "")
            self.settings_page.set_sessions([])
            return

        user = auth.current_user or {}
        self.settings_page.set_profile(
            str(user.get("display_name") or ""), str(user.get("email") or "")
        )
        self.settings_page.set_sessions(
            [self._session_row(item) for item in auth.sessions()]
        )

    def _session_row(self, item: dict[str, Any]) -> dict[str, Any]:
        """قالب‌بندی یک نشست برای جدول امنیت."""
        if item.get("revoked"):
            status = self.tr_.tr("settings.security.status_revoked")
        elif self._is_expired(item.get("expires_at")):
            status = self.tr_.tr("settings.security.status_expired")
        else:
            status = self.tr_.tr("settings.security.status_active")
        return {
            "id": item.get("id"),
            "device": item.get("device_label") or self.tr_.tr("common.never"),
            "created": self._localized_datetime(item.get("created_at")),
            "last_seen": self._localized_datetime(item.get("last_seen_at")),
            "status": status,
        }

    @staticmethod
    def _is_expired(moment: Any) -> bool:
        """آیا زمان انقضا گذشته است؟ مقدار نامعتبر یعنی «منقضی نشده»."""
        if moment is None:
            return False
        try:
            reference = moment
            if isinstance(reference, str):
                reference = datetime.fromisoformat(reference)
            if reference.tzinfo is None:
                return reference < datetime.now()
            return reference < datetime.now(reference.tzinfo)
        except (TypeError, ValueError):
            return False

    def save_email_settings(self, values: dict, password: str) -> None:
        """
        ذخیرهٔ تنظیمات SMTP.

        رمز به انبار رمزنگاری‌شده می‌رود نه جدول تنظیمات؛ و اگر کاربر
        فیلد رمز را خالی گذاشته باشد، رمز قبلی دست‌نخورده می‌ماند —
        وگرنه هر بار ذخیرهٔ یک تغییر کوچک، رمز را پاک می‌کرد.
        """
        for key, value in values.items():
            self.app.settings.set(key, value)
        if password:
            try:
                self.app.email.set_password(password)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Storing the SMTP password failed")
                self._on_error(self.tr_.tr("common.state.error"), exc)
                return

        self.settings_page.set_email_settings(
            {key: self.app.settings.get(key) for key in values},
            has_password=bool(self.app.email.configured),
        )
        self._toast(self.tr_.tr("settings.saved"), level="success")

    def test_email_connection(self) -> None:
        """
        آزمودن اتصال به سرور ایمیل، خارج از نخ رابط کاربری.

        اتصال SMTP تا ۲۰ ثانیه طول می‌کشد؛ روی نخ اصلی، برنامه یخ می‌زد.
        """
        self.settings_page.set_email_status(self.tr_.tr("common.state.loading"))

        async def probe() -> tuple[bool, str]:
            import asyncio

            return await asyncio.to_thread(self.app.email.test_connection)

        def done(result: tuple[bool, str]) -> None:
            ok, error = result
            if ok:
                self.settings_page.set_email_status(self.tr_.tr("email.test_ok"))
            else:
                self.settings_page.set_email_status(self.tr_.tr(error), error=True)

        def failed(exc: BaseException) -> None:
            self.settings_page.set_email_status(str(exc), error=True)

        self.runner.submit("email-test", probe(), on_success=done, on_error=failed)

    def save_profile(self, display_name: str, email: str) -> None:
        """ذخیرهٔ نام نمایشی و ایمیل کاربر."""
        if not self.app.auth.is_authenticated:
            self._toast(self.tr_.tr("auth.error.not_authenticated"), level="warning")
            return
        try:
            ok = self.app.auth.update_profile(display_name=display_name, email=email)
        except ValueError as exc:
            # ایمیل تکراری: پیام مشخص، نه «خطای ناشناخته»
            self._toast(self.tr_.tr(str(exc)), level="error")
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("Profile update failed")
            self._on_error(self.tr_.tr("common.state.error"), exc)
            return
        if not ok:
            self._toast(self.tr_.tr("common.state.error"), level="error")
            return
        self._toast(self.tr_.tr("settings.security.profile_saved"), level="success")
        self._sync_user_chrome()
        self.refresh_security()

    def change_password(self, current: str, new: str, confirm: str) -> None:
        """
        تغییر رمز عبور کاربر جاری.

        تطابق رمز جدید با تکرارش در همین لایه بررسی می‌شود تا کاربر پیش از
        رفتن به پایگاه داده بازخورد بگیرد.
        """
        if not self.app.auth.is_authenticated:
            self._toast(self.tr_.tr("auth.error.not_authenticated"), level="warning")
            return
        if new != confirm:
            self._toast(
                self.tr_.tr("settings.security.password_mismatch"), level="warning"
            )
            return
        try:
            ok, reason = self.app.auth.change_password(current, new)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Password change failed")
            self._on_error(self.tr_.tr("common.state.error"), exc)
            return
        if not ok:
            self._toast(self.tr_.tr(reason) if reason else
                        self.tr_.tr("common.state.error"), level="error")
            return
        self.settings_page.clear_password_inputs()
        self._toast(self.tr_.tr("auth.password_changed"), level="success")
        self.refresh_security()

    def revoke_session(self, session_id: int) -> None:
        """باطل‌کردن یک نشست مشخص."""
        try:
            ok = self.app.auth.revoke_session(int(session_id))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Session revoke failed")
            self._on_error(self.tr_.tr("common.state.error"), exc)
            return
        if not ok:
            self._toast(self.tr_.tr("common.state.error"), level="error")
            return
        self._toast(self.tr_.tr("settings.security.session_revoked"), level="success")
        self.refresh_security()

    def revoke_other_sessions(self) -> None:
        """خروج از همهٔ دستگاه‌های دیگر."""
        if not self.app.auth.is_authenticated:
            self._toast(self.tr_.tr("auth.error.not_authenticated"), level="warning")
            return
        try:
            count = self.app.auth.revoke_other_sessions()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Bulk session revoke failed")
            self._on_error(self.tr_.tr("common.state.error"), exc)
            return
        self._toast(
            self.tr_.tr("settings.security.others_revoked").format(
                count=self.tr_.format_number(count, 0)
            ),
            level="success",
        )
        self.refresh_security()

    def add_exchange_account(self) -> None:
        """
        افزودن حساب صرافی از روی فرم زبانهٔ صرافی.

        بدون ورود به حساب کاربری امکان‌پذیر نیست، چون حساب صرافی به کاربر
        گره خورده است.
        """
        if not self.app.auth.is_authenticated:
            self._toast(self.tr_.tr("auth.error.not_authenticated"), level="warning")
            self.show_auth_dialog()
            return

        exchange = str(self.settings_page.exchange_combo.currentData() or "")
        api_key = self.settings_page.api_key_input.text().strip()
        api_secret = self.settings_page.api_secret_input.text().strip()
        if not exchange or not api_key or not api_secret:
            self._toast(self.tr_.tr("settings.accounts.security_note"), level="warning")
            return

        self.app.exchange_accounts.add_account(
            user_id=self.app.auth.user_id,
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
        )
        # ورودی‌ها بلافاصله پاک می‌شوند تا کلید روی صفحه نماند
        self.settings_page.api_key_input.clear()
        self.settings_page.api_secret_input.clear()
        self.refresh_accounts()
        self._toast(self.tr_.tr("settings.accounts.saved"), level="success")

    def test_exchange_account(self, account_id: int) -> None:
        """آزمایش اتصال یک حساب صرافی در پس‌زمینه."""
        self.status(self.tr_.tr("settings.accounts.testing"))
        self.runner.submit(
            f"test-account-{account_id}",
            self.app.exchange_accounts.test_connection(
                int(account_id), self._build_private_provider
            ),
            on_success=lambda result: self._on_account_tested(result),
            on_error=self._on_error,
        )

    def activate_exchange_account(self, account_id: int) -> None:
        """
        انتخاب صرافیِ فعال برای کیف پول.

        وقتی کاربر چند حساب متصل دارد باید بتواند تعیین کند کیف پول کدام
        را نشان دهد. پس از تعویض، موجودی همان حساب بلافاصله گرفته می‌شود
        تا کاربر منتظر تازه‌سازی دستی نماند.
        """
        user_id = self.app.auth.user_id
        if user_id is None:
            return
        if not self.app.exchange_accounts.set_default(user_id, int(account_id)):
            self._toast(self.tr_.tr("settings.accounts.activate_failed"), level="error")
            return

        # قیمت‌های حساب قبلی به صرافی تازه ربطی ندارند
        self._asset_prices.clear()
        self.refresh_accounts()
        self._toast(self.tr_.tr("settings.accounts.activated"), level="success")
        self.sync_wallet()

    def remove_exchange_account(self, account_id: int) -> None:
        """حذف حساب صرافی پس از تأیید."""
        answer = QMessageBox.question(
            self.window,
            self.tr_.tr("settings.accounts.remove"),
            self.tr_.tr("settings.accounts.confirm_remove"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.app.exchange_accounts.delete_account(int(account_id))
        self.refresh_accounts()
        self._toast(self.tr_.tr("settings.accounts.removed"))

    def _localize_exchange_message(self, message: str) -> str:
        """
        ترجمهٔ پیام بازگشتی از ارائه‌دهندهٔ صرافی.

        ارائه‌دهنده‌ها به‌جای متن انگلیسی، کلید ترجمه برمی‌گردانند تا پیام
        در رابط فارسی هم فارسی باشد. قالب `کلید|پارامتر` اجازه می‌دهد
        جزئیاتی مانند نوع خطا هم به ترجمه تزریق شود.
        """
        raw = str(message or "")
        key, separator, argument = raw.partition("|")
        if self.tr_.has(key):
            return self.tr_.tr(key, reason=argument) if separator else self.tr_.tr(key)
        return raw

    def _on_account_tested(self, result: tuple[bool, str]) -> None:
        """نمایش نتیجهٔ آزمایش اتصال."""
        ok, message = result
        if ok:
            self._toast(self.tr_.tr("settings.accounts.connected"), level="success")
        else:
            self._toast(
                self.tr_.tr(
                    "settings.accounts.failed",
                    error=self._localize_exchange_message(message),
                ),
                level="error",
            )
        self.refresh_accounts()

    def _wallet_price_lookup(self):
        """
        ساخت تابع قیمت‌یابی دارایی‌ها برای کیف پول.

        به‌صورت متد مستقل نوشته شده (نه تابع تودرتو) تا هم آزمون‌پذیر
        باشد و هم منطق ارزش‌گذاری در یک جا بماند.
        """

        async def price_lookup(asset: str) -> float:
            """
            ارزش تتریِ هر دارایی برای محاسبهٔ جمع کل.

            مسیرها به ترتیب: تتر، ارز ملی از راه نرخ تومان، جدول بازارهای
            در حافظه، بازار مستقیم با تتر، و در نبود آن مسیر غیرمستقیم از
            راه یک ارز واسط (BTC/ETH/USDC).
            """
            code = str(asset or "").upper()
            if code in ("USDT", "USD"):
                return 1.0

            # ریال/تومان جفت تتری ندارد و از راه نرخ تتر حساب می‌شود؛
            # بدون این، موجودی تومانی کاربران صرافی‌های ایرانی مثل
            # بیت‌پین همیشه بدون ارزش نشان داده می‌شد. قیمت باید در
            # `_asset_prices` هم ثبت شود وگرنه ستون «ارزش» خط تیره می‌ماند.
            if code in ("IRT", "TMN", "TOMAN", "IRR", "RLS"):
                rate = float(self._toman_rate or 0.0)
                if rate <= 0:
                    return 0.0
                divisor = rate * 10.0 if code in ("IRR", "RLS") else rate
                unit_price = 1.0 / divisor
                self._asset_prices[code] = unit_price
                return unit_price

            cached = self._last_price(f"{code}/USDT")
            if cached > 0:
                self._asset_prices[code] = cached
                return cached

            price = await self._usdt_price(code)
            if price > 0:
                self._asset_prices[code] = price
            return price

        return price_lookup

    def _build_private_provider(self, exchange: str, api_key: str, api_secret: str) -> Any:
        """
        ساخت ارائه‌دهندهٔ صرافی با اعتبارنامهٔ کاربر.

        از رجیستری ساخته می‌شود، پس هیچ صرافی‌ای در این لایه سخت‌کد نیست
        و افزودن صرافی تازه نیازی به تغییر کنترلر ندارد.
        """
        from market.providers.registry import exchange_registry

        return exchange_registry.create(
            exchange, api_key=api_key, api_secret=api_secret
        )

    # ------------------------------------------------------------------
    # تاریخچهٔ معاملات (کاغذی)
    # ------------------------------------------------------------------
    def refresh_trades(self) -> None:
        """
        بارگذاری دوبارهٔ جدول معاملات با فیلترهای جاری.

        خواندن از پایگاه دادهٔ محلی سریع است، پس نیازی به اجرای ناهمگام
        نیست و نتیجه بی‌درنگ روی صفحه می‌نشیند.
        """
        try:
            filters = self.trades.filters()
            user_id = self.app.auth.user_id
            repository = self.app.trade_repository

            start = self._as_datetime(filters.get("start"))
            end = self._as_datetime(filters.get("end"), end_of_day=True)
            page_size = int(filters.get("page_size") or 25)
            page = max(1, int(filters.get("page") or 1))

            criteria = {
                "user_id": user_id,
                "symbol": filters.get("symbol") or "",
                "side": filters.get("side") or "",
                "status": filters.get("status") or "",
                "start": start,
                "end": end,
            }
            total = repository.count_trades(**criteria)
            pages = max(1, (total + page_size - 1) // page_size)
            page = min(page, pages)

            rows = repository.list_trades(
                **criteria, limit=page_size, offset=(page - 1) * page_size
            )
            self.trades.set_trades(
                [self._trade_row(item) for item in rows],
                page=page,
                pages=pages,
                page_text=self.tr_.tr(
                    "trades.page_info",
                    page=self._digits(page),
                    pages=self._digits(pages),
                ),
            )
            self.trades.set_symbols(repository.symbols_traded(user_id))
            self.trades.set_metrics(self._trade_metrics(repository.statistics(user_id=user_id)))
        except Exception as exc:  # noqa: BLE001 - جدول خالی بهتر از سقوط است
            logger.exception("Loading trades failed")
            self._on_error(self.tr_.tr("common.state.error"), exc)

    def record_paper_trade(self, signal: dict[str, Any]) -> None:
        """
        ثبت یک معاملهٔ کاغذی از روی سیگنال.

        کاربر خواسته است فعلاً هیچ سفارش واقعی ارسال نشود؛ مقدار `mode`
        روی «paper» می‌ماند تا وقتی سفارش‌گذاری واقعی فعال شود.
        """
        try:
            entry = float(signal.get("entry_price") or signal.get("entry_min") or 0.0)
            if entry <= 0:
                self.status(self.tr_.tr("common.state.no_data"))
                return
            direction = str(signal.get("direction", "")).upper()
            if direction not in ("LONG", "SHORT"):
                # آرگومان دوم `tr` مقدار پیش‌فرض است نه متغیر؛ نام جهت باید
                # با کلیدواژه بیاید وگرنه «{direction}» عیناً چاپ می‌شود.
                self.status(
                    self.tr_.tr(
                        "signals.wait_no_trade",
                        direction=self.tr_.tr(f"signals.{direction.lower()}", direction),
                    )
                )
                return

            balance = float(self.app.settings.get("risk.account_balance", 1000) or 1000)
            risk_percent = float(self.app.settings.get("risk.risk_percent", 1) or 1)
            stop = float(signal.get("stop_loss") or 0.0)
            distance = abs(entry - stop) or entry * 0.01
            quantity = (balance * risk_percent / 100.0) / distance

            trade = self.app.trade_repository.open_trade(
                symbol=str(signal.get("symbol", "")),
                side="long" if direction == "LONG" else "short",
                quantity=quantity,
                entry_price=entry,
                user_id=self.app.auth.user_id,
                signal_id=signal.get("id"),
                stop_loss=stop or None,
                take_profit=float(signal.get("take_profit") or 0.0) or None,
                leverage=float(signal.get("leverage") or 1.0),
                note=str(signal.get("reason", ""))[:200],
            )
            self.status(self.tr_.tr("trades.opened"))
            self._toast(self.tr_.tr("trades.opened"), level="success")
            self.refresh_trades()
            logger.info("Paper trade recorded from signal: id=%s", trade.get("id"))
        except Exception as exc:  # noqa: BLE001
            self._on_error(self.tr_.tr("common.state.error"), exc)

    # ------------------------------------------------------------------
    # معاملهٔ خودکار
    # ------------------------------------------------------------------
    def _auto_trader(self) -> Any:
        """
        ساخت (یا بازگرداندن) موتور معاملهٔ خودکار.

        موتور تنبل ساخته می‌شود تا تنظیم‌های کاربر در لحظهٔ شروع خوانده
        شود، نه در زمان بالا آمدن برنامه؛ وگرنه تغییر هدف سود در تنظیمات
        تا ری‌استارت بعدی بی‌اثر می‌ماند.
        """
        existing = getattr(self, "_auto_trader_engine", None)
        if existing is not None:
            existing.apply_config(self._auto_trade_config())
            return existing

        from trading.auto_trader import AutoTrader
        from trading.scalp_service import ScalpService

        service = ScalpService(self.app)
        config = self._auto_trade_config()

        bound_market = self.app.market

        async def price_source(symbol: str) -> float:
            """REST همان صرافی‌ای که موتور به آن متصل شد."""
            market = bound_market
            if market is None:
                return 0.0
            return await market.refresh_execution_quote(symbol, self._tick_engine)

        # کاربر خواست معاملهٔ خودکار روی **همهٔ ارزها** تحلیل کند و هر
        # نمادی که اطمینانش از حد تعیین‌شده بالاتر رفت وارد معامله شود.
        # منبع قبلی (اسکالپ) بر پایهٔ نوسان پنج‌دقیقه‌ای کار می‌کرد و
        # اصلاً «اطمینان» نداشت. حالا هر دو در دسترس‌اند و کاربر در
        # تنظیمات انتخاب می‌کند.
        from trading.confidence_source import ConfidenceCandidateSource

        confidence_source = ConfidenceCandidateSource(self.app)

        async def candidate_source() -> list:
            """
            نامزدهای معامله بر پایهٔ حالت موتور (خواستهٔ §۳).

            selected → همان منبع قبلی، فقط نمادهای انتخابی کاربر
            scan     → همان رفتار قبلی (کل بازار با فیلتر کاربر)
            ai       → تحلیل نمادهای برتر با موتور پیش‌بینی + نردبان
                       روند + تصمیم‌ساز AI؛ خروجی یا معاملهٔ کامل است
                       یا NO TRADE با دلیل.
            """
            engine_mode = str(
                self.app.settings.get("scalp.engine_mode", "scan") or "scan"
            ).strip().lower()
            source_mode = str(
                self.app.settings.get("scalp.candidate_source", "confidence") or "confidence"
            ).strip().lower()

            if engine_mode == "ai":
                return await self._ai_candidate_scan()

            selected = self._auto_selected_symbols()
            if source_mode == "confidence":
                candidates = await confidence_source.scan(symbols=selected if engine_mode == "selected" else None)
            else:
                candidates = await service.scan(symbols=selected if engine_mode == "selected" else None)
                candidates = [c for c in candidates if service.feasibility(c)[0]]
            if engine_mode == "selected" and selected is not None:
                candidates = [
                    c for c in candidates
                    if str(getattr(c, "symbol", "")).upper() in selected
                ]
            return candidates

        from trading.execution import build_gateway

        exchange = str(self.app.settings.get("exchange.active", "lbank") or "lbank")
        engine = AutoTrader(
            config=config,
            price_source=price_source,
            repository=self.app.trade_repository,
            candidate_source=candidate_source,
            gateway=build_gateway(exchange),
            user_id=self.app.auth.user_id,
            portfolio_source=self._portfolio_snapshot,
            invalidation_source=self._prediction_direction,
        )
        # مسیر تیک: هر تیک وب‌سوکت بلافاصله TP/SL/سر‌به‌سر/تریلینگ را
        # می‌سنجد — پایش فقط fallback است (خواستهٔ §۶).
        engine.attach_tick_engine(self._ensure_tick_engine())
        engine.add_listener(self._on_auto_trade_event)
        self._auto_trader_engine = engine
        self._update_streamed_symbols()
        return engine

    def save_auto_trade_settings(self, values: dict) -> None:
        """
        ذخیرهٔ عددهای دستی معاملهٔ خودکار از صفحهٔ معاملات.

        همان کلیدهای `scalp.*` نوشته می‌شوند که صفحهٔ تنظیمات هم
        می‌نویسد. اگر موتور در حال اجرا باشد، عددهای تازه همان لحظه
        با `apply_config` اعمال می‌شوند؛ وگرنه تا شروع بعدی بی‌اثرند.
        """
        try:
            self.app.settings.set_many(dict(values))
        except Exception as exc:  # noqa: BLE001
            self._on_error(self.tr_.tr("common.state.error"), exc)
            return
        engine = getattr(self, "_auto_trader_engine", None)
        if engine is not None:
            engine.apply_config(self._auto_trade_config())
        self.refresh_auto_config()
        self._toast(self.tr_.tr("trades.auto.settings_saved"), level="success")

    def refresh_auto_config(self) -> None:
        """تازه‌سازی ورودی‌های دستی و خلاصهٔ تنظیمات روی صفحهٔ معاملات."""
        keys = (
            "scalp.margin_per_trade",
            "scalp.target_profit",
            "scalp.max_loss",
            "scalp.leverage",
            "scalp.max_concurrent",
            "scalp.min_confidence",
            "scalp.candidate_source",
            "scalp.mode",
            "scalp.live_confirmation",
            "scalp.poll_seconds",
            # v2.0 — حالت‌ها و محافظ‌ها
            "scalp.engine_mode",
            "scalp.selected_symbols",
            "scalp.min_liquidity",
            "scalp.max_spread_percent",
            "scalp.scan_interval_seconds",
            "scalp.stale_after_seconds",
            "scalp.slippage_percent",
            "scalp.trailing_enabled",
            "scalp.break_even_enabled",
            "scalp.signal_invalidation",
            "scalp.allocation_mode",
            "scalp.allocation_percent",
            "scalp.max_total_margin_percent",
        )
        values = {key: self.app.settings.get(key) for key in keys}
        if hasattr(self.trades, "load_auto_settings"):
            self.trades.load_auto_settings(values)

    def _on_auto_trade_event(self, event: str, payload: dict) -> None:
        """
        رویداد موتور → نوار وضعیت و تازه‌سازی جدول.

        موتور روی نخ شبکه اجرا می‌شود، پس مستقیم به ویجت دست نمی‌زنیم؛
        از سیگنال Qt رد می‌شویم تا رابط کاربری خراب نشود.
        """
        self.auto_trade_event.emit(str(event), dict(payload or {}))

    def _handle_auto_trade_event(self, event: str, payload: dict) -> None:
        """نمایش رویداد معاملهٔ خودکار روی صفحه (نخ رابط کاربری)."""
        # موتور، معامله را زیر کلید `trade` و نتیجهٔ ذخیره‌شده را زیر
        # `record` می‌فرستد؛ خواندن مستقیم `symbol` از payload همیشه
        # «؟» می‌داد.
        trade = payload.get("trade")
        record = payload.get("record") or {}
        symbol = getattr(trade, "symbol", "") or record.get("symbol", "?")

        if event == "opened":
            price = getattr(trade, "entry_price", None) or record.get("entry_price", "?")
            self._toast(
                self.tr_.tr(
                    "trades.auto.opened",
                    symbol=symbol,
                    price=f"{float(price):,.6g}" if isinstance(price, (int, float)) else price,
                ),
                level="info",
            )
        elif event == "closed":
            pnl = float(record.get("pnl", 0) or 0)
            self._toast(
                self.tr_.tr(
                    "trades.auto.closed",
                    symbol=symbol,
                    pnl=f"{pnl:+.2f}",
                    reason=str(payload.get("reason", "")),
                ),
                level="success" if pnl >= 0 else "warning",
            )
        elif event == "halted":
            self._toast(
                self.tr_.tr("trades.auto.blocked", reason=payload.get("reason", "")),
                level="warning",
            )
        if event in {"opened", "closed"}:
            self._update_streamed_symbols()
        self.refresh_trades()
        self._refresh_auto_trade_panel()

    def _refresh_auto_trade_panel(self) -> None:
        """هماهنگ‌کردن پنل با وضعیت واقعی موتور و تنظیم‌های جاری."""
        engine = getattr(self, "_auto_trader_engine", None)
        running = bool(engine is not None and engine.is_running)

        # ورودی‌های دستی باید عددهای واقعی ذخیره‌شده را نشان دهند،
        # وگرنه کاربر صفر می‌بیند و فکر می‌کند تنظیمی وجود ندارد.
        self.refresh_auto_config()

        try:
            from trading.scalp_service import ScalpService

            config = (
                engine.config if engine is not None
                else ScalpService(self.app).build_trader_config()
            )
            mode_key = "trades.auto.mode_live" if config.is_live else "trades.auto.mode_paper"
            self.trades.set_auto_config(
                self.tr_.tr(
                    "trades.auto.config",
                    mode=self.tr_.tr(mode_key),
                    target=f"{config.target_profit:g}$",
                    stop=f"{config.max_loss:g}$",
                    leverage=f"{config.leverage:g}",
                    margin=f"{config.margin_per_trade:g}",
                    concurrency=config.max_concurrent,
                )
            )
        except Exception:  # noqa: BLE001
            # خواندن تنظیمات نباید صفحه را از کار بیندازد.
            self.trades.set_auto_config(self.tr_.tr("trades.auto.settings_hint"))

        detail = ""
        if engine is not None and running:
            detail = self.tr_.tr(
                "trades.auto.config",
                mode=self.tr_.tr(
                    "trades.auto.mode_live" if engine.config.is_live
                    else "trades.auto.mode_paper"
                ),
                target=f"{engine.config.target_profit:g}$",
                stop=f"{engine.config.max_loss:g}$",
                leverage=f"{engine.config.leverage:g}",
                margin=f"{engine.config.margin_per_trade:g}",
                concurrency=engine.config.max_concurrent,
            )
            detail = f"{len(engine.open_trades)} / {engine.config.max_concurrent}"
            detail = self.tr_.tr("trades.auto.running") + f" • {detail}"
        if not detail:
            detail = self._auto_economics_text()
        self.trades.set_auto_state(running, detail)

    def toggle_auto_trading(self, start: bool) -> None:
        """روشن یا خاموش کردن معاملهٔ خودکار به درخواست کاربر."""
        if start and getattr(self, "_exchange_switching", False):
            self._toast(self.tr_.tr("trades.auto.exchange_locked"), level="warning")
            return
        if start:
            engine = self._auto_trader()

            def started(result: Any) -> None:
                ok, message = result
                if ok:
                    self._toast(self.tr_.tr("trades.auto.started"), level="success")
                else:
                    self._toast(
                        self.tr_.tr("trades.auto.blocked", reason=message),
                        level="warning",
                    )
                self._refresh_auto_trade_panel()

            self.runner.submit(
                "auto-trade-start",
                engine.start(),
                on_success=started,
                on_error=self._on_error,
            )
            return

        engine = getattr(self, "_auto_trader_engine", None)
        if engine is None:
            self._refresh_auto_trade_panel()
            return

        def stopped(_result: Any) -> None:
            self._toast(self.tr_.tr("trades.auto.stopped_msg"), level="info")
            self._refresh_auto_trade_panel()

        self.runner.submit(
            "auto-trade-stop",
            engine.stop(),
            on_success=stopped,
            on_error=self._on_error,
        )

    def close_paper_trade(self, trade_id: int) -> None:
        """یک مسیر خروج برای تاریخچه، مودال و موقعیت‌ها؛ بدون قیمت کهنهٔ UI."""
        key = f"close-trade-{int(trade_id)}"
        if key in set(self.runner.active_keys()):
            return
        engine = getattr(self, "_auto_trader_engine", None)
        managed = next((t for t in engine.open_trades if t.trade_id == int(trade_id)), None) if engine else None
        ticks = self._ensure_tick_engine()
        market = self.app.market
        if market is None:
            self.status(self.tr_.tr("common.state.no_data"))
            return

        async def close():
            if managed is not None:
                return await engine.close_trade(managed, "manual")
            from trading.paper_execution import close_paper_position
            return await close_paper_position(
                self.app.trade_repository, int(trade_id), ticks,
                lambda symbol: market.refresh_execution_quote(symbol, ticks),
                slippage_percent=self._auto_trade_config().slippage_percent,
                fee_rate=self._auto_trade_config().fee_rate,
            )

        def done(result):
            self._toast(self.tr_.tr("trades.closed" if result else "trades.auto.close_failed"),
                        level="success" if result else "warning")
            self.refresh_trades()
            self.refresh_wallet()

        self.runner.submit(key, close(), on_success=done, on_error=self._on_error)

    def clear_trade_history(self) -> None:
        """پاک‌کردن تاریخچه پس از تأیید کاربر."""
        answer = QMessageBox.question(
            self.window,
            self.tr_.tr("trades.clear_history"),
            self.tr_.tr("trades.confirm_clear"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.app.trade_repository.clear_history(self.app.auth.user_id)
        self.refresh_trades()

    def export_trades(self) -> None:
        """
        خروجی CSV از معاملات فیلترشده.

        کدگذاری `utf-8-sig` است تا اکسل فارسی را درست باز کند.
        """
        import csv

        path, _ = QFileDialog.getSaveFileName(
            self.window, self.tr_.tr("trades.export_csv"), "trades.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            filters = self.trades.filters()
            rows = self.app.trade_repository.list_trades(
                user_id=self.app.auth.user_id,
                symbol=filters.get("symbol") or "",
                side=filters.get("side") or "",
                status=filters.get("status") or "",
                start=self._as_datetime(filters.get("start")),
                end=self._as_datetime(filters.get("end"), end_of_day=True),
                limit=10_000,
            )
            columns = [
                "id", "symbol", "side", "status", "mode", "quantity", "entry_price",
                "exit_price", "stop_loss", "take_profit", "leverage", "fee",
                "pnl", "pnl_percent", "opened_at", "closed_at",
            ]
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([row.get(name, "") for name in columns])
            self._toast(self.tr_.tr("reports.exported"), level="success")
        except OSError as exc:
            self._on_error(self.tr_.tr("common.state.error"), exc)

    # ------------------------------------------------------------------
    # کیف پول
    # ------------------------------------------------------------------
    def sync_wallet(self) -> None:
        """
        گرفتن موجودی تازه از صرافی و سپس تازه‌سازی صفحه.

        پیش‌تر دکمهٔ «همگام‌سازی» فقط همان دادهٔ ذخیره‌شده را دوباره رسم
        می‌کرد و هیچ درخواستی به صرافی نمی‌رفت؛ برای همین کیف پول حتی با
        اتصال موفق هم خالی می‌ماند.
        """
        user_id = self.app.auth.user_id
        account = (
            self.app.exchange_accounts.default_account(user_id)
            if user_id is not None
            else None
        )
        if account is None:
            self.wallet.set_connected(False)
            self.status(self.tr_.tr("wallet.no_account"))
            return

        account_id = int(account["id"])
        self.wallet.set_busy(True)
        self.status(self.tr_.tr("wallet.syncing"))

        # از همان سازندهٔ مشترک استفاده می‌شود تا منطق ساخت ارائه‌دهنده در
        # دو جا تکرار (و واگرا) نشود.
        factory = self._build_private_provider

        price_lookup = self._wallet_price_lookup()

        async def run() -> dict[str, Any]:
            """همگام‌سازی در پس‌زمینه تا رابط کاربری قفل نشود."""
            return await self.app.exchange_accounts.sync_balances(
                account_id, factory, price_lookup=price_lookup
            )

        def done(result: dict[str, Any]) -> None:
            """نمایش نتیجه؛ خطا هم باید دیده شود نه اینکه بی‌صدا رد شود."""
            self.wallet.set_busy(False)
            if result.get("balances"):
                self.status(self.tr_.tr("wallet.sync_done"))
            else:
                fresh = self.app.exchange_accounts.get_account(account_id) or {}
                stored_error = str(fresh.get("last_error") or "")
                self.status(
                    self._localize_exchange_message(stored_error)
                    if stored_error
                    else self.tr_.tr("wallet.sync_empty")
                )
            self.refresh_wallet()

        def failed(text: str, exc: Any = None) -> None:
            """شکست همگام‌سازی نباید بی‌صدا بماند."""
            self.wallet.set_busy(False)
            self._on_error(self.tr_.tr("wallet.sync_failed"), exc)
            self.refresh_wallet()

        self.runner.submit(
            f"wallet-sync-{account_id}", run(), on_success=done, on_error=failed
        )

    def refresh_wallet(self) -> None:
        """
        به‌روزرسانی صفحهٔ کیف پول.

        منبع داده: حساب صرافی متصل کاربر. اگر حسابی نباشد، حالت راهنما
        نشان داده می‌شود — این تنها جای تصمیم‌گیری دربارهٔ آن است.
        """
        try:
            user_id = self.app.auth.user_id
            account = (
                self.app.exchange_accounts.default_account(user_id)
                if user_id is not None
                else None
            )
            self.wallet.set_connected(account is not None)
            if account is None:
                return

            balances = account.get("balances") or {}
            total = float(account.get("total_value_usdt") or 0.0)
            # تفکیک اسپات/فیوچرز که هنگام همگام‌سازی ذخیره شده است
            by_wallet = dict(
                (account.get("extra_config") or {}).get("balances_by_wallet") or {}
            )
            assets = self._wallet_assets(balances, total, by_wallet)
            self.wallet.set_assets(assets)

            statistics = self.app.trade_repository.statistics(user_id=user_id)
            available = float(balances.get("USDT", 0.0) or 0.0)
            self.wallet.set_summary(
                total=self._money(total),
                available=self._money(available),
                wallet_split=self._wallet_split_text(by_wallet),
                pnl=self._money(statistics.get("total_pnl", 0.0)),
                pnl_delta=statistics.get("average_pnl_percent"),
                total_series=self.app.trade_repository.equity_curve(
                    user_id=user_id, starting_balance=total
                )[-24:],
                toman=self._toman_text(total),
            )
            curve = self.app.trade_repository.equity_curve(
                user_id=user_id, starting_balance=total
            )
            self.wallet.set_growth(curve)
            self.wallet.set_last_sync(
                self._localized_datetime(account.get("last_sync_at"))
                if account.get("last_sync_at")
                else ""
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Wallet refresh failed")
            self._on_error(self.tr_.tr("common.state.error"), exc)

    # ------------------------------------------------------------------
    # نوار بالا
    # ------------------------------------------------------------------
    def _remember_prices(self, rows: list[dict[str, Any]]) -> None:
        """
        نگه‌داشتن آخرین قیمت‌ها برای نمودار ستون «روند».

        سقف دارد تا حافظه رشد نکند و فقط نمادهایی که هنوز در بازار
        هستند نگه داشته می‌شوند.
        """
        seen = set()
        for row in rows:
            symbol = str(row.get("symbol", ""))
            if not symbol:
                continue
            seen.add(symbol)
            price = float(row.get("price") or 0.0)
            if price <= 0:
                continue
            series = self._price_history.setdefault(symbol, [])
            series.append(price)
            if len(series) > PRICE_HISTORY_POINTS:
                del series[: len(series) - PRICE_HISTORY_POINTS]
            row["history"] = list(series)

        for symbol in [s for s in self._price_history if s not in seen]:
            self._price_history.pop(symbol, None)

    def _refresh_search_suggestions(self) -> None:
        """
        ساخت فهرست پیشنهادهای جست‌وجوی سراسری.

        هم نام صفحه‌ها و هم نمادهای بازار پیشنهاد می‌شوند تا با نوشتن
        چند حرف، گزینه‌ها زیر کادر جست‌وجو فهرست شوند.
        """
        entries: list[tuple[str, str, str]] = []

        # صفحه‌ها اول می‌آیند: تعدادشان کم است و کاربر زود پیدایشان می‌کند
        for key, _page in self.window.PAGES:
            entries.append(("page", key, self.tr_.tr(key)))

        # نمادها؛ سقف می‌گذاریم تا فهرست هزارتایی رابط را کند نکند
        for symbol in self._symbols[:400]:
            entries.append(("symbol", symbol, symbol))

        self.window.topbar.search.set_suggestions(entries)

    def _on_search_suggestion(self, kind: str, value: str) -> None:
        """باز کردن آیتمی که کاربر از فهرست پیشنهادها برگزید."""
        if kind == "page":
            for index, (key, _page) in enumerate(self.window.PAGES):
                if key == value:
                    self.window.go_to_page(index)
                    return
        elif kind == "symbol":
            self.show_coin_details(value)
            return
        self.global_search(value)

    def global_search(self, query: str) -> None:
        """
        جستجوی سراسری: نماد یا نام صفحه.

        اگر عبارت با یک نماد بازار بخواند، صفحهٔ تحلیل همان نماد باز
        می‌شود؛ وگرنه میان نام صفحه‌ها جستجو می‌گردد.
        """
        text = (query or "").strip()
        if not text:
            return

        needle = text.upper()
        for symbol in self._symbols:
            if symbol.upper().startswith(needle) or symbol.upper() == needle:
                self.show_coin_details(symbol)
                return

        lowered = text.casefold()
        for index, (key, _) in enumerate(self.window.PAGES):
            if lowered in self.tr_.tr(key).casefold():
                self.window.go_to_page(index)
                return
        self.status(self.tr_.tr("common.state.no_data"))

    def refresh_current_page(self) -> None:
        """تازه‌سازی صفحهٔ فعال از نوار بالا یا Ctrl+R."""
        index = self.window.stack.currentIndex()
        key = self.window.PAGES[index][0] if index < len(self.window.PAGES) else ""
        handlers = {
            "nav.dashboard": self.refresh_dashboard,
            "nav.markets": self.refresh_markets,
            "nav.trades": self.refresh_trades,
            "nav.wallet": self.refresh_wallet,
            "nav.signals": self._load_signal_history,
            "nav.reports": self._refresh_outcome_view,
        }
        handler = handlers.get(key)
        if handler is not None:
            handler()

    # ------------------------------------------------------------------
    # کمکی — معامله و کیف پول
    # ------------------------------------------------------------------
    def _sync_user_chrome(self) -> None:
        """هماهنگ‌کردن نوار بالا با کاربر جاری."""
        auth = self.app.auth
        name = auth.display_name
        if not auth.is_authenticated:
            name = self.tr_.tr("auth.guest")
        self.window.set_user(name, authenticated=auth.is_authenticated)

    def _trade_row(self, item: dict[str, Any]) -> dict[str, Any]:
        """قالب‌بندی یک معامله برای نمایش در جدول."""
        item = dict(item)
        ticks = getattr(self, "_tick_engine", None)
        quote = ticks.get(str(item.get("symbol") or "")) if ticks is not None else None
        estimated_fee = float(item.get("fee") or 0)
        if item.get("status") == "open" and quote is not None:
            side = str(item.get("side") or "long")
            price = quote.exit_price(side)
            slip = self._auto_trade_config().slippage_percent / 100
            price *= 1 - slip if side == "long" else 1 + slip
            estimated_fee += self._exit_fee(item, price=price)
            quantity = float(item.get("quantity") or 0)
            entry = float(item.get("entry_price") or 0)
            margin = quantity * entry / float(item.get("leverage") or 1)
            item["last_price"] = price
            item["pnl"] = (price - entry) * quantity * (1 if side == "long" else -1) - estimated_fee
            item["pnl_percent"] = item["pnl"] / margin * 100 if margin else 0
        row = dict(item)
        row["data_age_text"] = (
            self.tr_.tr("trades.auto.stale_data") if quote is None or ticks.is_stale(quote.symbol)
            else f"{quote.age_ms:.0f} ms"
        ) if item.get("status") == "open" else "—"
        row["date_text"] = self._localized_datetime(item.get("opened_at"))
        fmt = self.tr_.format_number
        entry = float(item.get("entry_price") or 0)
        quantity = float(item.get("quantity") or 0)
        leverage = float(item.get("leverage") or 1)
        row["side_text"] = self.tr_.tr(f"trades.sides.{item.get('side')}")
        row["status_text"] = self.tr_.tr(f"trades.statuses.{item.get('status')}")
        row["margin_text"] = fmt(entry * quantity / leverage, 2)
        row["notional_text"] = fmt(entry * quantity, 2)
        row["tp_text"] = fmt(item.get("take_profit") or 0, 6)
        row["sl_text"] = fmt(item.get("stop_loss") or 0, 6)
        row["fee_text"] = fmt(estimated_fee, 4)
        row["quantity_text"] = self.tr_.format_number(item.get("quantity") or 0.0, 4)
        row["entry_text"] = self.tr_.format_number(item.get("entry_price") or 0.0, 4)
        exit_price = item.get("exit_price")
        if exit_price:
            row["exit_text"] = self.tr_.format_number(exit_price, 4)
        else:
            # معاملهٔ باز: قیمت زندهٔ بازار نمایش داده می‌شود تا ستون
            # «خروج» یک خط تیرهٔ بی‌معنا نباشد و کاربر ببیند معامله‌اش
            # همراه بازار حرکت می‌کند.
            live = float(item.get("last_price") or 0.0) or self._last_price(
                str(item.get("symbol") or "")
            )
            row["exit_text"] = (
                self.tr_.format_number(live, 4) if live > 0 else "—"
            )
        row["current_text"] = row["exit_text"]
        row["leverage_text"] = f"{self.tr_.format_number(item.get('leverage') or 1.0, 0)}x"
        pnl = float(item.get("pnl") or 0.0)
        row["pnl_text"] = ("+" if pnl >= 0 else "") + self.tr_.format_number(pnl, 2)
        percent = float(item.get("pnl_percent") or 0.0)
        row["pnl_percent_text"] = ("+" if percent >= 0 else "") + self.tr_.format_number(percent, 2) + "%"
        return row

    def _digits(self, value: Any) -> str:
        """تبدیل عدد به رشته با ارقام زبان جاری."""
        text = str(value)
        return self.tr_.to_persian_digits(text) if self.tr_.language == "fa" else text

    def _localized_datetime(self, moment: Any) -> str:
        """
        قالب‌بندی تاریخ و زمان با ارقام زبان جاری.

        در فارسی ارقام باید فارسی باشند وگرنه جدول دورگه به نظر می‌رسد.
        """
        if not moment:
            return "—"
        text = format_datetime(moment)
        return self.tr_.to_persian_digits(text) if self.tr_.language == "fa" else text

    def _trade_metrics(self, statistics: dict[str, Any]) -> dict[str, str]:
        """قالب‌بندی نوار معیارهای صفحهٔ معاملات."""
        return {
            "total": self.tr_.format_number(statistics.get("total", 0), 0),
            "win_rate": self.tr_.format_number(statistics.get("win_rate", 0.0), 1) + "%",
            "total_pnl": self._money(statistics.get("total_pnl", 0.0)),
            "profit_factor": self.tr_.format_number(statistics.get("profit_factor", 0.0), 2),
        }

    def _wallet_split_text(self, by_wallet: dict[str, Any]) -> str:
        """
        متن کوتاه «اسپات x • فیوچرز y» برای زیر کارت موجودی.

        وقتی کاربر فقط یکی از دو کیف پول را دارد چیزی نشان داده نمی‌شود
        تا فضای کارت بی‌دلیل شلوغ نشود.
        """
        spot = (by_wallet or {}).get("spot") or {}
        futures = (by_wallet or {}).get("futures") or {}
        if not futures:
            return ""

        def total_of(source: dict[str, Any]) -> float:
            """ارزش تتری یک کیف پول با قیمت‌های همین حالا."""
            amount = 0.0
            for asset, quantity in source.items():
                code = str(asset).upper()
                price = (
                    1.0
                    if code in ("USDT", "USD")
                    else (self._last_price(f"{code}/USDT") or self._asset_prices.get(code, 0.0))
                )
                try:
                    amount += float(quantity or 0.0) * float(price)
                except (TypeError, ValueError):
                    continue
            return amount

        return "{spot} • {futures}".format(
            spot=f"{self.tr_.tr('wallet.spot')}: {self._money(total_of(spot))}",
            futures=f"{self.tr_.tr('wallet.futures')}: {self._money(total_of(futures))}",
        )

    def _wallet_assets(
        self,
        balances: dict[str, Any],
        total: float,
        by_wallet: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        ساخت ردیف‌های جدول دارایی از موجودی خام.

        `by_wallet` تفکیک اسپات/فیوچرز است تا کاربر بداند هر دارایی در کدام
        کیف پول صرافی نگهداری می‌شود.
        """
        spot = dict((by_wallet or {}).get("spot") or {})
        futures = dict((by_wallet or {}).get("futures") or {})
        assets: list[dict[str, Any]] = []
        for name, amount in sorted(
            (balances or {}).items(), key=lambda pair: -float(pair[1] or 0.0)
        ):
            quantity = float(amount or 0.0)
            if quantity <= 0:
                continue
            code = name.upper()
            if code in ("USDT", "USD"):
                price = 1.0
            else:
                # اول جدول بازارها، بعد قیمت‌های گرفته‌شده در همگام‌سازی
                price = self._last_price(f"{name}/USDT") or self._asset_prices.get(code, 0.0)
            # اگر قیمت هنوز نرسیده باشد، «۰ دلار» نمایش نمی‌دهیم؛ خط تیره
            # صادقانه‌تر از عددی است که کاربر آن را ارزش واقعی می‌پندارد.
            known = price > 0
            value = quantity * price if known else 0.0
            share = (value / total * 100.0) if (known and total) else 0.0
            change = self._change_percent(f"{name}/USDT") if known else None
            in_spot = float(spot.get(name, spot.get(code, 0.0)) or 0.0) > 0
            in_futures = float(futures.get(name, futures.get(code, 0.0)) or 0.0) > 0
            if in_spot and in_futures:
                wallet_text = self.tr_.tr("wallet.spot_futures")
            elif in_futures:
                wallet_text = self.tr_.tr("wallet.futures")
            elif in_spot:
                wallet_text = self.tr_.tr("wallet.spot")
            else:
                wallet_text = ""

            assets.append(
                {
                    "asset": name.upper(),
                    "wallet_text": wallet_text,
                    "amount": quantity,
                    "amount_text": self.tr_.format_number(quantity, 6),
                    "value": value,
                    "value_text": self._money(value) if known else "—",
                    "share": share,
                    "share_text": (self.tr_.format_number(share, 1) + "%") if known else "—",
                    "change": change,
                    "change_text": self._change_text(f"{name}/USDT") if known else "—",
                }
            )
        return assets

    async def _ticker_price(self, symbol: str) -> float:
        """قیمت آخرین معاملهٔ یک نماد؛ نبودِ بازار خطا محسوب نمی‌شود."""
        try:
            ticker = await self.app.market.get_ticker(symbol, max_age_seconds=60.0)
        except Exception as exc:  # noqa: BLE001
            logger.debug("No market for %s: %s", symbol, exc)
            return 0.0
        return float(getattr(ticker, "last_price", 0.0) or 0.0)

    async def _usdt_price(self, code: str) -> float:
        """
        ارزش تتری یک دارایی، در صورت لزوم از راه ارز واسط.

        اگر «X/USDT» وجود نداشته باشد، «X/BTC» (یا ETH/USDC) را در قیمت
        تتری همان واسط ضرب می‌کنیم. بدون این کار، دارایی‌هایی که فقط با
        بیت‌کوین جفت دارند بی‌ارزش به نظر می‌رسند.
        """
        # خودِ تتر بازار «USDT/USDT» ندارد؛ این نگهبان باید داخل همین متد
        # باشد نه فقط در فراخوان، وگرنه هر تماس مستقیم صفر می‌گیرد.
        if code in ("USDT", "USD"):
            return 1.0

        direct = await self._ticker_price(f"{code}/USDT")
        if direct > 0:
            return direct

        for bridge in ("BTC", "ETH", "USDC"):
            if bridge == code:
                continue
            pair_price = await self._ticker_price(f"{code}/{bridge}")
            if pair_price <= 0:
                continue
            bridge_price = (
                1.0
                if bridge == "USDC"
                else (
                    self._asset_prices.get(bridge)
                    or self._last_price(f"{bridge}/USDT")
                    or await self._ticker_price(f"{bridge}/USDT")
                )
            )
            if bridge_price > 0:
                self._asset_prices[bridge] = bridge_price
                return pair_price * bridge_price
        return 0.0



    def _remember_price(self, symbol: str, price: float) -> None:
        """نگه داشتن آخرین قیمت، حتی اگر پایش معاملات هنوز شروع نشده باشد."""
        if not hasattr(self, "_live_prices"):
            self._live_prices = {}
        if price > 0:
            self._live_prices[str(symbol).upper()] = float(price)

    def _auto_economics_text(self) -> str:
        """یک خط کارمزد و هدف خالص برای برچسب وضعیت موجود."""
        try:
            from trading.micro_plan import plan_levels

            config = self._auto_trade_config()
            plan = plan_levels(
                config.margin_per_trade,
                config.leverage,
                config.target_profit,
                config.max_loss,
                config.fee_rate,
            )
            return self.tr_.tr(
                "trades.auto.economics",
                notional=f"{plan.notional:.0f}",
                fee=f"{plan.round_trip_fee:.2f}",
                target=f"{plan.net_target:.2f}",
                gross=f"{plan.gross_target:.2f}",
            )
        except Exception:  # noqa: BLE001
            return ""

    def _auto_trade_config(self) -> Any:
        """پیکربندی موتور خودکار از تنظیم‌های ذخیره‌شده."""
        from trading.scalp_service import ScalpService

        return ScalpService(self.app).build_trader_config()

    # ------------------------------------------------------------------
    # ترمینال معاملهٔ خودکار (v2.0) — کش تیک، نردبان، AI، داشبورد
    # ------------------------------------------------------------------
    def _ensure_tick_engine(self) -> Any:
        """
        ساخت (یک‌بار) کش تیک و اتصال آن به جریان وب‌سوکت.

        هر تیک صرافی با سه مهر زمانی (صرافی/دریافت/پردازش) ثبت
        می‌شود؛ سن داده و تأخیر از همین‌جا حساب می‌شود (خواستهٔ §۶).
        شنونده روی نخ asyncio صدا زده می‌شود و فقط دادهٔ خام را
        ثبت می‌کند — هیچ ویجتی لمس نمی‌شود.
        """
        existing = getattr(self, "_tick_engine", None)
        if existing is not None:
            return existing

        from trading.price_cache import TickEngine

        stale_after = float(
            self.app.settings.get("scalp.stale_after_seconds", 10.0) or 10.0
        )
        engine = TickEngine(stale_after_seconds=max(1.0, stale_after))
        self._tick_engine = engine

        market = self.app.market
        if market is not None:
            market.add_ticker_listener(
                lambda ticker: self._on_market_ticker(ticker) if self.app.market is market else None
            )

        # نوسازی دوره‌ای دفتر سفارش برای Bid/Ask — تیک وب‌سوکتِ این
        # صرافی Bid/Ask ندارد؛ دفتر واقعی جداگانه خوانده و روی کش
        # تیک لایه می‌شود.
        self._orderbook_timer = QTimer(self.window)
        self._orderbook_timer.setInterval(ORDERBOOK_REFRESH_MS)
        self._orderbook_timer.timeout.connect(self._refresh_orderbooks)
        self._orderbook_timer.start()
        return engine

    def _on_market_ticker(self, ticker: Any) -> None:
        """تیک خام صرافی → کش تیک (نخ asyncio؛ بدون ویجت)."""
        engine = getattr(self, "_tick_engine", None)
        if engine is None:
            return
        try:
            engine.record(
                str(getattr(ticker, "symbol", "") or ""),
                float(getattr(ticker, "last_price", 0.0) or 0.0),
                source="websocket",
                exchange_ts=int(getattr(ticker, "timestamp", 0) or 0),
                change_percent=float(getattr(ticker, "change_percent", 0.0) or 0.0),
            )
        except Exception:  # noqa: BLE001 - تیک بد نباید جریان را ببندد
            logger.debug("Tick record failed", exc_info=True)

    def _refresh_orderbooks(self) -> None:
        """
        خواندن دفتر سفارش نمادهای مهم (نخ پس‌زمینه).

        فقط نمادهای دارای موقعیت باز یا پنل پیش‌بینی/حالت Selected —
        نه کل بازار؛ فشار شبکه کنترل‌شده می‌ماند.
        """
        if self.app.market is None or getattr(self, "runner", None) is None:
            return
        symbols = list(dict.fromkeys(self._stream_symbols()))
        if not symbols:
            return

        async def refresh() -> None:
            market = self.app.market
            for symbol in symbols[:12]:
                try:
                    book = await market.get_orderbook(symbol, depth=5)
                except Exception:  # noqa: BLE001
                    continue
                engine = getattr(self, "_tick_engine", None)
                if engine is not None and book is not None and market is self.app.market:
                    engine.record_book(symbol, book)

        self.runner.submit(
            "terminal-orderbook",
            refresh(),
            on_error=lambda message, exc=None: logger.debug(
                "Orderbook refresh failed: %s", message
            ),
        )

    def _auto_selected_symbols(self) -> list[str] | None:
        """نمادهای حالت Selected؛ None یعبی حالت selected فعال نیست."""
        engine_mode = str(
            self.app.settings.get("scalp.engine_mode", "scan") or "scan"
        ).strip().lower()
        if engine_mode != "selected":
            return None
        raw = str(self.app.settings.get("scalp.selected_symbols", "") or "")
        items = [
            item.strip().upper()
            for item in raw.replace(";", ",").split(",")
            if item.strip()
        ]
        seen: list[str] = []
        for item in items:
            if item not in seen:
                seen.append(item)
        return seen

    def _portfolio_snapshot(self) -> dict[str, Any]:
        """
        وضعیت پرتفوی برای موتور و تصمیم‌ساز AI.

        موجودی از حساب متصل می‌آید؛ اگر حسابی نباشد از مجموع معاملات
        کاغذی (صفر در بدترین حالت) — هیچ عددی از بیرون ساخته نمی‌شود.
        """
        engine = getattr(self, "_auto_trader_engine", None)
        managed = {t.trade_id: t for t in engine.open_trades} if engine else {}
        used_margin = sum(t.used_margin() for t in managed.values())
        open_count = len(managed)
        try:
            rows = self.app.trade_repository.open_trades(self.app.auth.user_id)
            for row in rows:
                if row.get("id") in managed:
                    continue
                open_count += 1
                used_margin += float(row.get("entry_price") or 0) * float(row.get("quantity") or 0) / float(row.get("leverage") or 1)
        except Exception:
            logger.debug("Portfolio records unavailable", exc_info=True)
        balance = 0.0
        try:
            user_id = self.app.auth.user_id
            account = (
                self.app.exchange_accounts.default_account(user_id)
                if user_id is not None
                else None
            )
            if account is not None:
                balance = float(account.get("total_value_usdt") or 0.0)
        except Exception:  # noqa: BLE001
            pass
        stats = getattr(self, "_terminal_stats", {}) or {}
        return {
            "balance": balance,
            "used_margin": used_margin,
            "available_margin": max(0.0, balance - used_margin),
            "open_count": open_count,
            "daily_pnl": stats.get("daily_pnl", 0.0),
            "win_rate": stats.get("win_rate", 0.0),
        }

    def _cached_prediction_dict(self, symbol: str) -> dict[str, Any] | None:
        """گزارش کش‌شدهٔ موتور پیش‌بینی برای یک نماد (بدون بازمحاسبه)."""
        engine = getattr(self.app, "prediction_engine", None)
        if engine is None:
            return None
        try:
            report = engine.report(str(symbol or "").upper())
        except Exception:  # noqa: BLE001
            return None
        if report is None:
            return None
        try:
            return report.to_dict()
        except Exception:  # noqa: BLE001
            return None

    def _prediction_direction(self, symbol: str) -> str:
        """
        جهت فعلی پیش‌بینی نماد (LONG/SHORT/"") برای ابطال سیگنال.

        افق مرجع همان ۱۵ دقیقه است؛ اگر گزارش کش‌شده نباشد، رشتهٔ خالی
        برمی‌گردد — یعنی «نمی‌دانم» و معامله بسته نمی‌شود.
        """
        payload = self._cached_prediction_dict(symbol)
        if not payload:
            return ""
        from trading.ai_decider import direction_from_horizon, pick_horizon

        horizon = pick_horizon(payload)
        return direction_from_horizon(horizon) if horizon else ""

    def change_auto_engine_mode(self, mode: str) -> None:
        """تغییر حالت موتور (Selected/Scan/AI) از صفحهٔ معاملات."""
        value = str(mode or "scan").strip().lower()
        if value not in ("selected", "scan", "ai"):
            return
        try:
            self.app.settings.set("scalp.engine_mode", value)
        except Exception as exc:  # noqa: BLE001
            self._on_error(self.tr_.tr("common.state.error"), exc)
            return
        engine = getattr(self, "_auto_trader_engine", None)
        if engine is not None:
            engine.apply_config(self._auto_trade_config())
        self._update_streamed_symbols()
        self._toast(self.tr_.tr("trades.auto.mode_changed", mode=value), level="info")

    def on_auto_symbol_selected(self, symbol: str) -> None:
        """نماد نمودار/پیش‌بینی ترمینال عوض شد — تیک، گزارش و کندل بده."""
        clean = str(symbol or "").strip().upper()
        self._auto_prediction_symbol = clean
        self._auto_prediction_payload = None
        if clean:
            self._update_streamed_symbols()
            self._run_auto_prediction(clean)
            self._load_terminal_chart(clean, self._auto_timeframe())

    def _auto_timeframe(self) -> str:
        """تایم‌فریم فعلی نمودار ترمینال (پیش‌فرض ۱۵ دقیقه — ستاپ اسکلپ)."""
        tf = str(getattr(self, "_terminal_timeframe", "") or "15m")
        return tf if tf in ("1m", "5m", "15m", "1h", "4h") else "15m"

    def on_auto_timeframe_changed(self, timeframe: str) -> None:
        """تایم‌فریم نمودار ترمینال عوض شد — کندل تازه و اشتراک سوکت."""
        tf = str(timeframe or "15m").strip().lower()
        if tf not in ("1m", "5m", "15m", "1h", "4h"):
            return
        self._terminal_timeframe = tf
        symbol = str(getattr(self, "_auto_prediction_symbol", "") or "").strip().upper()
        if not symbol:
            return
        self._load_terminal_chart(symbol, tf)

    def _load_terminal_chart(self, symbol: str, timeframe: str) -> None:
        """
        کندل‌های واقعی نمودار ترمینال (مرجع UI — §۳).

        کندل + حجم از همان موتور بازار تحلیل می‌آید؛ هیچ داده‌ای
        ساخته نمی‌شود. دادهٔ کم → پیام صادقانهٔ «بدون داده».
        """
        page = self.trades
        if self.app.market is None or not symbol:
            page.price_chart.show_placeholder()
            return

        async def load() -> list:
            return list(
                await self.app.market.get_candles(symbol, timeframe, limit=300)
            )

        def apply(candles: list) -> None:
            # اگر کاربر نماد/تایم‌فریم را عوض کرده، نتیجهٔ کهنه را نکش
            if symbol != str(
                getattr(self, "_auto_prediction_symbol", "") or ""
            ).upper() or timeframe != self._auto_timeframe():
                return
            if candles:
                page.set_chart_candles(candles, timeframe, symbol)
                # کندل‌ها برای محاسبهٔ اندیکاتورها نگه داشته می‌شوند
                self._terminal_candles = list(candles)
                self._mark_terminal_chart()
                self._apply_chart_indicators()
            else:
                page.price_chart.show_placeholder()

        self.runner.submit(
            "terminal-chart",
            load(),
            on_success=apply,
            on_error=lambda message, exc=None: logger.debug(
                "Terminal chart load failed: %s", message
            ),
        )

    def _mark_terminal_chart(self) -> None:
        """
        خطوط موقعیت و پیش‌بینی روی نمودار ترمینال (§۳).

        ورود/SL مؤثر/TP از موقعیت‌های واقعی بازِ همان نماد؛ اگر
        موقعیتی نیست، خطوط پاک می‌شوند تا نمودار دروغ نگوید.
        """
        page = self.trades
        symbol = str(getattr(self, "_auto_prediction_symbol", "") or "").upper()
        engine = getattr(self, "_auto_trader_engine", None)
        entry = stop = None
        targets: list[float] = []
        if engine is not None and symbol:
            for managed in engine.open_trades:
                if managed.symbol == symbol:
                    entry = managed.entry_price
                    stop = (
                        managed.effective_stop
                        if managed.effective_stop > 0
                        else managed.stop_price
                    )
                    if managed.target_price > 0:
                        targets.append(managed.target_price)
                    break
        # خطوط مهم پیش‌بینی: P50 افق مرجع همان نماد (منبع واحد)
        payload = getattr(self, "_auto_prediction_payload", None)
        if payload:
            horizons = payload.get("horizons") or []
            if horizons:
                quantiles = (horizons[0] or {}).get("quantiles") or {}
                p50 = quantiles.get("p50")
                if p50 and (entry is None or abs(float(p50) - entry) > 1e-9):
                    targets.append(float(p50))
        page.mark_chart_position(entry, stop, targets)

    def on_opportunity_enter(self, symbol: str) -> None:
        """
        ورود دستی به فرصت انتخاب‌شدهٔ جدول (§۵ — ستون Action).

        نامزدِ ذخیره‌شده از همان مسیر `open_trade` می‌گذرد؛ همهٔ
        دروازه‌ها (دادهٔ تازه، اسپرد، نقدینگی، روند، ظرفیت) دوباره
        سنجیده می‌شوند و ردِ مجدد ممکن و صادقانه است.
        """
        engine = getattr(self, "_auto_trader_engine", None)
        clean = str(symbol or "").strip().upper()
        if getattr(self, "_exchange_switching", False):
            self._toast(self.tr_.tr("trades.auto.exchange_locked"), level="warning")
            return
        key = f"auto-manual-enter-{clean}"
        runner = getattr(self, "runner", None)
        if runner is not None and key in set(runner.active_keys()):
            return
        candidate = engine.opportunity_candidate(clean) if engine is not None else None
        if candidate is None:
            # نامزد پویش پس‌زمینه (v2.2) — همان پروتکل موتور
            candidate = (getattr(self, "_watch_candidates", {}) or {}).get(clean)
        if candidate is None:
            self._toast(
                self.tr_.tr("trades.auto.blocked", reason="no_candidate"),
                level="warning",
            )
            return
        if engine is None:
            # موتور فقط وقتی نامزد واقعی هست ساخته می‌شود.
            engine = self._auto_trader()

        def done(result: Any) -> None:
            if result is not None:
                self._toast(
                    self.tr_.tr("trades.auto.opened", symbol=clean,
                                price=f"{getattr(result, 'entry_price', 0):,.6g}"),
                    level="info",
                )
                self._go_to("nav.trades")
                self.trades.show_open_history()
            else:
                self._toast(
                    self.tr_.tr(
                        "trades.auto.blocked", reason=engine.rejection_reason(clean)
                    ),
                    level="warning",
                )
            self.refresh_trades()

        self._toast(self.tr_.tr("trades.auto.entering"), level="info")
        self.runner.submit(
            key,
            engine.open_trade(candidate),
            on_success=done,
            on_error=self._on_error,
        )

    # ------------------------------------------------------------------
    # v2.2 — اندیکاتورهای نمودار ترمینال
    # ------------------------------------------------------------------
    def on_chart_indicators_changed(self, state: dict) -> None:
        """تیک اندیکاتور → محاسبه از کندل‌های واقعی همان نمودار."""
        self._indicator_state = dict(state or {})
        self._apply_chart_indicators()

    def _apply_chart_indicators(self) -> None:
        """
        ترسیم/حذف اندیکاتورهای فعال روی نمودار ترمینال.

        محاسبه از همان کتابخانهٔ اندیکاتورهای تحلیل (منبع واحد) روی
        کندل‌های واقعیِ بارگذاری‌شده؛ دادهٔ کم → پیام صادقانه.
        """
        page = self.trades
        state = getattr(self, "_indicator_state", {}) or {}
        candles = getattr(self, "_terminal_candles", None) or []
        timestamps = [float(c.timestamp) for c in candles]

        specs = (
            ("ema", "EMA 21", ("ema",)),
            ("sma", "SMA 50", ("sma",)),
            ("bb", "BB upper", ("upper",)),
            ("bb", "BB lower", ("lower",)),
        )
        for key, name, output_keys in specs:
            if state.get(key):
                self._draw_terminal_indicator(
                    page, key, name, output_keys, candles, timestamps
                )
            else:
                page.price_chart.remove_overlay(name)

    def _draw_terminal_indicator(
        self,
        page: Any,
        key: str,
        name: str,
        output_keys: tuple[str, ...],
        candles: list,
        timestamps: list[float],
    ) -> None:
        """محاسبه و ترسیم یک اندیکاتور روی نمودار ترمینال."""
        from indicators.trend import EMAIndicator, SMAIndicator
        from indicators.volatility import BollingerBandsIndicator

        try:
            indicator = {
                "ema": EMAIndicator,
                "sma": SMAIndicator,
                "bb": BollingerBandsIndicator,
            }[key]()
            result = indicator.calculate(candles, self._auto_timeframe())
            for output_key in output_keys:
                series = result.values.get(output_key)
                if series:
                    page.price_chart.set_overlay(
                        name, timestamps, list(series)
                    )
        except Exception as exc:  # noqa: BLE001 - دادهٔ کم و …
            self._toast(
                self.tr_.tr("trades.auto.indicator_failed", name=name),
                level="warning",
            )
            logger.debug("Terminal indicator %s failed: %s", name, exc)

    # ------------------------------------------------------------------
    # v2.2 — نظر هوش مصنوعی روی پنل تصمیم
    # ------------------------------------------------------------------
    def on_ai_opinion_requested(self, symbol: str) -> None:
        """
        درخواست تحلیل لحظه‌ای عامل هوش مصنوعی برای نماد نمودار.

        همان عامل خودمختار صفحهٔ تحلیل (منبع واحد) روی همان نماد و
        تایم‌فریمِ نمودار ترمینال؛ داده از ابزارهای واقعی می‌آید و
        مدل فقط توضیح می‌دهد — عددسازی ممنوع (قواعد سند حاکم).
        """
        page = self.trades
        agent = self.app.autonomous_agent()
        if agent is None:
            page.set_ai_opinion(
                self.tr_.tr("analysis.ai_disabled"), failed=True
            )
            return
        symbol = str(symbol or "").strip().upper()
        timeframe = self._auto_timeframe()

        def apply(outcome: Any) -> None:
            page.set_ai_opinion(self._format_agent_outcome(outcome))

        def failed(message: str, _exc: Exception | None = None) -> None:
            page.set_ai_opinion(
                self.tr_.tr("analysis.ai_failed", error=message), failed=True
            )

        self.runner.submit(
            "terminal-ai-opinion",
            agent.run(symbol, timeframe=timeframe),
            on_success=apply,
            on_error=failed,
        )

    # ------------------------------------------------------------------
    # v2.2 — تنظیمات پویش و نمادهای انتخابی
    # ------------------------------------------------------------------
    def on_scanner_settings_saved(self, values: dict) -> None:
        """ذخیرهٔ تنظیمات پویش (کلیدهای scalp.watch_*) + ریست تایمر."""
        self.save_auto_trade_settings(dict(values or {}))
        # شمارنده را صفر کن تا پویش تازه با فاصلهٔ تازه شروع شود
        self._terminal_stats_tick = 0

    def on_selected_symbols_saved(self, symbols: list) -> None:
        """
        نمادهای انتخابیِ تازه → تنظیمات + فهرست علاقه‌مندی‌ها.

        خواستهٔ کاربر: همین لیست در دیتابیس به‌عنوان «نمادهای
        مورد علاقهٔ من» ذخیره شود و همه‌جا (داشبورد/تحلیل/سیگنال)
        قابل استفاده باشد — همان فهرست پیگیری (watchlist) سیستم.
        """
        chosen = [
            str(s).strip().upper() for s in symbols or [] if str(s).strip()
        ]
        try:
            self.app.settings.set("scalp.selected_symbols", ",".join(chosen))
        except Exception as exc:  # noqa: BLE001
            self._on_error(self.tr_.tr("common.state.error"), exc)
            return

        # همگام‌سازی با فهرست پیگیری دیتابیس
        try:
            repository = self.app.symbol_repository
            exchange = str(self.app.settings.active_exchange or "")
            current = set(repository.get_watchlist())
            for symbol in chosen:
                if symbol not in current:
                    repository.add_to_watchlist(symbol, exchange)
            for symbol in current - set(chosen):
                repository.remove_from_watchlist(symbol, exchange)
        except Exception:  # noqa: BLE001 - دیتابیس نباید ذخیره را بگیرد
            logger.debug("Watchlist sync failed", exc_info=True)

        self.refresh_auto_config()
        self._update_streamed_symbols()
        self._toast(
            self.tr_.tr("trades.auto.picker_saved", count=len(chosen)),
            level="success",
        )

    # ------------------------------------------------------------------
    # v2.2 — پویش دائمی بازار برای جدول فرصت‌ها
    # ------------------------------------------------------------------
    def _run_watch_scan(self) -> None:
        """
        پویش پس‌زمینهٔ بازار حتی وقتی موتور معامله خاموش است.

        خواستهٔ کاربر: «جدول فرصت‌ها همیشه خالی است» — چون فقط هنگام
        اجرای موتور پر می‌شد. حالا همان پویش AI (موتور واحد) هر چند
        ثانیه روی نمادهای پویش اجرا می‌شود و نامزدها را زنده نگه
        می‌دارد؛ اجرا/عدم‌اجرای معامله همچنان فقط با موتور روشن.
        """
        if getattr(self, "_watch_scan_running", False):
            return
        if self.app.market is None:
            return
        self._watch_scan_running = True
        bound_market = self.app.market

        def apply(candidates: list) -> None:
            self._watch_scan_running = False
            if self.app.market is not bound_market:
                return
            self._watch_candidates = {
                str(getattr(c, "symbol", "") or ""): c for c in candidates or []
            }
            self._watch_rows = self._watch_rows_from_candidates(candidates or [])
            engine = getattr(self, "_auto_trader_engine", None)
            if not (engine is not None and engine.is_running and engine.opportunities()):
                self.trades.set_opportunities(self._watch_rows)

        def failed(_message: str, _exc: Exception | None = None) -> None:
            self._watch_scan_running = False

        self.runner.submit(
            "terminal-watch-scan",
            self._ai_candidate_scan(),
            on_success=apply,
            on_error=failed,
        )

    def _watch_rows_from_candidates(self, candidates: list) -> list[dict[str, Any]]:
        """
        تبدیل نامزدهای پویش به ردیف‌های جدول فرصت‌ها.

        «قابل ورود» یعنی اطمینان ≥ آستانهٔ تنظیم‌شدهٔ کاربر و اسپرد
        در محدوده — ورودِ واقعی همچنان دروازه‌های موتور را می‌گذرد.
        """
        min_confidence = float(
            self.app.settings.get("scalp.watch_min_confidence", 70) or 70
        )
        max_spread = float(
            self.app.settings.get("scalp.watch_max_spread", 0.25) or 0.25
        )
        cap = max(5, int(self.app.settings.get("scalp.watch_row_cap", 30) or 30))
        rows: list[dict[str, Any]] = []
        for candidate in candidates or []:
            symbol = str(getattr(candidate, "symbol", "") or "")
            if not symbol:
                continue
            score = float(getattr(candidate, "score", 0.0) or 0.0)
            spread = float(getattr(candidate, "spread_percent", 0.0) or 0.0)
            optional = lambda name: (  # noqa: E731 - خوانایی در نگاشت
                getattr(candidate, name, None)
            )
            rows.append(
                {
                    "symbol": symbol,
                    "direction": str(getattr(candidate, "direction", "") or ""),
                    "confidence": score,
                    "probability": optional("probability"),
                    "expected_move": optional("expected_move_percent"),
                    "trend": "",
                    "mtf": str(getattr(candidate, "mtf", "") or ""),
                    "risk": optional("risk_reward"),
                    "spread": spread,
                    "liquidity": float(
                        getattr(candidate, "turnover_24h", 0.0) or 0.0
                    ),
                    "score": score,
                    "entry": optional("entry_price"),
                    "tp": optional("take_profit"),
                    "sl": optional("stop_loss"),
                    "leverage": optional("leverage"),
                    "margin": optional("margin"),
                    "prediction": str(getattr(candidate, "prediction", "") or ""),
                    "decision": "watch",
                    "reason": "؛ ".join(
                        str(r) for r in list(getattr(candidate, "reasons", []) or [])[:2]
                    ),
                    "actionable": score >= min_confidence and spread <= max_spread,
                }
            )
        rows.sort(key=lambda row: float(row.get("score", 0.0) or 0.0), reverse=True)
        return rows[:cap]

    def _run_auto_prediction(self, symbol: str) -> None:
        """
        گزارش پیش‌بینی برای پنل تصمیم ترمینال (خواستهٔ §۲).

        همان موتور واحد؛ فقط با تایم‌فریم‌های نردبان (4h/1h/15m/5m)
        تا رژیم همهٔ پله‌ها موجود باشد. None صادقانه «داده نیست» است.
        """
        symbol = str(symbol or "").strip().upper()
        page = self.trades
        if not symbol or self.app.market is None:
            page.update_prediction_summary(None)
            return

        async def compute() -> dict[str, Any] | None:
            engine = self.app.prediction_engine
            if engine is None:
                return None
            report = await engine.assess(
                symbol, timeframes=("5m", "15m", "1h", "4h")
            )
            return report.to_dict() if report is not None else None

        def apply(payload: dict[str, Any] | None) -> None:
            if str(self._auto_prediction_symbol or "").upper() != symbol:
                return  # کاربر نماد را عوض کرده؛ گزارش کهنه را نشان نده
            self._auto_prediction_payload = payload
            page.update_prediction_summary(self._enrich_auto_prediction(symbol, payload))

        self.runner.submit(
            "auto-prediction",
            compute(),
            on_success=apply,
            on_error=lambda message, exc=None: logger.debug(
                "Auto prediction failed: %s", message
            ),
        )

    def _enrich_auto_prediction(
        self, symbol: str, payload: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """تزریق قیمت زنده و جهت 1m (از تیک‌ها) به گزارش موتور."""
        if not payload:
            return payload
        result = dict(payload)
        tick_engine = getattr(self, "_tick_engine", None)
        quote = tick_engine.get(symbol) if tick_engine is not None else None
        if quote is not None:
            result["live_price"] = quote.last
            # پلهٔ 1m از خود تیک‌ها — جهت میکرو برای ورود (خواستهٔ §۴)
            history = tick_engine.history(symbol, limit=20)
            prices = [price for _, price in history]
            if len(prices) >= 5:
                average = sum(prices) / len(prices)
                last = prices[-1]
                direction = (
                    1 if last > average * 1.0002
                    else (-1 if last < average * 0.9998 else 0)
                )
                regimes = dict(result.get("regimes") or {})
                regimes["1m"] = {"regime": "live_tick", "direction": direction}
                result["regimes"] = regimes
        return result

    def close_auto_position(self, trade_id: int) -> None:
        """تمام دکمه‌های خروج از مسیر مشترک با محافظ قیمت تازه عبور می‌کنند."""
        self.close_paper_trade(trade_id)

    def emergency_exit_positions(self) -> None:
        """خروج اضطراری همهٔ موقعیت‌های موتور (دکمهٔ پانیک)."""
        engine = getattr(self, "_auto_trader_engine", None)
        if engine is None or not engine.open_trades:
            self._toast(self.tr_.tr("trades.no_open_trade_selected"), level="warning")
            return

        def done(_records: Any) -> None:
            self._toast(self.tr_.tr("trades.auto.emergency_done"), level="warning")
            self.refresh_trades()

        self.runner.submit(
            "auto-emergency",
            engine.emergency_exit_all("emergency"),
            on_success=done,
            on_error=self._on_error,
        )

    def _position_rows(self) -> list[dict[str, Any]]:
        """
        ردیف‌های جدول موقعیت‌های باز (خواستهٔ §۸).

        منبع: موقعیت‌های زندهٔ موتور (با Bid/Ask و سن داده از کش تیک)
        و در نبود موتور، معامله‌های بازِ مخزن. قالب‌بندی عدد اینجا
        انجام می‌شود تا صفحه فقط نمایش بدهد.
        """
        tick_engine = getattr(self, "_tick_engine", None)
        stale_after = float(
            self.app.settings.get("scalp.stale_after_seconds", 10.0) or 10.0
        )
        fmt = self.tr_.format_number
        rows: list[dict[str, Any]] = []

        def quote_for(symbol: str) -> Any:
            return tick_engine.get(symbol) if tick_engine is not None else None

        engine = getattr(self, "_auto_trader_engine", None)
        if engine is not None and engine.open_trades:
            for managed in engine.open_trades:
                quote = quote_for(managed.symbol)
                price = float(getattr(quote, "last", 0.0) or 0.0)
                if price <= 0:
                    price = self._cached_symbol_price(managed.symbol, max_age=30.0)
                if price <= 0:
                    price = managed.entry_price
                if quote is not None:
                    price = engine._exit_price_for(managed, quote)
                pnl = managed.net_unrealised(price)
                notional = managed.margin * managed.leverage
                age_ms = (
                    float(getattr(quote, "age_ms", -1.0))
                    if quote is not None else -1.0
                )
                stale = age_ms < 0 or age_ms > stale_after * 1000.0
                duration = int(
                    (datetime.now(UTC) - managed.opened_at).total_seconds()
                )
                exit_reason = ""
                if managed.trailing_active:
                    exit_reason = self.tr_.tr("trades.auto.pos_reason_trailing")
                elif managed.break_even_armed:
                    exit_reason = self.tr_.tr("trades.auto.pos_reason_breakeven")
                rows.append(
                    {
                        "id": managed.trade_id,
                        "symbol": managed.symbol,
                        "side": managed.side,
                        "side_text": self.tr_.tr(
                            f"trades.sides.{managed.side}", managed.side
                        ),
                        "quantity_text": fmt(managed.quantity, 6),
                        "entry_text": fmt(managed.entry_price, 4),
                        "current_text": fmt(price, 4),
                        "bid_text": fmt(float(getattr(quote, "bid", 0.0) or 0.0), 4)
                        if quote is not None and quote.bid > 0 else "—",
                        "ask_text": fmt(float(getattr(quote, "ask", 0.0) or 0.0), 4)
                        if quote is not None and quote.ask > 0 else "—",
                        "margin_text": fmt(managed.margin, 2),
                        "notional_text": fmt(notional, 2),
                        "leverage_text": f"{managed.leverage:g}×",
                        "tp_text": fmt(managed.target_price, 4),
                        "sl_text": fmt(managed.effective_stop, 4),
                        "pnl": pnl,
                        "fee_text": fmt(managed.unrealised(price) - pnl, 4),
                        "status": "open",
                        "pnl_text": f"{pnl:+.2f}",
                        "pnl_percent_text": (
                            f"{(pnl / managed.margin * 100):+.1f}٪"
                            if managed.margin > 0 else "—"
                        ),
                        "duration_text": f"{duration // 60}:{duration % 60:02d}",
                        "data_age_text": (
                            self.tr_.tr("trades.auto.stale_data")
                            if stale
                            else f"{fmt(age_ms, 0)} ms"
                            if age_ms >= 0
                            else "—"
                        ),
                        "exit_reason_text": exit_reason or "—",
                        "status_text": self.tr_.tr(
                            "trades.auto.mode_live" if managed.mode == "live"
                            else "trades.auto.mode_paper"
                        ),
                    }
                )

        existing_ids = {row["id"] for row in rows}
        try:
            for record in self.app.trade_repository.open_trades(self.app.auth.user_id):
                if record.get("id") in existing_ids:
                    continue
                symbol = str((record or {}).get("symbol") or "")
                quote = quote_for(symbol)
                price = float(getattr(quote, "last", 0.0) or 0.0)
                if price <= 0:
                    price = self._cached_symbol_price(symbol, max_age=30.0)
                entry = float((record or {}).get("entry_price") or 0.0)
                quantity = float((record or {}).get("quantity") or 0.0)
                side = str((record or {}).get("side") or "long")
                sign = 1.0 if side == "long" else -1.0
                from trading.trade_monitor import position_from_record
                position = position_from_record(record)
                pnl = position.unrealised(price)[0] if position is not None else 0.0
                margin = float((record or {}).get("margin") or 0.0)
                leverage = float((record or {}).get("leverage") or 1.0) or 1.0
                age_ms = (
                    float(getattr(quote, "age_ms", -1.0))
                    if quote is not None else -1.0
                )
                stale = age_ms < 0 or age_ms > stale_after * 1000.0
                rows.append(
                    {
                        "id": (record or {}).get("id"),
                        "symbol": symbol,
                        "side": side,
                        "side_text": self.tr_.tr(f"trades.sides.{side}", side),
                        "quantity_text": fmt(quantity, 6) if quantity else "—",
                        "entry_text": fmt(entry, 4) if entry else "—",
                        "current_text": fmt(price, 4) if price else "—",
                        "bid_text": fmt(float(getattr(quote, "bid", 0.0) or 0.0), 4)
                        if quote is not None and quote.bid > 0 else "—",
                        "ask_text": fmt(float(getattr(quote, "ask", 0.0) or 0.0), 4)
                        if quote is not None and quote.ask > 0 else "—",
                        "margin_text": fmt(margin, 2) if margin else "—",
                        "notional_text": fmt(margin * leverage, 2) if margin else "—",
                        "leverage_text": f"{leverage:g}×",
                        "tp_text": fmt(float((record or {}).get("take_profit") or 0.0), 4)
                        if (record or {}).get("take_profit") else "—",
                        "sl_text": fmt(float((record or {}).get("stop_loss") or 0.0), 4)
                        if (record or {}).get("stop_loss") else "—",
                        "pnl": pnl,
                        "pnl_text": f"{pnl:+.2f}",
                        "pnl_percent_text": (
                            f"{(pnl / margin * 100):+.1f}٪" if margin > 0 else "—"
                        ),
                        "duration_text": "—",
                        "data_age_text": (
                            self.tr_.tr("trades.auto.stale_data")
                            if stale
                            else f"{fmt(age_ms, 0)} ms"
                            if age_ms >= 0
                            else "—"
                        ),
                        "exit_reason_text": "—",
                        "status_text": str((record or {}).get("status") or "open"),
                    }
                )
        except Exception:  # noqa: BLE001
            logger.debug("Open positions unavailable", exc_info=True)
        return rows

    def _risk_panel_data(self, portfolio: dict, tick_stats: dict) -> dict[str, Any]:
        """
        داده‌های پنل ریسک (مرجع UI — §۱۱) — همه از منابع واقعی.

        زیان روزانه و سقف‌ها از موتور/تنظیم، افت سرمایه از منحنی
        سهام مخزن، اسپرد/کهداتی از کش تیک. حکم نهایی بدترین حالتِ
        خانه‌هاست؛ خودِ جلوی ورود را موتور می‌گیرد.
        """
        config = self._auto_trade_config()
        engine = getattr(self, "_auto_trader_engine", None)
        stats = getattr(self, "_terminal_stats", {}) or {}
        daily_pnl = float(stats.get("daily_pnl", 0.0) or 0.0)
        daily_limit = float(config.daily_loss_limit)
        loss_used = max(0.0, -daily_pnl) / daily_limit if daily_limit > 0 else 0.0

        # حداکثر افت از منحنی سهام واقعی مخزن
        max_drawdown = 0.0
        try:
            curve = self.app.trade_repository.equity_curve(
                user_id=self.app.auth.user_id,
                starting_balance=float(portfolio.get("balance", 0.0) or 0.0),
            )
            peak = None
            for _ts, value in curve or []:
                value = float(value or 0.0)
                peak = value if peak is None else max(peak, value)
                if peak > 0:
                    max_drawdown = max(max_drawdown, (peak - value) / peak)
        except Exception:  # noqa: BLE001
            pass

        # ریسک اسپرد: بدترین اسپرد میان نمادهای دارای موقعیت/پنل
        tick_engine = getattr(self, "_tick_engine", None)
        worst_spread = 0.0
        stale_count = 0
        symbols = set()
        if engine is not None:
            symbols.update(t.symbol for t in engine.open_trades)
        panel_symbol = str(
            getattr(self, "_auto_prediction_symbol", "") or ""
        ).upper()
        if panel_symbol:
            symbols.add(panel_symbol)
        for symbol in symbols:
            quote = tick_engine.get(symbol) if tick_engine is not None else None
            if quote is None:
                stale_count += 1
                continue
            worst_spread = max(worst_spread, float(quote.spread_percent or 0.0))
            if tick_engine.is_stale(symbol):
                stale_count += 1

        balance = float(portfolio.get("balance", 0.0) or 0.0)
        used = float(portfolio.get("used_margin", 0.0) or 0.0)
        margin_usage = (used / balance * 100.0) if balance > 0 else 0.0
        exposure = sum(
            float(t.margin * t.leverage)
            for t in (engine.open_trades if engine is not None else [])
        )
        open_count = int(portfolio.get("open_count", 0) or 0)

        spread_ok = worst_spread <= float(config.max_spread_percent)
        margin_ok = margin_usage <= float(config.max_total_margin_percent)
        data_ok = stale_count == 0
        loss_ok = loss_used < 1.0
        capacity_ok = open_count < int(config.max_concurrent)
        halted = engine is not None and bool(getattr(engine, "halted_reason", ""))

        verdict_role = "chip_up"
        if halted or not (loss_ok and capacity_ok):
            verdict_role = "chip_down"
        elif not (spread_ok and margin_ok and data_ok):
            verdict_role = "chip_warn"
        verdict_key = {
            "chip_up": "trades.auto.risk_verdict_ok",
            "chip_warn": "trades.auto.risk_verdict_warn",
            "chip_down": "trades.auto.risk_verdict_block",
        }[verdict_role]

        return {
            "daily_loss": f"{daily_pnl:+.2f}$ / {daily_limit:g}$",
            "max_drawdown": f"{max_drawdown * 100:.1f}٪",
            "exposure": self._money(exposure),
            "margin_usage": f"{margin_usage:.0f}٪ / {float(config.max_total_margin_percent):g}٪",
            "open_trades": f"{open_count} / {int(config.max_concurrent)}",
            "risk_per_trade": f"{float(config.max_loss):g}$",
            "leverage": f"{float(config.leverage):g}×",
            "spread_risk": (
                f"{worst_spread:.3f}٪"
                if symbols
                else self.tr_.tr("common.none", default="—")
            ),
            "liquidity_risk": (
                "OK" if float(config.min_liquidity) > 0 else "—"
            ),
            "data_risk": (
                self.tr_.tr("trades.auto.stale_data") if stale_count
                else self.tr_.tr("common.online")
            ),
            "verdict": self.tr_.tr(verdict_key),
            "verdict_role": verdict_role,
        }

    def _terminal_timer_tick(self) -> None:
        """
        تیک ۱ ثانیه‌ای ترمینال (۲.۴.۲): وقتی صفحهٔ معاملات دیده نمی‌شود،
        نشاندن کارت‌ها، نمودار و جدول‌هایش فقط CPU و GIL را هدر می‌دهد.
        خروج موقعیت‌ها تیک‌محور است و به این نمایش وابسته نیست.
        """
        try:
            if not self.trades.isVisible():
                return
        except RuntimeError:
            return
        self._refresh_auto_terminal()

    def _refresh_auto_terminal(self) -> None:
        """
        تازه‌سازی ترمینال (تایمر ۱ ثانیه — فقط نمایش).

        خروج موقعیت‌ها تیک‌محور است و اینجا اتفاق نمی‌افتد؛ این متد
        فقط آخرین وضعیت واقعی را روی کارت‌ها، قرص‌های هدر، نمودار،
        پنل ریسک و جدول‌ها می‌نشیند.
        """
        try:
            page = self.trades
            engine = getattr(self, "_auto_trader_engine", None)
            tick_engine = self._ensure_tick_engine()

            # آمار سنگین (SQLite) هر ۵ تیک؛ بقیهٔ مقادیر هر تیک
            self._terminal_stats_tick += 1
            if self._terminal_stats_tick % 5 == 0:
                try:
                    statistics = self.app.trade_repository.statistics(
                        user_id=self.app.auth.user_id
                    )
                    realised = float(engine.realised_today) if engine is not None else 0.0
                    self._terminal_stats = {
                        "daily_pnl": realised
                        + float(statistics.get("total_pnl", 0.0) or 0.0),
                        "win_rate": float(statistics.get("win_rate", 0.0) or 0.0),
                    }
                except Exception:  # noqa: BLE001
                    pass
            stats = getattr(self, "_terminal_stats", {}) or {}

            portfolio = self._portfolio_snapshot()

            # رژیم و روند از گزارش کش‌شدهٔ همان موتور واحد
            auto_symbol = str(
                getattr(self, "_auto_prediction_symbol", "") or ""
            ).upper()
            payload = self._cached_prediction_dict(auto_symbol) if auto_symbol else None
            # روند (هم‌راستایی MTF) برای ردیف وضعیت زیر نمودار؛ رژیمِ
            # کامل در پنل پیش‌بینی همان نماد نمایش داده می‌شود.
            trend_text = "—"
            if payload:
                alignment = str((payload.get("multi_timeframe") or {}).get("alignment") or "")
                trend_text = (
                    self.tr_.tr(f"prediction.alignment.{alignment}", default=alignment)
                    if alignment else "—"
                )

            market = self.app.market
            websocket_ok = False
            if market is not None:
                from app.core.constants import ConnectionStatus

                websocket_ok = market.websocket_status is ConnectionStatus.CONNECTED
            tick_stats = tick_engine.stats()

            # --- قرص آخرین تیک: زمان واقعی پردازش آخرین تیک ---
            last_age = tick_stats.get("last_tick_age_ms")
            tick_pill = {
                "websocket": websocket_ok,
                "connections": market.stream_stats if market is not None else {},
                "avg_total_latency_ms": tick_stats.get("avg_total_latency_ms"),
                "stale": bool(
                    last_age is not None
                    and float(last_age) > tick_engine.stale_after_ms
                ),
                "last_tick_text": "",
            }
            if last_age is not None:
                processed_ago = float(last_age)
                processed_at = datetime.now() - timedelta(milliseconds=processed_ago)
                tick_pill["last_tick_text"] = self.tr_.tr(
                    "trades.auto.hdr_tick",
                    value=processed_at.strftime("%H:%M:%S") + f".{processed_at.microsecond // 1000:03d}",
                )

            # --- کارت‌های اطلاعاتی ۹گانه ---
            risk = self._risk_panel_data(portfolio, tick_stats)
            # ردیف‌های نمایشی: موتورِ در حال اجرا غنی‌تر است؛ وگرنه
            # نامزدهای پویش پس‌زمینه (v2.2) جدول را زنده نگه می‌دارند.
            engine_rows = engine.opportunities() if engine is not None else []
            if engine is not None and engine.is_running and engine_rows:
                opportunities = engine_rows
            else:
                opportunities = getattr(self, "_watch_rows", []) or []
            page.set_auto_dashboard(
                {
                    "balance": self._money(portfolio.get("balance", 0.0)),
                    "available": self._money(portfolio.get("available_margin", 0.0)),
                    "used": self._money(portfolio.get("used_margin", 0.0)),
                    "daily_pnl": f"{float(stats.get('daily_pnl', 0.0)):+.2f}$",
                    "open_count": self._digits(portfolio.get("open_count", 0)),
                    "opportunities": self._digits(len(opportunities)),
                    "win_rate": "{}٪".format(
                        self.tr_.format_number(float(stats.get("win_rate", 0.0) or 0.0), 0)
                    ),
                    "drawdown": str(risk.get("max_drawdown", "—")),
                    "risk_status": str(risk.get("verdict", "—")),
                }
            )
            page.set_tick_status(tick_pill)
            # History stays live after manual-entry navigation, not only at close.
            if page.tabs.currentIndex() == 1 and time.monotonic() - getattr(self, "_history_refreshed_at", 0) >= 1:
                self._history_refreshed_at = time.monotonic()
                self.refresh_trades()
            page.set_paper_live(
                bool(engine is not None and engine.config.is_live)
                if engine is not None
                else bool(self._auto_trade_config().is_live)
            )
            page.set_risk_panel(risk)
            page.set_opportunities(opportunities)
            page.set_open_positions(self._position_rows())

            # --- پویش پس‌زمینهٔ فرصت‌ها (v2.2) ---
            if bool(self.app.settings.get("scalp.watch_scan_enabled", True)):
                interval = max(
                    5,
                    int(
                        float(
                            self.app.settings.get("scalp.watch_scan_interval", 20)
                            or 20
                        )
                    ),
                )
                if self._terminal_stats_tick % interval == 0:
                    self._run_watch_scan()
            if self._terminal_stats_tick % 30 == 0:
                page.set_scanner_values(
                    {
                        "watch_scan_enabled": self.app.settings.get(
                            "scalp.watch_scan_enabled", True
                        ),
                        "watch_scan_interval": self.app.settings.get(
                            "scalp.watch_scan_interval", 20
                        ),
                        "watch_min_confidence": self.app.settings.get(
                            "scalp.watch_min_confidence", 70
                        ),
                        "watch_max_spread": self.app.settings.get(
                            "scalp.watch_max_spread", 0.25
                        ),
                        "watch_row_cap": self.app.settings.get(
                            "scalp.watch_row_cap", 30
                        ),
                    }
                )

            # --- نمودار: قیمت زنده، خطوط موقعیت/پیش‌بینی، وضعیت ---
            if auto_symbol:
                quote = tick_engine.get(auto_symbol)
                if quote is not None and quote.last > 0:
                    history = tick_engine.history(auto_symbol, limit=120)
                    page.update_price_tick(
                        auto_symbol,
                        quote.last,
                        [price for _, price in history],
                    )
                    page.set_chart_live_price(float(quote.last))
                    stale = tick_engine.is_stale(auto_symbol)
                    page.set_chart_status(
                        price=self.tr_.format_number(float(quote.last), 4),
                        trend=trend_text,
                        age=(
                            self.tr_.tr("trades.auto.stale_data")
                            if stale
                            else f"{self.tr_.format_number(float(quote.age_ms), 0)} ms"
                        ),
                        stale=stale,
                    )
                    self._mark_terminal_chart()
                # بازخوانی دوره‌ای کندل — هر ۵ ثانیه (خواستهٔ رال‌تایم)
                if self._terminal_stats_tick % 5 == 0:
                    self._load_terminal_chart(auto_symbol, self._auto_timeframe())
                # بازمحاسبهٔ دوره‌ای گزارش (موتور خودش کش دارد)
                if self._terminal_stats_tick % 30 == 0:
                    self._run_auto_prediction(auto_symbol)
            elif not getattr(self, "_terminal_symbol_bootstrapped", False):
                # هنوز نمادی انتخاب نشده — از تحلیل یا فهرست پیگیری.
                # هر تیک امتحان می‌شود تا بازار بارگذاری شود؛ پس از
                # نخستین موفقیت دیگر تلاش نمی‌کند.
                try:
                    symbol = self.analysis.symbol_combo.currentText().strip().upper()
                except Exception:  # noqa: BLE001
                    symbol = ""
                if not symbol:
                    watchlist = self._watchlist_symbols()
                    symbol = watchlist[0] if watchlist else ""
                if symbol:
                    self._terminal_symbol_bootstrapped = True
                    self._auto_prediction_symbol = symbol
                    page.set_auto_symbol(symbol)
                    self._run_auto_prediction(symbol)
                    self._load_terminal_chart(symbol, self._auto_timeframe())
        except Exception:  # noqa: BLE001 - تایمر نمایش نباید برنامه را ببندد
            logger.debug("Auto terminal refresh failed", exc_info=True)

    async def _ai_candidate_scan(self) -> list:
        """
        پویش حالت AI Auto (خواستهٔ §۳).

        برای هر نماد برتر (تیک تازه + گردش بالا، تا سقف تنظیم‌شده):
        گزارش موتور پیش‌بینی → نردبان روند → تصمیم‌ساز AI. خروجی فقط
        نامزدهای کامل است؛ نامزدهای رد‌شده با دلیل در جدول فرصت‌ها
        ثبت می‌شوند. هیچ داده‌ای ساخته نمی‌شود — گزارش نبود یعنی skip.
        """
        from trading.ai_decider import (
            AICandidate,
            PortfolioState,
            decide as ai_decide,
        )
        from trading.trend_ladder import build_ladder

        engine = getattr(self, "_auto_trader_engine", None)
        tick_engine = getattr(self, "_tick_engine", None)
        prediction_engine = getattr(self.app, "prediction_engine", None)
        market = self.app.market
        if market is None or prediction_engine is None or tick_engine is None:
            return []

        scan_limit = max(1, int(self.app.settings.get("scalp.scan_limit", 10) or 10))
        from trading.universe import RotatingUniverse
        if not hasattr(self, "_ai_universe"):
            self._ai_universe = RotatingUniverse()
        tickers = await market.get_all_tickers()
        symbols = self._ai_universe.select(
            tickers, limit=scan_limit, selected=self._auto_selected_symbols(),
            favorites=self._watchlist_symbols(),
            min_turnover=float(self._auto_trade_config().min_liquidity),
        )

        config = self._auto_trade_config()
        portfolio_dict = self._portfolio_snapshot()
        portfolio = PortfolioState(
            balance=float(portfolio_dict.get("balance", 0.0) or 0.0),
            used_margin=float(portfolio_dict.get("used_margin", 0.0) or 0.0),
            open_count=int(portfolio_dict.get("open_count", 0) or 0),
            max_concurrent=int(config.max_concurrent),
            max_total_margin_percent=float(config.max_total_margin_percent),
        )

        async def assess(symbol):
            if tick_engine.is_stale(symbol):
                await asyncio.wait_for(market.refresh_execution_quote(symbol, tick_engine), timeout=5.0)
            quote = tick_engine.get(symbol)
            if quote is None or quote.last <= 0 or tick_engine.is_stale(symbol):
                return None
            try:
                ticker = await market.get_ticker(symbol)
                turnover = float(getattr(ticker, "turnover_24h", 0.0) or 0.0)
            except Exception:  # noqa: BLE001
                turnover = 0.0

            # گزارش همان موتور واحد — با کش خودش (REPORT_TTL)
            report = await prediction_engine.assess(
                symbol, timeframes=("5m", "15m", "1h", "4h")
            )
            if report is None:
                return None
            payload = report.to_dict()
            ladder = build_ladder(
                symbol,
                regimes=payload.get("regimes"),
                tick_history=[
                    (ts, price)
                    for ts, price in tick_engine.history(symbol, limit=30)
                ],
            )

            if tick_engine.is_stale(symbol):
                await asyncio.wait_for(market.refresh_execution_quote(symbol, tick_engine), timeout=5.0)
            quote = tick_engine.get(symbol)
            decision = ai_decide(
                symbol=symbol,
                report=payload,
                ladder=ladder,
                quote=quote,
                turnover_24h=turnover,
                portfolio=portfolio,
                min_confidence=float(
                    self.app.settings.get("scalp.min_confidence", 55) or 55
                ),
                min_liquidity=float(config.min_liquidity),
                max_spread_percent=float(config.max_spread_percent),
                allocation_mode=str(config.allocation_mode),
                base_margin=float(config.margin_per_trade),
                max_leverage=float(config.leverage),
                trend_policy=str(config.trend_conflict_policy),
                stale_after_ms=float(config.stale_after_seconds) * 1000.0,
            )
            if not decision.ok:
                if engine is not None:
                    horizons_all = payload.get("horizons") or []
                    first_horizon = horizons_all[0] if horizons_all else {}
                    engine.note_rejected(
                        symbol=symbol,
                        direction=str(
                            (first_horizon or {}).get("direction", "") or ""
                        ).upper().replace("BULLISH", "LONG").replace("BEARISH", "SHORT"),
                        confidence=float(
                            (first_horizon or {}).get("confidence", 0.0) or 0.0
                        ),
                        reason=decision.reason,
                        turnover_24h=turnover,
                        trend_ladder=ladder,
                    )
                return None

            horizons = payload.get("horizons") or []
            prediction_text = ""
            probability = 0.0
            expected_move = 0.0
            if horizons:
                first = horizons[0]
                probability = float(first.get("probability", 0.0) or 0.0)
                prediction_text = "{} {}٪".format(
                    str(first.get("direction", "")), self.tr_.format_number(probability, 0)
                )
                # حرکت موردانتظار: پ50 افق نسبت به قیمت زنده
                p50 = float((first.get("quantiles") or {}).get("p50", 0.0) or 0.0)
                if p50 > 0 and quote.last > 0:
                    expected_move = (p50 / quote.last - 1.0) * 100.0
            return AICandidate(
                    symbol=symbol,
                    price=quote.last,
                    direction=decision.direction,
                    score=decision.confidence,
                    turnover_24h=turnover,
                    spread_percent=quote.spread_percent,
                    entry_price=decision.entry_price,
                    margin=decision.margin,
                    leverage=decision.leverage,
                    take_profit=decision.take_profit,
                    stop_loss=decision.stop_loss,
                    prediction=prediction_text,
                    trend_ladder=ladder,
                    reasons=list(decision.reasons),
                    probability=probability,
                    expected_move_percent=round(expected_move, 3),
                    mtf=str(
                        (payload.get("multi_timeframe") or {}).get("alignment") or ""
                    ),
                    risk_reward=round(decision.risk_reward, 2),
                )

        semaphore = asyncio.Semaphore(3)
        async def limited(symbol):
            async with semaphore:
                try:
                    return await assess(symbol)
                except Exception:
                    logger.debug("Candidate assessment failed for %s", symbol, exc_info=True)
                    return None
        candidates = await asyncio.gather(*(limited(symbol) for symbol in symbols))
        return sorted((c for c in candidates if c is not None),
                      key=lambda c: (c.score, c.risk_reward), reverse=True)

    def _market_reachable(self) -> bool:
        """آنلاین اگر REST سالم باشد یا قیمت تازه از سوکت آمده باشد."""
        market = self.app.market
        if market is not None and market.is_online:
            return True
        feed = getattr(self, "_live_feed", None)
        if feed is not None and feed.is_fresh:
            return True
        if market is not None and getattr(market, "_live_tickers", None):
            return True
        return False

    def _cached_symbol_price(self, symbol: str, max_age: float = 8.0) -> float:
        """قیمت کش‌شده. تیکری که زمان دیده‌شدن ندارد کهنه حساب نمی‌شود."""
        target = str(symbol or "").strip().upper()
        if not target:
            return 0.0
        now = datetime.now(UTC)
        feed = getattr(self, "_live_feed", None)
        if feed is not None:
            update = feed.get(target) or feed.get(symbol)
            if update is not None:
                price = float(getattr(update, "price", 0) or 0)
                updated = getattr(update, "updated_at", None)
                if price > 0:
                    if updated is None:
                        return price
                    try:
                        age = (now - updated).total_seconds()
                    except TypeError:
                        return price
                    if age <= max_age:
                        return price
        market = self.app.market
        live_map = getattr(market, "_live_tickers", {}) if market is not None else {}
        live = live_map.get(target) or live_map.get(symbol)
        if live is not None:
            price = float(getattr(live, "last_price", 0) or 0)
            seen = int(getattr(live, "timestamp", 0) or 0)
            if price > 0 and seen <= 0:
                return price
            if price > 0 and seen > 0:
                stamp = seen / 1000.0 if seen > 10_000_000_000 else float(seen)
                if now.timestamp() - stamp <= max_age:
                    return price
        return 0.0

    def _peek_chart(self, symbol: str, timeframe: str) -> list[Any]:
        """کندل کش‌شده، بدون درخواست شبکه."""
        market = self.app.market
        if market is None or not hasattr(market, "peek_candles"):
            return []
        try:
            return list(market.peek_candles(symbol, timeframe, 300) or [])
        except Exception:  # noqa: BLE001
            return []

    def _exit_fee(self, record: Any, *, price: float | None = None) -> float:
        """کارمزد خروج از روی ارزش موقعیت. ورود جداگانه ذخیره شده است."""
        from trading.micro_plan import exit_fee_from_notional

        def _get(name: str) -> float:
            if record is None:
                return 0.0
            raw = record.get(name) if isinstance(record, dict) else getattr(record, name, 0)
            try:
                return float(raw or 0.0)
            except (TypeError, ValueError):
                return 0.0

        rate = float(self.app.settings.get("scalp.taker_fee_rate", 0.0006) or 0.0)
        extra = record.get("extra", {}) if isinstance(record, dict) else getattr(record, "extra", {})
        rate = float((extra or {}).get("fee_rate", rate))
        return exit_fee_from_notional(_get("quantity") * (price if price is not None else _get("entry_price")), rate)

    def start_connection_keepalive(self) -> None:
        """هر ۱۵ ثانیه پینگ و تلاش دوبارهٔ سوکت."""
        self._keepalive_timer = QTimer(self.window)
        self._keepalive_timer.setInterval(KEEPALIVE_TICK_MS)
        self._keepalive_timer.timeout.connect(self._connection_keepalive)
        self._keepalive_timer.start()

    def _connection_keepalive(self) -> None:
        """نگه داشتن اتصال روی نخ شبکه."""
        market = self.app.market
        if market is None or not hasattr(market, "keepalive"):
            return
        if "market-keepalive" in set(self.runner.active_keys()):
            return
        self.runner.submit(
            "market-keepalive",
            market.keepalive(),
            on_success=lambda *_: self._update_streamed_symbols(),
            on_error=lambda *_: None,
        )

    def start_scorecard_timer(self) -> None:
        """زمان‌بند ساعتی دفترچه. تا وقتی تیک روشن نباشد هیچ درخواستی نمی‌رود."""
        self._scorecard_timer = QTimer(self.window)
        self._scorecard_timer.setInterval(SCORECARD_TICK_MS)
        self._scorecard_timer.timeout.connect(self._scorecard_tick)
        self._scorecard_timer.start()

    def _scorecard_tick(self) -> None:
        """اجرای دفترچه فقط با اجازهٔ صریح کاربر."""
        if not self.app.settings.get_bool("signals.scorecard_auto", False):
            return
        if "forecast-scorecard" in set(self.runner.active_keys()):
            return
        self.refresh_scorecard()

    def save_scorecard_auto(self, enabled: bool) -> None:
        """ذخیرهٔ تیک به‌روزرسانی خودکار دفترچه."""
        self.app.settings.set("signals.scorecard_auto", bool(enabled))

    def _last_price(self, symbol: str) -> float:
        """
        آخرین قیمت شناخته‌شدهٔ یک نماد.

        دو منبع به ترتیب سرعت بررسی می‌شوند:
            ۱. جدول بازارها (اگر کاربر آن صفحه را دیده باشد)
            ۲. کش قیمت‌های پایش زندهٔ معاملات

        چرا دو منبع؟
            پیش‌تر فقط منبع اول بود. کاربری که هرگز به صفحهٔ «بازارها»
            نرفته بود، همیشه صفر می‌گرفت — و چون بستن معامله با قیمت
            صفر لغو می‌شود، دکمهٔ «بستن معامله» بی‌صدا هیچ کاری نمی‌کرد.
            این دقیقاً همان «دستی هم بسته نمی‌شود» بود.
        """
        if not symbol:
            return 0.0
        target = symbol.upper()
        cached_live = self._cached_symbol_price(target, max_age=30.0)
        if cached_live > 0:
            return cached_live

        for row in getattr(self.markets, "_all_rows", []) or []:
            if str(row.get("symbol", "")).upper() == target:
                try:
                    price = float(row.get("price") or 0.0)
                except (TypeError, ValueError):
                    price = 0.0
                if price > 0:
                    return price

        cached = float(getattr(self, "_live_prices", {}).get(target, 0.0) or 0.0)
        if cached > 0:
            return cached

        return 0.0

    def _change_percent(self, symbol: str) -> float:
        """درصد تغییر ۲۴ ساعتهٔ یک نماد."""
        for row in getattr(self.markets, "_all_rows", []) or []:
            if str(row.get("symbol", "")).upper() == symbol.upper():
                try:
                    return float(row.get("change_percent") or 0.0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0

    def _change_text(self, symbol: str) -> str:
        """متن درصد تغییر با علامت."""
        value = self._change_percent(symbol)
        return ("+" if value >= 0 else "") + self.tr_.format_number(value, 2) + "%"

    def _money(self, value: Any) -> str:
        """قالب‌بندی مبلغ دلاری."""
        try:
            number = float(value or 0.0)
        except (TypeError, ValueError):
            number = 0.0
        return f"{self.tr_.format_number(number, 2)} $"

    def _toman_text(self, usdt_value: float) -> str:
        """
        معادل تومانی یک مبلغ دلاری.

        اگر نرخ تتر در دسترس نباشد رشتهٔ خالی برمی‌گردد تا چیزی نادرست
        نمایش داده نشود.
        """
        if not self.app.settings.get_bool("ui.show_toman", True):
            return ""
        rate = self._toman_rate
        if not rate:
            return ""
        return f"{self.tr_.format_number(usdt_value * float(rate), 0)} {self.tr_.tr('markets.toman', 'تومان')}"

    @staticmethod
    def _as_datetime(value: Any, *, end_of_day: bool = False) -> Any:
        """تبدیل تاریخ فیلتر به `datetime` قابل استفاده در پرس‌وجو."""
        if value is None:
            return None
        from datetime import date, datetime, time

        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, time.max if end_of_day else time.min)
        return None

    def _toast(self, message: str, *, level: str = "info") -> None:
        """نمایش اعلان شناور روی پنجرهٔ اصلی."""
        try:
            from ui.widgets import Toast

            Toast.show_message(self.window, message, level=level)
        except Exception:  # noqa: BLE001 - اعلان نباید جریان کار را بشکند
            self.status(message)

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def status(self, text: str) -> None:
        """نمایش پیام در نوار وضعیت."""
        self.window.set_status(text)

    def _on_error(self, message: str, exception: Exception | None = None) -> None:
        """
        نمایش خطا بدون بستن برنامه.

        خطای شبکه در حالت آفلاین امری عادی است؛ برنامه باید سرپا بماند.
        """
        user_key = getattr(exception, "user_key", "") if exception else ""
        text = self.tr_.tr(user_key) if user_key and self.tr_.has(user_key) else message
        self.status(f"⚠ {text}")
        logger.warning("UI error: %s", message)
