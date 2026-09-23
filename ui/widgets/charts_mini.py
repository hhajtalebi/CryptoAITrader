"""
نمودارهای کوچک و بدون وابستگی: اسپارک‌لاین، حلقهٔ اطمینان، دونات و
نمودار مساحتی.

چرا نقاشی دستی به‌جای pyqtgraph؟
    این عنصرها ده‌ها بار در یک صفحه (مثلاً یک ستون جدول) تکرار می‌شوند و
    ساخت یک نمونهٔ کامل pyqtgraph برای هرکدام سنگین است. رسم مستقیم با
    QPainter سبک و سریع است.

همهٔ رنگ‌ها از پوسته می‌آیند؛ هیچ رنگ سخت‌کدشده‌ای اینجا نیست مگر
مقدار پشتیبان وقتی پوسته هنوز تنظیم نشده باشد.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui.themes import get_theme
from ui.themes.tokens import ThemeTokens


class ThemedWidget(QWidget):
    """
    پایهٔ ویجت‌های نقاشی‌شده که باید با تغییر پوسته رنگ عوض کنند.

    چون QSS روی نقاشی دستی اثر ندارد، پوسته صریحاً تزریق می‌شود.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme: ThemeTokens = get_theme(None)

    def apply_theme(self, theme: ThemeTokens | str | None) -> None:
        """اعمال پوستهٔ تازه و رسم دوباره."""
        self._theme = theme if isinstance(theme, ThemeTokens) else get_theme(theme)
        self.update()

    @property
    def theme(self) -> ThemeTokens:
        """پوستهٔ فعال این ویجت."""
        return self._theme

    def _color(self, name: str, fallback: str = "#808080") -> QColor:
        """خواندن یک رنگ از پوسته با مقدار پشتیبان."""
        return QColor(getattr(self._theme.colors, name, fallback))


