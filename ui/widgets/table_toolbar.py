"""
نوار ابزار بالای جدول‌ها: تمام‌صفحه، خروجی و جست‌وجو.

چرا یک ویجت مشترک؟
    کاربر خواست «این قابلیت در تمام جدول‌های سیستم» باشد. پیاده‌سازی
    جداگانه در هر صفحه یعنی هشت نسخهٔ کمی متفاوت که با هم از هم دور
    می‌شوند. اینجا یک ویجت است که به هر `QTableWidget` وصل می‌شود.

روش تمام‌صفحه
    جدول از چیدمانش **جدا نمی‌شود**. جداکردن و برگرداندن یک ویجت بین
    والدها در Qt شکننده است: کشش‌ها، سیاست اندازه و ترتیب ستون‌ها گم
    می‌شوند و در بدترین حالت ویجت پاک می‌شود. در عوض یک پنجرهٔ بدون‌قاب
    روی برنامه باز می‌شود و جدول موقتاً به آن منتقل و در بازگشت دقیقاً
    به جای قبلی‌اش برگردانده می‌شود؛ همان شیء، همان داده، بدون
    بازسازی.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.common import make_button
from ui.widgets.controls import set_role


class FullscreenTableDialog(QDialog):
    """
    پنجرهٔ تمام‌صفحهٔ یک جدول.

    جدول در `__init__` به این پنجره منتقل می‌شود و هنگام بسته‌شدن به
    چیدمان اصلی‌اش بازگردانده می‌شود — چه با دکمهٔ بستن، چه با Escape،
    چه با بستن پنجره از نوار عنوان. هر سه مسیر به `closeEvent` می‌رسند،
    پس بازگرداندن در همان یک جا انجام می‌شود.
    """

    def __init__(
        self,
        table: QWidget,
        origin_layout: Any,
        origin_index: int,
        title: str,
        close_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._table = table
        self._origin_layout = origin_layout
        self._origin_index = origin_index
        self._restored = False

        self.setWindowTitle(title)
        self.setLayoutDirection(
            parent.layoutDirection() if parent is not None else Qt.LayoutDirection.RightToLeft
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(title, self)
        set_role(self.title_label, "title")
        header.addWidget(self.title_label)
        header.addStretch(1)

        self.close_button = make_button(close_text, role="ghost")
        self.close_button.clicked.connect(self.close)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        layout.addWidget(table, 1)

        # Escape باید همیشه راه خروج باشد؛ QDialog این را خودش می‌دهد
        # ولی صریح‌بودنش از رگرسیون جلوگیری می‌کند.
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut.activated.connect(self.close)

    def restore(self) -> None:
        """
        بازگرداندن جدول به چیدمان اصلی.

        محافظت‌شده در برابر فراخوانی دوباره: اگر هم `closeEvent` و هم
        فراخوانی دستی اتفاق بیفتد، جدول نباید دو بار درج شود.
        """
        if self._restored:
            return
        self._restored = True
        if self._origin_layout is not None:
            self._origin_layout.insertWidget(self._origin_index, self._table)
        self._table.show()

    def closeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """هر مسیر بستن باید جدول را برگرداند، وگرنه صفحه خالی می‌ماند."""
        self.restore()
        super().closeEvent(event)


class TableToolbar(QWidget):
    """
    نوار ابزار کوچک بالای یک جدول.

    فعلاً دکمهٔ تمام‌صفحه را دارد و برای افزودن دکمه‌های دیگر (خروجی،
    جست‌وجو) با `add_widget` باز است.
    """

    #: جدول تمام‌صفحه شد یا برگشت
    fullscreen_toggled = Signal(bool)

    #: جدول با موفقیت در این مسیر ذخیره شد
    exported = Signal(str)

    def __init__(
        self,
        table: QWidget,
        translator: Any,
        *,
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._table = table
        self.tr_ = translator
        self._title = title
        self._dialog: FullscreenTableDialog | None = None

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 4)
        self._layout.setSpacing(6)
        self._layout.addStretch(1)

        # خروجی CSV پیش از دکمهٔ تمام‌صفحه می‌نشیند. چون این نوار به
        # صورت خودکار به هر جدول برنامه وصل می‌شود، این یک دکمه یعنی
        # «خروجی از هر جدول سیستم» بدون دست‌زدن به تک‌تک صفحه‌ها.
        self.export_button = make_button("", role="ghost")
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.clicked.connect(self.export_csv)
        self._layout.addWidget(self.export_button)

        self.fullscreen_button = make_button("", role="ghost")
        self.fullscreen_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self._layout.addWidget(self.fullscreen_button)

        self.retranslate()

    # ------------------------------------------------------------------ API
    def add_widget(self, widget: QWidget) -> None:
        """افزودن یک کنترل دلخواه پیش از دکمهٔ تمام‌صفحه."""
        self._layout.insertWidget(self._layout.count() - 1, widget)

    @property
    def is_fullscreen(self) -> bool:
        """آیا جدول در حالت تمام‌صفحه است؟"""
        return self._dialog is not None

    def set_title(self, title: str) -> None:
        """عنوانی که در پنجرهٔ تمام‌صفحه نشان داده می‌شود."""
        self._title = title

    def toggle_fullscreen(self) -> None:
        """رفتن به تمام‌صفحه یا بازگشت از آن."""
        if self._dialog is not None:
            self._dialog.close()
            return
        self.enter_fullscreen()

    def enter_fullscreen(self) -> None:
        """
        باز کردن جدول در پنجرهٔ تمام‌صفحه.

        جای دقیق جدول در چیدمان پیش از انتقال ذخیره می‌شود تا در
        بازگشت، ترتیب ویجت‌های صفحه به هم نریزد.
        """
        if self._dialog is not None:
            return

        layout = self._table.parentWidget().layout() if self._table.parentWidget() else None
        index = layout.indexOf(self._table) if layout is not None else -1
        if layout is None or index < 0:
            # جدول در چیدمان قابل‌بازگشتی نیست؛ تمام‌صفحه‌کردنش یعنی
            # ریسک گم‌شدن. بی‌صدا صرف‌نظر می‌کنیم.
            return

        window = self.window()
        dialog = FullscreenTableDialog(
            self._table,
            layout,
            index,
            self._resolve_title(),
            self.tr_.tr("common.exit_fullscreen"),
            window,
        )
        dialog.finished.connect(self._on_dialog_finished)
        self._dialog = dialog
        self._sync_button()
        self.fullscreen_toggled.emit(True)

        if window is not None:
            dialog.resize(window.size())
        dialog.showMaximized()

    def exit_fullscreen(self) -> None:
        """بستن پنجرهٔ تمام‌صفحه (اگر باز است)."""
        if self._dialog is not None:
            self._dialog.close()

    # ------------------------------------------------------- خروجی CSV
    def table_to_rows(self) -> list[list[str]]:
        """
        محتوای جدول به شکل سطرهای متنی، شامل سرستون‌ها.

        ستون‌های پنهان نادیده گرفته می‌شوند: کاربر همان چیزی را که
        می‌بیند خروجی می‌گیرد. سلولی که به‌جای متن ویجت دارد (مثل دکمهٔ
        «تحلیل هوشمند») خالی می‌ماند، چون متنِ آن دکمه داده نیست.
        """
        table = self._table
        if not isinstance(table, QTableWidget):
            return []

        columns = [c for c in range(table.columnCount()) if not table.isColumnHidden(c)]
        header: list[str] = []
        for column in columns:
            item = table.horizontalHeaderItem(column)
            header.append(item.text().strip() if item is not None else "")

        rows: list[list[str]] = [header]
        for row in range(table.rowCount()):
            if table.isRowHidden(row):
                continue
            line: list[str] = []
            for column in columns:
                item = table.item(row, column)
                # نشانگرهای جهت‌نویسی برای اکسل معنایی ندارند و فقط
                # کاراکتر ناخوانا تولید می‌کنند.
                text = item.text() if item is not None else ""
                line.append(text.replace("\u200e", "").replace("\u200f", "").strip())
            rows.append(line)
        return rows

    def export_csv(self) -> str:
        """
        ذخیرهٔ محتوای جدول در یک فایل CSV.

        مسیر انتخابی کاربر برگردانده می‌شود؛ رشتهٔ خالی یعنی انصراف.
        """
        rows = self.table_to_rows()
        if len(rows) <= 1:
            QMessageBox.information(
                self,
                self.tr_.tr("common.export_csv"),
                self.tr_.tr("common.export_empty"),
            )
            return ""

        suggested = f"{self._resolve_title() or 'table'}.csv".replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr_.tr("common.export_csv"),
            suggested,
            "CSV (*.csv)",
        )
        if not path:
            return ""
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            self.write_csv(path, rows)
        except OSError as exc:
            QMessageBox.warning(
                self,
                self.tr_.tr("common.export_csv"),
                self.tr_.tr("common.export_failed", error=str(exc)),
            )
            return ""

        self.exported.emit(path)
        return path

    @staticmethod
    def write_csv(path: str, rows: list[list[str]]) -> None:
        """
        نوشتن سطرها در فایل.

        ‏`utf-8-sig` عمدی است: اکسل ویندوز بدون BOM فایل UTF-8 را با
        کدگذاری محلی می‌خواند و همهٔ متن فارسی به هم می‌ریزد — همان
        مشکلی که یک بار در خروجی PDF دیدیم.
        """
        import csv

        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            csv.writer(handle).writerows(rows)

    def retranslate(self) -> None:
        """به‌روزرسانی متن‌ها پس از تغییر زبان."""
        self._sync_button()

    # -------------------------------------------------------------- درونی
    def _on_dialog_finished(self, _result: int = 0) -> None:
        """پاک‌کردن ارجاع پس از بسته‌شدن پنجره."""
        self._dialog = None
        self._sync_button()
        self.fullscreen_toggled.emit(False)

    def _resolve_title(self) -> str:
        """
        عنوان پنجرهٔ تمام‌صفحه.

        اگر عنوان صریحی داده نشده باشد، عنوان نزدیک‌ترین کارتِ دربرگیرنده
        خوانده می‌شود. مزیتش این است که با تغییر زبان خودبه‌خود درست
        می‌ماند، چون از خود برچسبِ ترجمه‌شده خوانده می‌شود نه از یک کپی.
        """
        if self._title:
            return self._title
        node = self.parentWidget()
        while node is not None:
            label = getattr(node, "title_label", None)
            if label is not None and label.text():
                return str(label.text())
            # جدولی که داخل کارتِ عنوان‌دار نیست (مثل جدول معاملات که
            # خودش تمام صفحه است) عنوانِ خود صفحه را می‌گیرد.
            header = getattr(node, "header", None)
            header_label = getattr(header, "title_label", None)
            if header_label is not None and header_label.text():
                return str(header_label.text())
            node = node.parentWidget()
        return self.tr_.tr("common.table")

    def _sync_button(self) -> None:
        """متن و راهنمای دکمه بر پایهٔ حالت فعلی."""
        if self._dialog is not None:
            self.fullscreen_button.setText("⤡  " + self.tr_.tr("common.exit_fullscreen"))
            self.fullscreen_button.setToolTip(self.tr_.tr("common.exit_fullscreen"))
        else:
            self.fullscreen_button.setText("⤢  " + self.tr_.tr("common.fullscreen"))
            self.fullscreen_button.setToolTip(self.tr_.tr("common.fullscreen_hint"))
        self.export_button.setText("⤓  " + self.tr_.tr("common.export_csv"))
        self.export_button.setToolTip(self.tr_.tr("common.export_csv_hint"))


def attach_table_toolbar(
    table: QWidget,
    translator: Any,
    *,
    title: str = "",
) -> TableToolbar | None:
    """
    افزودن نوار ابزار درست بالای یک جدول، درون همان چیدمان.

    جای جدول را در چیدمان والدش پیدا می‌کند و نوار را یک ردیف بالاتر
    درج می‌کند؛ بنابراین صفحه‌ها نیازی به بازچینش دستی ندارند. اگر جدول
    هنوز در چیدمانی نباشد، `None` برمی‌گردد تا فراخوان بداند کاری انجام
    نشده است — سکوت بدون نشانه، اشکال را پنهان می‌کند.
    """
    parent = table.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is None:
        return None
    index = layout.indexOf(table)
    if index < 0:
        return None

    toolbar = TableToolbar(table, translator, title=title, parent=parent)
    insert = getattr(layout, "insertWidget", None)
    if insert is None:
        return None
    insert(index, toolbar)
    return toolbar


def attach_table_toolbars(root: QWidget, translator: Any) -> list[TableToolbar]:
    """
    افزودن نوار ابزار به **همهٔ** جدول‌های زیرمجموعهٔ یک ویجت.

    کاربر خواست این کنترل روی تمام جدول‌های سیستم باشد. به‌جای اینکه
    نویسندهٔ هر صفحه یادش بماند، یک بار اینجا روی درخت ویجت‌ها پیمایش
    می‌شود؛ صفحهٔ تازه‌ای هم که بعداً اضافه شود خودبه‌خود این کنترل را
    دارد.

    جدولی که از قبل نوار دارد دوباره نمی‌گیرد، و جدولی که در چیدمان
    قابل‌بازگشتی نیست رد می‌شود.
    """
    from PySide6.QtWidgets import QTableWidget  # درون‌تابعی برای پرهیز از حلقهٔ وارد‌کردن

    attached: list[TableToolbar] = []
    for table in root.findChildren(QTableWidget):
        if table.property("hasTableToolbar"):
            continue
        toolbar = attach_table_toolbar(table, translator)
        if toolbar is None:
            continue
        table.setProperty("hasTableToolbar", True)
        attached.append(toolbar)
    return attached


__all__ = [
    "FullscreenTableDialog",
    "TableToolbar",
    "attach_table_toolbar",
    "attach_table_toolbars",
]
