"""
نشان کاربر (آواتار) برای نوار بالایی.

پیش‌تر آواتار با متن ساخته می‌شد («  ح  حسین») که نه گرد بود، نه وضعیت
ورود را نشان می‌داد و در چیدمان راست‌به‌چپ هم فاصله‌هایش به‌هم می‌ریخت.
اینجا یک دایرهٔ واقعی رسم می‌شود با گرادیان پوسته، حرف اول نام، و یک
حلقهٔ نازک که رنگش می‌گوید کاربر وارد شده یا مهمان است.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

#: اندازهٔ پیش‌فرض دایره (پیکسل)
DEFAULT_AVATAR_SIZE = 28

#: ضخامت حلقهٔ وضعیت
RING_WIDTH = 2.0


class Avatar(QWidget):
    """
    دایرهٔ آواتار با حرف اول نام و حلقهٔ وضعیت.

    نمونه‌سازی:
        avatar = Avatar()
        avatar.set_user("حسین", authenticated=True)
        avatar.apply_theme(theme)
    """

    def __init__(self, size: int = DEFAULT_AVATAR_SIZE, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = int(size)
        self._initial = "?"
        self._authenticated = False

        # رنگ‌های اولیه تا پیش از نخستین apply_theme چیزی خالی نماند
        self._start = QColor("#22d3ee")
        self._end = QColor("#a78bfa")
        self._text_color = QColor("#0a0e1a")
        self._online = QColor("#34d399")
        self._offline = QColor("#94a3b8")
        self._ring_bg = QColor("#0a0e1a")

        self.setFixedSize(self._size, self._size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def set_user(self, display_name: str, *, authenticated: bool) -> None:
        """تعیین نام نمایشی و وضعیت ورود."""
        name = str(display_name or "").strip()
        self._initial = name[:1].upper() if name else "?"
        self._authenticated = bool(authenticated)
        self.update()

    def apply_theme(self, theme) -> None:  # type: ignore[no-untyped-def]
        """گرفتن رنگ‌ها از پوستهٔ جاری؛ هیچ رنگی سخت‌کد نمی‌شود."""
        colors = theme.colors
        self._start = QColor(colors.primary)
        self._end = QColor(getattr(colors, "accent", colors.primary))
        self._text_color = QColor(getattr(colors, "primary_text", "#ffffff"))
        self._online = QColor(getattr(colors, "success", "#34d399"))
        self._offline = QColor(getattr(colors, "text_muted", "#94a3b8"))
        self._ring_bg = QColor(getattr(colors, "background", "#0a0e1a"))
        self.update()

    # ------------------------------------------------------------------
    # ترسیم
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم دایره، حرف اول و حلقهٔ وضعیت."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(0, 0, self._size, self._size)
        inset = RING_WIDTH + 1.0
        disc = outer.adjusted(inset, inset, -inset, -inset)

        # حلقهٔ وضعیت: سبز یعنی وارد شده، خاکستری یعنی مهمان
        ring_color = self._online if self._authenticated else self._offline
        pen = QPen(ring_color, RING_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(outer.adjusted(1, 1, -1, -1))

        # دایرهٔ اصلی با گرادیان پوسته
        gradient = QLinearGradient(QPointF(disc.topLeft()), QPointF(disc.bottomRight()))
        gradient.setColorAt(0.0, self._start)
        gradient.setColorAt(1.0, self._end)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(disc)

        # حرف اول نام
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(max(7.0, self._size * 0.42))
        painter.setFont(font)
        painter.setPen(QPen(self._text_color))
        painter.drawText(disc, Qt.AlignmentFlag.AlignCenter, self._initial)

        painter.end()
