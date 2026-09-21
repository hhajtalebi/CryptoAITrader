"""
کنترل‌های مشترک رابط کاربری: بخش‌بندی تایم‌فریم، کلید روشن/خاموش،
نوار تراشه‌ها، کارت آمار، صفحه‌بندی و اعلان شناور.

همهٔ این‌ها پوسته‌آگاه‌اند: ظاهرشان از QSS (خاصیت `role`) می‌آید و هیچ
رنگی درونشان نوشته نشده است.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.charts_mini import Sparkline


def set_role(widget: QWidget, role: str) -> QWidget:
    """
    تعیین نقش ظاهری یک ویجت برای انتخابگرهای QSS.

    اگر ویجت از قبل نمایش داده شده باشد، سبک آن دوباره محاسبه می‌شود؛
    بدون این کار تغییر نقش در زمان اجرا بی‌اثر می‌ماند.
    """
    widget.setProperty("role", role)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    return widget


class SegmentedControl(QWidget):
    """
    ردیف دکمه‌های انحصاری — برای تایم‌فریم (۱m/۵m/…) و بازه‌های زمانی.

    نمونه‌سازی:
        bar = SegmentedControl([("1h", "۱ ساعت"), ("4h", "۴ ساعت")])
        bar.selection_changed.connect(handler)

    سیگنال: `selection_changed(str)` با کلید گزینهٔ انتخاب‌شده.
    """

    selection_changed = Signal(str)

    def __init__(
        self,
        options: Sequence[tuple[str, str]] | None = None,
        parent: QWidget | None = None,
        *,
        spacing: int = 2,
    ) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(spacing)

        set_role(self, "plain")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        if options:
            self.set_options(options)

    def set_options(self, options: Sequence[tuple[str, str]]) -> None:
        """جایگزینی کامل گزینه‌ها؛ انتخاب فعلی در صورت امکان حفظ می‌شود."""
        previous = self.current()
        for button in list(self._buttons.values()):
            self._group.removeButton(button)
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()

        for key, label in options:
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            set_role(button, "segment")
            button.clicked.connect(lambda _checked=False, k=key: self._on_clicked(k))
            self._group.addButton(button)
            self._layout.addWidget(button)
            self._buttons[key] = button

        if previous in self._buttons:
            self.set_current(previous, emit=False)
        elif self._buttons:
            self.set_current(next(iter(self._buttons)), emit=False)

    def set_labels(self, labels: dict[str, str]) -> None:
        """به‌روزرسانی متن دکمه‌ها هنگام تغییر زبان."""
        for key, text in labels.items():
            if key in self._buttons:
                self._buttons[key].setText(text)

    def current(self) -> str:
        """کلید گزینهٔ فعال."""
        for key, button in self._buttons.items():
            if button.isChecked():
                return key
        return ""

    def set_current(self, key: str, *, emit: bool = True) -> None:
        """انتخاب یک گزینه به‌صورت برنامه‌ای."""
        button = self._buttons.get(key)
        if button is None:
            return
        button.setChecked(True)
        if emit:
            self.selection_changed.emit(key)

    def _on_clicked(self, key: str) -> None:
        """واکنش به کلیک کاربر."""
        self.selection_changed.emit(key)


class ChipBar(QWidget):
    """
    نوار تراشه‌های فیلتر (همه / صعودی / نزولی / …).

    برخلاف `SegmentedControl` می‌تواند چندانتخابی باشد؛ صفحهٔ بازارها از
    حالت تک‌انتخابی و صفحهٔ سیگنال‌ها از چندانتخابی استفاده می‌کند.
    """

    selection_changed = Signal(list)

    def __init__(
        self,
        options: Sequence[tuple[str, str]] | None = None,
        parent: QWidget | None = None,
        *,
        exclusive: bool = True,
    ) -> None:
        super().__init__(parent)
        self._exclusive = exclusive
        self._buttons: dict[str, QPushButton] = {}

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        set_role(self, "plain")
        if options:
            self.set_options(options)

    def set_options(self, options: Sequence[tuple[str, str]]) -> None:
        """جایگزینی تراشه‌ها."""
        for button in list(self._buttons.values()):
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()

        for key, label in options:
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            set_role(button, "chip")
            button.clicked.connect(lambda _c=False, k=key: self._on_clicked(k))
            self._layout.addWidget(button)
            self._buttons[key] = button

        if self._exclusive and self._buttons:
            next(iter(self._buttons.values())).setChecked(True)

    def set_labels(self, labels: dict[str, str]) -> None:
        """به‌روزرسانی متن‌ها هنگام تغییر زبان."""
        for key, text in labels.items():
            if key in self._buttons:
                self._buttons[key].setText(text)

    def selection(self) -> list[str]:
        """فهرست کلیدهای فعال."""
        return [key for key, button in self._buttons.items() if button.isChecked()]

    def set_selection(self, keys: Sequence[str], *, emit: bool = False) -> None:
        """تعیین انتخاب به‌صورت برنامه‌ای."""
        wanted = set(keys)
        for key, button in self._buttons.items():
            button.setChecked(key in wanted)
        if emit:
            self.selection_changed.emit(self.selection())

    def _on_clicked(self, key: str) -> None:
        """اعمال قاعدهٔ انحصار و انتشار سیگنال."""
        if self._exclusive:
            for other, button in self._buttons.items():
                button.setChecked(other == key)
        self.selection_changed.emit(self.selection())


class ToggleSwitch(QAbstractButton):
    """
    کلید کشویی روشن/خاموش با انیمیشن.

    نمونه‌سازی:
        toggle = ToggleSwitch()
        toggle.toggled.connect(handler)

    چرا به‌جای QCheckBox؟ در تصاویر مرجع، تنظیمات از کلید کشویی استفاده
    می‌کند؛ ولی رفتار و سیگنال‌ها همان `toggled` استاندارد است تا کد
    فراخوان تفاوتی حس نکند.
    """

    def __init__(self, parent: QWidget | None = None, *, width: int = 46, height: int = 24) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(width, height)
        self._offset = 0.0
        self._on_color = QColor("#22d3ee")
        self._off_color = QColor("#3a4256")
        self._knob_color = QColor("#ffffff")
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._animate)

    def get_offset(self) -> float:
        """موقعیت افقی دکمهٔ گرد (۰ تا ۱)."""
        return self._offset

    def set_offset(self, value: float) -> None:
        """تنظیم موقعیت و رسم دوباره."""
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    def apply_theme(self, theme) -> None:
        """گرفتن رنگ‌ها از پوسته."""
        colors = theme.colors
        self._on_color = QColor(colors.primary)
        self._off_color = QColor(colors.border_strong)
        self._knob_color = QColor(colors.surface if theme.is_dark else "#ffffff")
        self.update()

    def _animate(self, checked: bool) -> None:
        """اجرای انیمیشن جابه‌جایی."""
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - نام Qt
        """تنظیم وضعیت و همگام‌سازی فوری موقعیت دکمه."""
        super().setChecked(checked)
        self._offset = 1.0 if checked else 0.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم شیار و دکمهٔ گرد."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        radius = self.height() / 2
        track = QColor(self._on_color if self.isChecked() else self._off_color)
        if not self.isEnabled():
            track.setAlpha(110)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(self.rect(), radius, radius)

        knob_d = self.height() - 6
        travel = self.width() - knob_d - 6
        x = 3 + travel * self._offset
        painter.setBrush(self._knob_color)
        painter.drawEllipse(int(x), 3, knob_d, knob_d)
        painter.end()

    def sizeHint(self) -> QSize:  # noqa: N802 - نام Qt
        """اندازهٔ پیشنهادی ثابت."""
        return QSize(self.width(), self.height())


class StatCard(QFrame):
    """
    کارت آمار: عنوان، مقدار بزرگ، تغییر درصدی و اسپارک‌لاین.

    نمونه‌سازی:
        card = StatCard()
        card.set_data(title="ارزش کل", value="۱۲٬۴۵۰$", delta=2.4, series=[...])
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        icon: str = "",
        show_sparkline: bool = True,
    ) -> None:
        super().__init__(parent)
        set_role(self, "card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.icon_label = QLabel(icon, self)
        self.icon_label.setVisible(bool(icon))
        self.title_label = QLabel("", self)
        set_role(self.title_label, "muted")
        header.addWidget(self.icon_label)
        header.addWidget(self.title_label)
        header.addStretch(1)
        self.delta_label = QLabel("", self)
        set_role(self.delta_label, "chip_up")
        self.delta_label.setVisible(False)
        header.addWidget(self.delta_label)
        layout.addLayout(header)

        self.value_label = QLabel("—", self)
        set_role(self.value_label, "metric")
        layout.addWidget(self.value_label)

        self.caption_label = QLabel("", self)
        set_role(self.caption_label, "faint")
        self.caption_label.setVisible(False)
        layout.addWidget(self.caption_label)

        self.sparkline = Sparkline(self, width=140, height=32)
        self.sparkline.setVisible(show_sparkline)
        layout.addWidget(self.sparkline)

    def set_data(
        self,
        *,
        title: str | None = None,
        value: str | None = None,
        delta: float | None = None,
        delta_text: str | None = None,
        caption: str | None = None,
        series: Sequence[float] | None = None,
        icon: str | None = None,
    ) -> None:
        """
        به‌روزرسانی محتوای کارت.

        هر آرگومان `None` یعنی «تغییر نکن»، بنابراین می‌توان فقط یک بخش
        را تازه کرد بدون آنکه بقیه پاک شود.
        """
        if title is not None:
            self.title_label.setText(title)
        if value is not None:
            self.value_label.setText(value)
        if icon is not None:
            self.icon_label.setText(icon)
            self.icon_label.setVisible(bool(icon))
        if caption is not None:
            self.caption_label.setText(caption)
            self.caption_label.setVisible(bool(caption))
        if delta is not None or delta_text is not None:
            # نشانگر چپ‌به‌راست تا علامت + یا − در چیدمان راست‌به‌چپ جابه‌جا نشود
            text = delta_text if delta_text is not None else f"\u200e{delta:+.2f}%"
            self.delta_label.setText(text)
            self.delta_label.setVisible(bool(text))
            if delta is not None:
                set_role(self.delta_label, "chip_up" if delta >= 0 else "chip_down")
        if series is not None:
            self.sparkline.set_values(series)
            self.sparkline.setVisible(True)

    def apply_theme(self, theme) -> None:
        """انتقال پوسته به اسپارک‌لاین درونی."""
        self.sparkline.apply_theme(theme)


class TickerStrip(QFrame):
    """
    نوار افقی قیمت‌های زنده در بالای داشبورد.

    داده‌ها از همان سرویس بازار می‌آیند؛ این ویجت فقط نمایش‌دهنده است.
    """

    symbol_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "stat")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(14, 8, 14, 8)
        self._layout.setSpacing(18)
        self._layout.addStretch(1)
        self.setFixedHeight(44)

    def set_items(self, items: Sequence[dict]) -> None:
        """
        تنظیم آیتم‌ها.

        هر آیتم: `{"symbol": str, "price": str, "change": float}`.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for entry in items:
            cell = QWidget(self)
            row = QHBoxLayout(cell)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)

            symbol = QLabel(str(entry.get("symbol", "")), cell)
            symbol.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            symbol.setStyleSheet("font-weight: 700;")

            price = QLabel(str(entry.get("price", "—")), cell)
            price.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            set_role(price, "muted")

            change = float(entry.get("change") or 0.0)
            delta = QLabel(f"\u200e{change:+.2f}%", cell)
            delta.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            set_role(delta, "bullish" if change >= 0 else "bearish")

            row.addWidget(symbol)
            row.addWidget(price)
            row.addWidget(delta)

            # کلیک روی هر قلم، جزئیات همان ارز را باز می‌کند
            name = str(entry.get("symbol", ""))
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
            cell.mousePressEvent = (  # type: ignore[method-assign]
                lambda _event, value=name: self.symbol_clicked.emit(value)
            )
            self._layout.addWidget(cell)

        self._layout.addStretch(1)

    def apply_theme(self, theme) -> None:  # noqa: ARG002
        """
        هماهنگی با پوسته.

        رنگ‌های این نوار از نقش‌های QSS (`bullish`/`bearish`) می‌آیند و
        خودکار عوض می‌شوند؛ این متد فقط برای یکدستی رابط با بقیهٔ
        ویجت‌های نقاشی‌شده وجود دارد.
        """
        return None


class Pagination(QWidget):
    """
    نوار صفحه‌بندی جدول‌ها (تاریخچهٔ معاملات).

    سیگنال: `page_changed(int)` با شمارهٔ صفحهٔ جدید (از ۱).
    """

    page_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._page = 1
        self._pages = 1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.prev_button = QPushButton("‹", self)
        self.next_button = QPushButton("›", self)
        for button in (self.prev_button, self.next_button):
            set_role(button, "icon")
            button.setFixedWidth(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.info_label = QLabel("", self)
        set_role(self.info_label, "muted")

        layout.addStretch(1)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.info_label)
        layout.addWidget(self.next_button)

        self.prev_button.clicked.connect(lambda: self.set_page(self._page - 1))
        self.next_button.clicked.connect(lambda: self.set_page(self._page + 1))

    def configure(self, *, page: int, pages: int, text: str = "") -> None:
        """تنظیم وضعیت بدون انتشار سیگنال (پس از بارگذاری داده)."""
        self._pages = max(1, int(pages))
        self._page = max(1, min(self._pages, int(page)))
        self.info_label.setText(text or f"{self._page} / {self._pages}")
        self.prev_button.setEnabled(self._page > 1)
        self.next_button.setEnabled(self._page < self._pages)

    def page(self) -> int:
        """شمارهٔ صفحهٔ فعلی."""
        return self._page

    def set_page(self, page: int) -> None:
        """رفتن به صفحهٔ خواسته‌شده و انتشار سیگنال در صورت تغییر."""
        target = max(1, min(self._pages, int(page)))
        if target == self._page:
            return
        self._page = target
        self.configure(page=target, pages=self._pages)
        self.page_changed.emit(target)


class Toast(QFrame):
    """
    اعلان شناور کوتاه‌مدت روی پنجرهٔ اصلی.

    نمونه‌سازی:
        Toast.show_message(window, "ذخیره شد", level="success")

    چرا نه QMessageBox؟ پیام موفقیت نباید جریان کار کاربر را قطع کند.
    """

    _LEVEL_ROLE = {
        "success": "chip_up",
        "error": "chip_down",
        "warning": "chip_warn",
        "info": "chip_info",
    }

    def __init__(self, parent: QWidget, message: str, *, level: str = "info") -> None:
        super().__init__(parent)
        set_role(self, "card")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        icon = {"success": "✓", "error": "✕", "warning": "!", "info": "i"}.get(level, "i")
        badge = QLabel(icon, self)
        set_role(badge, self._LEVEL_ROLE.get(level, "chip_info"))
        badge.setFixedWidth(26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(message, self)
        label.setWordWrap(True)

        layout.addWidget(badge)
        layout.addWidget(label, 1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

    @classmethod
    def show_message(
        cls, parent: QWidget, message: str, *, level: str = "info", timeout: int = 3200
    ) -> "Toast":
        """نمایش یک اعلان و حذف خودکار آن پس از مهلت تعیین‌شده."""
        toast = cls(parent, message, level=level)
        toast.adjustSize()
        width = min(420, max(240, toast.sizeHint().width()))
        toast.setFixedWidth(width)
        toast.move(
            max(12, (parent.width() - width) // 2),
            max(12, parent.height() - toast.sizeHint().height() - 70),
        )
        toast.show()
        toast.raise_()
        QTimer.singleShot(timeout, toast.deleteLater)
        return toast


class StatusDot(QLabel):
    """
    نقطهٔ رنگی وضعیت (متصل/قطع/در حال اتصال).

    رنگ از پوسته می‌آید تا در همهٔ پوسته‌ها خوانا بماند.
    """

    def __init__(self, parent: QWidget | None = None, *, size: int = 9) -> None:
        super().__init__(parent)
        self._size = size
        self._color = QColor("#94a3b8")
        self.setFixedSize(size + 4, size + 4)

    def set_status(self, color: str) -> None:
        """تنظیم رنگ نقطه با کد رنگ."""
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم دایرهٔ رنگی با هالهٔ ملایم."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        halo = QColor(self._color)
        halo.setAlpha(60)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(0, 0, self._size + 4, self._size + 4)
        painter.setBrush(self._color)
        painter.drawEllipse(2, 2, self._size, self._size)
        painter.end()


class EmptyState(QWidget):
    """
    نمای «داده‌ای نیست» با نماد، عنوان، توضیح و دکمهٔ اختیاری.

    برای حالت‌های خالی/خطا/آفلاین در همهٔ صفحه‌ها استفاده می‌شود تا
    تجربهٔ یکدستی وجود داشته باشد.
    """

    action_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel("", self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 34px;")

        self.title_label = QLabel("", self)
        set_role(self.title_label, "subtitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.detail_label = QLabel("", self)
        set_role(self.detail_label, "muted")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)

        self.action_button = QPushButton("", self)
        set_role(self.action_button, "primary")
        self.action_button.setVisible(False)
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.clicked.connect(self.action_clicked)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignCenter)

    def configure(
        self,
        *,
        icon: str = "",
        title: str = "",
        detail: str = "",
        action: str = "",
    ) -> None:
        """تنظیم محتوای حالت خالی."""
        self.icon_label.setText(icon)
        self.icon_label.setVisible(bool(icon))
        self.title_label.setText(title)
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))
        self.action_button.setText(action)
        self.action_button.setVisible(bool(action))


__all__ = [
    "ChipBar",
    "EmptyState",
    "Pagination",
    "SegmentedControl",
    "StatCard",
    "StatusDot",
    "TickerStrip",
    "Toast",
    "ToggleSwitch",
    "set_role",
]
