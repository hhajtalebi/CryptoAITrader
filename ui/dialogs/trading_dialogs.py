"""
مودال‌های صفحهٔ معاملهٔ خودکار (v2.2).

هر دو دیالوگ فقط «نمایش و انتخاب»اند — منطق معامله و داده در
کنترلر و موتورهاست. `SymbolPickerDialog` لیست نمادهای تیک‌خور را
برمی‌گرداند و `PositionDetailDialog` همهٔ فیلدهای واقعی یک موقعیتِ
باز را نشان می‌دهد و دکمهٔ بستن دارد.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStyledItemDelegate,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.widgets import set_role, make_button


def _symbol_hue(name: str) -> int:
    """رنگ ثابت برای هر نماد — از مجموع حروف نام."""
    return sum(ord(ch) for ch in str(name or "X")) % 360


class SymbolIconWidget(QWidget):
    """دایرهٔ رنگی با حروف اول نماد — آیکون سبک صرافی‌ها."""

    def __init__(self, symbol: str, size: int = 22, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._symbol = str(symbol or "?")
        self._size = size
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        hue = _symbol_hue(self._symbol)
        color = QColor.fromHsl(hue, 160, 140)
        painter.setPen(QPen(color.darker(120), 1))
        painter.setBrush(color)
        painter.drawEllipse(1, 1, self._size - 2, self._size - 2)
        painter.setPen(QColor("#0a0e1a"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(8, self._size // 2 - 2))
        painter.setFont(font)
        initials = (self._symbol.split("/")[0] or "?")[:3]
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, initials)
        painter.end()


class SymbolIconDelegate(QStyledItemDelegate):
    """
    رسم آیکون نماد در منوی کشویی کمبو — دایرهٔ رنگی + نام.

    سبک صرافی‌ها: هر نماد رنگ ثابت خودش را دارد (از روی نام) تا
    چشم سریع پیدایش کند.
    """

    def paint(self, painter: QPainter, option: Any, index: Any) -> None:
        symbol = str(index.data() or "")
        painter.save()
        option.text = ""
        if option.widget is not None:
            option.widget.style().drawControl(
                QStyle.ControlElement.CE_ItemViewItem, option, painter, option.widget
            )
        icon = SymbolIconWidget(symbol, 20)
        pixmap = icon.grab()
        painter.drawPixmap(
            option.rect.left() + 8,
            option.rect.center().y() - 10,
            pixmap,
        )
        painter.setPen(
            QColor("#e9eefb")
            if option.state & QStyle.StateFlag.State_Selected
            else QColor("#c8d0e0")
        )
        painter.drawText(
            option.rect.adjusted(36, 0, -8, 0),
            Qt.AlignmentFlag.AlignVCenter,
            symbol,
        )
        painter.restore()

    def sizeHint(self, option: Any, index: Any) -> Any:  # noqa: N802
        return QSize(190, 30)


class SymbolPickerDialog(QDialog):
    """
    انتخاب چند نماد با تیک + جست‌وجو (خواستهٔ v2.2).

    لیست کامل از بیرون داده می‌شود (کنترلر/مخزن)؛ انتخاب‌های فعلی
    هم‌زمان با تایپ جست‌وجو فیلتر می‌شوند. تأیید → فهرست نمادها.
    """

    def __init__(
        self,
        translator: Translator,
        symbols: list[str],
        selected: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self.setWindowTitle(translator.tr("trades.auto.picker_title"))
        self.setMinimumSize(420, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        hint = QLabel(translator.tr("trades.auto.picker_hint"), self)
        set_role(hint, "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText(translator.tr("trades.auto.search_hint"))
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.list_widget = QListWidget(self)
        self.list_widget.setAlternatingRowColors(True)
        self._all_symbols = [str(s) for s in symbols or []]
        chosen = {str(s).strip().upper() for s in selected or []}
        for symbol in self._all_symbols:
            item = QListWidgetItem(symbol)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if symbol.strip().upper() in chosen
                else Qt.CheckState.Unchecked
            )
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(
            lambda item: self.list_widget.setItemWidget(item, None)
            or self._toggle(item)
        )
        layout.addWidget(self.list_widget, 1)

        self.count_label = QLabel("", self)
        set_role(self.count_label, "muted")
        layout.addWidget(self.count_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            translator.tr("common.save")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            translator.tr("common.cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_count()

    def _toggle(self, item: QListWidgetItem) -> None:
        """دوبار کلیک = تغییر تیک (میان‌بر)."""
        item.setCheckState(
            Qt.CheckState.Unchecked
            if item.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._update_count()

    def _filter(self, needle: str) -> None:
        """نمایش فقط نمادهای منطبق با جست‌وجو."""
        needle = (needle or "").strip().upper()
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            item.setHidden(bool(needle) and needle not in item.text().upper())
        self._update_count()

    def _update_count(self) -> None:
        chosen = self.checked_symbols()
        self.count_label.setText(self.tr_.tr("trades.auto.picker_count", count=len(chosen)))

    def checked_symbols(self) -> list[str]:
        """نمادهای تیک‌خور به ترتیب لیست."""
        result: list[str] = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if not item.isHidden() and item.checkState() == Qt.CheckState.Checked:
                result.append(item.text())
        return result


class PositionDetailDialog(QDialog):
    """
    جزئیات کامل یک موقعیت باز + دکمهٔ بستن (خواستهٔ v2.2).

    ردیف داده از همان دیکشنری جدول موقعیت‌ها می‌آید؛ هیچ عددی
    اینجا ساخته نمی‌شود. دکمهٔ بستن فقط سیگنال می‌دهد — بستنِ
    واقعی کار موتور است.
    """

    close_trade_requested = Signal(int)

    #: ترتیب نمایش فیلدها — (کلید ردیف، کلید ترجمه)
    FIELD_ORDER: list[tuple[str, str]] = [
        ("symbol", "pos_symbol"),
        ("side_text", "pos_side"),
        ("quantity_text", "pos_quantity"),
        ("entry_text", "pos_entry"),
        ("current_text", "pos_current"),
        ("bid_text", "pos_bid"),
        ("ask_text", "pos_ask"),
        ("margin_text", "pos_margin"),
        ("notional_text", "pos_notional"),
        ("leverage_text", "pos_leverage"),
        ("tp_text", "pos_tp"),
        ("sl_text", "pos_sl"),
        ("pnl_text", "pos_pnl"),
        ("pnl_percent_text", "pos_pnl_percent"),
        ("duration_text", "pos_duration"),
        ("data_age_text", "pos_data_age"),
        ("exit_reason_text", "pos_exit_reason"),
        ("status_text", "pos_status"),
        ("fee_text", "pos_fee"),
    ]

    def __init__(
        self,
        translator: Translator,
        row: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._trade_id = row.get("id")
        self.setWindowTitle(
            translator.tr("trades.auto.detail_title", symbol=str(row.get("symbol", "—")))
        )
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # سربرگ: آیکون نماد + جهت رنگی
        head = QHBoxLayout()
        head.addWidget(SymbolIconWidget(str(row.get("symbol", "?")), 34, self))
        title = QLabel(str(row.get("symbol", "—")), self)
        set_role(title, "subtitle")
        head.addWidget(title)
        side = QLabel(str(row.get("side_text", "—")), self)
        is_long = str(row.get("side", "")).lower() == "long"
        set_role(side, "chip_up" if is_long else "chip_down")
        head.addWidget(side)
        head.addStretch(1)
        pnl = QLabel(str(row.get("pnl_text", "—")), self)
        set_role(pnl, "chip_up" if float(row.get("pnl") or 0) >= 0 else "chip_down")
        head.addWidget(pnl)
        layout.addLayout(head)

        # شبکهٔ فیلدها در ناحیهٔ پیمایش (مقاوم در رزولوشن کم)
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        for index, (key, tr_key) in enumerate(self.FIELD_ORDER):
            if key not in row:
                continue
            caption = QLabel(translator.tr(f"trades.auto.{tr_key}"), grid_widget)
            set_role(caption, "muted")
            value = QLabel(str(row.get(key) or "—"), grid_widget)
            value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            grid.addWidget(caption, index // 2, (index % 2) * 2)
            grid.addWidget(value, index // 2, (index % 2) * 2 + 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(grid_widget)
        layout.addWidget(scroll, 1)

        # دکمه‌ها
        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton(translator.tr("common.close"), self)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        if self._trade_id is not None and row.get("status", "open") == "open":
            close_btn = make_button(
                translator.tr("trades.auto.close_selected"), primary=True
            )
            close_btn.clicked.connect(self._emit_close)
            actions.addWidget(close_btn)
        layout.addLayout(actions)

    def _emit_close(self) -> None:
        """درخواست بستن — شناسهٔ عددی موقعیت."""
        try:
            self.close_trade_requested.emit(int(self._trade_id))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        self.accept()


class ScannerSettingsDialog(QDialog):
    """
    تنظیمات پویش فرصت‌ها — مودال (خواستهٔ v2.2).

    همهٔ مقادیر اولیه از تنظیمات واقعی کاربر می‌آید و نتیجه به‌صورت
    دیکشنری کلید→مقدار برگردانده می‌شود؛ ذخیره‌سازی کار کنترلر است.
    """

    def __init__(
        self,
        translator: Translator,
        values: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self.setWindowTitle(translator.tr("trades.auto.scanner_title"))
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

        hint = QLabel(translator.tr("trades.auto.scanner_hint"), self)
        set_role(hint, "muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        self.enabled_check = QCheckBox(
            translator.tr("trades.auto.scanner_enabled"), self
        )
        self.enabled_check.setChecked(bool(values.get("watch_scan_enabled", True)))
        grid.addWidget(self.enabled_check, 0, 0, 1, 2)

        def add_spin(
            row: int, caption_key: str, key: str, fallback: float,
            minimum: float, maximum: float, decimals: int, suffix: str = "",
        ) -> None:
            caption = QLabel(translator.tr(f"trades.auto.{caption_key}"), self)
            set_role(caption, "muted")
            grid.addWidget(caption, row, 0)
            if decimals == 0:
                spin: QWidget = QSpinBox(self)
                spin.setRange(int(minimum), int(maximum))
                spin.setValue(int(float(values.get(key, fallback) or fallback)))
            else:
                dspin = QDoubleSpinBox(self)
                dspin.setDecimals(decimals)
                dspin.setRange(minimum, maximum)
                dspin.setValue(float(values.get(key, fallback) or fallback))
                spin = dspin
            spin.setSuffix(suffix)
            grid.addWidget(spin, row, 1)
            setattr(self, key, spin)

        add_spin(1, "scanner_interval", "watch_scan_interval", 20, 5, 300, 0, " s")
        add_spin(2, "scanner_min_confidence", "watch_min_confidence", 70, 0, 100, 0, " %")
        add_spin(3, "scanner_max_spread", "watch_max_spread", 0.25, 0.01, 5.0, 2, " %")
        add_spin(4, "scanner_row_cap", "watch_row_cap", 30, 5, 100, 0)
        layout.addLayout(grid)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            translator.tr("common.save")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            translator.tr("common.cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, Any]:
        """مقادیر مودال به‌صورت کلیدهای تنظیمات."""
        return {
            "scalp.watch_scan_enabled": self.enabled_check.isChecked(),
            "scalp.watch_scan_interval": float(self.watch_scan_interval.value()),
            "scalp.watch_min_confidence": float(self.watch_min_confidence.value()),
            "scalp.watch_max_spread": float(self.watch_max_spread.value()),
            "scalp.watch_row_cap": int(self.watch_row_cap.value()),
        }
