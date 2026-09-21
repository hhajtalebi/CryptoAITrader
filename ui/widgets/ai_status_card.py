"""
کارت وضعیت هوش مصنوعی در نوار کناری.

چه چیزی نشان می‌دهد
    آیا هوش مصنوعی وصل است، کدام سرویس فعال است و کدام مدل در حال
    استفاده. پیش از این کاربر تنها وقتی می‌فهمید سرویس قطع است که یک
    تحلیل شکست می‌خورد — و آن موقع هم علتش روشن نبود.

چرا به‌روزرسانی دوره‌ای
    وضعیت سرویس می‌تواند بدون دخالت کاربر عوض شود: اولامای محلی بسته
    می‌شود، اینترنت قطع می‌شود، یا سهمیهٔ سرویس ابری تمام می‌شود. کاربر
    بازهٔ سه دقیقه‌ای خواست؛ کوتاه‌تر از آن برای سرویس ابری یعنی
    درخواست بی‌مورد و برای مدل محلی یعنی بیدارکردن بیهودهٔ مدل.

    تایمر در خود ویجت نیست — ویجت فقط نمایش‌دهنده است و
    `MainController` زمان‌بندی و فراخوانی شبکه را انجام می‌دهد. این
    مرز باعث می‌شود ویجت بدون شبکه هم قابل آزمون بماند.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.icons import icon_pixmap
from ui.widgets.controls import StatusDot, set_role

#: بازهٔ به‌روزرسانی خودکار (میلی‌ثانیه) — سه دقیقه، طبق خواستهٔ کاربر
REFRESH_INTERVAL_MS = 180_000

#: بیشترین طول نام مدل پیش از کوتاه‌شدن. نام‌های کامل مثل
#: `deepseek/deepseek-r1-distill-llama-70b:free` نوار کناری را می‌شکنند.
MAX_MODEL_CHARS = 22


def short_model_name(model: str) -> str:
    """
    کوتاه‌کردن نام مدل برای جاشدن در نوار کناری.

    بخش سازنده (`openai/`) حذف می‌شود چون نام سرویس جداگانه نمایش داده
    می‌شود و تکرارش فضای باارزش را می‌خورد. اگر باز هم بلند بود، از
    وسط کوتاه می‌شود تا هم ابتدا و هم انتهای نام (که نسخه را دارد)
    دیده شوند.
    """
    name = str(model or "").strip()
    if not name:
        return ""
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    if len(name) <= MAX_MODEL_CHARS:
        return name
    keep = (MAX_MODEL_CHARS - 1) // 2
    return f"{name[:keep]}…{name[-keep:]}"


class AIStatusCard(QFrame):
    """
    کارت مستطیلی وضعیت هوش مصنوعی.

    سه حالت دارد:
        connected    — سرویس پاسخ داد (نقطهٔ سبز)
        disconnected — سرویس در دسترس نیست (نقطهٔ قرمز)
        unknown      — هنوز بررسی نشده یا خاموش است (نقطهٔ خنثی)
    """

    #: کاربر روی کارت کلیک کرد (→ تنظیمات هوش مصنوعی)
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        set_role(self, "aiStatus")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._theme: Any = None
        self._state = "unknown"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        # --- ردیف بالا: آیکون + عنوان + نقطهٔ وضعیت ---
        header = QHBoxLayout()
        header.setSpacing(7)

        self.icon_label = QLabel(self)
        self.icon_label.setPixmap(icon_pixmap("robot", "#a78bfa", 15))
        header.addWidget(self.icon_label)

        self.title_label = QLabel("", self)
        self.title_label.setStyleSheet("font-weight: 700;")
        header.addWidget(self.title_label)
        header.addStretch(1)

        self.dot = StatusDot(self)
        header.addWidget(self.dot)
        layout.addLayout(header)

        # --- ردیف میانی: نام سرویس ---
        self.provider_label = QLabel("", self)
        # نام سرویس و مدل همیشه لاتین‌اند؛ در چیدمان راست‌به‌چپ بدون این
        # تنظیم، پرانتز و خط تیره جابه‌جا می‌شوند.
        self.provider_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        set_role(self.provider_label, "badge")
        layout.addWidget(self.provider_label)

        # --- ردیف پایین: نام مدل ---
        self.model_label = QLabel("", self)
        self.model_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        set_role(self.model_label, "faint")
        self.model_label.setWordWrap(False)
        layout.addWidget(self.model_label)

        # --- پیام وضعیت/خطا ---
        self.detail_label = QLabel("", self)
        set_role(self.detail_label, "faint")
        self.detail_label.setWordWrap(True)
        self.detail_label.setVisible(False)
        layout.addWidget(self.detail_label)

    # ------------------------------------------------------------------ API
    @property
    def state(self) -> str:
        """وضعیت فعلی: connected / disconnected / checking / unknown."""
        return self._state

    def set_status(
        self,
        *,
        state: str,
        title: str,
        provider: str = "",
        model: str = "",
        detail: str = "",
    ) -> None:
        """
        به‌روزرسانی کامل کارت.

        `state` یکی از connected / disconnected / unknown است؛ مقدار
        ناشناخته به unknown تبدیل می‌شود تا کارت هرگز بی‌رنگ نماند.
        """
        self._state = state if state in {"connected", "disconnected", "unknown"} else "unknown"
        self.title_label.setText(title)

        self.provider_label.setText(str(provider or "").upper())
        self.provider_label.setVisible(bool(provider))

        short = short_model_name(model)
        self.model_label.setText(short)
        self.model_label.setVisible(bool(short))
        # نام کامل در راهنمای ابزار، چون نمایشش کوتاه شده است
        self.model_label.setToolTip(str(model or ""))

        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))

        self._paint_dot()

    def set_checking(self, text: str) -> None:
        """
        نشان‌دادن اینکه بررسی در جریان است، بدون پاک‌کردن داده‌های قبلی.

        وضعیت به «checking» می‌رود نه اینکه روی حالت قبلی بماند: چراغ
        سبزِ کهنه در حین بررسی، به کاربر دروغ می‌گوید که سرویس همین
        الان هم وصل است.
        """
        self._state = "checking"
        self.detail_label.setText(text)
        self.detail_label.setVisible(bool(text))
        self._paint_dot()

    def apply_theme(self, theme: Any) -> None:
        """گرفتن رنگ‌ها از پوستهٔ فعال."""
        self._theme = theme
        self.icon_label.setPixmap(icon_pixmap("robot", theme.colors.accent, 15))
        self._paint_dot()

    # -------------------------------------------------------------- درونی
    def _paint_dot(self) -> None:
        """رنگ نقطهٔ وضعیت بر پایهٔ حالت و پوسته."""
        colors = getattr(self._theme, "colors", None)
        fallback = {
            "connected": "#34d399",
            "disconnected": "#fb7185",
            "checking": "#fbbf24",
            "unknown": "#94a3b8",
        }
        token = {
            "connected": "success",
            "disconnected": "danger",
            "checking": "warning",
            "unknown": "neutral",
        }[self._state]
        colour = str(getattr(colors, token, "") or fallback[self._state])
        self.dot.set_status(colour)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """کلیک روی کارت → تنظیمات هوش مصنوعی."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


__all__ = ["AIStatusCard", "MAX_MODEL_CHARS", "REFRESH_INTERVAL_MS", "short_model_name"]
