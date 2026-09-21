"""
سلول «روند» جدول بازارها.

کاربر گفت: «در قسمت بازار روندها مشخص نیست. روند هم به صورت نمودار خطی
هم به صورت فارسی بنویسه صعودی و نزولی، رنگ هم مشخص بشه که سبز یا قرمز
است».

پیش‌تر این ستون فقط یک نمودار کوچک بود و آن هم وقتی داده نداشت خالی
می‌ماند؛ در عمل کاربر یک ستون سفید می‌دید. حالا هر سلول سه چیز دارد:

    ۱) نمودار خطی کوچک (اگر تاریخچه موجود باشد)
    ۲) برچسب فارسی «صعودی» / «نزولی» / «خنثی»
    ۳) رنگ سبز یا قرمز که از پوستهٔ جاری می‌آید، نه رنگ سخت‌کدشده

اگر تاریخچهٔ قیمت نرسد، باز هم برچسب و رنگ نمایش داده می‌شوند تا ستون
هرگز خالی نماند.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from ui.widgets.charts_mini import Sparkline

#: آستانهٔ بی‌طرفی. تغییر کمتر از این مقدار «خنثی» است، نه صعودی/نزولی.
NEUTRAL_THRESHOLD = 0.05


class TrendCell(QWidget):
    """
    نمایش روند یک نماد: نمودار + متن فارسی + رنگ.

    نمونه:
        cell = TrendCell(translator)
        cell.set_trend(2.31, history=[100.0, 101.2, 103.0])
    """

    def __init__(self, translator, parent: QWidget | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.tr_ = translator
        self._theme = None
        self._direction = 0

        layout = QHBoxLayout(self)
        # سلول جدول جای تنگی است؛ حاشیهٔ کم، ولی نه چسبیده به لبه
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        self.spark = Sparkline(width=56, height=22)
        layout.addWidget(self.spark)

        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # بدون کمینه‌پهنا، «صعودی» در ستون تنگ روی نمودار می‌افتاد
        self.label.setMinimumWidth(74)
        self.label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.label, 1)

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def set_trend(self, change_percent: float, history: Sequence[float] | None = None) -> None:
        """
        تعیین جهت روند و به‌روزرسانی هر سه بخش سلول.

        `change_percent` درصد تغییر ۲۴ ساعته و `history` تاریخچهٔ قیمت
        برای نمودار است. نبودن تاریخچه فقط نمودار را پنهان می‌کند؛ متن و
        رنگ سر جای خود می‌مانند.
        """
        try:
            change = float(change_percent or 0.0)
        except (TypeError, ValueError):
            change = 0.0

        if change > NEUTRAL_THRESHOLD:
            self._direction = 1
            key, color_name = "markets.trend_up", "success"
        elif change < -NEUTRAL_THRESHOLD:
            self._direction = -1
            key, color_name = "markets.trend_down", "danger"
        else:
            self._direction = 0
            key, color_name = "markets.trend_flat", "text_muted"

        # پیکان جهت. نشانگر چپ‌به‌راست لازم نیست چون خود متن فارسی است و
        # پیکان پیش از آن می‌آید.
        arrow = "▲" if self._direction > 0 else ("▼" if self._direction < 0 else "—")
        self.label.setText(f"{arrow} {self.tr_.tr(key)}")

        values = [float(v) for v in (history or []) if isinstance(v, (int, float))]
        if values:
            self.spark.show()
            self.spark.set_values(values, color_name if color_name != "text_muted" else "neutral")
        else:
            # بدون داده، نمودار خالیِ گمراه‌کننده نشان نمی‌دهیم
            self.spark.hide()

        self._apply_color(color_name)

    def _apply_color(self, color_name: str) -> None:
        """رنگ‌آمیزی متن بر پایهٔ پوستهٔ جاری."""
        color = "#94a3b8"
        if self._theme is not None:
            colors = getattr(self._theme, "colors", None)
            if colors is not None:
                color = getattr(colors, color_name, None) or color
        self.label.setStyleSheet(f"color: {color}; font-weight: 600;")

    # ------------------------------------------------------------------
    # پوسته
    # ------------------------------------------------------------------
    def apply_theme(self, theme) -> None:  # type: ignore[no-untyped-def]
        """هم‌رنگ شدن با پوستهٔ جاری."""
        self._theme = theme
        self.spark.apply_theme(theme)
        name = (
            "success"
            if self._direction > 0
            else ("danger" if self._direction < 0 else "text_muted")
        )
        self._apply_color(name)

    def retranslate(self, translator) -> None:  # type: ignore[no-untyped-def]
        """به‌روزرسانی متن پس از تغییر زبان."""
        self.tr_ = translator


__all__ = ["TrendCell", "NEUTRAL_THRESHOLD"]
