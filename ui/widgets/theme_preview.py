"""
نوار پیش‌نمایش پوسته.

کاربر پیش از انتخاب، ترکیب رنگی هر پوسته را می‌بیند: پس‌زمینه، کارت،
رنگ اصلی، تأکید و رنگ‌های صعودی/نزولی.

چرا نقاشی دستی؟
    این ویجت باید رنگ‌های پوسته‌ای را نشان دهد که هنوز اعمال نشده است؛
    بنابراین نمی‌تواند از QSS برنامه رنگ بگیرد.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui.themes import get_theme
from ui.themes.tokens import ThemeTokens


class ThemePreview(QWidget):
    """
    پیش‌نمایش کوچک یک پوسته.

    نمونه‌سازی:
        preview = ThemePreview()
        preview.show_theme(ThemeManager.tokens_for("glass_dark"))
    """

    def __init__(self, parent: QWidget | None = None, *, height: int = 62) -> None:
        super().__init__(parent)
        self._theme: ThemeTokens = get_theme(None)
        self.setMinimumHeight(height)
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def show_theme(self, theme: ThemeTokens | str | None) -> None:
        """نمایش پوستهٔ خواسته‌شده."""
        self._theme = theme if isinstance(theme, ThemeTokens) else get_theme(theme)
        self.setToolTip(self._theme.name_fa)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم یک صفحهٔ کوچک نمونه با رنگ‌های پوسته."""
        colors = self._theme.colors
        metrics = self._theme.metrics
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # پس‌زمینه
        painter.setPen(QPen(QColor(colors.border), 1))
        painter.setBrush(QColor(colors.bg))
        area = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.drawRoundedRect(area, metrics.radius_md, metrics.radius_md)

        # نوار کناری
        sidebar_w = max(18.0, self.width() * 0.13)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.sidebar_bg))
        painter.drawRoundedRect(
            QRectF(2, 2, sidebar_w, self.height() - 4), metrics.radius_sm, metrics.radius_sm
        )

        # سه ردیف منو
        painter.setBrush(QColor(colors.sidebar_active_bg))
        painter.drawRoundedRect(QRectF(5, 8, sidebar_w - 6, 7), 3, 3)
        painter.setBrush(QColor(colors.sidebar_text))
        for index in range(2):
            painter.drawRoundedRect(QRectF(5, 20 + index * 11, sidebar_w - 10, 5), 2, 2)

        # کارت محتوا
        card_x = sidebar_w + 8
        card_w = self.width() - card_x - 8
        painter.setPen(QPen(QColor(colors.border), 1))
        painter.setBrush(QColor(colors.surface))
        painter.drawRoundedRect(
            QRectF(card_x, 8, card_w, self.height() - 16), metrics.radius_sm, metrics.radius_sm
        )

        # خطوط متن نمونه
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.text))
        painter.drawRoundedRect(QRectF(card_x + 7, 15, card_w * 0.42, 6), 3, 3)
        painter.setBrush(QColor(colors.text_muted))
        painter.drawRoundedRect(QRectF(card_x + 7, 26, card_w * 0.62, 4), 2, 2)

        # دکمهٔ اصلی و نشان‌های رنگی
        painter.setBrush(QColor(colors.primary))
        painter.drawRoundedRect(
            QRectF(card_x + 7, self.height() - 24, 40, 12), metrics.radius_sm, metrics.radius_sm
        )
        for index, color in enumerate((colors.accent, colors.success, colors.danger, colors.warning)):
            painter.setBrush(QColor(color))
            painter.drawEllipse(QRectF(card_x + 56 + index * 15, self.height() - 23, 10, 10))

        painter.end()


__all__ = ["ThemePreview"]