class Sparkline(ThemedWidget):
    """
    نمودار خطی کوچک روند قیمت.

    نمونه‌سازی:
        spark = Sparkline()
        spark.set_values([1.0, 1.2, 0.9, 1.4])

    رنگ به‌صورت خودکار از مقایسهٔ نقطهٔ اول و آخر تعیین می‌شود مگر آنکه
    صریحاً رنگی داده شود.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        width: int = 90,
        height: int = 28,
        filled: bool = True,
        fixed: bool = True,
    ) -> None:
        """
        `fixed=False` نمودار را کشسان می‌کند (حداقل اندازه + رشد در
        چیدمان) — برای نمودارهای بزرگِ داشبورد که باید با پنجره
        هم‌اندازه شوند (v2.0). پیش‌فرض ثابت است تا مصرف‌کنندگان فعلی
        تغییری نبینند.
        """
        super().__init__(parent)
        self._values: list[float] = []
        self._color_name: str | None = None
        self._filled = filled
        if fixed:
            self.setFixedSize(width, height)
        else:
            self.setMinimumSize(width, height)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_values(self, values: Sequence[float] | None, color_name: str | None = None) -> None:
        """
        تنظیم داده‌های نمودار.

        `color_name` نام یک رنگ پوسته است (`success`/`danger`/`primary`).
        اگر داده نشود، جهت روند تعیین‌کننده است.
        """
        cleaned: list[float] = []
        for item in values or []:
            try:
                number = float(item)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                cleaned.append(number)
        self._values = cleaned
        self._color_name = color_name
        self.update()

    def clear(self) -> None:
        """پاک‌کردن نمودار."""
        self.set_values([])

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم خط روند و در صورت نیاز مساحت زیر آن."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if len(self._values) < 2:
            pen = QPen(self._color("text_faint"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            middle = self.height() / 2
            painter.drawLine(2, int(middle), self.width() - 2, int(middle))
            painter.end()
            return

        name = self._color_name
        if name is None:
            # رنگ صعود/نزول از خود پوسته می‌آید، نه یک سبز ثابت؛ هر پوسته
            # سبز و قرمز مخصوص نمودار خودش را دارد.
            name = "chart_up" if self._values[-1] >= self._values[0] else "chart_down"
        color = self._color(name)

        low = min(self._values)
        high = max(self._values)
        span = high - low or 1.0
        pad = 3.0
        usable_h = self.height() - 2 * pad
        step = (self.width() - 2 * pad) / (len(self._values) - 1)

        points = [
            QPointF(pad + index * step, pad + usable_h * (1 - (value - low) / span))
            for index, value in enumerate(self._values)
        ]

        if self._filled:
            area = QPainterPath()
            area.moveTo(points[0].x(), self.height())
            for point in points:
                area.lineTo(point)
            area.lineTo(points[-1].x(), self.height())
            area.closeSubpath()
            fill = QColor(color)
            fill.setAlpha(38)
            painter.fillPath(area, QBrush(fill))

        line = QPainterPath()
        line.moveTo(points[0])
        for point in points[1:]:
            line.lineTo(point)
        painter.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(line)
        painter.end()


class ConfidenceRing(ThemedWidget):
    """
    حلقهٔ درصدی — برای نمایش «اطمینان سیگنال».

    نمونه‌سازی:
        ring = ConfidenceRing()
        ring.set_value(78, label="۷۸٪")

    رنگ بر پایهٔ مقدار انتخاب می‌شود: بالای ۷۰ سبز، بالای ۴۰ زرد، پایین‌تر
    خاکستری. این کار خواندن سریع را ممکن می‌کند.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        size: int = 132,
        thickness: int = 11,
    ) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._label = ""
        self._caption = ""
        self._thickness = thickness
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_value(self, value: float, *, label: str = "", caption: str = "") -> None:
        """تنظیم درصد (۰ تا ۱۰۰) و متن‌های میانی."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        self._value = max(0.0, min(100.0, number))
        self._label = label or f"{int(round(self._value))}%"
        self._caption = caption
        self.update()

    def _ring_color(self) -> QColor:
        """رنگ حلقه بر پایهٔ شدت مقدار."""
        if self._value >= 70:
            return self._color("success")
        if self._value >= 40:
            return self._color("warning")
        return self._color("neutral")

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم حلقهٔ پس‌زمینه، کمان مقدار و متن میانی."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        margin = self._thickness / 2 + 2
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)

        painter.setPen(
            QPen(self._color("border"), self._thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawArc(rect, 0, 360 * 16)

        if self._value > 0:
            painter.setPen(
                QPen(
                    self._ring_color(),
                    self._thickness,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._value / 100))

        font = QFont(self.font())
        font.setPointSize(max(12, int(self.width() * 0.19)))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(self._color("text")))
        text_rect = QRectF(0, 0, self.width(), self.height())
        if self._caption:
            text_rect.adjust(0, -10, 0, -10)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self._label)

        if self._caption:
            caption_font = QFont(self.font())
            caption_font.setPointSize(max(8, int(self.width() * 0.09)))
            painter.setFont(caption_font)
            painter.setPen(QPen(self._color("text_muted")))
            painter.drawText(
                QRectF(0, self.height() / 2 + 6, self.width(), self.height() / 2 - 6),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self._caption,
            )
        painter.end()


class DonutChart(ThemedWidget):
    """
    نمودار دونات برای سهم‌بندی (مثلاً سهم خرید/فروش/انتظار).

    نمونه‌سازی:
        donut = DonutChart()
        donut.set_segments([("خرید", 42, "success"), ("فروش", 32, "danger")])
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        size: int = 168,
        thickness: int = 26,
    ) -> None:
        super().__init__(parent)
        self._segments: list[tuple[str, float, str]] = []
        self._center_label = ""
        self._thickness = thickness
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_segments(
        self, segments: Sequence[tuple[str, float, str]], *, center_label: str = ""
    ) -> None:
        """تنظیم بخش‌ها به شکل (برچسب، مقدار، نام رنگ پوسته)."""
        self._segments = [
            (str(label), max(0.0, float(value)), str(color))
            for label, value, color in segments or []
        ]
        self._center_label = center_label
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم کمان هر بخش به نسبت سهمش از کل."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        side = min(self.width(), self.height())
        margin = self._thickness / 2 + 2
        left = (self.width() - side) / 2 + margin
        top = (self.height() - side) / 2 + margin
        rect = QRectF(left, top, side - 2 * margin, side - 2 * margin)

        total = sum(value for _, value, _ in self._segments)
        if total <= 0:
            painter.setPen(QPen(self._color("border"), self._thickness))
            painter.drawArc(rect, 0, 360 * 16)
            painter.setPen(QPen(self._color("text_faint")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")
            painter.end()
            return

        start = 90 * 16
        for _, value, color_name in self._segments:
            span = -int(360 * 16 * value / total)
            painter.setPen(
                QPen(self._color(color_name), self._thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
            )
            painter.drawArc(rect, start, span)
            start += span

        if self._center_label:
            font = QFont(self.font())
            font.setPointSize(max(10, int(side * 0.11)))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(self._color("text")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._center_label)
        painter.end()


class AreaChart(ThemedWidget):
    """
    نمودار مساحتی سبک برای «رشد سرمایه» و «روند عملکرد».

    نمونه‌سازی:
        chart = AreaChart()
        chart.set_series([100, 104, 99, 112], labels=["فرو", "اسف", "فرو", "ارد"])
    """

    def __init__(self, parent: QWidget | None = None, *, height: int = 210) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self._labels: list[str] = []
        self._color_name = "primary"
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_series(
        self,
        values: Sequence[float] | None,
        *,
        labels: Sequence[str] | None = None,
        color_name: str = "primary",
    ) -> None:
        """تنظیم مقادیر، برچسب محور افقی و رنگ."""
        cleaned: list[float] = []
        for item in values or []:
            try:
                number = float(item)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                cleaned.append(number)
        self._values = cleaned
        self._labels = [str(item) for item in (labels or [])]
        self._color_name = color_name
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم خطوط راهنما، مساحت و خط روند."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pad_x, pad_top = 12.0, 14.0
        pad_bottom = 26.0 if self._labels else 14.0
        plot_w = self.width() - 2 * pad_x
        plot_h = self.height() - pad_top - pad_bottom

        painter.setPen(QPen(self._color("chart_grid"), 1))
        for index in range(5):
            y = pad_top + plot_h * index / 4
            painter.drawLine(QPointF(pad_x, y), QPointF(pad_x + plot_w, y))

        if len(self._values) < 2:
            painter.setPen(QPen(self._color("text_faint")))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
            painter.end()
            return

        low, high = min(self._values), max(self._values)
        span = (high - low) or 1.0
        step = plot_w / (len(self._values) - 1)
        points = [
            QPointF(pad_x + index * step, pad_top + plot_h * (1 - (value - low) / span))
            for index, value in enumerate(self._values)
        ]

        color = self._color(self._color_name)
        area = QPainterPath()
        area.moveTo(points[0].x(), pad_top + plot_h)
        for point in points:
            area.lineTo(point)
        area.lineTo(points[-1].x(), pad_top + plot_h)
        area.closeSubpath()

        fill = QColor(color)
        fill.setAlpha(46)
        painter.fillPath(area, QBrush(fill))

        line = QPainterPath()
        line.moveTo(points[0])
        for point in points[1:]:
            line.lineTo(point)
        painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(line)

        if self._labels:
            font = QFont(self.font())
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QPen(self._color("text_muted")))
            count = len(self._labels)
            for index, label in enumerate(self._labels):
                x = pad_x + plot_w * (index / max(1, count - 1))
                painter.drawText(
                    QRectF(x - 26, self.height() - pad_bottom + 4, 52, 18),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )
        painter.end()


__all__ = ["AreaChart", "ConfidenceRing", "DonutChart", "Sparkline", "ThemedWidget"]


class QuantileFan(ThemedWidget):
    """
    نمودار بادبزن چندک افق‌ها (v2.0 — داشبورد پیش‌بینی).

    برای هر افقِ فعال، باند P10–P90 و باند باریک‌تر P25–P75 و خط
    میانهٔ P50 رسم می‌شود؛ خط‌چین، آخرین قیمت واقعی است. همهٔ داده‌ها
    مستقیم از چندک‌های موتور پیش‌بینی می‌آیند — این ویجت هیچ چیزی
    حدس نمی‌زند؛ افق بدون چندک رسم نمی‌شود.

    نمونه‌سازی:
        fan = QuantileFan()
        fan.set_points([("15m", 63900, 64000, 64100, 64200, 64300), ...],
                       last_price=64000)
    """

    def __init__(self, parent: QWidget | None = None, *, height: int = 190) -> None:
        super().__init__(parent)
        self._points: list[tuple[str, float, float, float, float, float]] = []
        self._last_price: float = 0.0
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_points(
        self,
        points: "Sequence[tuple[str, float, float, float, float, float]] | None",
        *,
        last_price: float = 0.0,
    ) -> None:
        """
        تنظیم نقاط: (نام افق، p10، p25، p50، p75، p90).

        نقاط نامعتبر (قیمت غیرمثبت یا ترتیب نادرست) حذف می‌شوند تا
        نمودار هیچ‌وقت شکل گیج‌کننده نسازد.
        """
        cleaned: list[tuple[str, float, float, float, float, float]] = []
        for item in points or []:
            try:
                name, p10, p25, p50, p75, p90 = item
                values = [float(p10), float(p25), float(p50), float(p75), float(p90)]
            except (TypeError, ValueError):
                continue
            if any(not math.isfinite(v) or v <= 0 for v in values):
                continue
            if not (values[0] <= values[1] <= values[2] <= values[3] <= values[4]):
                continue
            cleaned.append((str(name), *values))
        self._points = cleaned
        try:
            self._last_price = float(last_price) if last_price else 0.0
        except (TypeError, ValueError):
            self._last_price = 0.0
        self.update()

    def clear(self) -> None:
        """پاک‌کردن نمودار."""
        self.set_points(None, last_price=0.0)

    def paintEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """رسم بادبزن چندک + خط آخرین قیمت."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pad = 10.0
        width = float(self.width())
        height = float(self.height())

        if len(self._points) < 1:
            pen = QPen(self._color("text_faint"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(
                int(pad), int(height / 2), int(width - pad), int(height / 2)
            )
            painter.setPen(self._color("text_faint"))
            painter.drawText(
                self.rect().adjusted(0, 0, -8, -6),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
                "—",
            )
            painter.end()
            return

        lows = [p[1] for p in self._points]
        highs = [p[5] for p in self._points]
        low = min(lows + ([self._last_price] if self._last_price > 0 else []))
        high = max(highs + ([self._last_price] if self._last_price > 0 else []))
        span = high - low or 1.0

        usable_h = height - 2 * pad
        step = (width - 2 * pad) / max(1, (len(self._points) - 1))

        def y_of(value: float) -> float:
            return pad + usable_h * (1 - (value - low) / span)

        # باند پهن P10–P90
        band = QPainterPath()
        band.moveTo(pad, y_of(self._points[0][1]))
        for index, point in enumerate(self._points):
            band.lineTo(pad + index * step, y_of(point[1]))
        for index in range(len(self._points) - 1, -1, -1):
            band.lineTo(pad + index * step, y_of(self._points[index][5]))
        band.closeSubpath()
        wide = QColor(self._color("primary"))
        wide.setAlpha(36)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(wide)
        painter.drawPath(band)

        # باند باریک P25–P75
        narrow = QPainterPath()
        narrow.moveTo(pad, y_of(self._points[0][2]))
        for index, point in enumerate(self._points):
            narrow.lineTo(pad + index * step, y_of(point[2]))
        for index in range(len(self._points) - 1, -1, -1):
            narrow.lineTo(pad + index * step, y_of(self._points[index][4]))
        narrow.closeSubpath()
        tight = QColor(self._color("primary"))
        tight.setAlpha(80)
        painter.setBrush(tight)
        painter.drawPath(narrow)

        # خط میانه P50
        median = QPainterPath()
        median.moveTo(pad, y_of(self._points[0][3]))
        for index, point in enumerate(self._points):
            median.lineTo(pad + index * step, y_of(point[3]))
        painter.setPen(QPen(self._color("primary"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(median)

        # خط آخرین قیمت
        if self._last_price > 0:
            painter.setPen(QPen(self._color("text_faint"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(pad), int(y_of(self._last_price)), int(width - pad), int(y_of(self._last_price)))

        # نام افق‌ها زیر نمودار
        painter.setPen(self._color("text_muted"))
        for index, point in enumerate(self._points):
            x = pad + index * step
            painter.drawText(
                QRectF(x - 18, height - 12, 36, 12),
                Qt.AlignmentFlag.AlignCenter,
                point[0],
            )
        painter.end()
