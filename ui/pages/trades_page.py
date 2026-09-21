"""
صفحه تاریخچه معاملات.

معاملات کاغذی ثبت‌شده را با فیلتر بازهٔ تاریخ، جهت و وضعیت نشان می‌دهد،
نوار معیارها را محاسبه می‌کند و امکان خروجی CSV و صفحه‌بندی می‌دهد.

یادآوری معماری: همهٔ معاملات در حالت «کاغذی» ثبت می‌شوند و هیچ سفارش
واقعی ارسال نمی‌گردد؛ ستون `mode` از همین حالا وجود دارد تا روشن‌کردن
سفارش‌گذاری واقعی در آینده این صفحه را تغییر ندهد.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets import (
    EmptyState,
    Pagination,
    RefreshButton,
    set_role,
    configure_table,
    make_button,
)

#: گزینه‌های فیلتر جهت معامله
SIDE_FILTERS = ("all", "long", "short")

#: گزینه‌های فیلتر وضعیت
STATUS_FILTERS = ("all", "open", "closed", "cancelled")

#: شمار ردیف در هر صفحه
PAGE_SIZE = 25


class TradesPage(BasePage):
    """تاریخچهٔ معاملات کاغذی."""

    title_key = "nav.trades"
    subtitle_key = "trades.subtitle"

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

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._rows: list[dict[str, Any]] = []
        self._theme: Any = None
        self._page = 1
        self._pages = 1
        self._page_text = ""
        super().__init__(translator, parent)

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def build(self) -> None:
        """ساخت نوار فیلتر، معیارها، جدول و صفحه‌بندی."""
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

        self.layout_root().addWidget(self._build_auto_panel())
        self.layout_root().addWidget(self._build_filters())
        self.layout_root().addWidget(self._build_metrics())

        # --- جدول ---
        self.table = QTableWidget(0, 10, self)
        configure_table(self.table, stretch_column=1)
        self.table.cellDoubleClicked.connect(self._on_row_activated)
        self.layout_root().addWidget(self.table, 1)

        # بستن معامله پیش‌تر فقط با دوبار کلیک ممکن بود و هیچ نشانه‌ای
        # روی صفحه نداشت؛ یک قابلیت کشف‌نشدنی عملاً وجود ندارد.
        actions_row = QHBoxLayout()
        self.close_trade_button = make_button(self.tr_.tr("trades.close_trade"))
        self.close_trade_button.clicked.connect(self._emit_close_selected)
        self.close_hint = QLabel(self.tr_.tr("trades.close_hint"))
        self.close_hint.setProperty("role", "faint")
        self.close_hint.setWordWrap(True)
        actions_row.addWidget(self.close_trade_button)
        actions_row.addWidget(self.close_hint, 1)
        self.layout_root().addLayout(actions_row)

        self.empty_state = EmptyState(self)
        self.empty_state.configure(
            icon="⇄",
            title=self.tr_.tr("trades.empty"),
            detail=self.tr_.tr("trades.empty_hint"),
        )
        self.empty_state.setVisible(False)
        self.layout_root().addWidget(self.empty_state)

        self.pagination = Pagination(self)
        self.pagination.page_changed.connect(self._on_page_changed)
        self.layout_root().addWidget(self.pagination)

        self._retranslate_headers()

    def _build_auto_panel(self) -> QWidget:
        """
        پنل معاملهٔ خودکار.

        کاربر خواست بخشی باشد که خودش معامله را باز کند و به‌محض رسیدن
        به هدف سود ببندد و بعدی را باز کند. موتورش از پیش ساخته شده بود
        ولی هیچ راهی برای روشن‌کردنش وجود نداشت — یعنی عملاً نبود.

        همهٔ عددها (هدف سود، حد ضرر، اهرم، سرمایهٔ هر معامله) در تنظیمات
        دست کاربر است؛ اینجا فقط نمایش داده می‌شوند تا پیش از شروع
        معلوم باشد با چه چیزی معامله می‌شود.
        """
        frame = QFrame(self)
        set_role(frame, "card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel(self.tr_.tr("trades.auto.title"))
        set_role(title, "subtitle")
        top.addWidget(title)
        top.addStretch(1)

        self.auto_state_label = QLabel(self.tr_.tr("trades.auto.stopped"))
        set_role(self.auto_state_label, "chip_warn")
        top.addWidget(self.auto_state_label)

        self.auto_toggle_button = make_button(
            self.tr_.tr("trades.auto.start"), primary=True
        )
        self.auto_toggle_button.clicked.connect(self._on_auto_toggle)
        top.addWidget(self.auto_toggle_button)
        layout.addLayout(top)

        # خلاصهٔ تنظیمات فعال — کاربر باید پیش از زدن «شروع» بداند
        # با چه هدف، چه حد ضرر و چه اهرمی معامله می‌شود.
        self.auto_config_label = QLabel("—")
        set_role(self.auto_config_label, "muted")
        self.auto_config_label.setWordWrap(True)
        layout.addWidget(self.auto_config_label)

        self.auto_status_label = QLabel(self.tr_.tr("trades.auto.hint"))
        set_role(self.auto_status_label, "faint")
        self.auto_status_label.setWordWrap(True)
        layout.addWidget(self.auto_status_label)

        # ----------------------------------------------------------
        # تنظیم دستی روی همین صفحه
        # ----------------------------------------------------------
        # کاربر خواست بتواند عددها را هم خودکار بگذارد هم دستی، بدون
        # رفتن به صفحهٔ تنظیمات. این‌ها همان کلیدهای `scalp.*` هستند،
        # پس هر تغییری اینجا و آنجا یکی است.
        layout.addWidget(self._build_auto_manual_box())

        return frame

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
        self.auto_leverage_input.setRange(1, 25)
        self.auto_leverage_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.auto_concurrent_input = QSpinBox()
        self.auto_concurrent_input.setRange(1, 10)
        self.auto_concurrent_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
            ("trades.auto.min_confidence", self.auto_confidence_input),
            ("trades.auto.source", self.auto_source_combo),
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
            # جمع‌کردن واقعی، نه فقط غیرفعال‌کردن: پنل بسته نباید
            # ارتفاع صفحه را بگیرد.
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
        self.auto_confidence_input.setValue(int(values.get("scalp.min_confidence", 75)))
        index = self.auto_source_combo.findData(
            str(values.get("scalp.candidate_source", "confidence"))
        )
        if index >= 0:
            self.auto_source_combo.setCurrentIndex(index)

    def collect_auto_settings(self) -> dict:
        """خواندن عددهای دستی برای ذخیره."""
        return {
            "scalp.margin_per_trade": self.auto_margin_input.value(),
            "scalp.target_profit": self.auto_target_input.value(),
            "scalp.max_loss": self.auto_loss_input.value(),
            "scalp.leverage": self.auto_leverage_input.value(),
            "scalp.max_concurrent": self.auto_concurrent_input.value(),
            "scalp.min_confidence": self.auto_confidence_input.value(),
            "scalp.candidate_source": self.auto_source_combo.currentData(),
        }

    def _emit_auto_settings(self) -> None:
        """اعلام تغییر عددها به کنترلر."""
        self.auto_settings_changed.emit(self.collect_auto_settings())

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
        if running:
            self.auto_toggle_button.setText(self.tr_.tr("trades.auto.stop"))
            self.auto_state_label.setText(self.tr_.tr("trades.auto.running"))
            set_role(self.auto_state_label, "chip_up")
        else:
            self.auto_toggle_button.setText(self.tr_.tr("trades.auto.start"))
            self.auto_state_label.setText(self.tr_.tr("trades.auto.stopped"))
            set_role(self.auto_state_label, "chip_warn")
        self.auto_status_label.setText(detail or self.tr_.tr("trades.auto.hint"))

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
        self._rows = list(rows or [])
        self._page, self._pages = page, pages

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._rows))

        for index, row in enumerate(self._rows):
            symbol = QTableWidgetItem(str(row.get("symbol", "")))
            symbol.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

            side_key = str(row.get("side", "")).lower()
            side_item = self._cell(self.tr_.tr(f"trades.sides.{side_key}", side_key))
            status_key = str(row.get("status", "")).lower()
            status_item = self._cell(
                self.tr_.tr(f"trades.statuses.{status_key}", status_key)
            )

            pnl_value = row.get("pnl")
            pnl_item = self._cell(row.get("pnl_text", ""))
            percent_item = self._cell(row.get("pnl_percent_text", ""))

            if self._theme is not None and isinstance(pnl_value, (int, float)):
                colors = self._theme.colors
                tint = QColor(colors.success if pnl_value >= 0 else colors.danger)
                pnl_item.setForeground(tint)
                percent_item.setForeground(tint)
            if self._theme is not None:
                colors = self._theme.colors
                side_item.setForeground(
                    QColor(colors.success if side_key == "long" else colors.danger)
                )

            cells = [
                self._cell(row.get("date_text", "")),
                symbol,
                side_item,
                status_item,
                self._cell(row.get("quantity_text", "")),
                self._cell(row.get("entry_text", "")),
                self._cell(row.get("exit_text", "")),
                self._cell(row.get("leverage_text", "")),
                pnl_item,
                percent_item,
            ]
            for column, item in enumerate(cells):
                self.table.setItem(index, column, item)

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
        self.empty_state.configure(
            icon="⇄",
            title=self.tr_.tr("trades.empty"),
            detail=self.tr_.tr("trades.empty_hint"),
        )
        self._fill_filter_combos()
        self._retranslate_headers()

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
        """عنوان ستون‌های جدول."""
        self.table.setHorizontalHeaderLabels(
            [
                self.tr_.tr("trades.date"),
                self.tr_.tr("trades.symbol"),
                self.tr_.tr("trades.side"),
                self.tr_.tr("trades.status"),
                self.tr_.tr("trades.quantity"),
                self.tr_.tr("trades.entry"),
                self.tr_.tr("trades.exit"),
                self.tr_.tr("trades.leverage"),
                self.tr_.tr("trades.pnl"),
                self.tr_.tr("trades.pnl_percent"),
            ]
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

    def _on_row_activated(self, row: int, _column: int) -> None:
        """دوبار کلیک روی معاملهٔ باز آن را می‌بندد."""
        data = self.trade_row(row)
        if data and str(data.get("status")) == "open":
            self.close_requested.emit(int(data.get("id", 0)))

    @staticmethod
    def _cell(text: str) -> QTableWidgetItem:
        """ساخت خانهٔ جدول با چینش وسط."""
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item


__all__ = ["PAGE_SIZE", "SIDE_FILTERS", "STATUS_FILTERS", "TradesPage"]
