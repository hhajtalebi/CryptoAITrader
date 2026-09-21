"""
کارت انتخاب پوسته.

کاربر گفت «در تنظیمات اصلاً برای تغییر تم چیزی نیست». فهرست کشویی قبلی
ته زبانهٔ «عمومی» گم شده بود. این کارت‌ها پوسته‌ها را به شکل دیداری و
قابل کلیک نشان می‌دهند: نام پوسته، توضیح کوتاه و نمونهٔ رنگ‌ها.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.icons import icon_pixmap
from ui.themes.catalog import ThemeTokens
from ui.widgets.controls import set_role


class ThemeSwatch(QWidget):
    """نوار کوچک نمونه‌رنگ‌های یک پوسته."""

    def __init__(self, theme: ThemeTokens, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        # کاربر گفت پالت‌ها بزرگ‌اند و باید به مربع نزدیک باشند. ارتفاع
        # ثابت را با نسبت ابعاد جایگزین کردیم: مینیاتور همیشه کمی
        # پهن‌تر از مربع می‌ماند و با عرض کارت کوچک و بزرگ می‌شود.
        self.setMinimumHeight(34)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # بدون این، Qt نسبت ابعاد را نادیده می‌گیرد: `heightForWidth`
        # تعریف می‌شد ولی چیدمان هرگز صدایش نمی‌زد و مینیاتور ارتفاع
        # ثابت می‌گرفت، پس کارت‌ها در عرض‌های مختلف کشیده و له می‌شدند.
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - نام Qt
        """ارتفاع این ویجت از عرضش پیروی می‌کند."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - نام Qt
        """
        نسبت ابعاد ثابت تا کارت‌ها در هر اندازه‌ای هم‌شکل بمانند.

        نسبت عمداً پهن‌تر از مربع است: خود مینیاتور یک پنجرهٔ کوچک را
        نشان می‌دهد و پنجره پهن است؛ ولی چون نام زیرش می‌نشیند، کارت
        کامل به مربع نزدیک می‌شود — همان چیزی که خواسته شد.
        """
        return max(34, int(width * 0.52))

    def set_theme(self, theme: ThemeTokens) -> None:
        """جایگزینی پوستهٔ نمایش‌داده‌شده."""
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم یک مینیاتور از پنجرهٔ برنامه با رنگ‌های پوسته."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        colors = self._theme.colors

        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()), float(rect.width()),
                            float(rect.height()), 8.0, 8.0)
        painter.fillPath(path, QColor(colors.bg))

        # نوار کناری
        sidebar_width = rect.width() * 0.22
        sidebar = QPainterPath()
        sidebar.addRoundedRect(float(rect.x()), float(rect.y()), float(sidebar_width),
                               float(rect.height()), 8.0, 8.0)
        painter.fillPath(sidebar, QColor(colors.surface))

        # سه خط محتوا
        painter.setPen(Qt.PenStyle.NoPen)
        left = rect.x() + sidebar_width + 8
        width = rect.width() - sidebar_width - 16
        for index, ratio in enumerate((0.9, 0.65, 0.4)):
            y = rect.y() + 10 + index * 11
            bar = QPainterPath()
            bar.addRoundedRect(float(left), float(y), float(width * ratio), 5.0, 2.5, 2.5)
            color = QColor(colors.primary if index == 0 else colors.text_muted)
            if index:
                color.setAlpha(150)
            painter.fillPath(bar, color)

        # سه نقطهٔ رنگ تأکید
        for index, name in enumerate((colors.primary, colors.success, colors.danger)):
            painter.setBrush(QColor(name))
            painter.drawEllipse(
                int(rect.x() + 6), int(rect.y() + 8 + index * 11), 6, 6
            )
        painter.end()


class ThemeCard(QFrame):
    """
    یک کارت قابل کلیک برای انتخاب پوسته.

    کلیک روی کارت، سیگنال `selected(key)` را منتشر می‌کند. کارت فعال با
    ویژگی `selected` در QSS متمایز می‌شود.
    """

    selected = Signal(str)

    def __init__(
        self,
        theme: ThemeTokens,
        name: str,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._key = theme.key
        set_role(self, "card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QVBoxLayout(self)
        # حاشیه‌ها نصف شدند تا کارت جمع‌وجور شود؛ در شبکهٔ چهارستونی
        # حاشیهٔ ۱۲ پیکسلی جای خود مینیاتور را می‌خورد.
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        self.preview = ThemeSwatch(theme, self)
        layout.addWidget(self.preview)

        self.name_label = QLabel(name, self)
        set_role(self.name_label, "cardTitle")
        self.name_label.setWordWrap(False)
        layout.addWidget(self.name_label)

        # توضیح بلند، کارت کوچک را دوباره بلند می‌کرد. متن کامل به
        # tooltip رفت و خود کارت فقط نام را نشان می‌دهد.
        self.description_label = QLabel(description, self)
        set_role(self.description_label, "faint")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(False)
        layout.addWidget(self.description_label)
        self.setToolTip(description)

        self.check_label = QLabel(self)
        self.check_label.setVisible(False)
        layout.addWidget(self.check_label, 0, Qt.AlignmentFlag.AlignLeft)

        self._accent = theme.colors.primary

    @property
    def key(self) -> str:
        """کلید پوستهٔ این کارت."""
        return self._key

    def set_texts(self, name: str, description: str = "") -> None:
        """به‌روزرسانی متن‌ها هنگام تغییر زبان."""
        self.name_label.setText(name)
        self.description_label.setText(description)
        # توضیح روی خود کارت پنهان می‌ماند (کارت باید کوچک بماند) و در
        # tooltip دیده می‌شود.
        self.setToolTip(description)

    def set_selected(self, selected: bool) -> None:
        """
        علامت‌گذاری کارت فعال.

        علاوه بر ویژگی QSS، یک تیک هم نمایش داده می‌شود تا انتخاب در
        پوسته‌های کم‌کنتراست هم پیدا باشد.
        """
        self.setProperty("selected", bool(selected))
        self.check_label.setVisible(bool(selected))
        if selected:
            self.check_label.setPixmap(icon_pixmap("check", self._accent, 16))
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """کلیک روی هر جای کارت، پوسته را انتخاب می‌کند."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._key)
        super().mousePressEvent(event)
