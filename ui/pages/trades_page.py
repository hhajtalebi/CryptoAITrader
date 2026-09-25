"""
صفحهٔ تاریخچه معاملات + ترمینال معاملهٔ خودکار.

ساختار صفحه دو زبانهٔ اصلی دارد (v2.0):

    زبانهٔ «معاملهٔ خودکار» — ترمینال زنده (خواستهٔ §۸):
        • داشبورد وضعیت (Running/Mode/Balance/Margin/PnL/WinRate/Regime/…)
        • خلاصهٔ Prediction همان نماد — تصمیم‌محور، از همان موتور واحد
        • جدول Opportunity Monitor (زنده)
        • جدول Open Positions (Bid/Ask، سن داده، دلیل خروج)
    زبانهٔ «تاریخچه» — همان صفحهٔ قبل، دست‌نخورده:
        فیلترها، معیارها، جدول، صفحه‌بندی

یادآوری معماری: همهٔ معاملات در حالت «کاغذی» ثبت می‌شوند و هیچ سفارش
واقعی ارسال نمی‌گردد؛ این صفحه فقط نمایش‌دهنده است — هر عددی که
می‌بیند از موتورهای واقعی می‌آید، نه از دادهٔ نمایشی.

جدول‌ها هرگز له نمی‌شوند (خواستهٔ §۹): حداقل ارتفاع ردیف و عرض ستون
تضمین شده و در کمبود فضا اسکرول عمودی/افقی فعال می‌شود.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHeaderView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from trading.auto_trader import HARD_MAX_CONCURRENT, HARD_MAX_LEVERAGE

from localization import Translator
from ui.charts import PriceChart
from ui.pages.base_page import BasePage
from ui.widgets import (
    EmptyState,
    Pagination,
    RefreshButton,
    ResponsiveRow,
    SegmentedControl,
    set_role,
    configure_table,
    harden_table,
    make_button,
)

#: گزینه‌های فیلتر جهت معامله
SIDE_FILTERS = ("all", "long", "short")

#: گزینه‌های فیلتر وضعیت
STATUS_FILTERS = ("all", "open", "closed", "cancelled")

#: شمار ردیف در هر صفحه
PAGE_SIZE = 25

#: حالت‌های موتور خودکار (خواستهٔ §۳) — مقدار = کلید تنظیم
AUTO_ENGINE_MODES = (
    ("selected", "trades.auto.mode_selected"),
    ("scan", "trades.auto.mode_scan"),
    ("ai", "trades.auto.mode_ai"),
    ("ultra", "trades.auto.mode_ultra"),
)

#: ستون‌های جدول فرصت‌ها — ترمینال حرفه‌ای (v2.1)
OPPORTUNITY_COLUMNS = (
    "symbol", "direction", "confidence", "probability", "expected_move",
    "trend", "mtf", "risk", "spread", "strength", "entry", "tp", "sl",
    "leverage", "margin", "status", "action",
)

#: ستون‌های جدول موقعیت‌های باز — Bid/Ask و Notional و سن داده نگه
#: داشته شدند؛ Quantity اضافه شد (v2.1)
POSITION_COLUMNS = (
    "symbol", "side", "entry", "current", "bid", "ask", "quantity",
    "margin", "notional", "leverage", "tp", "sl", "pnl", "pnl_percent",
    "duration", "data_age", "exit_reason", "status", "action",
)

#: ستون‌های جدول تاریخچهٔ معاملات — بازسازی v2.5.0.
#: عنوان‌ها از همین فهرست ساخته می‌شوند (`trades.history_cols.<name>`) تا
#: عنوان و محتوای ستون هرگز از هم جدا نیفتند؛ پیش‌تر عنوان‌ها فقط هنگام
#: تغییر زبان نشانده می‌شدند و جدول با سرستون «۱، ۲، ۳…» باز می‌شد.
HISTORY_COLUMNS = (
    "opened", "symbol", "side", "status", "entry", "price", "quantity",
    "leverage", "margin", "sl", "targets", "pnl", "pnl_percent", "fee",
    "closed", "action",
)

#: کلید متن هر ستون در ردیف آماده‌شدهٔ کنترلر
HISTORY_TEXT_KEYS = {
    "opened": "date_text",
    "entry": "entry_text",
    "price": "exit_text",
    "quantity": "quantity_text",
    "leverage": "leverage_text",
    "margin": "margin_text",
    "sl": "sl_text",
    "targets": "targets_text",
    "pnl": "pnl_text",
    "pnl_percent": "pnl_percent_text",
    "fee": "fee_text",
    "closed": "closed_text",
}

#: کارت‌های اطلاعاتی بالای ترمینال (v2.1 — مرجع UI)
INFO_CARDS = (
    "balance", "available", "used", "daily_pnl", "open_count",
    "opportunities", "win_rate", "drawdown", "risk_status",
)

#: نام قدیمی برای سازگاری (کلید عمومی)
DASHBOARD_CELLS = INFO_CARDS

#: خانه‌های پنل ریسک (v2.1 — §۱۱)
RISK_CELLS = (
    "daily_loss", "max_drawdown", "exposure", "margin_usage",
    "open_trades", "risk_per_trade", "leverage", "spread_risk",
    "liquidity_risk", "data_risk",
)

#: تایم‌فریم‌های نمودار ترمینال — نردبان اسکلپ
AUTO_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h")


class TradesPage(BasePage):
    """تاریخچهٔ معاملات کاغذی + ترمینال معاملهٔ خودکار."""

    title_key = "nav.trades"
    subtitle_key = "trades.subtitle"

    #: صفحه در هر رزولوشن پیمایش دارد؛ محتوا هرگز فشرده نمی‌شود
    scrollable = True

    # ---- سیگنال‌های موجود (دست‌نخورده) ----
    #: فیلترها تغییر کرد — کنترلر داده را دوباره می‌گیرد
    filters_changed = Signal(dict)
    #: کاربر خواست معامله‌ای بسته شود (شناسه)
    close_requested = Signal(int)
    #: کاربر «بستن معامله» را بدون انتخاب معاملهٔ باز زده است
    close_blocked = Signal()
    #: کاربر خواست معامله‌ای حذف شود (شناسه)
    delete_requested = Signal(int)
    #: خروجی CSV
    export_requested = Signal()
    #: پاک‌کردن کل تاریخچه
    clear_requested = Signal()
    #: تازه‌سازی
    refresh_requested = Signal()
    #: کاربر معاملهٔ خودکار را روشن یا خاموش کرد
    auto_trade_toggled = Signal(bool)
    #: کاربر عددهای معاملهٔ خودکار را روی همین صفحه عوض کرد
    auto_settings_changed = Signal(dict)

    # ---- سیگنال‌های v2.0 ----
    #: حالت موتور (selected/scan/ai) عوض شد
    auto_mode_changed = Signal(str)
    #: نماد انتخاب‌شدهٔ پنل پیش‌بینی عوض شد
    auto_symbol_changed = Signal(str)
    #: بستن موقعیت باز از جدول موقعیت‌ها (شناسه)
    close_position_requested = Signal(int)
    #: خروج اضطراری همهٔ موقعیت‌ها
    emergency_exit_requested = Signal()
    #: بستن موقعیت بدون انتخاب
    close_position_blocked = Signal()
    # ---- v2.1: ترمینال حرفه‌ای ----
    #: تایم‌فریم نمودار ترمینال عوض شد (1m/5m/15m/1h/4h)
    auto_timeframe_changed = Signal(str)
    #: ورود دستی به فرصت انتخاب‌شدهٔ جدول فرصت‌ها
    opportunity_enter_requested = Signal(str)
    #: v2.2 — اندیکاتورهای نمودار (ema/sma/bb)، تنظیمات پویش،
    #: نمادهای انتخابی ذخیره‌شده، درخواست نظر هوش مصنوعی
    chart_indicators_changed = Signal(dict)
    scanner_settings_saved = Signal(dict)
    selected_symbols_saved = Signal(list)
    ai_opinion_requested = Signal(str)
    #: پیام کوتاه برای اعلان شناور (مثل نتیجهٔ عکس‌لحظه‌ای)
    notice_requested = Signal(str)

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._rows: list[dict[str, Any]] = []
        self._position_rows: list[dict[str, Any]] = []
        self._opportunity_rows: list[dict[str, Any]] = []
        self._theme: Any = None
        self._page = 1
        self._pages = 1
        self._page_text = ""
        self._auto_symbol = ""
        super().__init__(translator, parent)
        # اسکرول افقی لازم است تا جدول‌های پهن در رزولوشن کوچک له نشوند
        if self._scroll is not None:
            from PySide6.QtCore import Qt as _Qt

            self._scroll.setHorizontalScrollBarPolicy(
                _Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def build(self) -> None:
        """ساخت زبانه‌ها: ترمینال خودکار + تاریخچه."""
        self.refresh_button = RefreshButton(
            self.tr_.tr("common.refresh"),
            busy_text=self.tr_.tr("common.state.loading"),
            done_text=self.tr_.tr("common.refresh"),
        )
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.header.add_action(self.refresh_button)

        self.export_button = make_button(self.tr_.tr("trades.export_csv"))
        self.export_button.clicked.connect(self.export_requested)
        self.header.add_action(self.export_button)

        self.clear_button = make_button(self.tr_.tr("trades.clear_history"))
        self.clear_button.clicked.connect(self.clear_requested)
        self.header.add_action(self.clear_button)

        # --- یادآوری حالت کاغذی ---
        self.notice = QLabel(self.tr_.tr("trades.paper_notice"), self)
        set_role(self.notice, "chip_info")
        self.notice.setWordWrap(True)
        self.layout_root().addWidget(self.notice)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_auto_tab(), self.tr_.tr("trades.auto.tab_title"))
        self.tabs.addTab(self._build_history_tab(), self.tr_.tr("trades.auto.tab_history"))
        self.layout_root().addWidget(self.tabs, 1)

    # ------------------------------------------------------------------
    # زبانهٔ معاملهٔ خودکار — ترمینال (خواستهٔ §۸)
    # ------------------------------------------------------------------
    def _build_auto_tab(self) -> QWidget:
        """
        ساخت ترمینال معامله — چیدمان ترمینال حرفه‌ای (v2.1.1).

        هدر یک‌ردیفی → کارت‌های سرمایه → تنظیمات (پیش‌فرض جمع‌شده) →
        ردیف اصلی: نمودارِ غالب | ستون راست (پیش‌بینی + ریسک) →
        زبانه‌های پایین: فرصت‌ها | موقعیت‌های باز.

        بدون addStretch انتهایی: نمودار و جدول‌ها با پنجره بزرگ
        می‌شوند (۱۰۸۰p = ترمینال تمام‌صفحه بدون اسکرول؛ ۷۲۰p =
        اسکرول BasePage فعال می‌شود تا هیچ داده‌ای حذف نشود).
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._build_terminal_header())
        layout.addWidget(self._build_auto_dashboard())

        # پنل تنظیمات — پیش‌فرض جمع‌شده؛ دکمهٔ تنظیمات در هدر
        self.config_panel = self._build_config_panel()
        layout.addWidget(self.config_panel)
        self._config_collapsed = False
        self._toggle_config_panel()

        # --- ردیف اصلی: نمودار (غلبه) | پیش‌بینی + ریسک ---
        self.chart_card = self._build_chart_card()
        self.prediction_card, self.prediction_widgets = self._build_prediction_card()
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(self.prediction_card, 3)
        right_layout.addWidget(self._build_risk_panel(), 2)
        self.chart_row = ResponsiveRow(
            self.chart_card, right_column, stretch=(5, 2)
        )
        layout.addWidget(self.chart_row, 3)

        # --- زبانه‌های پایین: فرصت‌ها | موقعیت‌های باز ---
        self.terminal_tabs = QTabWidget(tab)
        self.terminal_tabs.addTab(
            self._build_opportunity_card(),
            self.tr_.tr("trades.auto.opportunity_title"),
        )
        self.terminal_tabs.addTab(
            self._build_positions_card(),
            self.tr_.tr("trades.auto.positions_title"),
        )
        layout.addWidget(self.terminal_tabs, 2)
        return tab

    def _build_terminal_header(self) -> QWidget:
        """
        هدر ترمینال — یک ردیف فشرده (مرجع UI — §۱).

        عنوان + قرص‌های وضعیت (موتور، Paper/Live، وب‌سوکت، آخرین
        تیک، تأخیر) + تنظیمات + شروع/توقف. همه از دادهٔ واقعی
        موتورها تازه می‌شوند؛ ارتفاع کم = جای بیشتر برای نمودار.
        """
        frame = QFrame(self)
        set_role(frame, "card")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        title = QLabel(self.tr_.tr("trades.auto.title"))
        set_role(title, "subtitle")
        layout.addWidget(title)

        self.auto_state_label = QLabel(self.tr_.tr("trades.auto.stopped"))
        set_role(self.auto_state_label, "chip_warn")
        layout.addWidget(self.auto_state_label)

        self.auto_paper_live_label = QLabel(
            self.tr_.tr("trades.auto.mode_paper")
        )
        set_role(self.auto_paper_live_label, "chip_info")
        layout.addWidget(self.auto_paper_live_label)

        self.auto_ws_label = QLabel(self.tr_.tr("common.offline"))
        set_role(self.auto_ws_label, "chip_warn")
        layout.addWidget(self.auto_ws_label)

        self.auto_tick_label = QLabel(self.tr_.tr("trades.auto.hdr_no_tick"))
        set_role(self.auto_tick_label, "muted")
        layout.addWidget(self.auto_tick_label)

        self.auto_latency_label = QLabel(self.tr_.tr("trades.auto.hdr_latency_none"))
        set_role(self.auto_latency_label, "muted")
        layout.addWidget(self.auto_latency_label)

        layout.addStretch(1)

        self.auto_settings_button = make_button(self.tr_.tr("trades.auto.settings_open"))
        self.auto_settings_button.clicked.connect(self._toggle_config_panel)
        layout.addWidget(self.auto_settings_button)

        self.auto_toggle_button = make_button(
            self.tr_.tr("trades.auto.start"), primary=True
        )
        self.auto_toggle_button.clicked.connect(self._on_auto_toggle)
        layout.addWidget(self.auto_toggle_button)
        return frame

    def _toggle_config_panel(self) -> None:
        """
        باز و بسته کردن پنل تنظیمات از دکمهٔ هدر.

        وضعیت جمع‌شدگی با پرچم دنبال می‌شود؛ `isVisible()` در پنجرهٔ
        هنوز نمایش‌داده‌نشده همیشه False است و جهت را برمی‌گرداند.
        """
        self._config_collapsed = not getattr(self, "_config_collapsed", False)
        collapsed = self._config_collapsed
        if hasattr(self, "config_panel"):
            self.config_panel.setVisible(not collapsed)
        if hasattr(self, "auto_settings_button"):
            self.auto_settings_button.setText(
                self.tr_.tr(
                    "trades.auto.settings_open"
                    if collapsed
                    else "trades.auto.settings_toggle"
                )
            )

    def _build_config_panel(self) -> QWidget:
        """
        پنل تنظیمات معاملهٔ خودکار — جمع‌شونده (مرجع UI — §۷).

        حالت‌ها (Selected/Scan/AI)، نمادهای انتخابی، پروفایل‌ها و
        جعبه‌های تنظیم دستی/محافظ‌ها. همهٔ عددها در تنظیمات دست
        کاربر است؛ اینجا فقط نمایش داده می‌شوند.
        """
        frame = QFrame(self)
        set_role(frame, "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel(self.tr_.tr("trades.auto.settings_title"))
        set_role(title, "subtitle")
        top.addWidget(title)
        top.addStretch(1)

        self.auto_preset_combo = QComboBox()
        for target in (3, 4, 5):
            self.auto_preset_combo.addItem(
                self.tr_.tr("trades.auto.preset", target=target), target
            )
        top.addWidget(self.auto_preset_combo)
        self.auto_automatic_button = make_button(self.tr_.tr("trades.auto.automatic"))
        self.auto_automatic_button.clicked.connect(self._emit_automatic_profile)
        top.addWidget(self.auto_automatic_button)
        self.auto_ultra_button = make_button("⚡ " + self.tr_.tr("trades.auto.ultra_preset"))
        self.auto_ultra_button.setToolTip(self.tr_.tr("trades.auto.ultra_preset_hint"))
        self.auto_ultra_button.clicked.connect(self._emit_ultra_profile)
        top.addWidget(self.auto_ultra_button)
        layout.addLayout(top)

        # --- نوار حالت‌ها (خواستهٔ §۳) ---
        mode_row = QHBoxLayout()
        mode_label = QLabel(self.tr_.tr("trades.auto.engine_mode"))
        mode_row.addWidget(mode_label)
        self.auto_engine_mode_combo = QComboBox()
        for value, key in AUTO_ENGINE_MODES:
            self.auto_engine_mode_combo.addItem(self.tr_.tr(key), value)
        self.auto_engine_mode_combo.currentIndexChanged.connect(
            lambda _index: self.auto_mode_changed.emit(
                str(self.auto_engine_mode_combo.currentData() or "scan")
            )
        )
        mode_row.addWidget(self.auto_engine_mode_combo)

        self.auto_selected_label = QLabel(self.tr_.tr("trades.auto.selected_symbols"))
        self.auto_selected_input = QLineEdit()
        self.auto_selected_input.setPlaceholderText(
            self.tr_.tr("trades.auto.selected_hint")
        )
        self.auto_selected_input.setMinimumWidth(260)
        # v2.2 — انتخاب از مودال تیک‌خور، نه تایپ دستی؛ خط فقط
        # نمایش نتیجه است (و برای سازگاری منبع حقیقت می‌ماند).
        self.auto_selected_input.setReadOnly(True)
        self.auto_selected_button = QToolButton(self)
        self.auto_selected_button.setText("💱 " + self.tr_.tr("trades.auto.picker_short"))
        self.auto_selected_button.setToolTip(self.tr_.tr("trades.auto.picker_title"))
        self.auto_selected_button.clicked.connect(self._open_symbol_picker)
        mode_row.addWidget(self.auto_selected_label)
        mode_row.addWidget(self.auto_selected_input, 1)
        mode_row.addWidget(self.auto_selected_button)
        layout.addLayout(mode_row)

        # خلاصهٔ تنظیمات فعال
        self.auto_config_label = QLabel("—")
        set_role(self.auto_config_label, "muted")
        self.auto_config_label.setWordWrap(True)
        layout.addWidget(self.auto_config_label)

        self.auto_status_label = QLabel(self.tr_.tr("trades.auto.hint"))
        set_role(self.auto_status_label, "faint")
        self.auto_status_label.setWordWrap(True)
        layout.addWidget(self.auto_status_label)

        layout.addWidget(self._build_auto_manual_box())
        layout.addWidget(self._build_auto_guards_box())
        return frame

    def _build_auto_guards_box(self) -> QWidget:
        """
        جعبهٔ محافظ‌ها و تخصیص سرمایه (خواستهٔ §۱۲/§۱۳).

        پیش‌فرض بسته است؛ فهرست بلندِ محافظ‌ها فقط برای کسی که می‌خواهد
        تنظیم کند باز می‌شود.
        """
        box = QFrame(self)
        set_role(box, "panel")
        outer = QVBoxLayout(box)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        header = QHBoxLayout()
        self.auto_guards_check = QCheckBox(self.tr_.tr("trades.auto.guards_title"))
        header.addWidget(self.auto_guards_check)
        header.addStretch(1)
        outer.addLayout(header)

        self.auto_guards_box = QWidget()
        grid = QGridLayout(self.auto_guards_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        def _spin(minimum: float, maximum: float, step: float, decimals: int = 2):
            spin = QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            spin.setDecimals(decimals)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return spin

        self.auto_liquidity_input = _spin(0.0, 100_000_000.0, 100_000.0, 0)
        self.auto_spread_input = _spin(0.0, 5.0, 0.01)
        self.auto_scan_interval_input = _spin(1.0, 3600.0, 1.0)
        self.auto_stale_input = _spin(1.0, 300.0, 1.0)
        self.auto_slippage_input = _spin(0.0, 1.0, 0.01)
        self.auto_trailing_check = QCheckBox()
        self.auto_breakeven_check = QCheckBox()
        self.auto_invalidation_check = QCheckBox()

        self.auto_allocation_combo = QComboBox()
        for mode in ("fixed", "percent", "confidence", "risk", "hybrid", "ai"):
            self.auto_allocation_combo.addItem(
                self.tr_.tr(f"trades.auto.alloc_{mode}"), mode
            )
        self.auto_alloc_percent_input = _spin(0.1, 100.0, 0.5)
        self.auto_max_margin_input = _spin(1.0, 100.0, 5.0)

        fields = (
            ("trades.auto.min_liquidity", self.auto_liquidity_input),
            ("trades.auto.max_spread", self.auto_spread_input),
            ("trades.auto.scan_interval", self.auto_scan_interval_input),
            ("trades.auto.stale_after", self.auto_stale_input),
            ("trades.auto.slippage", self.auto_slippage_input),
            ("trades.auto.trailing", self.auto_trailing_check),
            ("trades.auto.breakeven", self.auto_breakeven_check),
            ("trades.auto.invalidation", self.auto_invalidation_check),
            ("trades.auto.allocation", self.auto_allocation_combo),
            ("trades.auto.alloc_percent", self.auto_alloc_percent_input),
            ("trades.auto.max_total_margin", self.auto_max_margin_input),
        )
        self._guard_fields = fields
        for index, (key, widget) in enumerate(fields):
            grid.addWidget(QLabel(self.tr_.tr(key)), index // 2, (index % 2) * 2)
            grid.addWidget(widget, index // 2, (index % 2) * 2 + 1)
        outer.addWidget(self.auto_guards_box)

        # شروع بسته — همان قاعدهٔ جعبهٔ دستی
        self.auto_guards_check.toggled.connect(
            lambda enabled: self.auto_guards_box.setVisible(enabled)
        )
        self.auto_guards_box.setVisible(False)
        return box

    def _build_auto_dashboard(self) -> QWidget:
        """
        کارت‌های اطلاعاتی سرمایه — ۹ کارت (مرجع UI — §۲).

        دو ردیف پنج‌تایی؛ هر کارت حداقل عرض دارد تا در رزولوشن پایین
        له نشود (صفحه اسکرول می‌گیرد، کارت کوچک نمی‌شود).
        """
        frame = QFrame(self)
        set_role(frame, "card")
        layout = QGridLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        self._dashboard_cells: dict[str, tuple[QLabel, QLabel]] = {}
        # آیکون هر کارت — هویت بصری مثل تصویر مرجع (عنوان/آیکون/مبلغ)
        icons = {
            "balance": "💰", "available": "🟢", "used": "🔒",
            "daily_pnl": "📈", "open_count": "📊", "opportunities": "🔍",
            "win_rate": "🎯", "drawdown": "📉", "risk_status": "🛡️",
        }
        for index, key in enumerate(INFO_CARDS):
            cell = QFrame(frame)
            set_role(cell, "stat")
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(12, 9, 12, 9)
            cell_layout.setSpacing(3)
            cell.setMinimumWidth(132)
            head = QHBoxLayout()
            head.setSpacing(7)
            icon = QLabel(icons.get(key, "•"), cell)
            icon.setStyleSheet("font-size: 15px; background: transparent;")
            head.addWidget(icon)
            caption = QLabel(self.tr_.tr(f"trades.auto.cell_{key}"), cell)
            set_role(caption, "muted")
            head.addWidget(caption)
            head.addStretch(1)
            cell_layout.addLayout(head)
            value = QLabel("—", cell)
            set_role(value, "metric")
            value.setStyleSheet("font-size: 14px; font-weight: 700;")
            cell_layout.addWidget(value)
            layout.addWidget(cell, index // 5, index % 5)
            self._dashboard_cells[key] = (caption, value)
        return frame

    def _build_chart_card(self) -> QWidget:
        """
        کارت نمودار حرفه‌ای (v2.2 — خواستهٔ کاربر).

        منوی نماد با آیکون، تایم‌فریم، نوع نمودار، اندیکاتورهای
        قابل‌افزودن (EMA/SMA/BB)، ابزار خط‌کشی (افقی/روند/پاک‌کردن)،
        عکس‌لحظه‌ای و بازنشانی زوم — همه روی همان PriceChart واحد.
        """
        from ui.dialogs.trading_dialogs import SymbolIconDelegate
        from ui.widgets import Card

        card = Card(self.tr_.tr("trades.auto.chart_title"), self)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.auto_symbol_combo = QComboBox()
        self.auto_symbol_combo.setMinimumWidth(190)
        self.auto_symbol_combo.setItemDelegate(SymbolIconDelegate(self.auto_symbol_combo))
        self.auto_symbol_combo.currentIndexChanged.connect(
            lambda _index: self._on_chart_symbol_changed(
                str(self.auto_symbol_combo.currentText() or "").strip().upper()
            )
        )
        header.addWidget(self.auto_symbol_combo)

        self.timeframe_bar = SegmentedControl(
            [(tf, tf) for tf in AUTO_TIMEFRAMES]
        )
        self.timeframe_bar.set_current("15m", emit=False)
        self.timeframe_bar.selection_changed.connect(self.auto_timeframe_changed.emit)
        header.addWidget(self.timeframe_bar)
        header.addStretch(1)

        # --- نوع نمودار: کندل / خط / ناحیه ---
        self.chart_type_combo = QComboBox()
        for key in ("type_candles", "type_line", "type_area"):
            self.chart_type_combo.addItem(
                self.tr_.tr(f"trades.auto.{key}"),
                key.removeprefix("type_"),
            )
        self.chart_type_combo.currentIndexChanged.connect(
            lambda _i: self.price_chart.set_chart_type(
                str(self.chart_type_combo.currentData() or "candles")
            )
        )
        header.addWidget(self.chart_type_combo)

        # --- اندیکاتورها: منوی تیک‌خور ---
        from PySide6.QtGui import QAction
        self._indicator_state: dict[str, bool] = {"ema": False, "sma": False, "bb": False}
        self.indicators_button = QToolButton(self)
        self.indicators_button.setText("ƒ " + self.tr_.tr("trades.auto.indicators"))
        self.indicators_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.indicators_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        indicator_menu = QMenu(self.indicators_button)
        for key in ("ema", "sma", "bb"):
            action = QAction(self.tr_.tr(f"trades.auto.ind_{key}"), indicator_menu)
            action.setCheckable(True)
            action.setData(key)
            action.toggled.connect(
                lambda checked, k=key: self._on_indicator_toggled(k, checked)
            )
            indicator_menu.addAction(action)
        self.indicators_button.setMenu(indicator_menu)
        header.addWidget(self.indicators_button)

        # --- ابزار خط‌کشی ---
        self.draw_button = QToolButton(self)
        self.draw_button.setText("✏ " + self.tr_.tr("trades.auto.draw"))
        self.draw_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        draw_menu = QMenu(self.draw_button)
        for mode, label_key in (
            ("hline", "draw_hline"), ("trend", "draw_trend"), ("", "draw_off"),
        ):
            action = QAction(self.tr_.tr(f"trades.auto.{label_key}"), draw_menu)
            action.setData(mode)
            action.triggered.connect(
                lambda _checked=False, m=mode: self._set_draw_mode(m)
            )
            draw_menu.addAction(action)
        clear_action = QAction(self.tr_.tr("trades.auto.draw_clear"), draw_menu)
        clear_action.triggered.connect(lambda: self.price_chart.clear_drawings())
        draw_menu.addSeparator()
        draw_menu.addAction(clear_action)
        self.draw_button.setMenu(draw_menu)
        header.addWidget(self.draw_button)

        # --- عکس‌لحظه‌ای + بازنشانی زوم ---
        self.screenshot_button = QToolButton(self)
        self.screenshot_button.setText("📷")
        self.screenshot_button.setToolTip(self.tr_.tr("trades.auto.screenshot"))
        self.screenshot_button.clicked.connect(self._screenshot_chart)
        header.addWidget(self.screenshot_button)

        self.zoom_button = QToolButton(self)
        self.zoom_button.setText("⤢")
        self.zoom_button.setToolTip(self.tr_.tr("trades.auto.reset_zoom"))
        # نمودار بعد از همین ردیف ساخته می‌شود — اتصال با lambda
        self.zoom_button.clicked.connect(
            lambda: self.price_chart.reset_zoom()
        )
        header.addWidget(self.zoom_button)
        card.body().addLayout(header)

        self.price_chart = PriceChart(self.tr_)
        self.price_chart.setMinimumHeight(380)
        card.body().addWidget(self.price_chart, 1)

        # وضعیت زیر نمودار: قیمت زنده، روند، سن داده
        status = QHBoxLayout()
        self.chart_price_label = QLabel("—")
        set_role(self.chart_price_label, "metric")
        status.addWidget(self.chart_price_label)
        self.chart_trend_label = QLabel("—")
        set_role(self.chart_trend_label, "muted")
        status.addWidget(self.chart_trend_label)
        self.chart_age_label = QLabel("—")
        set_role(self.chart_age_label, "muted")
        status.addWidget(self.chart_age_label)
        status.addStretch(1)
        card.body().addLayout(status)
        return card

    # ------------------------------------------------------------------
    # ابزارهای نمودار (v2.2)
    # ------------------------------------------------------------------
    def _on_indicator_toggled(self, key: str, checked: bool) -> None:
        """تیک اندیکاتور → سیگنال برای کنترلر (محاسبه از کندل واقعی)."""
        self._indicator_state[key] = bool(checked)
        self.chart_indicators_changed.emit(dict(self._indicator_state))

    def set_indicator_state(self, state: dict) -> None:
        """همگام‌سازی منوی اندیکاتورها از بیرون (بدون حلقهٔ سیگنال)."""
        for action in self.indicators_button.menu().actions():
            key = str(action.data() or "")
            if key in self._indicator_state:
                action.blockSignals(True)
                action.setChecked(bool(state.get(key, False)))
                action.blockSignals(False)
                self._indicator_state[key] = bool(state.get(key, False))

    def _set_draw_mode(self, mode: str) -> None:
        """حالت خط‌کشی روی نمودار."""
        self.price_chart.set_draw_mode(mode)

    def _screenshot_chart(self) -> None:
        """عکس‌لحظه‌ای از نمودار — ذخیره در فایل انتخابی کاربر."""
        from PySide6.QtWidgets import QFileDialog

        symbol = str(self.auto_symbol_combo.currentText() or "CHART").replace("/", "-")
        default = f"CryptoAITrader-{symbol}-{self._auto_timeframe or '15m'}.png"
        path, _selected = QFileDialog.getSaveFileName(
            self, self.tr_.tr("trades.auto.screenshot"), default, "PNG (*.png)"
        )
        if not path:
            return
        pixmap = self.price_chart.screenshot_pixmap()
        if pixmap is not None and not pixmap.isNull() and pixmap.save(path, "PNG"):
            self.notice_requested.emit(
                self.tr_.tr("trades.auto.screenshot_saved", path=path)
            )
        else:
            self.notice_requested.emit(self.tr_.tr("trades.auto.screenshot_failed"))

    def _auto_timeframe(self) -> str:
        """تایم‌فریم فعلی از نوار انتخاب (برای نام فایل و ...)."""
        try:
            return str(self.timeframe_bar.current() or "15m")
        except Exception:  # noqa: BLE001
            return "15m"

    def _build_risk_panel(self) -> QWidget:
        """
        پنل وضعیت ریسک (مرجع UI — §۱۱).

        ده خانه از دادهٔ واقعی (موتور، کش تیک، مخزن) + حکم نهایی.
        جلوی ورود خطرناک را خود موتور می‌گیرد؛ این پنل شفافیت می‌دهد.
        """
        from ui.widgets import Card

        card = Card(self.tr_.tr("trades.auto.risk_title"), self)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        self._risk_cells: dict[str, tuple[QLabel, QLabel]] = {}
        for index, key in enumerate(RISK_CELLS):
            cell = QWidget(card)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(2)
            caption = QLabel(self.tr_.tr(f"trades.auto.risk_{key}"), cell)
            set_role(caption, "muted")
            value = QLabel("—", cell)
            cell_layout.addWidget(caption)
            cell_layout.addWidget(value)
            grid.addWidget(cell, index // 5, index % 5)
            self._risk_cells[key] = (caption, value)
        card.body().addLayout(grid)

        self.risk_verdict_label = QLabel("—", card)
        set_role(self.risk_verdict_label, "chip_info")
        self.risk_verdict_label.setWordWrap(True)
        card.body().addWidget(self.risk_verdict_label)
        return card

    def _build_prediction_card(self) -> tuple[QWidget, dict[str, QLabel]]:
        """
        خلاصهٔ پیش‌بینی برای تصمیم معاملهٔ خودکار (خواستهٔ §۲).

        خلاصه و تصمیم‌محور: قیمت، روند، رژیم، جهت، اطمینان، حرکت
        موردانتظار، هم‌راستایی 1m تا 4h، چندک‌ها، توافق مدل‌ها و
        هشدار. تحلیل کامل در صفحهٔ «پیش‌بینی» است — هر دو از همان
        موتور واحد تغذیه می‌شوند.
        """
        from ui.widgets import Card

        card = Card(self.tr_.tr("trades.auto.prediction_title"), self)
        header = QHBoxLayout()
        # نمادِ همان نمودار — پیش‌بینی از همین نمودار تغذیه می‌شود
        self.prediction_symbol_label = QLabel("—")
        set_role(self.prediction_symbol_label, "metric")
        header.addWidget(self.prediction_symbol_label)
        self.prediction_state_label = QLabel("—")
        set_role(self.prediction_state_label, "muted")
        header.addWidget(self.prediction_state_label, 1)
        card.body().addLayout(header)

        widgets: dict[str, QLabel] = {}

        def cell(parent: QWidget) -> QWidget:
            inner = QWidget(parent)
            lay = QVBoxLayout(inner)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(2)
            return inner

        top = QHBoxLayout()
        for key in ("price", "direction", "confidence", "expected_move"):
            holder = cell(card)
            caption = QLabel(self.tr_.tr(f"trades.auto.pred_{key}"), holder)
            set_role(caption, "muted")
            value = QLabel("—", holder)
            set_role(value, "metric")
            holder.layout().addWidget(caption)
            holder.layout().addWidget(value)
            top.addWidget(holder)
            widgets[key] = value
        card.body().addLayout(top)

        mid = QHBoxLayout()
        for key in ("regime", "stage", "trend", "agreement"):
            holder = cell(card)
            caption = QLabel(self.tr_.tr(f"trades.auto.pred_{key}"), holder)
            set_role(caption, "muted")
            value = QLabel("—", holder)
            holder.layout().addWidget(caption)
            holder.layout().addWidget(value)
            mid.addWidget(holder)
            widgets[key] = value
        card.body().addLayout(mid)

        # نردبان تایم‌فریم‌ها: 1m / 5m / 15m / 1h / 4h (خواستهٔ §۲)
        ladder_row = QHBoxLayout()
        self._ladder_labels: dict[str, QLabel] = {}
        for timeframe in ("1m", "5m", "15m", "1h", "4h"):
            chip = QLabel(timeframe, card)
            set_role(chip, "chip_info")
            chips = QWidget(card)
            chip_layout = QHBoxLayout(chips)
            chip_layout.setContentsMargins(0, 0, 0, 0)
            chip_layout.setSpacing(4)
            chip_layout.addWidget(chip)
            value = QLabel("—", card)
            value.setMinimumWidth(52)
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip_layout.addWidget(value)
            ladder_row.addWidget(chips)
            self._ladder_labels[timeframe] = value
        ladder_row.addStretch(1)
        card.body().addLayout(ladder_row)

        # چندک‌ها + کیفیت داده
        quantiles = QHBoxLayout()
        for key in ("p10", "p50", "p90", "quality"):
            holder = cell(card)
            caption = QLabel(self.tr_.tr(f"trades.auto.pred_{key}"), holder)
            set_role(caption, "muted")
            value = QLabel("—", holder)
            holder.layout().addWidget(caption)
            holder.layout().addWidget(value)
            quantiles.addWidget(holder)
            widgets[key] = value
        card.body().addLayout(quantiles)

        self.prediction_warning_label = QLabel("—", card)
        set_role(self.prediction_warning_label, "chip_warn")
        self.prediction_warning_label.setWordWrap(True)
        card.body().addWidget(self.prediction_warning_label)
        widgets["warning"] = self.prediction_warning_label

        # --- نظر هوش مصنوعی (v2.2) — تحلیل لحظه‌ای همان نماد ---
        from PySide6.QtWidgets import QTextEdit

        ai_bar = QHBoxLayout()
        self.ai_opinion_button = make_button(
            self.tr_.tr("trades.auto.ai_opinion"), primary=True
        )
        self.ai_opinion_button.clicked.connect(self._request_ai_opinion)
        ai_bar.addWidget(self.ai_opinion_button)
        self.ai_opinion_state = QLabel("—", card)
        set_role(self.ai_opinion_state, "muted")
        ai_bar.addWidget(self.ai_opinion_state, 1)
        card.body().addLayout(ai_bar)

        self.ai_opinion_text = QTextEdit(card)
        self.ai_opinion_text.setReadOnly(True)
        self.ai_opinion_text.setPlaceholderText(
            self.tr_.tr("trades.auto.ai_opinion_hint")
        )
        self.ai_opinion_text.setMinimumHeight(120)
        card.body().addWidget(self.ai_opinion_text, 1)
        return card, widgets

    def _request_ai_opinion(self) -> None:
        """دکمهٔ تحلیل هوش مصنوعی → سیگنال با نمادِ همین نمودار."""
        symbol = str(self._auto_symbol or "").strip().upper()
        if not symbol:
            self.notice_requested.emit(self.tr_.tr("trades.auto.ai_no_symbol"))
            return
        self.ai_opinion_state.setText(self.tr_.tr("trades.auto.ai_running"))
        self.ai_opinion_requested.emit(symbol)

    def set_ai_opinion(self, text: str, *, failed: bool = False) -> None:
        """نمایش نتیجهٔ عامل هوش مصنوعی در پنل."""
        self.ai_opinion_text.setPlainText(str(text or ""))
        self.ai_opinion_state.setText(
            self.tr_.tr("trades.auto.ai_failed" if failed else "trades.auto.ai_done")
        )

    def _build_opportunity_card(self) -> QWidget:
        """
        پویش فرصت‌ها — ۱۷ ستون + جست‌وجو + فیلتر (مرجع UI — §۵).

        مرتب‌سازی و تمام‌صفحه/CSV از نوار ابزار خودجدول می‌آید؛
        دوبار کلیک روی ردیفِ قابل‌ورود، درخواست ورود دستی می‌دهد
        (دروازه‌های موتور دوباره سنجیده می‌شوند).
        """
        from ui.widgets import Card

        card = Card(self.tr_.tr("trades.auto.opportunity_title"), self)
        bar = QHBoxLayout()
        self.opportunity_search = QLineEdit()
        self.opportunity_search.setPlaceholderText(
            self.tr_.tr("trades.auto.search_hint")
        )
        self.opportunity_search.textChanged.connect(self._filter_opportunities)
        bar.addWidget(self.opportunity_search, 1)

        self.opportunity_filter_combo = QComboBox()
        for key in ("opp_filter_all", "opp_filter_enterable", "opp_filter_skipped"):
            self.opportunity_filter_combo.addItem(
                self.tr_.tr(f"trades.auto.{key}"), key
            )
        self.opportunity_filter_combo.currentIndexChanged.connect(
            self._filter_opportunities
        )
        bar.addWidget(self.opportunity_filter_combo)

        # تنظیمات پویش — مودال حرفه‌ای (v2.2)
        self._scanner_values: dict = {}
        self.scanner_settings_button = QToolButton(card)
        self.scanner_settings_button.setText("⚙ " + self.tr_.tr("trades.auto.scanner_short"))
        self.scanner_settings_button.setToolTip(
            self.tr_.tr("trades.auto.scanner_title")
        )
        self.scanner_settings_button.clicked.connect(self._open_scanner_settings)
        bar.addWidget(self.scanner_settings_button)
        card.body().addLayout(bar)

        self.opportunity_table = QTableWidget(0, len(OPPORTUNITY_COLUMNS), self)
        harden_table(self.opportunity_table, min_row_height=30, min_table_height=180)
        self._set_columns(self.opportunity_table, OPPORTUNITY_COLUMNS, "trades.auto.opp_")
        self.opportunity_table.cellDoubleClicked.connect(self._on_opportunity_activated)
        card.body().addWidget(self.opportunity_table)

        self.opportunity_note = QLabel(self.tr_.tr("trades.auto.opp_empty"), self)
        set_role(self.opportunity_note, "faint")
        self.opportunity_note.setWordWrap(True)
        card.body().addWidget(self.opportunity_note)
        return card

    def _build_positions_card(self) -> QWidget:
        """جدول موقعیت‌های باز — ۱۷ ستون (خواستهٔ §۸)."""
        from ui.widgets import Card

        card = Card(self.tr_.tr("trades.auto.positions_title"), self)
        bar = QHBoxLayout()
        self.close_position_button = make_button(
            self.tr_.tr("trades.auto.close_selected")
        )
        self.close_position_button.clicked.connect(self._emit_close_position)
        self.emergency_button = make_button(self.tr_.tr("trades.auto.emergency"))
        set_role(self.emergency_button, "primary")
        self.emergency_button.clicked.connect(self.emergency_exit_requested.emit)
        bar.addStretch(1)
        bar.addWidget(self.close_position_button)
        bar.addWidget(self.emergency_button)
        card.body().addLayout(bar)

        self.positions_table = QTableWidget(0, len(POSITION_COLUMNS), self)
        harden_table(
            self.positions_table, min_row_height=32, min_table_height=200
        )
        self._set_columns(self.positions_table, POSITION_COLUMNS, "trades.auto.pos_")
        # جدول موقعیت‌ها هر ثانیه از نو پر می‌شود و دکمهٔ بستنِ هر
        # ردیف با ویجت سلولی کار می‌کند — مرتب‌سازیِ فعال دکمه‌ها را
        # از داده جدا می‌کند؛ پس این جدول مرتب‌ نمی‌شود (فیلتر و
        # اسکرول هست، فرصت‌ها مرتب‌شدنی‌اند).
        self.positions_table.setSortingEnabled(False)
        self.positions_table.cellDoubleClicked.connect(self._on_position_activated)
        # کلیک روی نماد → مودال جزئیات کامل معامله (v2.2)
        self.positions_table.cellClicked.connect(self._on_position_cell_clicked)
        card.body().addWidget(self.positions_table)

        self.positions_note = QLabel(self.tr_.tr("trades.auto.pos_empty"), self)
        set_role(self.positions_note, "faint")
        self.positions_note.setWordWrap(True)
        card.body().addWidget(self.positions_note)
        return card

    # ------------------------------------------------------------------
    # زبانهٔ تاریخچه — همان ساختار قبلی
    # ------------------------------------------------------------------
    def _build_history_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_filters())
        layout.addWidget(self._build_metrics())

        self.table = QTableWidget(0, len(HISTORY_COLUMNS), self)
        configure_table(self.table, stretch_column=HISTORY_COLUMNS.index("closed"))
        harden_table(self.table, min_row_height=30, min_table_height=220)
        # ستون اهداف هرگز بریده نشود (TP1 · TP2 · TP3 با علامت ✓)
        for name in ("targets", "symbol", "opened"):
            self.table.horizontalHeader().setSectionResizeMode(
                HISTORY_COLUMNS.index(name), QHeaderView.ResizeMode.ResizeToContents
            )
        # عنوان‌ها همین حالا نشانده می‌شوند، نه فقط هنگام تغییر زبان
        self._retranslate_headers()
        self.table.cellDoubleClicked.connect(self._on_row_activated)
        self.table.cellClicked.connect(self._on_history_cell_clicked)
        layout.addWidget(self.table, 1)

        actions_row = QHBoxLayout()
        self.close_trade_button = make_button(self.tr_.tr("trades.close_trade"))
        self.close_trade_button.clicked.connect(self._emit_close_selected)
        self.close_hint = QLabel(self.tr_.tr("trades.close_hint"))
        self.close_hint.setProperty("role", "faint")
        self.close_hint.setWordWrap(True)
        actions_row.addWidget(self.close_trade_button)
        actions_row.addWidget(self.close_hint, 1)
        layout.addLayout(actions_row)

        self.empty_state = EmptyState(self)
        self.empty_state.configure(
            icon="⇄",
            title=self.tr_.tr("trades.empty"),
            detail=self.tr_.tr("trades.empty_hint"),
        )
        self.empty_state.setVisible(False)
        layout.addWidget(self.empty_state)

        self.pagination = Pagination(self)
        self.pagination.page_changed.connect(self._on_page_changed)
        layout.addWidget(self.pagination)
        return tab

    def _build_auto_manual_box(self) -> QWidget:
        """
        جعبهٔ تنظیم دستی معاملهٔ خودکار.

        پیش‌فرض بسته است تا پنل شلوغ نشود؛ کسی که می‌خواهد دست ببرد
        بازش می‌کند.
        """
        box = QFrame(self)
        set_role(box, "panel")
        outer = QVBoxLayout(box)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        header = QHBoxLayout()
        self.auto_manual_check = QCheckBox(self.tr_.tr("trades.auto.manual_mode"))
        self.auto_manual_check.toggled.connect(self._on_auto_manual_toggled)
        header.addWidget(self.auto_manual_check)
        header.addStretch(1)
        self.auto_apply_button = make_button(self.tr_.tr("trades.auto.apply"))
        self.auto_apply_button.clicked.connect(self._emit_auto_settings)
        header.addWidget(self.auto_apply_button)
        outer.addLayout(header)

        # شبکه داخل یک ظرف می‌نشیند تا بشود کاملاً جمعش کرد. صرفاً
        # غیرفعال‌کردن، ارتفاع را آزاد نمی‌کند و صفحه از قد نمایشگر
        # لپ‌تاپ بلندتر می‌شد (آزمون `test_page_fits_a_laptop_screen`).
        self.auto_manual_box = QWidget()
        grid = QGridLayout(self.auto_manual_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        def _money(minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
            """ساخت ورودی عددی پولی با تراز وسط (قاعدهٔ ظاهری پروژه)."""
            spin = QDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            spin.setDecimals(2)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return spin

        self.auto_margin_input = _money(1.0, 100_000.0, 1.0)
        self.auto_target_input = _money(0.01, 10_000.0, 0.5)
        self.auto_loss_input = _money(0.01, 10_000.0, 0.5)

        self.auto_leverage_input = QSpinBox()
        self.auto_leverage_input.setRange(1, int(HARD_MAX_LEVERAGE))
        self.auto_leverage_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.auto_poll_input = QDoubleSpinBox()
        self.auto_poll_input.setRange(0.25, 60.0)
        self.auto_poll_input.setSingleStep(0.25)
        self.auto_poll_input.setDecimals(2)
        self.auto_poll_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.auto_mode_combo = QComboBox()
        self.auto_mode_combo.addItem(self.tr_.tr("trades.auto.mode_paper"), "paper")
        self.auto_mode_combo.addItem(self.tr_.tr("trades.auto.mode_live"), "live")

        self.auto_confirm_input = QLineEdit()
        self.auto_confirm_input.setPlaceholderText(self.tr_.tr("trades.auto.confirm_placeholder"))

        self.auto_concurrent_input = QSpinBox()
        self.auto_concurrent_input.setRange(1, int(HARD_MAX_CONCURRENT))
        self.auto_concurrent_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # نسخهٔ ۲.۵.۴: بیشترین زمان باز ماندن هر معامله (ثانیه)
        self.auto_hold_input = QSpinBox()
        self.auto_hold_input.setRange(10, 86_400)
        self.auto_hold_input.setSingleStep(10)
        self.auto_hold_input.setSuffix(" s")
        self.auto_hold_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.auto_confidence_input = QSpinBox()
        self.auto_confidence_input.setRange(50, 99)
        self.auto_confidence_input.setSuffix("٪")
        self.auto_confidence_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.auto_source_combo = QComboBox()
        self.auto_source_combo.addItem(self.tr_.tr("trades.auto.source_confidence"), "confidence")
        self.auto_source_combo.addItem(self.tr_.tr("trades.auto.source_scalp"), "scalp")

        fields = (
            ("trades.auto.margin", self.auto_margin_input),
            ("trades.auto.target", self.auto_target_input),
            ("trades.auto.max_loss", self.auto_loss_input),
            ("trades.auto.leverage", self.auto_leverage_input),
            ("trades.auto.concurrent", self.auto_concurrent_input),
            ("trades.auto.max_hold", self.auto_hold_input),
            ("trades.auto.min_confidence", self.auto_confidence_input),
            ("trades.auto.source", self.auto_source_combo),
            ("trades.auto.poll", self.auto_poll_input),
            ("trades.auto.mode_label", self.auto_mode_combo),
            ("trades.auto.confirm", self.auto_confirm_input),
        )
        for index, (key, widget) in enumerate(fields):
            grid.addWidget(QLabel(self.tr_.tr(key)), index // 2, (index % 2) * 2)
            grid.addWidget(widget, index // 2, (index % 2) * 2 + 1)
        outer.addWidget(self.auto_manual_box)

        self._auto_manual_widgets = [widget for _, widget in fields]
        self._on_auto_manual_toggled(False)
        return box

    def _on_auto_manual_toggled(self, enabled: bool) -> None:
        """
        باز و بسته کردن ورودی‌های دستی.

        وقتی حالت دستی خاموش است ورودی‌ها غیرفعال می‌شوند ولی پنهان
        نمی‌شوند: کاربر باید ببیند با چه عددهایی معامله می‌شود.
        """
        for widget in getattr(self, "_auto_manual_widgets", []):
            widget.setEnabled(enabled)
        if hasattr(self, "auto_manual_box"):
            self.auto_manual_box.setVisible(enabled)
        if hasattr(self, "auto_apply_button"):
            self.auto_apply_button.setEnabled(enabled)

    def load_auto_settings(self, values: dict) -> None:
        """پر کردن ورودی‌ها از روی تنظیم‌های ذخیره‌شده."""
        self.auto_margin_input.setValue(float(values.get("scalp.margin_per_trade", 10.0)))
        self.auto_target_input.setValue(float(values.get("scalp.target_profit", 2.0)))
        self.auto_loss_input.setValue(float(values.get("scalp.max_loss", 3.0)))
        self.auto_leverage_input.setValue(int(values.get("scalp.leverage", 10)))
        self.auto_concurrent_input.setValue(int(values.get("scalp.max_concurrent", 3)))
        self.auto_hold_input.setValue(int(float(values.get("scalp.max_hold_seconds", 900) or 900)))
        self.auto_confidence_input.setValue(int(values.get("scalp.min_confidence", 75)))
        index = self.auto_source_combo.findData(
            str(values.get("scalp.candidate_source", "confidence"))
        )
        if index >= 0:
            self.auto_source_combo.setCurrentIndex(index)
        if "scalp.mode" in values:
            mode_index = self.auto_mode_combo.findData(str(values.get("scalp.mode") or "paper"))
            if mode_index >= 0:
                self.auto_mode_combo.setCurrentIndex(mode_index)
        if "scalp.live_confirmation" in values:
            self.auto_confirm_input.setText(str(values.get("scalp.live_confirmation") or ""))
        if "scalp.poll_seconds" in values:
            try:
                self.auto_poll_input.setValue(float(values.get("scalp.poll_seconds") or 5.0))
            except (TypeError, ValueError):
                pass

        # حالت موتور + محافظ‌ها (v2.0)
        mode_index = self.auto_engine_mode_combo.findData(
            str(values.get("scalp.engine_mode", "scan") or "scan")
        )
        if mode_index >= 0:
            self.auto_engine_mode_combo.setCurrentIndex(mode_index)
        if "scalp.selected_symbols" in values:
            self.auto_selected_input.setText(
                str(values.get("scalp.selected_symbols") or "")
            )
        self._set_spin(self.auto_liquidity_input, values, "scalp.min_liquidity", 2_000_000.0)
        self._set_spin(self.auto_spread_input, values, "scalp.max_spread_percent", 0.25)
        self._set_spin(self.auto_scan_interval_input, values, "scalp.scan_interval_seconds", 15.0)
        self._set_spin(self.auto_stale_input, values, "scalp.stale_after_seconds", 10.0)
        self._set_spin(self.auto_slippage_input, values, "scalp.slippage_percent", 0.02)
        self.auto_trailing_check.setChecked(
            bool(values.get("scalp.trailing_enabled", False))
        )
        self.auto_breakeven_check.setChecked(
            bool(values.get("scalp.break_even_enabled", True))
        )
        self.auto_invalidation_check.setChecked(
            bool(values.get("scalp.signal_invalidation", True))
        )
        alloc_index = self.auto_allocation_combo.findData(
            str(values.get("scalp.allocation_mode", "fixed") or "fixed")
        )
        if alloc_index >= 0:
            self.auto_allocation_combo.setCurrentIndex(alloc_index)
        self._set_spin(self.auto_alloc_percent_input, values, "scalp.allocation_percent", 5.0)
        self._set_spin(self.auto_max_margin_input, values, "scalp.max_total_margin_percent", 60.0)

    @staticmethod
    def _set_spin(spin: QDoubleSpinBox, values: dict, key: str, fallback: float) -> None:
        """پرکردن امن یک ورودی عددی از تنظیم‌ها."""
        try:
            spin.setValue(float(values.get(key, fallback) or fallback))
        except (TypeError, ValueError):
            spin.setValue(fallback)

    def collect_auto_settings(self) -> dict:
        """خواندن عددهای دستی برای ذخیره — کلیدهای تازه هم برمی‌گردند."""
        return {
            "scalp.margin_per_trade": self.auto_margin_input.value(),
            "scalp.target_profit": self.auto_target_input.value(),
            "scalp.max_loss": self.auto_loss_input.value(),
            "scalp.leverage": self.auto_leverage_input.value(),
            "scalp.max_concurrent": self.auto_concurrent_input.value(),
            "scalp.max_hold_seconds": self.auto_hold_input.value(),
            "scalp.min_confidence": self.auto_confidence_input.value(),
            "scalp.candidate_source": self.auto_source_combo.currentData(),
            "scalp.poll_seconds": self.auto_poll_input.value(),
            "scalp.mode": self.auto_mode_combo.currentData(),
            "scalp.live_confirmation": self.auto_confirm_input.text().strip(),
            # v2.0
            "scalp.engine_mode": str(self.auto_engine_mode_combo.currentData() or "scan"),
            "scalp.selected_symbols": self.auto_selected_input.text().strip(),
            "scalp.min_liquidity": self.auto_liquidity_input.value(),
            "scalp.max_spread_percent": self.auto_spread_input.value(),
            "scalp.scan_interval_seconds": self.auto_scan_interval_input.value(),
            "scalp.stale_after_seconds": self.auto_stale_input.value(),
            "scalp.slippage_percent": self.auto_slippage_input.value(),
            "scalp.trailing_enabled": self.auto_trailing_check.isChecked(),
            "scalp.break_even_enabled": self.auto_breakeven_check.isChecked(),
            "scalp.signal_invalidation": self.auto_invalidation_check.isChecked(),
            "scalp.allocation_mode": str(self.auto_allocation_combo.currentData() or "fixed"),
            "scalp.allocation_percent": self.auto_alloc_percent_input.value(),
            "scalp.max_total_margin_percent": self.auto_max_margin_input.value(),
        }

    def _emit_auto_settings(self) -> None:
        """اعلام تغییر عددها به کنترلر."""
        self.auto_settings_changed.emit(self.collect_auto_settings())

    def _emit_automatic_profile(self) -> None:
        """
        پروفایل خیلی کوتاه: ۱۰ دلار، اهرم ۲۰۰، سود خالص ۳/۴/۵.

        حالت سفارش و عبارت تأیید دست نمی‌خورند. اگر کاربر LIVE را
        نوشته باشد، همین دکمه آن را پاک یا عوض نمی‌کند.
        """
        target = float(self.auto_preset_combo.currentData() or 3)
        self.auto_margin_input.setValue(10)
        self.auto_leverage_input.setValue(int(HARD_MAX_LEVERAGE))
        self.auto_target_input.setValue(target)
        self.auto_loss_input.setValue(target)
        self.auto_concurrent_input.setValue(1)
        self.auto_poll_input.setValue(0.4)
        payload = self.collect_auto_settings()
        payload.pop("scalp.mode", None)
        payload.pop("scalp.live_confirmation", None)
        payload["scalp.max_hold_seconds"] = 90
        payload["scalp.taker_fee_rate"] = 0.0006
        payload["scalp.settings_mode"] = "automatic"
        self.auto_settings_changed.emit(payload)

    #: پیش‌تنظیم اسکالپ فوق‌سریع (همه در تنظیم دستی قابل تغییرند)
    ULTRA_PRESET = {
        "scalp.engine_mode": "ultra",
        "scalp.margin_per_trade": 10.0,
        "scalp.leverage": 50,
        "scalp.target_profit": 2.0,
        "scalp.max_loss": 2.0,
        "scalp.max_concurrent": 100,
        "scalp.max_hold_seconds": 180,
        "scalp.poll_seconds": 0.5,
        "scalp.scan_interval_seconds": 1.0,
        "scalp.max_total_margin_percent": 100.0,
        "scalp.allocation_mode": "fixed",
        "scalp.taker_fee_rate": 0.0006,
    }

    def _emit_ultra_profile(self) -> None:
        """
        اسکالپ فوق‌سریع: ۱۰ دلار × اهرم ۵۰، بستن در سود خالص ۲ دلار، تا ۱۰۰ هم‌زمان.

        مثل «خودکار»، حالت سفارش (کاغذی/واقعی) و عبارت تأیید دست نمی‌خورند.
        """
        preset = dict(self.ULTRA_PRESET)
        self.auto_margin_input.setValue(preset["scalp.margin_per_trade"])
        self.auto_leverage_input.setValue(int(preset["scalp.leverage"]))
        self.auto_target_input.setValue(preset["scalp.target_profit"])
        self.auto_loss_input.setValue(preset["scalp.max_loss"])
        self.auto_concurrent_input.setValue(int(preset["scalp.max_concurrent"]))
        self.auto_hold_input.setValue(int(preset["scalp.max_hold_seconds"]))
        self.auto_poll_input.setValue(preset["scalp.poll_seconds"])
        self.auto_scan_interval_input.setValue(preset["scalp.scan_interval_seconds"])
        self.auto_max_margin_input.setValue(preset["scalp.max_total_margin_percent"])
        index = self.auto_engine_mode_combo.findData("ultra")
        if index >= 0:
            self.auto_engine_mode_combo.blockSignals(True)
            self.auto_engine_mode_combo.setCurrentIndex(index)
            self.auto_engine_mode_combo.blockSignals(False)
        payload = self.collect_auto_settings()
        payload.update(preset)
        payload.pop("scalp.mode", None)
        payload.pop("scalp.live_confirmation", None)
        payload["scalp.settings_mode"] = "ultra"
        self.auto_settings_changed.emit(payload)

    def _on_auto_toggle(self) -> None:
        """درخواست روشن یا خاموش کردن معاملهٔ خودکار."""
        starting = self.auto_toggle_button.text() == self.tr_.tr("trades.auto.start")
        self.auto_trade_toggled.emit(starting)

    def set_auto_config(self, text: str) -> None:
        """نمایش خلاصهٔ تنظیمات معاملهٔ خودکار."""
        self.auto_config_label.setText(text)

    def set_auto_state(self, running: bool, detail: str = "") -> None:
        """
        هماهنگ‌کردن ظاهر پنل با وضعیت واقعی موتور.

        متن دکمه تنها منبع حقیقت برای «الان چه کاری انجام می‌شود» است،
        پس هر بار از روی وضعیت موتور نوشته می‌شود نه از روی حدس.
        """
        self._auto_running = bool(running)
        if running:
            self.auto_toggle_button.setText(self.tr_.tr("trades.auto.stop"))
            self.auto_state_label.setText(self.tr_.tr("trades.auto.running"))
            set_role(self.auto_state_label, "chip_up")
        else:
            self.auto_toggle_button.setText(self.tr_.tr("trades.auto.start"))
            self.auto_state_label.setText(self.tr_.tr("trades.auto.stopped"))
            set_role(self.auto_state_label, "chip_warn")
        self.auto_status_label.setText(
            detail or getattr(self, "_auto_economics", "") or self.tr_.tr("trades.auto.hint")
        )

    def set_auto_economics(self, text: str) -> None:
        """نشاندن اقتصاد کارمزد روی همان برچسب وضعیت، بدون ردیف تازه."""
        self._auto_economics = str(text or "")
        if text and not getattr(self, "_auto_running", False):
            self.auto_status_label.setText(self._auto_economics)

    # ------------------------------------------------------------------
    # APIهای v2.0 — ترمینال
    # ------------------------------------------------------------------
    def set_auto_dashboard(self, values: dict[str, str]) -> None:
        """
        به‌روزرسانی کارت‌های سرمایه با متن‌های آمادهٔ کنترلر.

        سود/زیان روز بر اساس علامت رنگ می‌گیرد (سبز/قرمز) — رنگ
        از خودِ داده می‌آید، نه از حدس.
        """
        for key, (_, label) in self._dashboard_cells.items():
            text = str(values.get(key, "") or "—")
            label.setText(text)
            if key == "daily_pnl" and text != "—":
                if text.startswith("+"):
                    set_role(label, "chip_up")
                elif text.startswith("-"):
                    set_role(label, "chip_down")

    def _open_symbol_picker(self) -> None:
        """
        مودال انتخاب نمادهای تیک‌خور (v2.2).

        تأیید → فهرست در ورودی «نمادهای انتخابی» می‌نشیند و با
        سیگنال `selected_symbols_saved` به کنترلر می‌رود تا در
        تنظیمات ذخیره و با فهرست علاقه‌مندی‌های دیتابیس همگام شود.
        """
        from ui.dialogs.trading_dialogs import SymbolPickerDialog

        current = [
            part.strip().upper()
            for part in str(self.auto_selected_input.text() or "").split(",")
            if part.strip()
        ]
        dialog = SymbolPickerDialog(
            self.tr_,
            list(getattr(self, "_picker_symbols", []) or []),
            current,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen = dialog.checked_symbols()
            self.auto_selected_input.setText(",".join(chosen))
            self.selected_symbols_saved.emit(chosen)

    def set_auto_symbols(self, symbols: list[str]) -> None:
        """
        پرکردن کمبوی نماد نمودار با حفظ انتخاب.

        اگر چیزی انتخاب نشده باشد، نخستین نماد «با سیگنال» انتخاب
        می‌شود تا کنترلر همان لحظه کندل و پیش‌بینی را بیاورد —
        کمبوی خالی یعنی نمودار مرده.
        """
        current = self.auto_symbol_combo.currentText()
        # فهرست کامل برای مودال انتخاب نمادهای تیک‌خور
        self._picker_symbols = [str(s) for s in symbols or []]
        self.auto_symbol_combo.blockSignals(True)
        self.auto_symbol_combo.clear()
        for symbol in symbols or []:
            self.auto_symbol_combo.addItem(symbol)
        position = self.auto_symbol_combo.findText(current) if current else -1
        if position >= 0:
            self.auto_symbol_combo.setCurrentIndex(position)
            self.auto_symbol_combo.blockSignals(False)
        else:
            if self.auto_symbol_combo.count() > 0:
                # ایندکس را در حالت بی‌صدا به -1 برگردان تا
                # setCurrentIndex(0) واقعاً سیگنال بدهد — Qt برای
                # «همان ایندکس» سیگنال نمی‌فرستد و addItem خودش
                # ایندکس را ۰ کرده است.
                self.auto_symbol_combo.setCurrentIndex(-1)
            self.auto_symbol_combo.blockSignals(False)
            if self.auto_symbol_combo.count() > 0:
                # انتخابِ با سیگنال → کنترلر نمودار و پیش‌بینی را می‌آورد
                self.auto_symbol_combo.setCurrentIndex(0)
            elif self.auto_symbol_combo.currentIndex() < 0:
                pass

    def update_prediction_summary(self, payload: dict | None) -> None:
        """
        خلاصهٔ پیش‌بینی برای تصمیم معاملهٔ خودکار (خواستهٔ §۲).

        payload همان `report.to_dict()` موتور پیش‌بینی است به‌علاوهٔ
        `live_price` تازه. None یعنی «داده نیست» — صادقانه نمایش
        داده می‌شود، نه اسکلت قلابی.
        """
        widgets = getattr(self, "prediction_widgets", None)
        if widgets is None:
            return
        if not payload:
            for label in widgets.values():
                label.setText("—")
            self.prediction_state_label.setText(self.tr_.tr("prediction.no_data"))
            for label in self._ladder_labels.values():
                label.setText("—")
            self.prediction_warning_label.setVisible(False)
            return

        fmt = self.tr_.format_number
        tr = self.tr_.tr
        price = float(payload.get("live_price") or payload.get("last_price") or 0.0)
        widgets["price"].setText(fmt(price, 4) if price else "—")

        horizons = payload.get("horizons") or []
        primary = None
        for horizon in horizons:
            if str(horizon.get("horizon")) in ("15m", "5m", "30m"):
                primary = horizon
                break
        primary = primary or (horizons[0] if horizons else None)

        if primary:
            direction = str(primary.get("direction", ""))
            widgets["direction"].setText(
                tr(f"prediction.direction.{direction}", default=direction or "—")
            )
            set_role(
                widgets["direction"],
                "bullish" if direction == "bullish"
                else ("bearish" if direction == "bearish" else "neutral"),
            )
            widgets["confidence"].setText(
                "{}٪ / {}٪".format(
                    fmt(float(primary.get("confidence", 0) or 0), 0),
                    fmt(float(primary.get("probability", 0) or 0), 0),
                )
            )
            quantiles = primary.get("quantiles") or {}
            widgets["p10"].setText(fmt(float(quantiles.get("p10", 0) or 0), 4))
            widgets["p50"].setText(fmt(float(quantiles.get("p50", 0) or 0), 4))
            widgets["p90"].setText(fmt(float(quantiles.get("p90", 0) or 0), 4))
            expected = primary.get("expected_range")
            if isinstance(expected, dict):
                low, high = expected.get("low"), expected.get("high")
            elif isinstance(expected, (list, tuple)) and len(expected) == 2:
                low, high = expected[0], expected[1]
            else:
                low, high = None, None
            move_text = (
                "{}% … {}%".format(
                    fmt((float(low) / price - 1) * 100 if low and price else 0, 2),
                    fmt((float(high) / price - 1) * 100 if high and price else 0, 2),
                )
                if price and low
                else "—"
            )
            widgets["expected_move"].setText(move_text)
            agreement = primary.get("model_agreement")
            widgets["agreement"].setText(
                fmt(float(agreement) * 100, 0) + "٪" if agreement is not None else "—"
            )
        else:
            widgets["direction"].setText("—")
            widgets["confidence"].setText("—")
            widgets["expected_move"].setText("—")

        regimes = payload.get("regimes") or {}
        regime_4h = (regimes.get("4h") or {})
        widgets["regime"].setText(
            tr(f"prediction.regime.{regime_4h.get('regime', '')}",
               default=str(regime_4h.get("regime") or "—"))
        )
        stage = payload.get("market_stage") or ""
        widgets["stage"].setText(
            tr(f"prediction.stage.{stage}", default=str(stage or "—"))
        )
        mtf = payload.get("multi_timeframe") or {}
        alignment = str(mtf.get("alignment") or "")
        widgets["trend"].setText(
            tr(f"prediction.alignment.{alignment}", default=alignment or "—")
        )

        # نردبان 1m تا 4h — از رژیم‌های خود موتور (منبع واحد)؛
        # پلهٔ 1m از جهت تیک‌های زنده توسط کنترلر تزریق می‌شود.
        arrows = {1: "▲", -1: "▼", 0: "•"}
        for timeframe, label in self._ladder_labels.items():
            regime = regimes.get(timeframe)
            if isinstance(regime, dict) and regime.get("direction") in (1, -1, 0):
                direction = int(regime["direction"])
                label.setText(arrows.get(direction, "—"))
                set_role(
                    label,
                    "bullish" if direction == 1
                    else ("bearish" if direction == -1 else "neutral"),
                )
            else:
                label.setText("—")

        quality = payload.get("data_quality") or {}
        ratio = quality.get("ratio") if isinstance(quality, dict) else None
        widgets["quality"].setText(
            fmt(float(ratio) * 100, 0) + "٪" if ratio is not None else "—"
        )

        warnings = payload.get("warnings") or []
        if warnings:
            first = warnings[0]
            text = first.get("message", "") if isinstance(first, dict) else str(first)
            self.prediction_warning_label.setText(str(text or "—"))
            self.prediction_warning_label.setVisible(True)
        else:
            self.prediction_warning_label.setVisible(False)

        generated = str(payload.get("generated_at", ""))
        self.prediction_state_label.setText(
            tr("trades.auto.pred_state", value=generated or "—")
        )

    def update_price_tick(self, symbol: str, price: float, points: list[float]) -> None:
        """
        تیک تازهٔ نماد انتخاب‌شده: قیمت زندهٔ پنل پیش‌بینی و نمودار.

        `points` برای سازگاری API نگه داشته شده؛ خط زندهٔ نمودار از
        مسیر `set_chart_live_price` کنترلر می‌آید.
        """
        if symbol and symbol != self._auto_symbol:
            return
        widgets = getattr(self, "prediction_widgets", None)
        if widgets and price > 0:
            widgets["price"].setText(self.tr_.format_number(float(price), 4))

    def set_auto_symbol(self, symbol: str) -> None:
        """تنظیم نماد نمودار/پیش‌بینی (از بیرون — همگام با تحلیل)."""
        clean = str(symbol or "").strip().upper()
        self._auto_symbol = clean
        if hasattr(self, "prediction_symbol_label"):
            self.prediction_symbol_label.setText(clean or "—")
        if not clean:
            return
        position = self.auto_symbol_combo.findText(clean)
        if position >= 0:
            if self.auto_symbol_combo.currentIndex() != position:
                # انتخاب برنامه‌ای — سیگنال خود کار می‌افتد
                self.auto_symbol_combo.setCurrentIndex(position)
            return
        # نماد در کمبو نیست (مثلاً از تحلیل آمده) — افزوده و انتخاب کن
        self.auto_symbol_combo.blockSignals(True)
        self.auto_symbol_combo.insertItem(0, clean)
        self.auto_symbol_combo.setCurrentIndex(0)
        self.auto_symbol_combo.blockSignals(False)
        # سیگنال صریح — کنترلر باید بداند نمودار روی چه نمادی است
        self.auto_symbol_changed.emit(clean)

    def _update_terminal_tab_titles(self) -> None:
        """عنوان زبانه‌های پایین با شمار زندهٔ ردیف‌ها."""
        tabs = getattr(self, "terminal_tabs", None)
        if tabs is None:
            return
        tabs.setTabText(
            0,
            "{} ({})".format(
                self.tr_.tr("trades.auto.opportunity_title"),
                len(getattr(self, "_opportunity_rows", []) or []),
            ),
        )
        tabs.setTabText(
            1,
            "{} ({})".format(
                self.tr_.tr("trades.auto.positions_title"),
                len(getattr(self, "_position_rows", []) or []),
            ),
        )

    def _on_chart_symbol_changed(self, symbol: str) -> None:
        """
        نماد کمبوی نمودار عوض شد (توسط کاربر یا پرکردن کمبو).

        برچسب نمادِ پنل پیش‌بینی همان لحظه همگام می‌شود تا پیوند
        «نمودار ↔ پیش‌بینی» همیشه دیده شود.
        """
        if not symbol:
            return
        self._auto_symbol = symbol
        if hasattr(self, "prediction_symbol_label"):
            self.prediction_symbol_label.setText(symbol)
        self.auto_symbol_changed.emit(symbol)

    def set_opportunities(self, rows: list[dict[str, Any]]) -> None:
        """
        پرکردن جدول فرصت‌ها.

        هر ردیف از موتور واقعی می‌آید: نامزد پذیرفته‌شده یا رد‌شده با
        دلیل. تصمیمِ «skip» با دلیلش دیده می‌شود — شفافیت به‌جای
        سکوت.
        """
        self._opportunity_rows = list(rows or [])
        self._render_opportunities()
        self._update_terminal_tab_titles()

    def _render_opportunities(self) -> None:
        """رندر با جست‌وجو و فیلتر فعلی — ۱۷ ستون ترمینال."""
        needle = (self.opportunity_search.text() or "").strip().upper()
        filter_key = str(
            self.opportunity_filter_combo.currentData() or "opp_filter_all"
        )
        table = self.opportunity_table
        rows = []
        for row in self._opportunity_rows:
            if needle and needle not in str(row.get("symbol", "")):
                continue
            decision = str(row.get("decision", ""))
            if filter_key == "opp_filter_enterable" and not row.get("actionable"):
                continue
            if filter_key == "opp_filter_skipped" and decision != "skip":
                continue
            rows.append(row)
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        fmt = self.tr_.format_number

        def maybe(value: Any, decimals: int = 0) -> str:
            """عدد اختیاری — None یعنی «—»، نه صفر قلابی."""
            if value is None:
                return "—"
            try:
                return fmt(float(value), decimals)
            except (TypeError, ValueError):
                return "—"

        for index, row in enumerate(rows):
            decision = str(row.get("decision", ""))
            direction = str(row.get("direction", "")).lower()
            actionable = bool(row.get("actionable"))
            expected = row.get("expected_move")
            cells = [
                str(row.get("symbol", "")),
                self.tr_.tr(
                    f"prediction.direction.{direction}",
                    default=direction or "—",
                ),
                maybe(row.get("confidence")),
                maybe(row.get("probability")),
                (
                    maybe(expected, 2) + "٪"
                    if expected is not None else "—"
                ),
                str(row.get("trend", "") or "—"),
                str(row.get("mtf", "") or "—"),
                maybe(row.get("risk"), 2),
                (
                    maybe(row["spread"], 3) + "%"
                    if row.get("spread") is not None else "—"
                ),
                maybe(row.get("score")),
                maybe(row.get("entry"), 4),
                maybe(row.get("tp"), 4),
                maybe(row.get("sl"), 4),
                (
                    maybe(row.get("leverage"), 1) + "×"
                    if row.get("leverage") is not None else "—"
                ),
                maybe(row.get("margin"), 1),
                self.tr_.tr(
                    f"trades.auto.opp_decision_{decision}",
                    default=decision or "—",
                ),
                # اکشن: ورود دستی (دوبار کلیک) / انجام‌شده / هیچ
                self.tr_.tr("trades.auto.opp_action_enter")
                if actionable
                else (
                    "✓" if decision == "enter" else "—"
                ),
            ]
            for column, value in enumerate(cells):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 15 and decision == "enter":
                    set_role_item(item, "bullish", self._theme)
                if column == 16 and actionable:
                    set_role_item(item, "bullish", self._theme)
                if column == 0:
                    # ایندکس واقعی در دادهٔ نقش کاربر — مرتب‌سازی Qt
                    # ردیف‌ها را جابه‌جا می‌کند؛ دوبار کلیک باید به همین
                    # نگاشت برود، نه به شمارهٔ دیداری.
                    item.setData(Qt.ItemDataRole.UserRole, index)
                table.setItem(index, column, item)
            # دلیل رد در tooltip — جدول شلوغ نمی‌شود، دلیل گم نمی‌شود
            reason = str(row.get("reason", "") or "")
            if reason:
                table.item(index, 15).setToolTip(reason)
                if table.item(index, 16) is not None:
                    table.item(index, 16).setToolTip(
                        self.tr_.tr("trades.auto.opp_action_hint")
                    )
        table.setSortingEnabled(True)
        # ردیف‌های نمایان — ایندکس دوبار کلیک به همین‌ها اشاره می‌کند
        self._visible_opportunity_rows = rows
        self.opportunity_note.setVisible(not rows)
        self.opportunity_note.setText(self.tr_.tr("trades.auto.opp_empty"))

    def _filter_opportunities(self) -> None:
        """اعمال جست‌وجو/فیلتر جدول فرصت‌ها."""
        self._render_opportunities()

    def set_scanner_values(self, values: dict) -> None:
        """مقادیر فعلی تنظیمات پویش (از تنظیمات واقعی کاربر)."""
        self._scanner_values = dict(values or {})

    def _open_scanner_settings(self) -> None:
        """مودال تنظیمات پویش فرصت‌ها — ذخیره از طریق سیگنال."""
        from ui.dialogs.trading_dialogs import ScannerSettingsDialog

        dialog = ScannerSettingsDialog(self.tr_, dict(self._scanner_values), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values()
            self._scanner_values = dict(values)
            self.scanner_settings_saved.emit(values)

    def _on_opportunity_activated(self, row: int, _column: int) -> None:
        """
        دوبار کلیک روی فرصتِ قابل‌ورود → درخواست ورود دستی.

        موتور همهٔ دروازه‌ها را دوباره می‌سنجد؛ اگر داده کهنه یا
        اسپرد عجیب باشد، همان‌جا صادقانه رد می‌شود.
        """
        visible = getattr(self, "_visible_opportunity_rows", [])
        item = self.opportunity_table.item(row, 0)
        data_index = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )
        if data_index is None or not 0 <= int(data_index) < len(visible):
            return
        candidate = visible[int(data_index)]
        if candidate.get("actionable"):
            self.opportunity_enter_requested.emit(
                str(candidate.get("symbol", "") or "")
            )

    def set_open_positions(self, rows: list[dict[str, Any]]) -> None:
        """
        پرکردن جدول موقعیت‌های باز.

        ردیف‌ها از کنترلر با متن‌های آماده می‌آیند (`*_text`) — این
        صفحه درگیر قالب‌بندی عدد و تاریخ نمی‌شود. ستون‌های Bid/Ask و
        Data Age مستقیماً از کش تیک زنده می‌آیند.
        """
        self._position_rows = list(rows or [])
        self._update_terminal_tab_titles()
        table = self.positions_table
        table.setSortingEnabled(False)
        table.setRowCount(len(self._position_rows))
        for index, row in enumerate(self._position_rows):
            pnl_value = row.get("pnl")
            cells = [
                str(row.get("symbol", "")),
                str(row.get("side_text", "")),
                str(row.get("entry_text", "")),
                str(row.get("current_text", "")),
                str(row.get("bid_text", "")),
                str(row.get("ask_text", "")),
                str(row.get("quantity_text", "")),
                str(row.get("margin_text", "")),
                str(row.get("notional_text", "")),
                str(row.get("leverage_text", "")),
                str(row.get("tp_text", "")),
                str(row.get("sl_text", "")),
                str(row.get("pnl_text", "")),
                str(row.get("pnl_percent_text", "")),
                str(row.get("duration_text", "")),
                str(row.get("data_age_text", "")),
                str(row.get("exit_reason_text", "")),
                str(row.get("status_text", "")),
                "",  # ستون اکشن — دکمهٔ بستن (ویجت سلولی)
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 0:
                    # ایندکس واقعی — مصون از جابه‌جایی مرتب‌سازی
                    item.setData(Qt.ItemDataRole.UserRole, index)
                if column in (12, 13) and self._theme is not None and isinstance(
                    pnl_value, (int, float)
                ):
                    colors = self._theme.colors
                    tint = QColor(colors.success if pnl_value >= 0 else colors.danger)
                    item.setForeground(tint)
                if column == 1 and self._theme is not None:
                    colors = self._theme.colors
                    item.setForeground(
                        QColor(colors.success if row.get("side") == "long" else colors.danger)
                    )
                table.setItem(index, column, item)
            # دکمهٔ بستن هر ردیف (v2.2) — شناسه در آرگومان پیش‌فرض
            try:
                trade_id = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            close_button = QPushButton(
                self.tr_.tr("trades.auto.close_row"), table
            )
            set_role(close_button, "danger")
            close_button.setToolTip(
                self.tr_.tr("trades.auto.close_row_hint", symbol=str(row.get("symbol", "")))
            )
            close_button.clicked.connect(
                lambda _checked=False, tid=trade_id: self.close_position_requested.emit(tid)
            )
            table.setCellWidget(index, len(cells) - 1, close_button)
        self.positions_note.setVisible(not self._position_rows)
        self.positions_note.setText(self.tr_.tr("trades.auto.pos_empty"))

    # ------------------------------------------------------------------
    # APIهای ترمینال v2.1 — قرص‌های هدر، ریسک، نمودار
    # ------------------------------------------------------------------
    def set_tick_status(self, status: dict) -> None:
        """
        قرص‌های هدر ترمینال: وب‌سوکت، تأخیر، آخرین تیک (§۱/§۹).

        متن آخرین تیک و کهنگی از کنترلر می‌آید چون قالب‌بندی زمان
        وظیفهٔ آن است؛ اینجا فقط نمایش است.
        """
        connected = bool(status.get("websocket", False))
        self.auto_ws_label.setText(
            "WS: " + self.tr_.tr("common.online" if connected else "common.offline")
        )
        connections = status.get("connections") or {}
        if connections.get("connections"):
            self.auto_ws_label.setText(self.auto_ws_label.text() + f" ({connections.get('connected', 0)}/{connections['connections']})")
        set_role(self.auto_ws_label, "chip_up" if connected else "chip_warn")

        latency = status.get("avg_total_latency_ms")
        if latency is not None:
            self.auto_latency_label.setText(
                self.tr_.tr(
                    "trades.auto.hdr_latency",
                    value=self.tr_.format_number(float(latency), 0),
                )
            )
        else:
            self.auto_latency_label.setText(
                self.tr_.tr("trades.auto.hdr_latency_none")
            )

        tick_text = str(status.get("last_tick_text") or "")
        if tick_text:
            self.auto_tick_label.setText(tick_text)
            stale = bool(status.get("stale", False))
            set_role(
                self.auto_tick_label,
                "chip_warn" if stale else "muted",
            )

    def set_paper_live(self, is_live: bool) -> None:
        """قرص حالت اجرا: کاغذی یا واقعی (با تأیید کامل)."""
        self.auto_paper_live_label.setText(
            self.tr_.tr(
                "trades.auto.mode_live" if is_live else "trades.auto.mode_paper"
            )
        )
        set_role(
            self.auto_paper_live_label,
            "chip_down" if is_live else "chip_info",
        )

    def set_risk_panel(self, values: dict) -> None:
        """
        پنل ریسک (§۱۱) — مقادیر متنی از کنترلر + حکم نهایی.

        `values["verdict"]` متن حکم و `values["verdict_role"]` نقش رنگی
        آن است (chip_up / chip_warn / chip_down).
        """
        for key, (_, label) in getattr(self, "_risk_cells", {}).items():
            label.setText(str(values.get(key, "—") or "—"))
        verdict = str(values.get("verdict", "") or "—")
        self.risk_verdict_label.setText(verdict)
        set_role(
            self.risk_verdict_label,
            str(values.get("verdict_role", "chip_info") or "chip_info"),
        )

    # --- نمودار ترمینال (همان PriceChart پروژه) --------------------

    def set_chart_candles(self, candles: list, timeframe: str, symbol: str) -> None:
        """کندل‌ها + حجم روی نمودار ترمینال."""
        self.price_chart.set_candles(candles, timeframe, symbol)

    def set_chart_live_price(self, price: float | None) -> None:
        """خط قیمت زنده روی نمودار."""
        self.price_chart.set_live_price(price)

    def mark_chart_position(
        self, entry: float | None, stop: float | None, targets: list[float]
    ) -> None:
        """خطوط ورود/SL/TP موقعیت‌های باز نمادِ نمودار."""
        self.price_chart.mark_signal(entry, stop, targets or [])

    def set_chart_status(
        self, price: str, trend: str, age: str, *, stale: bool = False
    ) -> None:
        """ردیف وضعیت زیر نمودار: قیمت، روند، سن داده."""
        self.chart_price_label.setText(price or "—")
        self.chart_trend_label.setText(trend or "—")
        self.chart_age_label.setText(age or "—")
        set_role(self.chart_age_label, "chip_warn" if stale else "muted")

    def apply_chart_palette(self, palette: dict) -> None:
        """هماهنگی رنگ نمودار ترمینال با پوستهٔ فعال."""
        self.price_chart.apply_palette(palette)

    def retranslate_chart(self) -> None:
        """بازترجمهٔ متن‌های نمودار پس از تغییر زبان."""
        self.price_chart.retranslate()

    def _position_row_from_table(self, row: int) -> dict[str, Any] | None:
        """
        ردیف دادهٔ پشت سطر جدول — با نگاشت UserRole.

        مرتب‌سازی Qt سطرها را جابه‌جا می‌کند؛ شمارهٔ دیداری معتبر
        نیست و باید از ایندکس ذخیره‌شده در ستون نماد خوانده شود.
        """
        item = self.positions_table.item(row, 0)
        data_index = (
            item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        )
        if data_index is None:
            return None
        try:
            index = int(data_index)
        except (TypeError, ValueError):
            return None
        if 0 <= index < len(self._position_rows):
            return self._position_rows[index]
        return None

    def selected_position_id(self) -> int | None:
        """شناسهٔ موقعیت انتخاب‌شدهٔ جدول موقعیت‌ها."""
        row = self.positions_table.currentRow()
        data = self._position_row_from_table(row) if row >= 0 else None
        if data:
            try:
                return int(data.get("id"))
            except (TypeError, ValueError):
                return None
        return None

    def _emit_close_position(self) -> None:
        """بستن موقعیت انتخاب‌شده از جدول موقعیت‌ها."""
        trade_id = self.selected_position_id()
        if trade_id is None:
            self.close_position_blocked.emit()
            return
        self.close_position_requested.emit(trade_id)

    def _on_position_cell_clicked(self, row: int, column: int) -> None:
        """کلیک روی ستون نماد → مودال جزئیات کامل موقعیت."""
        if column != 0:
            return
        data = self._position_row_from_table(row)
        if not data:
            return
        from ui.dialogs.trading_dialogs import PositionDetailDialog

        dialog = PositionDetailDialog(self.tr_, dict(data), self)
        dialog.close_trade_requested.connect(self.close_position_requested.emit)
        dialog.exec()

    def _on_position_activated(self, row: int, _column: int) -> None:
        """دوبار کلیک جزئیات را نشان می‌دهد؛ خروج فقط با دکمهٔ صریح."""
        self._on_position_cell_clicked(row, 0)

    def _set_columns(self, table: QTableWidget, columns: tuple[str, ...], prefix: str) -> None:
        """عنوان‌دهی ستون‌های یک جدول از کلیدهای ترجمه."""
        table.setHorizontalHeaderLabels(
            [self.tr_.tr(f"{prefix}{name}") for name in columns]
        )

    # ------------------------------------------------------------------
    # فیلترها/معیارها/جدول تاریخچه — دست‌نخورده
    # ------------------------------------------------------------------
    def _build_filters(self) -> QWidget:
        """نوار فیلترها: بازهٔ تاریخ، نماد، جهت و وضعیت."""
        frame = QFrame(self)
        set_role(frame, "stat")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        self.from_label = QLabel(self.tr_.tr("trades.from_date"), frame)
        self.from_date = QDateEdit(frame)
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.from_date.dateChanged.connect(self._emit_filters)

        self.to_label = QLabel(self.tr_.tr("trades.to_date"), frame)
        self.to_date = QDateEdit(frame)
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.dateChanged.connect(self._emit_filters)

        self.symbol_label = QLabel(self.tr_.tr("trades.symbol"), frame)
        self.symbol_combo = QComboBox(frame)
        self.symbol_combo.addItem(self.tr_.tr("common.all"), "")
        self.symbol_combo.currentIndexChanged.connect(self._emit_filters)

        self.side_label = QLabel(self.tr_.tr("trades.side"), frame)
        self.side_combo = QComboBox(frame)
        self.side_combo.currentIndexChanged.connect(self._emit_filters)

        self.status_label = QLabel(self.tr_.tr("trades.status"), frame)
        self.status_combo = QComboBox(frame)
        self.status_combo.currentIndexChanged.connect(self._emit_filters)

        self._fill_filter_combos()

        for widget in (
            self.from_label, self.from_date,
            self.to_label, self.to_date,
            self.symbol_label, self.symbol_combo,
            self.side_label, self.side_combo,
            self.status_label, self.status_combo,
        ):
            layout.addWidget(widget)
        layout.addStretch(1)
        return frame

    def _build_metrics(self) -> QWidget:
        """نوار چهار معیار کلیدی."""
        frame = QFrame(self)
        set_role(frame, "card")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(24)

        self._metric_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for key in ("total", "win_rate", "total_pnl", "profit_factor"):
            cell = QWidget(frame)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(2)

            caption = QLabel(self.tr_.tr(f"trades.metrics.{key}"), cell)
            set_role(caption, "muted")
            value = QLabel("—", cell)
            set_role(value, "metric")
            value.setStyleSheet("font-size: 19px;")

            cell_layout.addWidget(caption)
            cell_layout.addWidget(value)
            layout.addWidget(cell)
            self._metric_labels[key] = (caption, value)

        layout.addStretch(1)
        return frame

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def set_trades(
        self,
        rows: list[dict[str, Any]],
        *,
        page: int = 1,
        pages: int = 1,
        page_text: str = "",
    ) -> None:
        """
        پرکردن جدول با معاملات.

        هر ردیف باید کلیدهای متنی از پیش قالب‌بندی‌شده داشته باشد
        (`*_text`) تا این صفحه درگیر قالب‌بندی عدد و تاریخ نشود؛ آن کار
        وظیفهٔ کنترلر است که به تنظیمات محلی دسترسی دارد.
        """
        selected = self.trade_row(self.table.currentRow())
        selected_id = selected.get("id") if selected else None
        self._rows = list(rows or [])
        self._page, self._pages = page, pages

        self.table.setSortingEnabled(False)
        # v2.5.0: اگر همان معاملات با همان ترتیب باشند (تیک زندهٔ قیمت)،
        # فقط متن خانه‌ها عوض می‌شود — دکمه‌ها از نو ساخته نمی‌شوند تا
        # جدول هر ثانیه چشمک نزند و کلیک روی «بستن» گم نشود.
        new_ids = [row.get("id") for row in self._rows]
        in_place = new_ids == getattr(self, "_row_ids", None) and self.table.rowCount() == len(self._rows)
        self._row_ids = new_ids
        if not in_place:
            self.table.setRowCount(len(self._rows))
        action_column = HISTORY_COLUMNS.index("action")

        for index, row in enumerate(self._rows):
            status_key = str(row.get("status", "")).lower()
            for column, name in enumerate(HISTORY_COLUMNS):
                if name == "action":
                    continue
                item = self._history_item(name, row)
                current = self.table.item(index, column)
                if (
                    in_place
                    and current is not None
                    and current.text() == item.text()
                    and current.foreground().color() == item.foreground().color()
                ):
                    continue
                self.table.setItem(index, column, item)

            has_button = self.table.cellWidget(index, action_column) is not None
            if status_key == "open":
                if not (in_place and has_button):
                    button = make_button(self.tr_.tr("trades.close_trade"))
                    button.clicked.connect(
                        lambda _checked=False, tid=int(row["id"]): self.close_requested.emit(tid)
                    )
                    self.table.setCellWidget(index, action_column, button)
                if self.table.item(index, action_column) is None:
                    self.table.setItem(index, action_column, self._cell(""))
            else:
                if has_button:
                    self.table.removeCellWidget(index, action_column)
                self.table.setItem(index, action_column, self._cell(""))

        selected_index = next((i for i, row in enumerate(self._rows) if row.get("id") == selected_id), -1)
        if selected_index >= 0:
            self.table.selectRow(selected_index)
        else:
            self.table.setCurrentCell(-1, -1)
            self.table.clearSelection()
        has_rows = bool(self._rows)
        self.table.setVisible(has_rows)
        self.empty_state.setVisible(not has_rows)
        self.pagination.setVisible(has_rows)
        self._page_text = page_text
        self.pagination.configure(
            page=page,
            pages=pages,
            text=page_text or self.tr_.tr("trades.page_info", page=page, pages=pages),
        )

    def _history_item(self, name: str, row: dict[str, Any]) -> QTableWidgetItem:
        """یک خانهٔ جدول تاریخچه با رنگ و چینش مناسب ستون (v2.5.0)."""
        colors = self._theme.colors if self._theme is not None else None
        if name == "symbol":
            item = QTableWidgetItem(str(row.get("symbol", "")))
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(self.tr_.tr("trades.history_cols.symbol_tip"))
            return item
        if name == "side":
            side_key = str(row.get("side", "")).lower()
            item = self._cell(self.tr_.tr(f"trades.sides.{side_key}", side_key))
            if colors is not None:
                item.setForeground(QColor(colors.success if side_key == "long" else colors.danger))
            return item
        if name == "status":
            status_key = str(row.get("status", "")).lower()
            text = self.tr_.tr(f"trades.statuses.{status_key}", status_key)
            if row.get("stage_text"):
                text = f"{text} · {row.get('stage_text')}"
            return self._cell(text)
        text = str(row.get(HISTORY_TEXT_KEYS.get(name, ""), "") or "—")
        if name == "targets" and text != "—":
            # جداسازی چپ‌به‌راست تا «TP1 … ✓» در چیدمان فارسی وارونه نشود
            text = f"\u2066{text}\u2069"
        item = self._cell(text)
        if name in ("pnl", "pnl_percent") and colors is not None:
            value = row.get("pnl")
            if isinstance(value, (int, float)):
                item.setForeground(QColor(colors.success if value >= 0 else colors.danger))
        if name == "targets" and row.get("targets_tip"):
            item.setToolTip(str(row.get("targets_tip")))
        if name == "price" and str(row.get("status", "")).lower() == "open":
            item.setToolTip(self.tr_.tr("trades.history_cols.price_live_tip"))
        return item

    def set_metrics(self, values: dict[str, str]) -> None:
        """به‌روزرسانی نوار معیارها با متن‌های آمادهٔ نمایش."""
        for key, (_, label) in self._metric_labels.items():
            label.setText(str(values.get(key, "—")))

    def set_symbols(self, symbols: list[str]) -> None:
        """
        پرکردن فیلتر نماد.

        انتخاب فعلی حفظ می‌شود تا فیلتر کاربر با تازه‌سازی از بین نرود.
        """
        current = self.symbol_combo.currentData()
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.clear()
        self.symbol_combo.addItem(self.tr_.tr("common.all"), "")
        for symbol in symbols:
            self.symbol_combo.addItem(symbol, symbol)
        position = self.symbol_combo.findData(current)
        if position >= 0:
            self.symbol_combo.setCurrentIndex(position)
        self.symbol_combo.blockSignals(False)
        # کمبوی نماد پنل پیش‌بینی هم همان فهرست را می‌گیرد
        self.set_auto_symbols(list(symbols or []))

    def filters(self) -> dict[str, Any]:
        """وضعیت فعلی فیلترها برای کنترلر."""
        return {
            "start": self.from_date.date().toPython(),
            "end": self.to_date.date().toPython(),
            "symbol": self.symbol_combo.currentData() or "",
            "side": self.side_combo.currentData() or "",
            "status": self.status_combo.currentData() or "",
            "page": self._page,
            "page_size": PAGE_SIZE,
        }

    def trade_row(self, index: int) -> dict[str, Any] | None:
        """داده یک ردیف بر پایهٔ موقعیت آن در جدول."""
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    # ------------------------------------------------------------------
    # پوسته و زبان
    # ------------------------------------------------------------------
    def apply_theme(self, theme: Any) -> None:
        """اعمال پوسته روی رنگ‌های وابسته به داده."""
        self._theme = theme
        if self._rows:
            self.set_trades(
                self._rows, page=self._page, pages=self._pages, page_text=self._page_text
            )
        if self._position_rows:
            self.set_open_positions(self._position_rows)
        if self._opportunity_rows:
            self._render_opportunities()

    def resizeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """چیدمان واکنش‌گرا: نمودار|پیش‌بینی در عرض کم زیر هم (§۱۲)."""
        super().resizeEvent(event)
        row = getattr(self, "chart_row", None)
        if row is not None:
            row.reflow(self.width())

    def retranslate(self) -> None:
        """بازسازی متن‌ها پس از تغییر زبان."""
        super().retranslate()
        self.close_trade_button.setText(self.tr_.tr("trades.close_trade"))
        self.close_hint.setText(self.tr_.tr("trades.close_hint"))
        self.refresh_button.setText(self.tr_.tr("common.refresh"))
        self.export_button.setText(self.tr_.tr("trades.export_csv"))
        self.clear_button.setText(self.tr_.tr("trades.clear_history"))
        self.notice.setText(self.tr_.tr("trades.paper_notice"))
        self.from_label.setText(self.tr_.tr("trades.from_date"))
        self.to_label.setText(self.tr_.tr("trades.to_date"))
        self.symbol_label.setText(self.tr_.tr("trades.symbol"))
        self.side_label.setText(self.tr_.tr("trades.side"))
        self.status_label.setText(self.tr_.tr("trades.status"))
        for key, (caption, _) in self._metric_labels.items():
            caption.setText(self.tr_.tr(f"trades.metrics.{key}"))
        for key, (caption, _) in getattr(self, "_dashboard_cells", {}).items():
            caption.setText(self.tr_.tr(f"trades.auto.cell_{key}"))
        for key, (caption, _) in getattr(self, "_risk_cells", {}).items():
            caption.setText(self.tr_.tr(f"trades.auto.risk_{key}"))
        self.auto_settings_button.setText(
            self.tr_.tr(
                "trades.auto.settings_open"
                if getattr(self, "_config_collapsed", False)
                else "trades.auto.settings_toggle"
            )
        )
        self._update_terminal_tab_titles()
        self.chart_card.set_title(self.tr_.tr("trades.auto.chart_title"))
        self.prediction_card.set_title(self.tr_.tr("trades.auto.prediction_title"))
        self.retranslate_chart()
        self.empty_state.configure(
            icon="⇄",
            title=self.tr_.tr("trades.empty"),
            detail=self.tr_.tr("trades.empty_hint"),
        )
        self._fill_filter_combos()
        self._retranslate_headers()
        self.tabs.setTabText(0, self.tr_.tr("trades.auto.tab_title"))
        self.tabs.setTabText(1, self.tr_.tr("trades.auto.tab_history"))
        self._set_columns(self.opportunity_table, OPPORTUNITY_COLUMNS, "trades.auto.opp_")
        self._set_columns(self.positions_table, POSITION_COLUMNS, "trades.auto.pos_")
        self.opportunity_search.setPlaceholderText(self.tr_.tr("trades.auto.search_hint"))
        self.close_position_button.setText(self.tr_.tr("trades.auto.close_selected"))
        self.emergency_button.setText(self.tr_.tr("trades.auto.emergency"))
        current_filter = self.opportunity_filter_combo.currentData()
        self.opportunity_filter_combo.blockSignals(True)
        self.opportunity_filter_combo.clear()
        for key in ("opp_filter_all", "opp_filter_enterable", "opp_filter_skipped"):
            self.opportunity_filter_combo.addItem(
                self.tr_.tr(f"trades.auto.{key}"), key
            )
        position = self.opportunity_filter_combo.findData(current_filter)
        if position >= 0:
            self.opportunity_filter_combo.setCurrentIndex(position)
        self.opportunity_filter_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    def _fill_filter_combos(self) -> None:
        """پرکردن گزینه‌های جهت و وضعیت با حفظ انتخاب فعلی."""
        for combo, keys, prefix in (
            (self.side_combo, SIDE_FILTERS, "trades.sides"),
            (self.status_combo, STATUS_FILTERS, "trades.statuses"),
        ):
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for key in keys:
                combo.addItem(self.tr_.tr(f"{prefix}.{key}"), "" if key == "all" else key)
            position = combo.findData(current)
            if position >= 0:
                combo.setCurrentIndex(position)
            combo.blockSignals(False)

    def _retranslate_headers(self) -> None:
        """عنوان ستون‌های جدول تاریخچه — از `HISTORY_COLUMNS` (v2.5.0)."""
        self.table.setHorizontalHeaderLabels(
            [self.tr_.tr(f"trades.history_cols.{name}") for name in HISTORY_COLUMNS]
        )

    def _emit_filters(self) -> None:
        """انتشار تغییر فیلتر؛ صفحه به اول بازمی‌گردد."""
        self._page = 1
        self.filters_changed.emit(self.filters())

    def _on_page_changed(self, page: int) -> None:
        """رفتن به صفحهٔ دیگر."""
        self._page = page
        self.filters_changed.emit(self.filters())

    def _selected_row(self) -> int:
        """
        سطر انتخاب‌شده؛ در چیدمان راست‌به‌چپ `currentRow` تنها کافی نیست.
        """
        row = self.table.currentRow()
        if row < 0:
            model = self.table.selectionModel()
            if model is not None:
                rows = model.selectedRows()
                if rows:
                    return rows[0].row()
        return row

    def _emit_close_selected(self) -> None:
        """بستن معاملهٔ بازِ انتخاب‌شده."""
        row = self._selected_row()
        data = self.trade_row(row) if row >= 0 else None
        if not data or str(data.get("status")) != "open":
            self.close_blocked.emit()
            return
        self.close_requested.emit(int(data.get("id", 0)))

    def show_open_history(self) -> None:
        """پس از ورود موفق، تاریخچهٔ باز بدون فیلتر پنهان‌کننده نمایش داده شود."""
        self._page = 1
        for combo, data in ((self.symbol_combo, "all"), (self.side_combo, "all"), (self.status_combo, "open")):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(data)))
            combo.blockSignals(False)
        for widget, date in ((self.from_date, QDate.currentDate().addDays(-30)), (self.to_date, QDate.currentDate())):
            widget.blockSignals(True)
            widget.setDate(date)
            widget.blockSignals(False)
        self.tabs.setCurrentIndex(1)

    def _on_history_cell_clicked(self, row: int, column: int) -> None:
        if column == 1:
            self._on_row_activated(row, column)

    def _on_row_activated(self, row: int, _column: int) -> None:
        """کلیک نماد/دوبار کلیک ردیف، مودال جزئیات؛ نه خروج ناخواسته."""
        data = self.trade_row(row)
        if not data:
            return
        from ui.dialogs.trading_dialogs import PositionDetailDialog
        dialog = PositionDetailDialog(self.tr_, dict(data), self)
        dialog.close_trade_requested.connect(self.close_requested.emit)
        dialog.exec()

    @staticmethod
    def _cell(text: str) -> QTableWidgetItem:
        """ساخت خانهٔ جدول با چینش وسط."""
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item


def set_role_item(item: QTableWidgetItem, role: str, theme: Any) -> None:
    """رنگ‌کردن یک خانهٔ جدول بر پایهٔ نقش — با پوستهٔ فعال."""
    if theme is None:
        return
    try:
        colors = theme.colors
        color = {
            "bullish": colors.success,
            "bearish": colors.danger,
        }.get(role)
        if color:
            item.setForeground(QColor(color))
    except Exception:  # noqa: BLE001 - پوسته نباید جدول را بشکند
        pass


__all__ = [
    "AUTO_ENGINE_MODES",
    "AUTO_TIMEFRAMES",
    "DASHBOARD_CELLS",
    "HISTORY_COLUMNS",
    "INFO_CARDS",
    "OPPORTUNITY_COLUMNS",
    "PAGE_SIZE",
    "POSITION_COLUMNS",
    "RISK_CELLS",
    "SIDE_FILTERS",
    "STATUS_FILTERS",
    "TradesPage",
]
