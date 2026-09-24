"""
صفحه سیگنال‌ها.

نمایش سیگنال جاری، سابقه سیگنال‌ها و یادآوری اینکه «انتظار» هم یک تصمیم
معتبر است.
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut

from localization import Translator
from market.timeframes import SUPPORTED_TIMEFRAMES
from ui.pages.base_page import BasePage
from ui.signal_share import copy_to_clipboard, format_signal_text, signal_symbol
from ui.signal_grading import (
    freshness_grade,
    CONFIDENCE_GOOD,
    color_for,
    confidence_grade,
    direction_grade,
    risk_grade,
    signal_risk_level,
)
from ui.widgets import (
    Card,
    ChipBar,
    SignalCard,
    configure_button_column,
    configure_table,
    make_button,
)

#: تایم‌فریم‌های پیش‌فرض تحلیل چنددوره‌ای (هم‌راستا با موتور سیگنال)
DEFAULT_SIGNAL_TIMEFRAMES = ("1d", "4h", "1h", "15m")


class _RecommendationTone:
    """
    آداپتور رنگ برای `color_for` که شیئی دارای `token` می‌خواهد.

    توصیه درجه‌بندی نیست، ولی باید از همان سامانهٔ رنگ پوسته استفاده
    کند تا با عوض‌شدن پوسته هماهنگ بماند.
    """

    __slots__ = ("token",)

    def __init__(self, token: str) -> None:
        self.token = token


class SignalsPage(BasePage):
    """صفحه تولید و سابقه سیگنال."""

    title_key = "nav.signals"
    subtitle_key = "signals.subtitle"

    # شلوغ‌ترین صفحهٔ برنامه: کنترل‌های تولید سیگنال، نوار تایم‌فریم‌ها،
    # کارت پویش با جدولش، کارت سیگنال‌گیری خودکار با دو ردیف تنظیمات، و
    # کارت‌های سیگنال جاری و سابقه. مجموع حداقل‌ ارتفاعشان از ارتفاع یک
    # نمایشگر معمولی لپ‌تاپ بیشتر می‌شود، پس بدون پیمایش همه‌چیز روی هم
    # فشرده می‌شد.
    scrollable = True

    # شمارهٔ ستون‌ها به‌صورت ثابت نام‌گذاری شده‌اند.
    #
    # چرا؟ افزودن ستون «اعتبار» در نسخهٔ ۱.۹.۵ پنج آزمون را شکست، چون
    # همه عدد خام ۷ را نوشته بودند. با نام‌گذاری، ستون بعدی فقط یک خط
    # اینجا را عوض می‌کند.
    SCAN_COL_FRESHNESS = 7
    SCAN_COL_ACTION = 8
    HISTORY_COL_RECOMMENDATION = 6
    HISTORY_COL_FRESHNESS = 7
    HISTORY_COL_ACTION = 8

    #: کاربر تحلیل نوشتاری یک سیگنال را خواست (شناسهٔ سیگنال)
    analysis_requested = Signal(int)

    #: کاربر دکمهٔ «پویش همهٔ نمادها» را زد
    scan_requested = Signal()
    #: کاربر پویش در جریان را متوقف کرد
    scan_stop_requested = Signal()
    #: کاربر برای یک ردیفِ نتیجهٔ پویش تحلیل هوشمند خواست (نماد)
    scan_ai_requested = Signal(str)
    #: کاربر روی یک ردیف نتیجهٔ پویش کلیک کرد و جزئیاتش را می‌خواهد (نماد)
    scan_detail_requested = Signal(str)
    #: تنظیمات سیگنال‌گیری خودکار تغییر کرد (دیکشنری مقادیر)
    auto_scan_changed = Signal(dict)
    #: کاربر خواست همین حالا یک چرخهٔ خودکار اجرا شود
    auto_scan_run_now = Signal()
    #: نسخهٔ ۲.۴.۰ — گزینه‌های پایدار پویش دستی (جهان، تعداد، پالایش) تغییر کرد
    scan_settings_changed = Signal(dict)
    #: نسخهٔ ۲.۴.۲ — پیام کوتاه «کپی شد» برای نمایش در اعلان برنامه
    copy_notice = Signal(str)

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._history_rows: list[dict[str, Any]] = []
        self._scan_rows: list[dict[str, Any]] = []
        self._current_signal: dict[str, Any] = {}
        super().__init__(translator, parent)

    def build(self) -> None:
        """ساخت کارت سیگنال جاری و جدول سابقه."""
        self._theme: Any = None
        controls = QHBoxLayout()

        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.setMinimumWidth(200)
        self.symbol_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = self.symbol_combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)

        # تایم‌فریمی که سیگنال در آن گرفته می‌شود — کاربر صریحاً خواست
        # بتواند تایم‌فریم سیگنال را انتخاب کند.
        self.timeframe_combo = QComboBox()
        for timeframe in SUPPORTED_TIMEFRAMES:
            self.timeframe_combo.addItem(timeframe.code, timeframe.code)
        default_index = self.timeframe_combo.findData("4h")
        if default_index >= 0:
            self.timeframe_combo.setCurrentIndex(default_index)

        self.use_ai_checkbox = QCheckBox(self.tr_.tr("analysis.use_ai"))
        self.use_ai_checkbox.setChecked(True)

        self.generate_button = make_button(self.tr_.tr("signals.generate"), primary=True)
        self.symbol_label = QLabel(self.tr_.tr("common.symbol"))
        self.timeframe_label = QLabel(self.tr_.tr("common.timeframe"))

        controls.addWidget(self.symbol_label)
        controls.addWidget(self.symbol_combo)
        controls.addWidget(self.timeframe_label)
        controls.addWidget(self.timeframe_combo)
        controls.addWidget(self.use_ai_checkbox)
        controls.addWidget(self.generate_button)
        controls.addStretch(1)
        self.layout_root().addLayout(controls)

        # ---- تایم‌فریم‌های مورد بررسی ----
        # موتور سیگنال چند تایم‌فریم را با هم وزن می‌دهد. پیش‌تر این
        # فهرست فقط از تنظیمات می‌آمد و کاربر در همین صفحه کنترلی رویش
        # نداشت؛ حالا می‌تواند برای هر سیگنال انتخابش را عوض کند.
        timeframe_row = QHBoxLayout()
        timeframe_row.setSpacing(8)
        self.timeframes_label = QLabel(self.tr_.tr("signals.timeframes"))
        self.timeframes_label.setProperty("role", "muted")
        self.timeframe_chips = ChipBar(exclusive=False)
        self.timeframe_chips.set_options(
            [(item.code, item.code) for item in SUPPORTED_TIMEFRAMES]
        )
        self.timeframe_chips.set_selection(DEFAULT_SIGNAL_TIMEFRAMES)
        timeframe_row.addWidget(self.timeframes_label)
        timeframe_row.addWidget(self.timeframe_chips)
        timeframe_row.addStretch(1)
        self.layout_root().addLayout(timeframe_row)

        # نوار پیشرفت و مسیر تصمیم عامل: کاربر باید ببیند هوش مصنوعی
        # دارد چه می‌کند، نه اینکه به دکمهٔ بی‌حرکت نگاه کند.
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        self.layout_root().addWidget(self.progress)

        self.agent_trail = QLabel("")
        self.agent_trail.setProperty("role", "muted")
        self.agent_trail.setWordWrap(True)
        self.agent_trail.hide()
        self.layout_root().addWidget(self.agent_trail)

        self._build_scanner()

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # کارت سیگنال جاری + دکمهٔ تحلیل.
        #
        # کاربر خواست از روی همین کارت هم بتواند تحلیل هوش مصنوعی را
        # ببیند یا دوباره بگیرد؛ قبلاً هیچ دکمه‌ای اینجا نبود و تنها راه
        # رفتن به جدول سابقه بود.
        current_box = QWidget()
        current_layout = QVBoxLayout(current_box)
        current_layout.setContentsMargins(0, 0, 0, 0)
        current_layout.setSpacing(8)

        self.signal_card = SignalCard(self._signal_labels())
        current_layout.addWidget(self.signal_card, 1)

        self.current_analysis_button = make_button(
            "🧠  " + self.tr_.tr("signals.rerun_ai")
        )
        self.current_analysis_button.setEnabled(False)
        self.current_analysis_button.clicked.connect(self._on_current_analysis)
        current_layout.addWidget(self.current_analysis_button)

        splitter.addWidget(current_box)

        self.history_card = Card(self.tr_.tr("signals.history"))

        # نوار مرتب‌سازی و دسته‌بندی سابقه.
        #
        # کاربر خواست سیگنال‌ها بر اساس میزان اطمینان و جهت (صعودی/نزولی)
        # مرتب شوند. ترتیب پیش‌فرض «قوی‌ترین اول» است، چون چیزی که کاربر
        # دنبالش است بهترین فرصت است نه جدیدترین ردیف.
        sort_row = QHBoxLayout()
        sort_row.setSpacing(8)
        self.history_sort_label = QLabel(self.tr_.tr("signals.sort_by"))
        self.history_sort_combo = QComboBox()
        for key in (
            "confidence_desc",
            "confidence_asc",
            "direction",
            "newest",
            "symbol",
        ):
            self.history_sort_combo.addItem(self.tr_.tr(f"signals.sort.{key}"), key)
        self.history_sort_combo.currentIndexChanged.connect(
            lambda _=0: self._resort_history()
        )
        self.history_group_check = QCheckBox(self.tr_.tr("signals.group_by_direction"))
        self.history_group_check.toggled.connect(lambda _=False: self._resort_history())
        sort_row.addWidget(self.history_sort_label)
        sort_row.addWidget(self.history_sort_combo, 1)
        sort_row.addWidget(self.history_group_check)
        self.history_card.body().addLayout(sort_row)

        self.history_table = QTableWidget(0, 9)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_card.add(self.history_table)
        self._install_copy_support(self.history_table, self.history_row_at)
        splitter.addWidget(self.history_card)
        splitter.setSizes([340, 620])

        # کارت‌های سیگنال جاری و سابقه ارتفاع معناداری لازم دارند، وگرنه
        # داخل ناحیهٔ پیمایش تا حد چند ردیف جمع می‌شوند.
        splitter.setMinimumHeight(320)
        self.layout_root().addWidget(splitter, 1)

        self.wait_note = QLabel(self.tr_.tr("signals.wait_note"))
        self.wait_note.setProperty("role", "muted")
        self.wait_note.setWordWrap(True)
        # برچسب چندخطی با `setWordWrap` ارتفاع لازمش را به چیدمان
        # اعلام نمی‌کند و به یک خط فشرده می‌شود؛ متن توضیح «انتظار»
        # نصفه دیده می‌شد.
        self.wait_note.setMinimumHeight(self.wait_note.sizeHint().height())
        self.layout_root().addWidget(self.wait_note)

        self._apply_headers()

    def _build_scanner(self) -> None:
        """
        بخش «پویش همهٔ نمادها».

        کاربر خواست دکمه‌ای باشد که سیستم را وادارد از همهٔ نمادها
        یکی‌یکی سیگنال بگیرد و بالاترین ضریب اطمینان بالا بنشیند. چون
        این کار روی صدها نماد اجرا می‌شود، عمداً فقط موتور ریاضی را صدا
        می‌زند؛ تحلیل هوش مصنوعی دکمهٔ جداگانه در هر ردیف دارد.
        """
        self.scan_card = Card(self.tr_.tr("signals.scan_results"))

        self.scan_hint = QLabel(self.tr_.tr("signals.scan_hint"))
        self.scan_hint.setProperty("role", "faint")
        self.scan_hint.setWordWrap(True)
        self.scan_card.add(self.scan_hint)

        row = QWidget()
        scan_row = QHBoxLayout(row)
        scan_row.setContentsMargins(0, 0, 0, 0)
        scan_row.setSpacing(8)

        self.scan_button = make_button(self.tr_.tr("signals.scan"), primary=True)
        self.scan_button.clicked.connect(self.scan_requested.emit)

        self.scan_stop_button = make_button(self.tr_.tr("signals.scan_stop"), role="ghost")
        self.scan_stop_button.clicked.connect(self.scan_stop_requested.emit)
        self.scan_stop_button.setVisible(False)

        # سقف شمار نمادها: پویش ۱۳۰۰ نماد چند دقیقه طول می‌کشد و
        # بیشترشان بی‌نقدشوندگی‌اند. نمادها بر پایهٔ گردش مالی مرتب
        # می‌شوند، پس «۱۲۰ تا» یعنی ۱۲۰ نماد پرگردش بازار.
        self.scan_limit_label = QLabel(self.tr_.tr("signals.scan_limit"))
        self.scan_limit_label.setProperty("role", "muted")
        self.scan_limit_spin = QSpinBox()
        self.scan_limit_spin.setRange(5, 500)
        self.scan_limit_spin.setSingleStep(10)
        self.scan_limit_spin.setValue(60)
        self.scan_limit_spin.setFixedWidth(88)

        self.scan_confidence_label = QLabel(self.tr_.tr("signals.scan_min_confidence"))
        self.scan_confidence_label.setProperty("role", "muted")
        self.scan_confidence_spin = QSpinBox()
        self.scan_confidence_spin.setRange(0, 95)
        self.scan_confidence_spin.setSingleStep(5)
        self.scan_confidence_spin.setValue(CONFIDENCE_GOOD)
        self.scan_confidence_spin.setSuffix(" %")
        self.scan_confidence_spin.setFixedWidth(88)

        self.scan_wait_check = QCheckBox(self.tr_.tr("signals.scan_include_wait"))

        # ---- نسخهٔ ۲.۴.۰: دامنهٔ پویش. کاربر خواست تعداد دستی بماند، ولی
        # گزینه‌ای باشد که کل نمادهای صرافی را پویش کند.
        self.scan_scope_label = QLabel(self.tr_.tr("signals.scan_scope"))
        self.scan_scope_label.setProperty("role", "muted")
        self.scan_scope_combo = QComboBox()
        self._fill_scope_combo(self.scan_scope_combo, "signals.scan_scope_top", "signals.scan_scope_all")
        self.scan_scope_combo.currentIndexChanged.connect(self._on_scan_scope_changed)
        self.scan_limit_spin.valueChanged.connect(self._emit_scan_settings)

        self.scan_smart_check = QCheckBox(self.tr_.tr("signals.scan_smart_filter"))
        self.scan_smart_check.setChecked(True)
        self.scan_smart_check.setToolTip(self.tr_.tr("signals.scan_smart_filter_tip"))
        self.scan_smart_check.toggled.connect(self._emit_scan_settings)

        self.scan_turnover_label = QLabel(self.tr_.tr("signals.scan_min_turnover"))
        self.scan_turnover_label.setProperty("role", "muted")
        self.scan_turnover_spin = self._make_turnover_spin()
        self.scan_turnover_spin.valueChanged.connect(self._emit_scan_settings)

        scan_row.addWidget(self.scan_button)
        scan_row.addWidget(self.scan_stop_button)
        scan_row.addSpacing(12)
        scan_row.addWidget(self.scan_scope_label)
        scan_row.addWidget(self.scan_scope_combo)
        scan_row.addWidget(self.scan_limit_label)
        scan_row.addWidget(self.scan_limit_spin)
        scan_row.addWidget(self.scan_confidence_label)
        scan_row.addWidget(self.scan_confidence_spin)
        scan_row.addWidget(self.scan_wait_check)
        scan_row.addStretch(1)
        self.scan_card.add(row)

        filter_row = QWidget()
        filter_line = QHBoxLayout(filter_row)
        filter_line.setContentsMargins(0, 0, 0, 0)
        filter_line.setSpacing(8)
        filter_line.addWidget(self.scan_smart_check)
        filter_line.addSpacing(12)
        filter_line.addWidget(self.scan_turnover_label)
        filter_line.addWidget(self.scan_turnover_spin)
        filter_line.addStretch(1)
        self.scan_card.add(filter_row)
        self._scan_started_at = 0.0
        self._on_scan_scope_changed(emit=False)

        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setTextVisible(True)
        self.scan_progress.hide()
        self.scan_card.add(self.scan_progress)

        self.scan_status = QLabel("")
        self.scan_status.setProperty("role", "muted")
        self.scan_status.setWordWrap(True)
        self.scan_card.add(self.scan_status)

        # ستون‌ها: رتبه، نماد، جهت، ضریب اطمینان، ریسک، R/R، اهرم، تحلیل
        self.scan_table = QTableWidget(0, 9)
        self.scan_table.verticalHeader().setVisible(False)
        self.scan_table.setAlternatingRowColors(True)
        self.scan_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.scan_table.setMinimumHeight(190)
        # ارتفاع ثابت یعنی کاربر داخل جدول اسکرول کند در حالی که خود
        # صفحه هم اسکرول دارد — دو اسکرول تو در تو، گیج‌کننده. حالا
        # جدول تا سقفی معقول با تعداد نتایج رشد می‌کند.
        self.scan_table.setSizePolicy(
            self.scan_table.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Fixed,
        )
        # کلیک روی ردیف باید جزئیات همان نماد را باز کند. کاربر گزارش
        # داد «روی نماد کلیک می‌کنی جزئیات باز نمی‌شود» — جدول پویش
        # هیچ اتصال کلیکی نداشت. هم تک‌کلیک و هم دوکلیک وصل می‌شوند
        # چون جدول سابقه با دوکلیک کار می‌کند و کاربر همان را انتظار دارد.
        self.scan_table.cellClicked.connect(self._on_scan_cell_clicked)
        self.scan_table.cellDoubleClicked.connect(self._on_scan_cell_clicked)
        self.scan_card.add(self.scan_table)

        self.scan_cap_note = QLabel("")
        self.scan_cap_note.setProperty("role", "faint")
        self.scan_cap_note.setWordWrap(True)
        self.scan_cap_note.setVisible(False)
        self.scan_card.add(self.scan_cap_note)
        self._install_copy_support(self.scan_table, self.scan_row_at)

        self.scan_copy_hint = QLabel(self.tr_.tr("signals.share.table_hint"))
        self.scan_copy_hint.setProperty("role", "faint")
        self.scan_copy_hint.setWordWrap(True)
        self.scan_card.add(self.scan_copy_hint)

        self.scan_legend = QLabel(self.tr_.tr("signals.legend_text"))
        self.scan_legend.setProperty("role", "faint")
        self.scan_legend.setWordWrap(True)
        self.scan_card.add(self.scan_legend)

        self.layout_root().addWidget(self.scan_card)
        self._apply_scan_headers()
        self._build_auto_scan()

    def _build_auto_scan(self) -> None:
        """
        پنل سیگنال‌گیری خودکار.

        کاربر خواست برنامه خودش هر چند دقیقه سیگنال بگیرد: هم روی
        نمادهای پراطمینانِ پویش‌های قبلی (تکرار سریع)، هم یک چرخش کامل
        روی همهٔ نمادها تا بهترین فرصت را خودش پیدا کند.
        """
        self.auto_card = Card(self.tr_.tr("signals.auto.title"))

        self.auto_hint = QLabel(self.tr_.tr("signals.auto.hint"))
        self.auto_hint.setProperty("role", "faint")
        self.auto_hint.setWordWrap(True)
        self.auto_card.add(self.auto_hint)

        # ---- سطر یک: روشن/خاموش و فاصلهٔ تمرکز
        row_one = QWidget()
        line_one = QHBoxLayout(row_one)
        line_one.setContentsMargins(0, 0, 0, 0)
        line_one.setSpacing(8)

        self.auto_enable_check = QCheckBox(self.tr_.tr("signals.auto.enable"))
        self.auto_enable_check.toggled.connect(self._on_auto_toggled)
        line_one.addWidget(self.auto_enable_check)
        line_one.addSpacing(12)

        # نسخهٔ ۲.۴.۰ — منبع: سیگنال‌های پیداشده، کل بازار یا هر دو
        self.auto_source_label = QLabel(self.tr_.tr("signals.auto.source"))
        self.auto_source_label.setProperty("role", "muted")
        self.auto_source_combo = QComboBox()
        for source in ("both", "found", "market"):
            self.auto_source_combo.addItem(
                self.tr_.tr(f"signals.auto.source_{source}"), source
            )
        self.auto_source_combo.currentIndexChanged.connect(self._on_auto_toggled)
        line_one.addWidget(self.auto_source_label)
        line_one.addWidget(self.auto_source_combo)

        self.auto_interval_label = QLabel(self.tr_.tr("signals.auto.interval"))
        self.auto_interval_label.setProperty("role", "muted")
        self.auto_interval_spin = QSpinBox()
        # بر حسب دقیقه؛ ثانیه در رابط کاربری بی‌معناست و کاربر را به
        # فاصله‌های غیرواقعی وسوسه می‌کند.
        self.auto_interval_spin.setRange(1, 720)
        self.auto_interval_spin.setValue(5)
        self.auto_interval_spin.setSuffix(" " + self.tr_.tr("common.minutes_short"))
        self.auto_interval_spin.setFixedWidth(104)
        self.auto_interval_spin.valueChanged.connect(self._emit_auto_config)
        line_one.addWidget(self.auto_interval_label)
        line_one.addWidget(self.auto_interval_spin)

        self.auto_focus_label = QLabel(self.tr_.tr("signals.auto.focus_size"))
        self.auto_focus_label.setProperty("role", "muted")
        self.auto_focus_spin = QSpinBox()
        self.auto_focus_spin.setRange(1, 100)
        self.auto_focus_spin.setValue(10)
        self.auto_focus_spin.setFixedWidth(80)
        self.auto_focus_spin.valueChanged.connect(self._emit_auto_config)
        line_one.addWidget(self.auto_focus_label)
        line_one.addWidget(self.auto_focus_spin)
        line_one.addStretch(1)
        self.auto_card.add(row_one)

        # ---- سطر دو: چرخش کامل روی همهٔ نمادها
        row_two = QWidget()
        line_two = QHBoxLayout(row_two)
        line_two.setContentsMargins(0, 0, 0, 0)
        line_two.setSpacing(8)

        self.auto_sweep_check = QCheckBox(self.tr_.tr("signals.auto.full_sweep"))
        self.auto_sweep_check.setChecked(True)
        self.auto_sweep_check.toggled.connect(self._on_auto_toggled)
        # از ۲.۴.۰ «منبع» جای این تیک را گرفته؛ برای سازگاری نگه داشته
        # و با منبع هم‌گام می‌شود (منبع ≠ found یعنی چرخش روشن).
        self.auto_sweep_check.setVisible(False)
        line_two.addWidget(self.auto_sweep_check)

        self.auto_sweep_interval_label = QLabel(self.tr_.tr("signals.auto.full_interval"))
        self.auto_sweep_interval_label.setProperty("role", "muted")
        self.auto_sweep_interval_spin = QSpinBox()
        self.auto_sweep_interval_spin.setRange(1, 1440)
        self.auto_sweep_interval_spin.setValue(30)
        self.auto_sweep_interval_spin.setSuffix(" " + self.tr_.tr("common.minutes_short"))
        self.auto_sweep_interval_spin.setFixedWidth(104)
        self.auto_sweep_interval_spin.valueChanged.connect(self._emit_auto_config)
        line_two.addWidget(self.auto_sweep_interval_label)
        line_two.addWidget(self.auto_sweep_interval_spin)

        self.auto_min_confidence_label = QLabel(self.tr_.tr("signals.auto.min_confidence"))
        self.auto_min_confidence_label.setProperty("role", "muted")
        self.auto_min_confidence_spin = QSpinBox()
        self.auto_min_confidence_spin.setRange(0, 95)
        self.auto_min_confidence_spin.setSingleStep(5)
        self.auto_min_confidence_spin.setValue(CONFIDENCE_GOOD)
        self.auto_min_confidence_spin.setSuffix(" %")
        self.auto_min_confidence_spin.setFixedWidth(88)
        self.auto_min_confidence_spin.valueChanged.connect(self._emit_auto_config)
        line_two.addWidget(self.auto_min_confidence_label)
        line_two.addWidget(self.auto_min_confidence_spin)

        self.auto_notify_check = QCheckBox(self.tr_.tr("signals.auto.notify"))
        self.auto_notify_check.setChecked(True)
        self.auto_notify_check.toggled.connect(self._emit_auto_config)
        line_two.addWidget(self.auto_notify_check)

        self.auto_run_button = make_button(self.tr_.tr("signals.auto.run_now"))
        self.auto_run_button.clicked.connect(self.auto_scan_run_now.emit)
        line_two.addWidget(self.auto_run_button)
        line_two.addStretch(1)
        self.auto_card.add(row_two)

        # ---- سطر سه (۲.۴.۰): جهان چرخش کامل و پالایش هوشمند
        row_three = QWidget()
        line_three = QHBoxLayout(row_three)
        line_three.setContentsMargins(0, 0, 0, 0)
        line_three.setSpacing(8)
        self.auto_universe_label = QLabel(self.tr_.tr("signals.auto.universe"))
        self.auto_universe_label.setProperty("role", "muted")
        self.auto_universe_combo = QComboBox()
        self._fill_scope_combo(self.auto_universe_combo, "signals.scan_scope_top", "signals.scan_scope_all")
        self.auto_universe_combo.setCurrentIndex(1)
        self.auto_universe_combo.currentIndexChanged.connect(self._on_auto_toggled)
        self.auto_sweep_limit_label = QLabel(self.tr_.tr("signals.scan_limit"))
        self.auto_sweep_limit_label.setProperty("role", "muted")
        self.auto_sweep_limit_spin = QSpinBox()
        self.auto_sweep_limit_spin.setRange(10, 1000)
        self.auto_sweep_limit_spin.setSingleStep(10)
        self.auto_sweep_limit_spin.setValue(120)
        self.auto_sweep_limit_spin.setFixedWidth(88)
        self.auto_sweep_limit_spin.valueChanged.connect(self._emit_auto_config)
        self.auto_smart_check = QCheckBox(self.tr_.tr("signals.scan_smart_filter"))
        self.auto_smart_check.setToolTip(self.tr_.tr("signals.scan_smart_filter_tip"))
        self.auto_smart_check.setChecked(True)
        self.auto_smart_check.toggled.connect(self._emit_auto_config)
        self.auto_turnover_label = QLabel(self.tr_.tr("signals.scan_min_turnover"))
        self.auto_turnover_label.setProperty("role", "muted")
        self.auto_turnover_spin = self._make_turnover_spin()
        self.auto_turnover_spin.valueChanged.connect(self._emit_auto_config)
        for widget in (
            self.auto_universe_label, self.auto_universe_combo,
            self.auto_sweep_limit_label, self.auto_sweep_limit_spin,
            self.auto_smart_check, self.auto_turnover_label, self.auto_turnover_spin,
        ):
            line_three.addWidget(widget)
        line_three.addStretch(1)
        self.auto_card.add(row_three)

        # ---- وضعیت زنده
        self.auto_status = QLabel(self.tr_.tr("signals.auto.status_off"))
        self.auto_status.setProperty("role", "muted")
        self.auto_status.setWordWrap(True)
        self.auto_card.add(self.auto_status)

        self.auto_focus_list = QLabel("")
        self.auto_focus_list.setProperty("role", "faint")
        self.auto_focus_list.setWordWrap(True)
        self.auto_focus_list.setVisible(False)
        self.auto_card.add(self.auto_focus_list)

        self.layout_root().addWidget(self.auto_card)
        self._on_auto_toggled()

    def _auto_source(self) -> str:
        """منبع انتخاب‌شدهٔ سیگنال‌گیری خودکار (both|found|market)."""
        return str(self.auto_source_combo.currentData() or "both")

    def _sync_auto_enabled(self) -> None:
        """فعال/غیرفعال کردن کنترل‌های وابسته بدون اعلام تغییر."""
        enabled = self.auto_enable_check.isChecked()
        source = self._auto_source()
        sweep = source != "found"
        focus = source != "market"
        # تیک پنهان «چرخش کامل» همیشه با منبع هم‌گام است
        self.auto_sweep_check.blockSignals(True)
        self.auto_sweep_check.setChecked(sweep)
        self.auto_sweep_check.blockSignals(False)
        for widget in (
            self.auto_source_combo,
            self.auto_interval_spin,
            self.auto_min_confidence_spin,
            self.auto_notify_check,
            self.auto_run_button,
        ):
            widget.setEnabled(enabled)
        self.auto_focus_spin.setEnabled(enabled and focus)
        self.auto_sweep_check.setEnabled(enabled)
        for widget in (
            self.auto_sweep_interval_spin,
            self.auto_universe_combo,
            self.auto_smart_check,
            self.auto_turnover_spin,
        ):
            widget.setEnabled(enabled and sweep)
        self.auto_sweep_limit_spin.setEnabled(
            enabled and sweep and self.auto_universe_combo.currentData() == "top"
        )

    def _on_auto_toggled(self) -> None:
        """فعال/غیرفعال کردن کنترل‌های وابسته و اعلام تغییر."""
        self._sync_auto_enabled()
        self._emit_auto_config()

    def _emit_auto_config(self) -> None:
        """اعلام تنظیمات تازه به کنترلر."""
        self.auto_scan_changed.emit(self.auto_scan_options())

    def auto_scan_options(self) -> dict[str, Any]:
        """تنظیمات جاری سیگنال‌گیری خودکار (دقیقه → ثانیه)."""
        return {
            "signals.auto_scan_enabled": bool(self.auto_enable_check.isChecked()),
            "signals.auto_scan_interval": int(self.auto_interval_spin.value()) * 60,
            "signals.auto_scan_full_sweep": bool(self.auto_sweep_check.isChecked()),
            "signals.auto_scan_full_interval": int(self.auto_sweep_interval_spin.value()) * 60,
            "signals.auto_scan_focus_size": int(self.auto_focus_spin.value()),
            "signals.auto_scan_min_confidence": int(self.auto_min_confidence_spin.value()),
            "signals.auto_scan_notify": bool(self.auto_notify_check.isChecked()),
            "signals.auto_scan_source": self._auto_source(),
            "signals.auto_scan_universe": str(self.auto_universe_combo.currentData() or "all"),
            "signals.auto_scan_sweep_limit": int(self.auto_sweep_limit_spin.value()),
            "signals.auto_scan_min_turnover": float(self.auto_turnover_spin.value()) * 1000.0,
            "signals.auto_scan_smart_filter": bool(self.auto_smart_check.isChecked()),
        }

    def set_auto_scan_options(self, values: dict[str, Any]) -> None:
        """
        نشاندن تنظیمات ذخیره‌شده در فرم.

        سیگنال‌ها موقتاً خاموش می‌شوند تا پرکردن فرم، خودش را به‌عنوان
        «تغییر کاربر» جا نزند و حلقهٔ ذخیره‌سازی راه نیندازد.
        """
        widgets = (
            self.auto_enable_check,
            self.auto_interval_spin,
            self.auto_sweep_check,
            self.auto_sweep_interval_spin,
            self.auto_focus_spin,
            self.auto_min_confidence_spin,
            self.auto_notify_check,
            self.auto_source_combo,
            self.auto_universe_combo,
            self.auto_sweep_limit_spin,
            self.auto_smart_check,
            self.auto_turnover_spin,
        )
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.auto_enable_check.setChecked(
                bool(values.get("signals.auto_scan_enabled", False))
            )
            self.auto_interval_spin.setValue(
                max(1, int(values.get("signals.auto_scan_interval", 300) or 300) // 60)
            )
            self.auto_sweep_check.setChecked(
                bool(values.get("signals.auto_scan_full_sweep", True))
            )
            self.auto_sweep_interval_spin.setValue(
                max(1, int(values.get("signals.auto_scan_full_interval", 1800) or 1800) // 60)
            )
            self.auto_focus_spin.setValue(
                int(values.get("signals.auto_scan_focus_size", 10) or 10)
            )
            self.auto_min_confidence_spin.setValue(
                int(values.get("signals.auto_scan_min_confidence", CONFIDENCE_GOOD) or 0)
            )
            self.auto_notify_check.setChecked(
                bool(values.get("signals.auto_scan_notify", True))
            )
            source = str(values.get("signals.auto_scan_source", "both") or "both").lower()
            if source not in ("both", "found", "market"):
                source = "both"
            # سازگاری: کاربری که پیش از ۲.۴.۰ چرخش کامل را خاموش کرده بود،
            # در عمل «فقط سیگنال‌های پیداشده» را می‌خواست.
            if source == "both" and not bool(values.get("signals.auto_scan_full_sweep", True)):
                source = "found"
            self._set_combo_data(self.auto_source_combo, source)
            universe = str(values.get("signals.auto_scan_universe", "all") or "all").lower()
            self._set_combo_data(self.auto_universe_combo, "top" if universe == "top" else "all")
            self.auto_sweep_limit_spin.setValue(
                int(values.get("signals.auto_scan_sweep_limit", 120) or 120)
            )
            self.auto_smart_check.setChecked(
                bool(values.get("signals.auto_scan_smart_filter", True))
            )
            self.auto_turnover_spin.setValue(
                self._safe_number(values.get("signals.auto_scan_min_turnover", 0.0)) / 1000.0
            )
        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self._sync_auto_enabled()

    def set_auto_scan_status(self, text: str, *, focus: list[str] | None = None) -> None:
        """نمایش وضعیت زنده و فهرست نمادهای تحت تمرکز."""
        self.auto_status.setText(text)
        symbols = list(focus or [])
        if symbols:
            self.auto_focus_list.setText(
                self.tr_.tr("signals.auto.focus_list", symbols="  ·  ".join(symbols))
            )
            self.auto_focus_list.setVisible(True)
        else:
            self.auto_focus_list.setVisible(False)

    def _apply_scan_headers(self) -> None:
        """سرستون‌های جدول نتیجهٔ پویش."""
        self.scan_table.setHorizontalHeaderLabels([
            "#",
            self.tr_.tr("common.symbol"),
            self.tr_.tr("signals.direction"),
            self.tr_.tr("signals.confidence"),
            self.tr_.tr("signals.risk"),
            self.tr_.tr("signals.risk_reward"),
            self.tr_.tr("signals.leverage"),
            self.tr_.tr("validity.column"),
            self.tr_.tr("signals.analysis"),
        ])
        configure_table(self.scan_table, stretch_column=1)
        # ستون آخر دکمه دارد: هم عرض ثابت می‌خواهد و هم ردیف بلندتر،
        # وگرنه دکمه زیر پدینگِ خانه له می‌شود و دیده نمی‌شود.
        configure_button_column(self.scan_table, SignalsPage.SCAN_COL_ACTION)

    def scan_options(self) -> dict[str, Any]:
        """گزینه‌های پویش که کاربر تنظیم کرده است."""
        return {
            "limit": int(self.scan_limit_spin.value()),
            "min_confidence": int(self.scan_confidence_spin.value()),
            "include_wait": bool(self.scan_wait_check.isChecked()),
        }

    # ------------------------------------------------------------------
    # نسخهٔ ۲.۴.۰ — دامنهٔ پویش و پالایش هوشمند
    # ------------------------------------------------------------------
    def _fill_scope_combo(self, combo: QComboBox, top_key: str, all_key: str) -> None:
        combo.blockSignals(True)
        current = combo.currentData()
        combo.clear()
        combo.addItem(self.tr_.tr(top_key), "top")
        combo.addItem(self.tr_.tr(all_key), "all")
        if current is not None:
            self._set_combo_data(combo, current)
        combo.blockSignals(False)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: Any) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _safe_number(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return number if number > 0 else 0.0

    def _make_turnover_spin(self) -> QDoubleSpinBox:
        """کمینهٔ گردش ۲۴ساعته بر حسب هزار USDT (۰ = بدون محدودیت)."""
        spin = QDoubleSpinBox()
        spin.setDecimals(0)
        spin.setRange(0, 10_000_000)
        spin.setSingleStep(50)
        spin.setValue(0)
        spin.setSuffix(" K$")
        spin.setFixedWidth(110)
        spin.setToolTip(self.tr_.tr("signals.scan_min_turnover_tip"))
        return spin

    def _on_scan_scope_changed(self, *_args: Any, emit: bool = True) -> None:
        """در حالت «کل بازار» تعداد معنا ندارد و غیرفعال می‌شود."""
        whole = self.scan_scope_combo.currentData() == "all"
        scanning = (not self.scan_stop_button.isHidden()) if hasattr(self, "scan_stop_button") else False
        self.scan_limit_spin.setEnabled(not whole and not scanning)
        if emit:
            self._emit_scan_settings()

    def _emit_scan_settings(self, *_args: Any) -> None:
        self.scan_settings_changed.emit(self.scan_settings())

    def scan_universe_options(self) -> dict[str, Any]:
        """
        گزینه‌های دامنهٔ پویش دستی.

        جدا از `scan_options` نگه داشته شده تا قرارداد قبلی (سه کلید)
        دست نخورد.
        """
        return {
            "universe": str(self.scan_scope_combo.currentData() or "top"),
            "min_turnover": float(self.scan_turnover_spin.value()) * 1000.0,
            "smart_filter": bool(self.scan_smart_check.isChecked()),
        }

    def scan_settings(self) -> dict[str, Any]:
        """کلیدهای تنظیمات پایدار پویش دستی."""
        options = self.scan_universe_options()
        return {
            "signals.scan_universe": options["universe"],
            "signals.scan_limit": int(self.scan_limit_spin.value()),
            "signals.scan_min_turnover": options["min_turnover"],
            "signals.scan_smart_filter": options["smart_filter"],
        }

    def set_scan_settings(self, values: dict[str, Any]) -> None:
        """نشاندن تنظیمات ذخیره‌شدهٔ پویش دستی (بدون اعلام تغییر)."""
        widgets = (
            self.scan_scope_combo, self.scan_limit_spin,
            self.scan_smart_check, self.scan_turnover_spin,
        )
        for widget in widgets:
            widget.blockSignals(True)
        try:
            universe = str(values.get("signals.scan_universe", "top") or "top").lower()
            self._set_combo_data(self.scan_scope_combo, "all" if universe == "all" else "top")
            try:
                limit = int(values.get("signals.scan_limit", 60) or 60)
            except (TypeError, ValueError):
                limit = 60
            self.scan_limit_spin.setValue(max(5, min(limit, self.scan_limit_spin.maximum())))
            self.scan_smart_check.setChecked(bool(values.get("signals.scan_smart_filter", True)))
            self.scan_turnover_spin.setValue(
                self._safe_number(values.get("signals.scan_min_turnover", 0.0)) / 1000.0
            )
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self._on_scan_scope_changed(emit=False)

    def set_scanning(self, scanning: bool) -> None:
        """
        قفل‌کردن کنترل‌ها هنگام پویش.

        دکمهٔ «توقف» فقط در همین حالت دیده می‌شود؛ دکمهٔ غیرفعالِ همیشه
        روی صفحه، کاربر را گیج می‌کند.
        """
        self.scan_button.setEnabled(not scanning)
        self.scan_button.setText(
            self.tr_.tr("signals.scan_running") if scanning else self.tr_.tr("signals.scan")
        )
        self.scan_stop_button.setVisible(scanning)
        for widget in (
            self.scan_limit_spin, self.scan_confidence_spin, self.scan_wait_check,
            self.scan_scope_combo, self.scan_smart_check, self.scan_turnover_spin,
        ):
            widget.setEnabled(not scanning)
        if not scanning:
            self._on_scan_scope_changed(emit=False)
        self.scan_progress.setVisible(scanning)
        if scanning:
            self.scan_progress.setValue(0)
            self._scan_started_at = time.monotonic()

    def set_scan_progress(self, done: int, total: int, symbol: str, found: int) -> None:
        """نمایش پیشرفت پویش."""
        total = max(1, int(total))
        self.scan_progress.setMaximum(total)
        self.scan_progress.setValue(int(done))
        self.scan_progress.setFormat(f"%v / %m  ({found})")
        text = self.tr_.tr("signals.scan_progress", done=done, total=total, symbol=symbol)
        eta = self._scan_eta_seconds(int(done), total)
        if eta is not None:
            text += "  ·  " + self.tr_.tr("signals.scan_eta", time=self._format_eta(eta))
        self.scan_status.setText(text)

    def _scan_eta_seconds(self, done: int, total: int) -> int | None:
        """برآورد زمان باقی‌مانده از سرعت واقعی تا این لحظه."""
        started = float(getattr(self, "_scan_started_at", 0.0) or 0.0)
        if started <= 0 or done < 3 or done >= total:
            return None
        elapsed = time.monotonic() - started
        if elapsed <= 0:
            return None
        return max(0, int(round(elapsed / done * (total - done))))

    @staticmethod
    def _format_eta(seconds: int) -> str:
        minutes, secs = divmod(max(0, int(seconds)), 60)
        return f"{minutes}:{secs:02d}"

    def set_scan_status(self, text: str) -> None:
        """نوشتن یک پیام وضعیت زیر نوار پیشرفت."""
        self.scan_status.setText(text)


    #: بیشترین ردیفی که جدول پویش بدون اسکرول داخلی نشان می‌دهد
    SCAN_VISIBLE_ROWS = 12
    #: نسخهٔ ۲.۴.۱ — سقف ردیف‌های نمایش‌داده‌شده در جدول پویش (بهترین‌ها)
    SCAN_MAX_ROWS = 200

    def _fit_scan_table_height(self) -> None:
        """
        هم‌اندازه‌کردن ارتفاع جدول پویش با تعداد نتیجه‌ها.

        صفحه خودش ناحیهٔ پیمایش دارد؛ اگر جدول هم ارتفاع ثابت داشته
        باشد، کاربر باید داخل جدول جداگانه اسکرول کند تا ردیف‌های پایین
        را ببیند. تا سقف `SCAN_VISIBLE_ROWS` ردیف، جدول کامل باز می‌شود
        و پیمایش را به خود صفحه می‌سپارد.
        """
        header = self.scan_table.horizontalHeader().height()
        rows = self.scan_table.rowCount()
        if rows <= 0:
            self.scan_table.setFixedHeight(190)
            return
        row_height = self.scan_table.rowHeight(0) or 34
        visible = min(rows, self.SCAN_VISIBLE_ROWS)
        # دو پیکسل برای قاب جدول
        self.scan_table.setFixedHeight(header + row_height * visible + 2)

    def set_scan_results(self, rows: list[dict[str, Any]]) -> None:
        """
        پرکردن جدول نتیجهٔ پویش.

        ردیف‌ها از پیش بر پایهٔ ضریب اطمینان مرتب‌اند، پس ردیف نخست
        بهترین سیگنال است — همان چیزی که کاربر خواست بالا بیاید. رنگ‌ها
        از پوستهٔ فعال گرفته می‌شوند تا در هر پوسته‌ای خوانا بمانند.
        """
        # نسخهٔ ۲.۴.۱: پویش کل صرافی می‌تواند صدها ردیف بسازد و جدول هنگام
        # پویش زنده هر چند صد میلی‌ثانیه از نو پر می‌شود. هر ردیف یک دکمه
        # (ویجت واقعی) دارد و ستون‌ها «به اندازهٔ محتوا» هستند، یعنی هر setItem
        # همهٔ ردیف‌ها را دوباره اندازه می‌گرفت — رابط هنگ می‌کرد. حالا فقط
        # بهترین‌ها (تا سقف) نمایش داده می‌شوند و جدول یک‌جا رسم می‌شود.
        total = len(rows)
        rows = list(rows[: self.SCAN_MAX_ROWS])
        self._scan_rows = [dict(row) for row in rows]
        self._scan_total_rows = total
        header = self.scan_table.horizontalHeader()
        from PySide6.QtWidgets import QHeaderView

        self.scan_table.setUpdatesEnabled(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        try:
            self._fill_scan_rows(rows)
        finally:
            self._apply_scan_headers()
            self.scan_table.setUpdatesEnabled(True)
        if total > len(rows):
            self.scan_cap_note.setText(
                self.tr_.tr("signals.scan_rows_capped", shown=len(rows), total=total)
            )
            self.scan_cap_note.setVisible(True)
        else:
            self.scan_cap_note.setVisible(False)
        self._fit_scan_table_height()

    def _fill_scan_rows(self, rows: list[dict[str, Any]]) -> None:
        """پرکردن خانه‌های جدول پویش (بدون رسم میانی)."""
        self.scan_table.setRowCount(len(rows))

        for index, row in enumerate(rows):
            symbol = str(row.get("symbol", ""))
            direction = str(row.get("direction", "WAIT")).upper()
            confidence = int(row.get("confidence") or 0)
            level = signal_risk_level(row)

            conf_grade = confidence_grade(confidence)
            dir_grade = direction_grade(direction)
            rsk_grade = risk_grade(level)

            rank = QTableWidgetItem(str(index + 1))
            rank.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scan_table.setItem(index, 0, rank)

            self.scan_table.setItem(index, 1, QTableWidgetItem(symbol))

            dir_item = QTableWidgetItem(
                f"{dir_grade.mark}  {self.tr_.tr(f'signals.{direction.lower()}', direction)}"
            )
            dir_item.setForeground(QBrush(QColor(color_for(dir_grade, self._theme))))
            self._emphasise(dir_item, dir_grade.emphasis)
            self.scan_table.setItem(index, 2, dir_item)

            conf_item = QTableWidgetItem(f"{conf_grade.mark}  {confidence}%")
            conf_item.setForeground(QBrush(QColor(color_for(conf_grade, self._theme))))
            self._emphasise(conf_item, conf_grade.emphasis)
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scan_table.setItem(index, 3, conf_item)

            risk_item = QTableWidgetItem(
                f"{rsk_grade.mark}  {self.tr_.tr(f'signals.risk_{level}')}"
            )
            risk_item.setForeground(QBrush(QColor(color_for(rsk_grade, self._theme))))
            self._emphasise(risk_item, rsk_grade.emphasis)
            self.scan_table.setItem(index, 4, risk_item)

            ratio = row.get("risk_reward")
            rr_item = QTableWidgetItem(f"{float(ratio):.2f}" if ratio else "—")
            rr_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scan_table.setItem(index, 5, rr_item)

            lev_item = QTableWidgetItem(f"×{int(row.get('leverage') or 1)}")
            lev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scan_table.setItem(index, 6, lev_item)

            # ستون اعتبار — قلب شکایت کاربر دربارهٔ «سیگنال سوخته».
            # یک ردیف پویش که ساعتی پیش ساخته شده، ظاهرش با ردیف تازه
            # مو نمی‌زد؛ حالا در نگاه اول جدا می‌شود.
            fresh_item = self._freshness_item(row)
            self.scan_table.setItem(index, self.SCAN_COL_FRESHNESS, fresh_item)

            button = make_button(self.tr_.tr("signals.scan_ai_analyze"), role="ghost")
            button.clicked.connect(
                lambda _=False, value=symbol: self.scan_ai_requested.emit(value)
            )
            self.scan_table.setCellWidget(index, self.SCAN_COL_ACTION, button)

    def _freshness_item(self, row: dict[str, Any]) -> QTableWidgetItem:
        """
        ساخت خانهٔ «اعتبار» برای یک ردیف سیگنال.

        متن کوتاه است چون در جدول جا نیست؛ توضیح کامل در راهنمای
        شناور (tooltip) می‌آید تا کاربر بداند **چرا** این وضعیت را
        گرفته است. دانستن «سوخته» بدون دانستن دلیلش، به کاربر کمکی
        نمی‌کند.
        """
        freshness = str(row.get("freshness") or "")
        grade = freshness_grade(freshness)
        label = self.tr_.tr(f"validity.{grade.key}_label")

        item = QTableWidgetItem(f"{grade.mark}  {label}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QBrush(QColor(color_for(grade, self._theme))))
        self._emphasise(item, grade.emphasis)

        reason_key = str(row.get("validity_reason") or "")
        if reason_key:
            args = row.get("validity_args") or {}
            item.setToolTip(self.tr_.tr(reason_key, **args))
        return item

    def _on_scan_cell_clicked(self, row: int, column: int) -> None:
        """
        کلیک روی یک ردیف نتیجهٔ پویش → درخواست جزئیات.

        ستون دکمهٔ تحلیل استثناست: آنجا خود دکمه کارش را می‌کند و
        بازکردن همزمان پنجرهٔ جزئیات، کلیک کاربر را دوکاره می‌کرد.
        """
        if column == self.SCAN_COL_ACTION:
            return
        item = self.scan_table.item(row, 1)
        if item is None:
            return
        symbol = item.text().strip()
        if symbol:
            self.scan_detail_requested.emit(symbol)

    # ------------------------------------------------------------------
    # کپی نام و اطلاعات سیگنال (۲.۴.۲)
    # ------------------------------------------------------------------
    def scan_row_at(self, row: int) -> dict[str, Any]:
        """دادهٔ ردیف `row` جدول پویش (همان ترتیب نمایش)."""
        item = self.scan_table.item(row, 1) if row >= 0 else None
        if item is None:
            return {}
        return self.scan_row(item.text().strip())

    def history_row_at(self, row: int) -> dict[str, Any]:
        """دادهٔ ردیف `row` جدول سابقه (همان ترتیب مرتب‌شدهٔ نمایش)."""
        if 0 <= row < len(self._history_rows):
            return dict(self._history_rows[row])
        return {}

    def _install_copy_support(self, table: QTableWidget, row_getter: Any) -> None:
        """منوی راست‌کلیک «کپی نماد / کپی اطلاعات» و میان‌بر Ctrl+C روی جدول."""
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, t=table, g=row_getter: self._show_copy_menu(t, g, pos)
        )
        shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Copy), table)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(
            lambda t=table, g=row_getter: self.copy_signal_info(g(t.currentRow()))
        )
        table.setToolTip(self.tr_.tr("signals.share.table_hint"))

    def _show_copy_menu(self, table: QTableWidget, row_getter: Any, pos: Any) -> None:
        index = table.indexAt(pos)
        if not index.isValid():
            return
        data = row_getter(index.row())
        if not data:
            return
        menu = QMenu(table)
        symbol_action = menu.addAction(self.tr_.tr("signals.share.copy_symbol"))
        info_action = menu.addAction(self.tr_.tr("signals.share.copy_info"))
        symbol_action.setEnabled(bool(signal_symbol(data)))
        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is symbol_action:
            self.copy_signal_symbol(data)
        elif chosen is info_action:
            self.copy_signal_info(data)

    def copy_signal_symbol(self, data: dict[str, Any]) -> bool:
        """کپی نام نماد یک ردیف."""
        symbol = signal_symbol(data)
        ok = copy_to_clipboard(symbol)
        if ok:
            self.copy_notice.emit(self.tr_.tr("signals.share.symbol_copied", symbol=symbol))
        return ok

    def copy_signal_info(self, data: dict[str, Any]) -> bool:
        """کپی متن کامل سیگنال یک ردیف."""
        if not data:
            return False
        ok = copy_to_clipboard(format_signal_text(data, self.tr_))
        if ok:
            self.copy_notice.emit(
                self.tr_.tr("signals.share.info_copied", symbol=signal_symbol(data))
            )
        return ok

    def scan_row(self, symbol: str) -> dict[str, Any]:
        """دادهٔ خام یک ردیف نتیجهٔ پویش."""
        for row in getattr(self, "_scan_rows", []):
            if str(row.get("symbol", "")).upper() == str(symbol).upper():
                return dict(row)
        return {}

    @staticmethod
    def _emphasise(item: QTableWidgetItem, emphasis: bool) -> None:
        """پررنگ‌کردن یک خانهٔ جدول، بدون دست‌زدن به قلم بقیه."""
        if not emphasis:
            return
        font = item.font()
        font.setBold(True)
        item.setFont(font)

    def _on_current_analysis(self) -> None:
        """درخواست تحلیل برای سیگنالی که هم‌اکنون در کارت نشان داده می‌شود."""
        signal_id = int((getattr(self, "_current_signal", {}) or {}).get("id") or 0)
        if signal_id:
            self.analysis_requested.emit(signal_id)

    def selected_timeframes(self) -> list[str]:
        """
        تایم‌فریم‌هایی که کاربر برای تحلیل چنددوره‌ای برگزیده است.

        اگر هیچ‌کدام انتخاب نشده باشد، فهرست پیش‌فرض برمی‌گردد تا موتور
        هرگز بدون داده نماند.
        """
        chosen = self.timeframe_chips.selection()
        return chosen or list(DEFAULT_SIGNAL_TIMEFRAMES)

    def _signal_labels(self) -> dict[str, str]:
        """برچسب‌های ترجمه‌شده کارت سیگنال."""
        return {
            "title": self.tr_.tr("signals.current"),
            "entry": self.tr_.tr("signals.entry_zone"),
            "stop_loss": self.tr_.tr("signals.stop_loss"),
            "take_profit": self.tr_.tr("signals.take_profit"),
            "risk_reward": self.tr_.tr("signals.risk_reward"),
            "leverage": self.tr_.tr("signals.leverage"),
            "confidence": self.tr_.tr("signals.confidence"),
            "confidence_note": self.tr_.tr("signals.confidence_note"),
            "long": self.tr_.tr("signals.long"),
            "short": self.tr_.tr("signals.short"),
            "wait": self.tr_.tr("signals.wait"),
            "forecast": self.tr_.tr("signals.forecast"),
        }

    def _apply_headers(self) -> None:
        """تنظیم سرستون‌های جدول سابقه."""
        self.history_table.setHorizontalHeaderLabels([
            self.tr_.tr("signals.generated_at"), self.tr_.tr("common.symbol"),
            self.tr_.tr("signals.direction"), self.tr_.tr("signals.confidence"),
            self.tr_.tr("signals.risk_reward"), self.tr_.tr("signals.leverage"),
            self.tr_.tr("recommendation.column"), self.tr_.tr("validity.column"),
            self.tr_.tr("signals.analysis"),
        ])
        configure_table(self.history_table, stretch_column=1)
        # ستون «تحلیل» هم دکمه دارد و همان دو تنظیم را لازم دارد
        configure_button_column(self.history_table, SignalsPage.HISTORY_COL_ACTION)

    def show_signal(self, payload: dict[str, Any]) -> None:
        """نمایش سیگنال تولیدشده و فعال‌کردن دکمهٔ تحلیل آن."""
        self.signal_card.show_signal(payload)
        self._current_signal = dict(payload or {})
        # تا وقتی سیگنال در پایگاه داده ذخیره نشده، شناسه ندارد و
        # تحلیل دوباره جایی برای ذخیره‌شدن ندارد.
        self.current_analysis_button.setEnabled(bool(self._current_signal.get("id")))

    def apply_theme(self, theme: Any) -> None:
        """اعمال پوسته روی ویجت‌های نقاشی‌شونده (حلقهٔ اطمینان)."""
        self._theme = theme
        self.signal_card.apply_theme(theme)
        # رنگ ردیف‌های پویش با کد در خودِ آیتم نشسته و از QSS نمی‌آید،
        # پس با عوض‌شدن پوسته باید دوباره ساخته شوند وگرنه رنگ پوستهٔ
        # قبلی روی پوستهٔ تازه می‌ماند.
        if self._scan_rows:
            self.set_scan_results(list(self._scan_rows))
        if self._history_rows:
            self.set_history(list(self._history_rows))

    def _sort_history_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        مرتب‌سازی و دسته‌بندی سابقه بر پایهٔ انتخاب کاربر.

        پیش‌فرض «بیشترین اطمینان» است: کاربر دنبال بهترین فرصت می‌گردد،
        نه جدیدترین ردیف. در حالت دسته‌بندی، ابتدا صعودی‌ها، سپس
        نزولی‌ها و در آخر انتظارها می‌آیند و درون هر دسته اطمینان
        نزولی مرتب می‌شود.
        """
        data = [dict(r) for r in rows]
        combo = getattr(self, "history_sort_combo", None)
        mode = combo.currentData() if combo is not None else "confidence_desc"
        group = bool(
            getattr(self, "history_group_check", None)
            and self.history_group_check.isChecked()
        )

        def confidence(row: dict[str, Any]) -> float:
            try:
                return float(row.get("confidence") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        def direction_rank(row: dict[str, Any]) -> int:
            order = {"LONG": 0, "SHORT": 1, "WAIT": 2}
            return order.get(str(row.get("direction", "")).upper(), 3)

        if mode == "confidence_asc":
            data.sort(key=confidence)
        elif mode == "direction":
            data.sort(key=lambda r: (direction_rank(r), -confidence(r)))
        elif mode == "newest":
            data.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        elif mode == "symbol":
            data.sort(key=lambda r: (str(r.get("symbol") or ""), -confidence(r)))
        else:  # confidence_desc
            data.sort(key=confidence, reverse=True)

        if group:
            data.sort(key=direction_rank)
        return data

    def _resort_history(self) -> None:
        """اعمال دوبارهٔ مرتب‌سازی روی داده‌های موجود."""
        if getattr(self, "_history_source", None) is None:
            return
        self.set_history(self._history_source, _resort=True)

    def set_history(
        self, rows: list[dict[str, Any]], *, _resort: bool = False
    ) -> None:
        """
        پر کردن جدول سابقه سیگنال‌ها.

        ستون آخر یک دکمهٔ «تحلیل» دارد؛ با کلیک روی آن، متن کامل تحلیل
        در یک مدال باز می‌شود و از همان‌جا می‌توان خروجی PDF فارسی گرفت.
        """
        # دادهٔ خام نگه داشته می‌شود تا تغییر ترتیب نیازی به خواندن
        # دوبارهٔ پایگاه داده نداشته باشد.
        self._history_source = [dict(r) for r in rows]
        rows = self._sort_history_rows(rows)
        self._history_rows = [dict(r) for r in rows]
        self.history_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            direction = str(row.get("direction", "WAIT")).lower()
            values = [
                str(row.get("created_at", "")),
                row.get("symbol", ""),
                self.tr_.tr(f"signals.{direction}", direction.upper()),
                f"{row.get('confidence', 0)}%",
                f"{row.get('risk_reward'):.2f}" if row.get("risk_reward") else "—",
                f"×{row.get('leverage', 1)}",
            ]
            for column, value in enumerate(values):
                self.history_table.setItem(index, column, QTableWidgetItem(str(value)))

            # همان درجه‌بندی رنگی جدول پویش روی سابقه هم اعمال می‌شود.
            # کاربر گفت «به همین ترتیب»؛ دو جدول با دو زبان رنگی متفاوت،
            # خواندن را سخت می‌کرد.
            dir_grade = direction_grade(direction)
            conf_grade = confidence_grade(row.get("confidence"))
            dir_item = self.history_table.item(index, 2)
            if dir_item is not None:
                dir_item.setText(f"{dir_grade.mark}  {dir_item.text()}")
                dir_item.setForeground(QBrush(QColor(color_for(dir_grade, self._theme))))
                self._emphasise(dir_item, dir_grade.emphasis)
            conf_item = self.history_table.item(index, 3)
            if conf_item is not None:
                conf_item.setText(f"{conf_grade.mark}  {conf_item.text()}")
                conf_item.setForeground(QBrush(QColor(color_for(conf_grade, self._theme))))
                self._emphasise(conf_item, conf_grade.emphasis)

            self.history_table.setItem(
                index, self.HISTORY_COL_RECOMMENDATION, self._recommendation_item(row)
            )
            self.history_table.setItem(
                index, self.HISTORY_COL_FRESHNESS, self._freshness_item(row)
            )

            signal_id = int(row.get("id") or 0)
            button = make_button("📄  " + self.tr_.tr("signals.view_analysis"), role="ghost")
            button.setEnabled(bool(signal_id))
            if signal_id:
                button.clicked.connect(
                    lambda _=False, value=signal_id: self.analysis_requested.emit(value)
                )
            self.history_table.setCellWidget(index, self.HISTORY_COL_ACTION, button)

    def _recommendation_item(self, row: dict[str, Any]) -> QTableWidgetItem:
        """
        سلول توصیهٔ صریح هوش مصنوعی برای جدول سابقه.

        کاربر خواست هوش مصنوعی پیشنهاد خرید و فروش بدهد. دیدن آن فقط
        داخل پنجرهٔ جزئیات یعنی برای هر سیگنال باید یک پنجره باز شود؛
        در جدول، ستون جواب را در یک نگاه می‌دهد.

        سیگنالی که توصیه ندارد خط تیره می‌گیرد، نه جهت حدسی.
        """
        payload = row.get("recommendation")
        if not isinstance(payload, dict) or not payload.get("action"):
            item = QTableWidgetItem("—")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(self.tr_.tr("recommendation.none"))
            return item

        action = str(payload["action"]).upper()
        label = self.tr_.tr(f"recommendation.action_{action.lower()}")
        confidence = payload.get("confidence")
        if confidence is not None:
            label = f"{label} ({int(confidence)}%)"

        item = QTableWidgetItem(label)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        token = {"BUY": "success", "SELL": "danger"}.get(action, "info")
        item.setForeground(QBrush(QColor(color_for(_RecommendationTone(token), self._theme))))

        rationale = str(payload.get("rationale") or "").strip()
        item.setToolTip(rationale or self.tr_.tr("recommendation.hint"))
        return item

    def history_row(self, signal_id: int) -> dict[str, Any]:
        """دادهٔ خام یک سیگنال از جدول سابقه."""
        for row in self._history_rows:
            if int(row.get("id") or 0) == int(signal_id):
                return dict(row)
        return {}

    def set_symbols(self, symbols: list[str]) -> None:
        """پر کردن فهرست نمادها."""
        current = self.symbol_combo.currentText()
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.clear()
        self.symbol_combo.addItems(symbols)
        self.symbol_combo.blockSignals(False)
        if current:
            self.symbol_combo.setCurrentText(current)

    def set_busy(self, busy: bool) -> None:
        """قفل کردن دکمه هنگام تولید سیگنال."""
        self.generate_button.setEnabled(not busy)
        self.generate_button.setText(
            self.tr_.tr("signals.generating") if busy else self.tr_.tr("signals.generate")
        )

    def retranslate(self) -> None:
        """بازسازی متن‌ها."""
        super().retranslate()
        self.timeframes_label.setText(self.tr_.tr("signals.timeframes"))
        self.symbol_label.setText(self.tr_.tr("common.symbol"))
        self.generate_button.setText(self.tr_.tr("signals.generate"))
        self.history_card.set_title(self.tr_.tr("signals.history"))
        self.wait_note.setText(self.tr_.tr("signals.wait_note"))
        self.timeframe_label.setText(self.tr_.tr("common.timeframe"))
        self.use_ai_checkbox.setText(self.tr_.tr("analysis.use_ai"))
        self.signal_card.set_labels(self._signal_labels())
        self.scan_card.set_title(self.tr_.tr("signals.scan_results"))
        self.scan_hint.setText(self.tr_.tr("signals.scan_hint"))
        self.scan_button.setText(self.tr_.tr("signals.scan"))
        self.scan_stop_button.setText(self.tr_.tr("signals.scan_stop"))
        self.scan_limit_label.setText(self.tr_.tr("signals.scan_limit"))
        self.scan_confidence_label.setText(self.tr_.tr("signals.scan_min_confidence"))
        self.scan_wait_check.setText(self.tr_.tr("signals.scan_include_wait"))
        self.scan_scope_label.setText(self.tr_.tr("signals.scan_scope"))
        self._fill_scope_combo(self.scan_scope_combo, "signals.scan_scope_top", "signals.scan_scope_all")
        self._fill_scope_combo(self.auto_universe_combo, "signals.scan_scope_top", "signals.scan_scope_all")
        self.scan_smart_check.setText(self.tr_.tr("signals.scan_smart_filter"))
        self.scan_turnover_label.setText(self.tr_.tr("signals.scan_min_turnover"))
        self.auto_source_label.setText(self.tr_.tr("signals.auto.source"))
        for index in range(self.auto_source_combo.count()):
            source = self.auto_source_combo.itemData(index)
            self.auto_source_combo.setItemText(index, self.tr_.tr(f"signals.auto.source_{source}"))
        self.auto_universe_label.setText(self.tr_.tr("signals.auto.universe"))
        self.auto_sweep_limit_label.setText(self.tr_.tr("signals.scan_limit"))
        self.auto_smart_check.setText(self.tr_.tr("signals.scan_smart_filter"))
        self.auto_turnover_label.setText(self.tr_.tr("signals.scan_min_turnover"))
        self.scan_legend.setText(self.tr_.tr("signals.legend_text"))
        self.scan_copy_hint.setText(self.tr_.tr("signals.share.table_hint"))
        self._apply_scan_headers()
        if self._scan_rows:
            self.set_scan_results(list(self._scan_rows))
        self._apply_headers()
        # جدول سابقه متن جهت و دکمه‌ها را با زبان تازه بازسازی می‌کند
        if self._history_rows:
            self.set_history(list(self._history_rows))
