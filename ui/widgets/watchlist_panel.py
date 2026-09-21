"""
مدیریت فهرست‌های دیده‌بانی (مورد ۵.۳ نقشهٔ راه).

مسئله:
    پایگاه داده از همان ابتدا ستون `list_name` و `position` داشت، ولی
    رابط کاربری فقط یک فهرست ثابت به نام `default` را می‌دید و هیچ راهی
    برای مرتب‌سازی دستی نبود. یعنی قابلیت نیمه‌ساخته رها شده بود.

این پنل سه کار می‌کند:
    ۱. ساخت، تغییر نام و حذف فهرست‌های نام‌گذاری‌شده
    ۲. جابه‌جایی دستی نمادها بالا و پایین
    ۳. یادداشت کوتاه روی هر نماد («منتظر شکست ۶۵ هزار»)

چرا دکمهٔ بالا/پایین و نه کشیدن‌ورهاکردن؟
    کشیدن‌ورهاکردن روی جدول با پیمایش و انتخاب چندتایی تداخل می‌کند و
    روی صفحه‌های لمسی و ترک‌پد ناپایدار است. دکمه همیشه کار می‌کند و
    با صفحه‌کلید هم در دسترس است.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import DEFAULT_WATCHLIST as DEFAULT_LIST
from localization import Translator
from ui.widgets.common import Card, configure_table, make_button
from ui.widgets.controls import set_role

#: ستون‌های جدول اعضا
COL_POSITION = 0
COL_SYMBOL = 1
COL_NOTE = 2


class WatchlistPanel(QWidget):
    """پنل مدیریت چند فهرست دیده‌بانی."""

    #: کاربر فهرست دیگری را برگزید (نام فهرست)
    list_selected = Signal(str)
    #: ساخت فهرست تازه (نام)
    list_created = Signal(str)
    #: تغییر نام فهرست (نام قدیم، نام تازه)
    list_renamed = Signal(str, str)
    #: حذف فهرست (نام)
    list_deleted = Signal(str)
    #: جابه‌جایی یک نماد (فهرست، نماد، جهت: ۱- بالا، ۱+ پایین)
    symbol_moved = Signal(str, str, int)
    #: حذف نماد از فهرست (فهرست، نماد)
    symbol_removed = Signal(str, str)
    #: ثبت یادداشت (فهرست، نماد، متن)
    note_changed = Signal(str, str, str)
    #: کاربر روی نماد دوبار کلیک کرد (نماد)
    symbol_activated = Signal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._rows: list[dict[str, Any]] = []
        self._names: list[str] = [DEFAULT_LIST]
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.card = Card(self.tr_.tr("watchlist.title"))
        self.card.body().addLayout(self._build_list_row())
        self.card.body().addLayout(self._build_action_row())
        self.card.add(self._build_table())

        self.empty_label = QLabel(self.tr_.tr("watchlist.empty"))
        set_role(self.empty_label, "muted")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card.add(self.empty_label)

        root.addWidget(self.card)
        self._apply_headers()

    # ------------------------------------------------------------- ساخت

    def _build_list_row(self) -> QHBoxLayout:
        """ردیف انتخاب فهرست و مدیریت آن."""
        row = QHBoxLayout()
        row.setSpacing(8)

        self.list_label = QLabel(self.tr_.tr("watchlist.list"))
        self.list_combo = QComboBox()
        self.list_combo.setMinimumWidth(180)
        self.list_combo.currentIndexChanged.connect(self._on_list_changed)

        self.new_button = make_button(self.tr_.tr("watchlist.new"))
        self.new_button.clicked.connect(self._ask_new_name)
        self.rename_button = make_button(self.tr_.tr("watchlist.rename"))
        self.rename_button.clicked.connect(self._ask_rename)
        self.delete_button = make_button(self.tr_.tr("watchlist.delete"), role="danger")
        self.delete_button.clicked.connect(self._confirm_delete)

        row.addWidget(self.list_label)
        row.addWidget(self.list_combo)
        row.addWidget(self.new_button)
        row.addWidget(self.rename_button)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        return row

    def _build_action_row(self) -> QHBoxLayout:
        """ردیف دکمه‌های ترتیب و ویرایش."""
        row = QHBoxLayout()
        row.setSpacing(8)

        self.up_button = make_button(self.tr_.tr("watchlist.move_up"))
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button = make_button(self.tr_.tr("watchlist.move_down"))
        self.down_button.clicked.connect(lambda: self._move(1))
        self.note_button = make_button(self.tr_.tr("watchlist.edit_note"))
        self.note_button.clicked.connect(self._ask_note)
        self.remove_button = make_button(
            self.tr_.tr("watchlist.remove_symbol"), role="danger"
        )
        self.remove_button.clicked.connect(self._remove_selected)

        self.count_label = QLabel("")
        set_role(self.count_label, "muted")

        row.addWidget(self.up_button)
        row.addWidget(self.down_button)
        row.addWidget(self.note_button)
        row.addWidget(self.remove_button)
        row.addWidget(self.count_label)
        row.addStretch(1)
        return row

    def _build_table(self) -> QTableWidget:
        """جدول اعضای فهرست."""
        self.table = QTableWidget(0, 3)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        return self.table

    def _apply_headers(self) -> None:
        """سرستون‌ها."""
        self.table.setHorizontalHeaderLabels(
            [
                self.tr_.tr("watchlist.position"),
                self.tr_.tr("common.symbol"),
                self.tr_.tr("watchlist.note"),
            ]
        )
        configure_table(self.table, stretch_column=COL_NOTE)

    # ------------------------------------------------------------- داده

    def set_lists(self, names: list[str], counts: dict[str, int] | None = None) -> None:
        """
        پرکردن فهرست‌های موجود.

        انتخاب فعلی در صورت امکان حفظ می‌شود؛ وگرنه کاربر با هر
        به‌روزرسانی به فهرست اول پرت می‌شود.
        """
        counts = counts or {}
        current = self.current_list()
        self._names = [str(name) for name in names] or [DEFAULT_LIST]

        self._loading = True
        self.list_combo.clear()
        for name in self._names:
            label = self._list_label(name, counts.get(name, 0))
            self.list_combo.addItem(label, name)
        index = self.list_combo.findData(current)
        self.list_combo.setCurrentIndex(index if index >= 0 else 0)
        self._loading = False

        # حذف فهرست پیش‌فرض ممکن نیست؛ فقط خالی می‌شود
        self.delete_button.setEnabled(self.current_list() != DEFAULT_LIST)
        self.rename_button.setEnabled(self.current_list() != DEFAULT_LIST)

    def _list_label(self, name: str, count: int) -> str:
        """برچسب فهرست همراه تعداد اعضا."""
        display = (
            self.tr_.tr("watchlist.default_name") if name == DEFAULT_LIST else name
        )
        return f"{display} ({self.tr_.format_number(count, 0)})"

    def set_items(self, rows: list[dict[str, Any]]) -> None:
        """نمایش اعضای فهرست جاری."""
        self._rows = [dict(row) for row in rows or []]
        self.empty_label.setVisible(not self._rows)
        self.table.setVisible(bool(self._rows))

        self.table.setRowCount(len(self._rows))
        for index, row in enumerate(self._rows):
            position = QTableWidgetItem(self.tr_.format_number(index + 1, 0))
            position.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(index, COL_POSITION, position)
            # نماد هرگز نباید با بازچینش راست‌به‌چپ به‌هم بریزد
            self.table.setItem(
                index, COL_SYMBOL, QTableWidgetItem(f"\u200e{row.get('symbol', '')}")
            )
            self.table.setItem(index, COL_NOTE, QTableWidgetItem(str(row.get("note", ""))))

        self.count_label.setText(
            self.tr_.tr(
                "watchlist.count", count=self.tr_.format_number(len(self._rows), 0)
            )
        )
        self._update_buttons()

    def current_list(self) -> str:
        """نام فهرست انتخاب‌شده."""
        data = self.list_combo.currentData()
        return str(data) if data else DEFAULT_LIST

    def selected_symbol(self) -> str:
        """نماد ردیف انتخاب‌شده."""
        row = self.table.currentRow()
        if 0 <= row < len(self._rows):
            return str(self._rows[row].get("symbol", ""))
        return ""

    def _update_buttons(self) -> None:
        """فعال یا غیرفعال کردن دکمه‌ها بر پایهٔ انتخاب."""
        has_selection = bool(self.selected_symbol())
        for button in (self.up_button, self.down_button, self.note_button, self.remove_button):
            button.setEnabled(has_selection)

    # -------------------------------------------------------- رویدادها

    def _on_list_changed(self, _index: int) -> None:
        """کاربر فهرست دیگری را برگزید."""
        if self._loading:
            return
        name = self.current_list()
        self.delete_button.setEnabled(name != DEFAULT_LIST)
        self.rename_button.setEnabled(name != DEFAULT_LIST)
        self.list_selected.emit(name)

    def _on_double_click(self, row: int, _column: int) -> None:
        """دوبار کلیک روی نماد آن را باز می‌کند."""
        if 0 <= row < len(self._rows):
            self.symbol_activated.emit(str(self._rows[row].get("symbol", "")))

    def _ask_new_name(self) -> None:
        """پرسش نام فهرست تازه."""
        name, accepted = QInputDialog.getText(
            self, self.tr_.tr("watchlist.new"), self.tr_.tr("watchlist.name_prompt")
        )
        if accepted and name.strip():
            self.list_created.emit(name.strip())

    def _ask_rename(self) -> None:
        """پرسش نام تازه برای فهرست جاری."""
        current = self.current_list()
        if current == DEFAULT_LIST:
            return
        name, accepted = QInputDialog.getText(
            self,
            self.tr_.tr("watchlist.rename"),
            self.tr_.tr("watchlist.name_prompt"),
            text=current,
        )
        if accepted and name.strip() and name.strip() != current:
            self.list_renamed.emit(current, name.strip())

    def _confirm_delete(self) -> None:
        """
        حذف فهرست جاری.

        تأیید از طریق کنترلر گرفته می‌شود تا پنل به `QMessageBox` وابسته
        نباشد و در آزمون بدون پنجرهٔ مزاحم کار کند.
        """
        current = self.current_list()
        if current != DEFAULT_LIST:
            self.list_deleted.emit(current)

    def _move(self, delta: int) -> None:
        """جابه‌جایی نماد انتخاب‌شده."""
        symbol = self.selected_symbol()
        if symbol:
            self.symbol_moved.emit(self.current_list(), symbol, int(delta))

    def _remove_selected(self) -> None:
        """حذف نماد انتخاب‌شده از فهرست."""
        symbol = self.selected_symbol()
        if symbol:
            self.symbol_removed.emit(self.current_list(), symbol)

    def _ask_note(self) -> None:
        """ویرایش یادداشت نماد انتخاب‌شده."""
        symbol = self.selected_symbol()
        if not symbol:
            return
        row = self.table.currentRow()
        existing = str(self._rows[row].get("note", "")) if 0 <= row < len(self._rows) else ""
        text, accepted = QInputDialog.getText(
            self,
            self.tr_.tr("watchlist.edit_note"),
            self.tr_.tr("watchlist.note_prompt", symbol=symbol),
            text=existing,
        )
        if accepted:
            self.note_changed.emit(self.current_list(), symbol, text.strip())

    def select_symbol(self, symbol: str) -> bool:
        """
        انتخاب برنامه‌ای یک نماد در جدول.

        از `setCurrentCell` استفاده می‌شود نه `selectRow`: وقتی جهت کل
        برنامه راست‌به‌چپ باشد (حالت فارسی) `selectRow` بی‌صدا کاری
        نمی‌کند و ردیف جاری منفی‌یک می‌ماند، پس پس از هر جابه‌جایی
        انتخاب کاربر می‌پرید.
        """
        for index, row in enumerate(self._rows):
            if str(row.get("symbol", "")) == symbol:
                self.table.setCurrentCell(index, COL_SYMBOL)
                # وضعیت دکمه‌ها صریح تازه می‌شود: انتخاب برنامه‌ای
                # همیشه سیگنال تغییر انتخاب را برنمی‌انگیزد.
                self._update_buttons()
                return True
        return False

    def retranslate(self) -> None:
        """بازسازی متن‌ها پس از تغییر زبان."""
        self.card.set_title(self.tr_.tr("watchlist.title"))
        self.list_label.setText(self.tr_.tr("watchlist.list"))
        self.new_button.setText(self.tr_.tr("watchlist.new"))
        self.rename_button.setText(self.tr_.tr("watchlist.rename"))
        self.delete_button.setText(self.tr_.tr("watchlist.delete"))
        self.up_button.setText(self.tr_.tr("watchlist.move_up"))
        self.down_button.setText(self.tr_.tr("watchlist.move_down"))
        self.note_button.setText(self.tr_.tr("watchlist.edit_note"))
        self.remove_button.setText(self.tr_.tr("watchlist.remove_symbol"))
        self.empty_label.setText(self.tr_.tr("watchlist.empty"))
        self._apply_headers()
        if self._rows:
            self.set_items(list(self._rows))


__all__ = ["COL_NOTE", "COL_POSITION", "COL_SYMBOL", "DEFAULT_LIST", "WatchlistPanel"]
