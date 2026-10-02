"""
ویجت‌های «مرکز فرمان» داشبورد (نسخهٔ 2.3.1).

هدف: کاربر در یک نگاه ببیند اتصال چقدر تازه است، پرتفوی کاغذی چه وضعی
دارد، موتور معامله چه می‌کند و بازار صعودی است یا نزولی. هیچ عددی ساخته
نمی‌شود؛ نبود داده با «—» نمایش داده می‌شود، نه صفر.

همهٔ رنگ‌ها از نقش‌های QSS پوسته می‌آیند (chip_up، bearish، …) تا با تغییر
پوسته هماهنگ بمانند؛ تنها نوار پهنای بازار رنگ را مستقیم از توکن‌ها می‌خواند.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _set_role(label: QLabel, role: str) -> None:
    if label.property("role") != role:
        label.setProperty("role", role)
        _repolish(label)


#: نقش رنگی → نقش برچسب «چیپ» وضعیت
_CHIP_FOR_ROLE = {
    "bullish": "chip_up",
    "bearish": "chip_down",
    "neutral": "chip_warn",
    "info": "chip_info",
}


class StatusDot(QWidget):
    """دایرهٔ کوچک رنگی وضعیت؛ رنگ از توکن‌های پوسته."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._role = "neutral"
        self._theme: Any = None
        self.setFixedSize(12, 12)

    def apply_theme(self, theme: Any) -> None:
        self._theme = theme
        self.update()

    def set_role(self, role: str) -> None:
        self._role = role
        self.update()

    def color(self) -> QColor:
        colors = getattr(self._theme, "colors", None)
        name = {"bullish": "success", "bearish": "danger", "info": "info"}.get(self._role, "warning")
        return QColor(getattr(colors, name, None) or {
            "success": "#16a34a", "danger": "#dc2626", "info": "#2563eb"
        }.get(name, "#d97706"))

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.color()
        halo = QColor(color)
        halo.setAlpha(60)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QRectF(0, 0, 12, 12))
        painter.setBrush(color)
        painter.drawEllipse(QRectF(3, 3, 6, 6))


class HealthTile(QFrame):
    """
    کاشی خلاصه: عنوان + چیپ وضعیت، عدد اصلی، توضیح و چند سطر جزئیات.

    `set_details` سطرها را به ترتیب داده‌شده نمایش می‌دهد؛ سطرهای اضافهٔ
    قبلی پنهان می‌شوند تا کاشی با دادهٔ کمتر به‌هم نریزد.
    """

    MAX_ROWS = 4

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setObjectName("HealthTile")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(220)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.dot = StatusDot()
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "muted")
        self.chip = QLabel("")
        self.chip.setProperty("role", "chip_info")
        self.chip.setVisible(False)
        top.addWidget(self.dot)
        top.addWidget(self.title_label)
        top.addStretch(1)
        top.addWidget(self.chip)
        root.addLayout(top)

        self.value_label = QLabel("—")
        self.value_label.setProperty("role", "metric")
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.value_label)

        self.caption_label = QLabel("")
        self.caption_label.setProperty("role", "faint")
        self.caption_label.setWordWrap(True)
        root.addWidget(self.caption_label)

        separator = QFrame()
        separator.setProperty("role", "separator")
        root.addWidget(separator)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self._rows: list[tuple[QLabel, QLabel]] = []
        for index in range(self.MAX_ROWS):
            key = QLabel("")
            key.setProperty("role", "muted")
            value = QLabel("")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(key, index, 0)
            grid.addWidget(value, index, 1)
            self._rows.append((key, value))
        grid.setColumnStretch(0, 1)
        root.addLayout(grid)
        root.addStretch(1)

        #: آخرین داده برای آزمون و بازسازی پس از تغییر زبان
        self.state: dict[str, Any] = {}

    def apply_theme(self, theme: Any) -> None:
        self.dot.apply_theme(theme)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def set_state(
        self,
        *,
        value: str,
        role: str = "neutral",
        chip: str = "",
        caption: str = "",
        value_role: str = "metric",
        details: list[tuple[str, str, str]] | None = None,
    ) -> None:
        """
        به‌روزرسانی کامل کاشی.

        details: فهرست (برچسب، مقدار، نقش رنگی) — نقش خالی یعنی رنگ عادی.
        """
        self.state = {"value": value, "role": role, "chip": chip, "caption": caption,
                      "details": list(details or [])}
        self.dot.set_role(role)
        self.value_label.setText(value)
        _set_role(self.value_label, value_role)
        self.chip.setText(chip)
        self.chip.setVisible(bool(chip))
        _set_role(self.chip, _CHIP_FOR_ROLE.get(role, "chip_info"))
        self.caption_label.setText(caption)
        self.caption_label.setVisible(bool(caption))
        rows = list(details or [])[: self.MAX_ROWS]
        for index, (key_label, value_label) in enumerate(self._rows):
            if index < len(rows):
                key, text, text_role = rows[index]
                key_label.setText(key)
                value_label.setText(text)
                _set_role(value_label, text_role or "")
                key_label.setVisible(True)
                value_label.setVisible(True)
            else:
                key_label.setVisible(False)
                value_label.setVisible(False)


