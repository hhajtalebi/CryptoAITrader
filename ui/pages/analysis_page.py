"""
صفحه تحلیل.

انتخاب نماد و تایم‌فریم‌ها، اجرای تحلیل چند تایم‌فریمی، و نمایش نتیجه
اندیکاتورها، ساختار بازار و تحلیل هوش مصنوعی.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from market.timeframes import SUPPORTED_TIMEFRAMES
from ui.charts import PriceChart
from ui.pages.base_page import BasePage
from ui.widgets import Card, SegmentedControl, ToggleSwitch, configure_table, make_button, set_role


#: تایم‌فریم‌های نوار بالای نمودار (مطابق تصاویر مرجع)
CHART_TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h", "1d", "1w")


class AnalysisPage(BasePage):
    """صفحه تحلیل تکنیکال."""

    title_key = "nav.analysis"
    subtitle_key = "analysis.subtitle"

    #: کاربر یک اندیکاتور را روشن/خاموش کرد: (نام، وضعیت)
    indicator_toggled = Signal(str, bool)
    #: کاربر تایم‌فریم را از نوار بالای نمودار عوض کرد
    timeframe_changed = Signal(str)

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        super().__init__(translator, parent)

    def build(self) -> None:
        """ساخت کنترل‌های ورودی و نمایشگر نتیجه."""
        self._indicator_rows: dict[str, dict[str, Any]] = {}
        controls = QHBoxLayout()

        # فهرست نمادها: قابل جست‌وجو، چون صرافی بیش از هزار نماد دارد و
        # پیمایش دستی چنین فهرستی عملاً ناممکن است.
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.setMinimumWidth(200)
        self.symbol_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = self.symbol_combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)

        # همهٔ تایم‌فریم‌های پشتیبانی‌شده، از یک دقیقه تا ماهانه
        self.timeframe_combo = QComboBox()
        for timeframe in SUPPORTED_TIMEFRAMES:
            self.timeframe_combo.addItem(timeframe.code, timeframe.code)
        default_index = self.timeframe_combo.findData("4h")
        if default_index >= 0:
            self.timeframe_combo.setCurrentIndex(default_index)

        self.use_ai_checkbox = QCheckBox(self.tr_.tr("analysis.use_ai"))
        self.use_ai_checkbox.setChecked(True)

        self.timeframe_combo.currentIndexChanged.connect(
            lambda _: self._sync_timeframe_bar()
        )

        self.run_button = make_button(self.tr_.tr("analysis.run"), primary=True)

        self.symbol_label = QLabel(self.tr_.tr("common.symbol"))
        self.timeframe_label = QLabel(self.tr_.tr("common.timeframe"))
        controls.addWidget(self.symbol_label)
        controls.addWidget(self.symbol_combo)
        controls.addWidget(self.timeframe_label)
        controls.addWidget(self.timeframe_combo)
        controls.addWidget(self.use_ai_checkbox)
        controls.addWidget(self.run_button)
        controls.addStretch(1)
        self.layout_root().addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.layout_root().addWidget(self.progress)

        # نوار تایم‌فریم بالای نمودار، مطابق تصاویر مرجع
        self.timeframe_bar = SegmentedControl(
            [(code, code) for code in CHART_TIMEFRAMES]
        )
        self.timeframe_bar.set_current("4h", emit=False)
        self.timeframe_bar.selection_changed.connect(self._on_timeframe_bar_changed)
        bar_row = QHBoxLayout()
        bar_row.addWidget(self.timeframe_bar)
        bar_row.addStretch(1)

        # --- ابزارهای نمودار، مشابه تریدینگ‌ویو ---
        #
        # نوع نمودار، برچسب قیمت زندهٔ آخر، و «تناسب صفحه» برای وقتی که
        # کاربر زوم کرده و می‌خواهد برگردد.
        self.chart_type_combo = QComboBox()
        for key, code in (
            ("charts.type_candles", "candles"),
            ("charts.type_line", "line"),
            ("charts.type_area", "area"),
        ):
            self.chart_type_combo.addItem(self.tr_.tr(key), code)
        self.chart_type_combo.currentIndexChanged.connect(self._on_chart_type_changed)
        bar_row.addWidget(self.chart_type_combo)

        self.live_price_label = QLabel("—")
        set_role(self.live_price_label, "chip_info")
        bar_row.addWidget(self.live_price_label)

        self.fit_button = make_button(self.tr_.tr("charts.fit"))
        self.fit_button.clicked.connect(self._on_fit_clicked)
        bar_row.addWidget(self.fit_button)

        self.layout_root().addLayout(bar_row)

        self.tabs = QTabWidget()

        # زبانه نمودار — نخستین چیزی که کاربر انتظار دارد ببیند
        self.chart = PriceChart(self.tr_)
        self.tabs.addTab(self.chart, self.tr_.tr("charts.title"))

        # زبانه اندیکاتورها
        self.indicators_table = QTableWidget(0, 4)
        self.indicators_table.verticalHeader().setVisible(False)
        self.indicators_table.setAlternatingRowColors(True)
        self.indicators_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.indicators_table, self.tr_.tr("analysis.indicators"))

        # زبانه سطوح کلیدی
        self.levels_table = QTableWidget(0, 4)
        self.levels_table.verticalHeader().setVisible(False)
        self.levels_table.setAlternatingRowColors(True)
        self.levels_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.levels_table, self.tr_.tr("analysis.levels"))

        # زبانه تحلیل هوش مصنوعی
        self.ai_text = QPlainTextEdit()
        self.ai_text.setReadOnly(True)
        self.ai_text.setPlaceholderText(self.tr_.tr("analysis.ai_disabled"))
        self.tabs.addTab(self.ai_text, self.tr_.tr("analysis.ai_analysis"))

        # ---- پنل اندیکاتورها در کنار نمودار ----
        self.indicators_card = Card(self.tr_.tr("analysis.indicators"))

        # کاربر گفت اندیکاتورها قابل انتخاب نیستند و می‌خواهد بتواند هم
        # گزینشی و هم «با همهٔ اندیکاتورها» تحلیل کند. این دو دکمه کار را
        # یک‌کلیکی می‌کنند؛ پیش‌تر باید ۲۴ کلید را تک‌تک می‌زد.
        selector_row = QWidget()
        selector_layout = QHBoxLayout(selector_row)
        selector_layout.setContentsMargins(0, 0, 0, 8)
        selector_layout.setSpacing(8)
        self.select_all_button = make_button(
            self.tr_.tr("analysis.select_all_indicators"), role="ghost"
        )
        self.select_all_button.clicked.connect(self.select_all_indicators)
        self.clear_indicators_button = make_button(
            self.tr_.tr("analysis.clear_indicators"), role="ghost"
        )
        self.clear_indicators_button.clicked.connect(self.clear_indicators)
        selector_layout.addWidget(self.select_all_button)
        selector_layout.addWidget(self.clear_indicators_button)
        selector_layout.addStretch(1)
        self.indicators_card.add(selector_row)

        self._indicator_container = QWidget()
        self._indicator_layout = QVBoxLayout(self._indicator_container)
        self._indicator_layout.setContentsMargins(0, 0, 0, 0)
        self._indicator_layout.setSpacing(10)
        self._indicator_layout.addStretch(1)

        indicator_scroll = QScrollArea()
        indicator_scroll.setWidgetResizable(True)
        # بدون کمینه‌پهنا، ستون کلیدها بیرون از کادر می‌افتاد و کاربر فکر
        # می‌کرد اندیکاتورها اصلاً قابل انتخاب نیستند.
        indicator_scroll.setMinimumWidth(300)
        indicator_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        indicator_scroll.setWidget(self._indicator_container)
        self.indicators_card.add(indicator_scroll)

        # اسپلیتر تا کاربر بتواند پهنای پنل را خودش تنظیم کند؛ در نمایشگر
        # کوچک، پنل جمع می‌شود و نمودار جای بیشتری می‌گیرد.
        self.splitter = QSplitter()
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self.indicators_card)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([720, 320])
        self.layout_root().addWidget(self.splitter, 1)
        self._apply_headers()

    def _apply_headers(self) -> None:
        """تنظیم سرستون جدول‌ها."""
        self.indicators_table.setHorizontalHeaderLabels([
            self.tr_.tr("analysis.indicators"), self.tr_.tr("common.timeframe"),
            self.tr_.tr("common.price"), self.tr_.tr("signals.direction"),
        ])
        self.levels_table.setHorizontalHeaderLabels([
            self.tr_.tr("common.price"), self.tr_.tr("analysis.structure"),
            self.tr_.tr("signals.confidence"), self.tr_.tr("common.change"),
        ])
        for table in (self.indicators_table, self.levels_table):
            configure_table(table, stretch_column=0)

    # ------------------------------------------------------------------
    # نمایش نتیجه
    # ------------------------------------------------------------------
    def _on_timeframe_bar_changed(self, code: str) -> None:
        """
        همگام‌سازی نوار تایم‌فریم با فهرست کشویی.

        هر دو کنترل یک مقدار را نشان می‌دهند؛ اگر همگام نشوند کاربر
        تایم‌فریمی را می‌بیند که تحلیل با آن اجرا نشده است.
        """
        index = self.timeframe_combo.findData(code)
        if index >= 0 and self.timeframe_combo.currentIndex() != index:
            self.timeframe_combo.setCurrentIndex(index)
        self.timeframe_changed.emit(code)

    def _sync_timeframe_bar(self) -> None:
        """بازتاب انتخاب فهرست کشویی روی نوار تایم‌فریم."""
        code = self.timeframe_combo.currentData() or self.timeframe_combo.currentText()
        if code in CHART_TIMEFRAMES:
            self.timeframe_bar.set_current(str(code), emit=False)

    def set_indicator_catalog(
        self, entries: list[dict[str, Any]], enabled: list[str] | None = None
    ) -> None:
        """
        ساخت فهرست کلیدهای اندیکاتور از روی رجیستری واقعی برنامه.

        هر ورودی: ``{"name": "RSI", "label": "...", "description": "..."}``.
        فهرست از رجیستری می‌آید تا افزودن اندیکاتور تازه به‌طور خودکار
        در این پنل دیده شود و جایی هاردکد نشود.
        """
        for row in self._indicator_rows.values():
            row["widget"].setParent(None)
        self._indicator_rows = {}

        active = set(enabled or [])
        for entry in entries:
            name = str(entry.get("name", ""))
            if not name:
                continue
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            toggle = ToggleSwitch()
            toggle.setChecked(name in active)
            toggle.toggled.connect(
                lambda checked, indicator=name: self._on_indicator_toggled(
                    indicator, checked
                )
            )

            text_box = QVBoxLayout()
            text_box.setContentsMargins(0, 0, 0, 0)
            text_box.setSpacing(0)
            title = QLabel(str(entry.get("label") or name))
            title.setProperty("role", "cardTitle")
            # توضیح در یک خط کوتاه می‌شود تا فهرست ۲۴ اندیکاتور بلند نشود؛
            # متن کامل در راهنمای شناور می‌ماند.
            description = str(entry.get("description") or "")
            caption = QLabel(description)
            caption.setProperty("role", "caption")
            caption.setWordWrap(False)
            caption.setTextFormat(Qt.TextFormat.PlainText)
            metrics = caption.fontMetrics()
            caption.setText(
                metrics.elidedText(description, Qt.TextElideMode.ElideRight, 190)
            )
            if description:
                caption.setToolTip(description)
                row_widget.setToolTip(description)
            text_box.addWidget(title)
            text_box.addWidget(caption)

            row_layout.addLayout(text_box, 1)
            row_layout.addWidget(toggle)

            self._indicator_layout.insertWidget(
                self._indicator_layout.count() - 1, row_widget
            )
            self._indicator_rows[name] = {
                "widget": row_widget,
                "toggle": toggle,
                "title": title,
                "caption": caption,
            }

    def select_all_indicators(self) -> None:
        """روشن‌کردن همهٔ اندیکاتورها (تحلیل کامل)."""
        self.set_enabled_indicators(list(self._indicator_rows))

    def clear_indicators(self) -> None:
        """خاموش‌کردن همه، برای انتخاب دستی چند اندیکاتور."""
        self.set_enabled_indicators([])

    def _on_indicator_toggled(self, name: str, checked: bool) -> None:
        """انتشار تغییر وضعیت یک اندیکاتور."""
        self.indicator_toggled.emit(name, bool(checked))

    def enabled_indicators(self) -> list[str]:
        """نام اندیکاتورهای روشن، به ترتیب نمایش."""
        return [
            name for name, row in self._indicator_rows.items() if row["toggle"].isChecked()
        ]

    def set_enabled_indicators(self, names: list[str]) -> None:
        """
        تعیین وضعیت کلیدها بدون انتشار سیگنال.

        هنگام بازیابی تنظیمات ذخیره‌شده لازم است، وگرنه هر بار بارگذاری،
        دوباره در تنظیمات نوشته می‌شد.
        """
        active = set(names or [])
        for name, row in self._indicator_rows.items():
            toggle = row["toggle"]
            toggle.blockSignals(True)
            toggle.setChecked(name in active)
            toggle.blockSignals(False)

    def apply_theme(self, theme: Any) -> None:
        """اعمال پوسته روی کلیدهای کشویی که خودشان نقاشی می‌شوند."""
        for row in self._indicator_rows.values():
            row["toggle"].apply_theme(theme)

    def set_busy(self, busy: bool) -> None:
        """نمایش یا پنهان کردن نوار پیشرفت."""
        self.progress.setVisible(busy)
        self.run_button.setEnabled(not busy)
        self.run_button.setText(
            self.tr_.tr("analysis.running") if busy else self.tr_.tr("analysis.run")
        )

    def set_symbols(self, symbols: list[str]) -> None:
        """پر کردن فهرست نمادها."""
        current = self.symbol_combo.currentText()
        self.symbol_combo.blockSignals(True)
        self.symbol_combo.clear()
        self.symbol_combo.addItems(symbols)
        self.symbol_combo.blockSignals(False)
        if current:
            self.symbol_combo.setCurrentText(current)

    def set_indicator_rows(self, rows: list[dict[str, Any]]) -> None:
        """نمایش نتیجه اندیکاتورها."""
        self.indicators_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            signal = str(row.get("signal", ""))
            values = [row.get("name", ""), row.get("timeframe", ""), row.get("value", ""), signal]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.indicators_table.setItem(index, column, item)

    def set_level_rows(self, rows: list[dict[str, Any]]) -> None:
        """نمایش سطوح حمایت و مقاومت."""
        self.levels_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            kind = str(row.get("type", ""))
            label = self.tr_.tr(f"analysis.{kind}", kind)
            values = [
                self.tr_.format_number(row.get("price", 0.0), 4),
                label,
                str(row.get("strength", "")),
                f"{row.get('distance_percent', 0.0):+.2f}%",
            ]
            for column, value in enumerate(values):
                self.levels_table.setItem(index, column, QTableWidgetItem(str(value)))

    def _on_chart_type_changed(self) -> None:
        """تعویض نوع نمودار بدون گرفتن دوبارهٔ داده."""
        self.chart.set_chart_type(str(self.chart_type_combo.currentData() or "candles"))

    def _on_fit_clicked(self) -> None:
        """بازگرداندن نمودار به نمای خودکار."""
        self.chart.reset_zoom()

    def set_live_price(self, price: float | None, *, change_percent: float | None = None) -> None:
        """
        به‌روزرسانی قیمت زندهٔ بالای نمودار و خط قیمت روی خود نمودار.

        کاربر خواست تغییرات به‌صورت زنده دیده شود؛ پس عدد باید بدون
        کشیدن دوبارهٔ کل نمودار هم تازه شود.
        """
        if price is None or float(price) <= 0:
            self.live_price_label.setText("—")
            return
        text = f"{float(price):,.6g}"
        if change_percent is not None:
            text = f"{text}  ({float(change_percent):+.2f}%)"
        self.live_price_label.setText(text)
        # `set_role` سبک را دوباره محاسبه می‌کند؛ `setProperty` خالی
        # در زمان اجرا هیچ تغییری روی ظاهر نمی‌گذارد.
        set_role(
            self.live_price_label,
            "chip_up" if (change_percent or 0) >= 0 else "chip_down",
        )
        self.chart.set_live_price(float(price))

    def set_chart_data(self, candles: list[Any], timeframe: str, symbol: str = "") -> None:
        """نمایش کندل‌ها روی نمودار."""
        self.chart.set_candles(candles, timeframe, symbol)

    def set_chart_overlay(self, name: str, timestamps: list[float], values: list[Any]) -> None:
        """افزودن خط اندیکاتور روی نمودار."""
        self.chart.set_overlay(name, timestamps, values)

    def set_chart_levels(self, levels: list[Any]) -> None:
        """ترسیم سطوح حمایت و مقاومت روی نمودار."""
        self.chart.set_levels(levels)

    def apply_chart_palette(self, palette: dict[str, str]) -> None:
        """هماهنگ کردن رنگ نمودار با پوسته جاری."""
        self.chart.apply_palette(palette)

    def set_ai_text(self, text: str) -> None:
        """نمایش متن تحلیل هوش مصنوعی."""
        self.ai_text.setPlainText(text or "")

    def retranslate(self) -> None:
        """بازسازی متن‌ها."""
        super().retranslate()
        self.symbol_label.setText(self.tr_.tr("common.symbol"))
        self.timeframe_label.setText(self.tr_.tr("common.timeframe"))
        self.run_button.setText(self.tr_.tr("analysis.run"))
        self.select_all_button.setText(self.tr_.tr("analysis.select_all_indicators"))
        self.clear_indicators_button.setText(self.tr_.tr("analysis.clear_indicators"))
        self.tabs.setTabText(0, self.tr_.tr("charts.title"))
        self.tabs.setTabText(1, self.tr_.tr("analysis.indicators"))
        self.tabs.setTabText(2, self.tr_.tr("analysis.levels"))
        self.tabs.setTabText(3, self.tr_.tr("analysis.ai_analysis"))
        self.chart.retranslate()
        self.ai_text.setPlaceholderText(self.tr_.tr("analysis.ai_disabled"))
        self.indicators_card.set_title(self.tr_.tr("analysis.indicators"))
        self._apply_headers()