class BreadthBar(QWidget):
    """نوار سه‌رنگ صعودی/بی‌تغییر/نزولی با گوشه‌های گرد."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._counts = (0, 0, 0)
        self._theme: Any = None
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def apply_theme(self, theme: Any) -> None:
        self._theme = theme
        self.update()

    def set_counts(self, up: int, flat: int, down: int) -> None:
        self._counts = (max(0, int(up)), max(0, int(flat)), max(0, int(down)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        colors = getattr(self._theme, "colors", None)
        palette = [
            QColor(getattr(colors, "success", "#16a34a")),
            QColor(getattr(colors, "border_strong", "#9ca3af")),
            QColor(getattr(colors, "danger", "#dc2626")),
        ]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, 5, 5)
        painter.setClipPath(clip)
        total = sum(self._counts)
        if total <= 0:
            painter.fillRect(rect, palette[1])
            return
        x = rect.left()
        # در چیدمان راست‌به‌چپ هم «صعودی» از سمت شروع خوانده می‌شود.
        order = list(zip(self._counts, palette, strict=True))
        if self.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            order.reverse()
        for count, color in order:
            width = rect.width() * count / total
            painter.fillRect(QRectF(x, rect.top(), width, rect.height()), color)
            x += width


class MoversList(QWidget):
    """فهرست فشردهٔ بیشترین رشد یا افت؛ کلیک روی نماد سیگنال می‌دهد."""

    symbol_clicked = Signal(str)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "muted")
        root.addWidget(self.title_label)
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(3)
        root.addLayout(self._grid)
        self._empty = QLabel("—")
        self._empty.setProperty("role", "faint")
        root.addWidget(self._empty)
        root.addStretch(1)
        self._cells: list[tuple[QLabel, QLabel, QLabel]] = []
        self.rows: list[dict[str, Any]] = []

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def set_empty_text(self, text: str) -> None:
        self._empty.setText(text)

    def set_rows(self, rows: list[dict[str, Any]], price_format=None) -> None:
        """rows: [{symbol, price, change_percent}] از قبل مرتب‌شده."""
        self.rows = [dict(r) for r in rows]
        while len(self._cells) < len(rows):
            index = len(self._cells)
            symbol = QLabel()
            symbol.setCursor(Qt.CursorShape.PointingHandCursor)
            symbol.setProperty("role", "symbol")
            symbol.mousePressEvent = lambda _e, i=index: self._clicked(i)  # type: ignore[method-assign]
            price = QLabel()
            price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            change = QLabel()
            change.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(symbol, index, 0)
            self._grid.addWidget(price, index, 1)
            self._grid.addWidget(change, index, 2)
            self._cells.append((symbol, price, change))
        self._grid.setColumnStretch(0, 1)
        for index, (symbol, price, change) in enumerate(self._cells):
            visible = index < len(rows)
            for label in (symbol, price, change):
                label.setVisible(visible)
            if not visible:
                continue
            row = rows[index]
            pct = float(row.get("change_percent") or 0.0)
            symbol.setText(str(row.get("symbol", "")))
            value = float(row.get("price") or 0.0)
            price.setText(price_format(value) if price_format else f"{value:,.6g}")
            change.setText(f"\u200e{pct:+.2f}%")
            _set_role(change, "chip_up" if pct >= 0 else "chip_down")
        self._empty.setVisible(not rows)

    def _clicked(self, index: int) -> None:
        if index < len(self.rows):
            symbol = str(self.rows[index].get("symbol", ""))
            if symbol:
                self.symbol_clicked.emit(symbol)
