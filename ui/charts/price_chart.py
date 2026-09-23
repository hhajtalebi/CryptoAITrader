"""
ویجت نمودار قیمت.

نمودار شمعی به‌همراه پنل حجم، خطوط میانگین متحرک، و سطوح حمایت/مقاومت.
این ویجت هیچ داده‌ای را خودش نمی‌گیرد؛ فقط آنچه را به آن می‌دهند نشان
می‌دهد. همین جدایی باعث می‌شود بدون شبکه و بدون موتور بازار هم قابل
آزمایش باشد.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.core.models import Candle, SupportResistanceLevel
from app.logging import get_logger
from localization import Translator
from market.timeframes import timeframe_seconds
from ui.charts.candlestick_item import CandlestickItem

logger = get_logger(__name__)

#: رنگ خطوط روی‌هم (میانگین‌های متحرک) به ترتیب استفاده
OVERLAY_COLORS: tuple[str, ...] = ("#3b82f6", "#f59e0b", "#a855f7", "#06b6d4")


class TimeAxis(pg.AxisItem):
    """
    محور زمان با برچسب تاریخ خوانا.

    مقدار خام روی محور، مهر زمانی یونیکس است؛ بدون این تبدیل کاربر
    عددی مثل ۱۷۵۷۳۰۰۰۰۰ می‌بیند که معنایی ندارد.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._fmt = "%m-%d %H:%M"

    def set_format(self, timeframe: str) -> None:
        """انتخاب قالب تاریخ متناسب با تایم‌فریم."""
        seconds = timeframe_seconds(timeframe) if timeframe else 3600
        self._fmt = "%Y-%m-%d" if seconds >= 86400 else "%m-%d %H:%M"

    def tickStrings(self, values: list[float], scale: float, spacing: float) -> list[str]:  # noqa: N802
        """تبدیل مهر زمانی به رشته تاریخ."""
        labels: list[str] = []
        for value in values:
            try:
                labels.append(datetime.fromtimestamp(float(value), UTC).strftime(self._fmt))
            except (ValueError, OSError, OverflowError):
                labels.append("")
        return labels


class PriceChart(QWidget):
    """
    نمودار قیمت و حجم.

    مثال:
        chart = PriceChart(translator)
        chart.set_candles(candles, "4h", symbol="BTC/USDT")
        chart.set_overlay("EMA(21)", timestamps, values)
        chart.set_levels(levels)
    """

    def __init__(
        self,
        translator: Translator,
        palette: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tr_ = translator
        self._palette = dict(palette or {})
        self._overlay_curves: dict[str, pg.PlotDataItem] = {}
        self._level_lines: list[pg.InfiniteLine] = []
        #: خطوط سیگنال (ورود/SL/TP) — جدا از سطوح، برای به‌روزرسانی مکرر
        self._signal_lines: list[pg.InfiniteLine] = []
        self._timeframe = "1h"
        self._chart_type = "candles"
        self._candles: list[Candle] = []
        self._user_zoomed = False
        self._last_price: float | None = None
        # خط‌کشی کاربر (v2.2)
        self._draw_mode = ""
        self._draw_items: list[Any] = []
        self._draw_pending: list[tuple[float, float]] = []

        pg.setConfigOptions(antialias=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._time_axis = TimeAxis(orientation="bottom")
        self._volume_axis = TimeAxis(orientation="bottom")

        self.price_plot = pg.PlotWidget(axisItems={"bottom": self._time_axis})
        self.price_plot.showGrid(x=True, y=True, alpha=0.15)
        self.price_plot.setMouseEnabled(x=True, y=True)
        self.price_plot.getAxis("left").setWidth(72)

        self.volume_plot = pg.PlotWidget(axisItems={"bottom": self._volume_axis})
        self.volume_plot.showGrid(x=True, y=True, alpha=0.15)
        self.volume_plot.setMaximumHeight(120)
        self.volume_plot.getAxis("left").setWidth(72)
        # محور زمان دو نمودار به هم قفل می‌شود تا با هم حرکت کنند
        self.volume_plot.setXLink(self.price_plot)

        self.candles_item = CandlestickItem()
        self.price_plot.addItem(self.candles_item)
        self.volume_item = pg.BarGraphItem(x=[], height=[], width=1, brush="#64748b")
        self.volume_plot.addItem(self.volume_item)

        self._legend = self.price_plot.addLegend(offset=(10, 10))
        self._crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#64748b", width=1))
        self._crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#64748b", width=1))
        self.price_plot.addItem(self._crosshair_v, ignoreBounds=True)
        self.price_plot.addItem(self._crosshair_h, ignoreBounds=True)
        self._label = pg.TextItem(anchor=(0, 1))
        self.price_plot.addItem(self._label, ignoreBounds=True)

        # --- نمودار خطی/ناحیه‌ای (جایگزین کندل) ---
        self._line_curve = pg.PlotDataItem(pen=pg.mkPen("#38bdf8", width=2))
        self._line_curve.setVisible(False)
        self.price_plot.addItem(self._line_curve)

        # --- خط قیمت زنده، مثل تریدینگ‌ویو ---
        #
        # آخرین قیمت باید همیشه روی نمودار دیده شود، نه اینکه کاربر
        # مجبور باشد نوک آخرین کندل را حدس بزند.
        self._price_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen("#f59e0b", width=1, style=Qt.PenStyle.DashLine),
        )
        self._price_line.setVisible(False)
        self.price_plot.addItem(self._price_line, ignoreBounds=True)
        self._price_tag = pg.TextItem(anchor=(0, 0.5), color="#0b1220", fill="#f59e0b")
        self._price_tag.setVisible(False)
        self.price_plot.addItem(self._price_tag, ignoreBounds=True)

        # تشخیص زوم/جابه‌جایی دستی کاربر
        self.price_plot.getViewBox().sigRangeChangedManually.connect(self._on_manual_range)

        self.price_plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        # نشانگر نقطهٔ اول خط روند + کلیک خط‌کشی (v2.2)
        self.draw_marker = pg.ScatterPlotItem(
            [], [], size=9,
            pen=pg.mkPen(None), brush=pg.mkBrush("#a78bfa"),
        )
        self.draw_marker.setVisible(False)
        self.price_plot.addItem(self.draw_marker, ignoreBounds=True)
        self.price_plot.scene().sigMouseClicked.connect(self._on_chart_clicked)

        layout.addWidget(self.price_plot, 1)
        layout.addWidget(self.volume_plot)

        self.apply_palette(self._palette)
        self.show_placeholder()

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def set_candles(self, candles: list[Candle], timeframe: str, symbol: str = "") -> None:
        """نمایش کندل‌ها و حجم متناظر."""
        if not candles:
            self.clear()
            self.show_placeholder()
            return

        self._timeframe = timeframe or self._timeframe
        interval = timeframe_seconds(self._timeframe)
        self._time_axis.set_format(self._timeframe)
        self._volume_axis.set_format(self._timeframe)

        self.candles_item.set_data(candles, interval)
        self._candles = list(candles)

        timestamps = [float(candle.timestamp) for candle in candles]
        volumes = [float(candle.volume) for candle in candles]
        colors = [
            self._palette.get("success", "#22c55e")
            if candle.close >= candle.open
            else self._palette.get("danger", "#ef4444")
            for candle in candles
        ]
        self.volume_item.setOpts(
            x=timestamps, height=volumes, width=interval * 0.7, brushes=colors, pen=None
        )

        title = f"{symbol} — {self._timeframe}" if symbol else self._timeframe
        self.price_plot.setTitle(title, color=self._palette.get("text", "#e6e9ef"), size="10pt")
        self._label.setText("")

        # نمودار خطی هم همان داده را می‌گیرد تا تعویض نوع، فوری باشد.
        closes = [float(candle.close) for candle in candles]
        self._line_curve.setData(timestamps, closes)
        self._apply_chart_type()

        # خط قیمت زنده روی آخرین بسته‌شدن
        self.set_live_price(closes[-1])

        # اگر کاربر خودش زوم کرده، دامنه را دست نمی‌زنیم.
        #
        # نمودار هر ۱۵ ثانیه تازه می‌شود؛ با `enableAutoRange` بی‌قید،
        # هر بار زوم کاربر پاک می‌شد و کار با نمودار عملاً ممکن نبود.
        if not self._user_zoomed:
            self.price_plot.enableAutoRange()
            self.volume_plot.enableAutoRange()
        logger.debug("Chart updated: %s %s (%d candles)", symbol, self._timeframe, len(candles))

    def set_overlay(self, name: str, timestamps: list[float], values: list[float | None]) -> None:
        """
        افزودن یا به‌روزرسانی یک خط روی نمودار (مثلاً میانگین متحرک).

        مقادیر `None` (دوره گرم‌شدن اندیکاتور) نادیده گرفته می‌شوند تا
        نمودار از صفر شروع نشود و مقیاس عمودی خراب نگردد.
        """
        points = [
            (float(ts), float(value))
            for ts, value in zip(timestamps, values, strict=False)
            if value is not None
        ]
        if not points:
            self.remove_overlay(name)
            return

        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        curve = self._overlay_curves.get(name)
        if curve is None:
            color = OVERLAY_COLORS[len(self._overlay_curves) % len(OVERLAY_COLORS)]
            curve = self.price_plot.plot(xs, ys, pen=pg.mkPen(color, width=2), name=name)
            self._overlay_curves[name] = curve
        else:
            curve.setData(xs, ys)

    def remove_overlay(self, name: str) -> None:
        """حذف یک خط روی نمودار."""
        curve = self._overlay_curves.pop(name, None)
        if curve is not None:
            self.price_plot.removeItem(curve)

    def set_levels(self, levels: list[SupportResistanceLevel]) -> None:
        """ترسیم سطوح حمایت و مقاومت به‌صورت خط افقی چین‌دار."""
        self._clear_levels()
        for level in levels:
            is_support = str(getattr(level, "kind", "")).lower().startswith("s")
            color = (
                self._palette.get("success", "#22c55e")
                if is_support
                else self._palette.get("danger", "#ef4444")
            )
            line = pg.InfiniteLine(
                pos=float(level.price),
                angle=0,
                movable=False,
                pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine),
                label=f"{level.price:,.4f}",
                labelOpts={"position": 0.05, "color": color, "movable": False},
            )
            self.price_plot.addItem(line, ignoreBounds=True)
            self._level_lines.append(line)

    def mark_signal(self, entry: float | None, stop_loss: float | None, targets: list[float]) -> None:
        """
        علامت‌گذاری ورود، حد ضرر و اهداف روی نمودار.

        فراخوانی مکرر مجاز است: خطوط سیگنالِ قبلی پاک می‌شوند ولی
        سطوح حمایت/مقاومت دست‌نخورده می‌مانند (ترمینال معاملهٔ خودکار
        همین را هر ثانیه صدا می‌زند).
        """
        specs: list[tuple[float, str, str]] = []
        if entry is not None:
            specs.append((entry, self.tr_.tr("signals.entry"), self._palette.get("primary", "#3b82f6")))
        if stop_loss is not None:
            specs.append((stop_loss, self.tr_.tr("signals.stop_loss"), self._palette.get("danger", "#ef4444")))
        for index, target in enumerate(targets or [], start=1):
            specs.append((target, f"TP{index}", self._palette.get("success", "#22c55e")))

        self._clear_signal_lines()
        for price, label, color in specs:
            line = pg.InfiniteLine(
                pos=float(price),
                angle=0,
                movable=False,
                pen=pg.mkPen(color, width=2),
                label=f"{label} {price:,.4f}",
                labelOpts={"position": 0.9, "color": color, "movable": False},
            )
            self.price_plot.addItem(line, ignoreBounds=True)
            self._signal_lines.append(line)

    # ------------------------------------------------------------------
    # وضعیت نمایش
    # ------------------------------------------------------------------
    def _on_manual_range(self, *_args: Any) -> None:
        """کاربر خودش زوم یا جابه‌جا کرد — از این پس دامنه را حفظ کن."""
        self._user_zoomed = True

    # ------------------------------------------------------------------
    # ابزار خط‌کشی (v2.2)
    # ------------------------------------------------------------------
    def set_draw_mode(self, mode: str) -> None:
        """
        فعال/غیرفعال کردن حالت خط‌کشی روی نمودار.

        حالت‌ها: "" (خاموش)، "hline" (خط افقی با هر کلیک)،
        "trend" (خط روند با دو کلیک). خطوطِ کشیده‌شده ملکی از
        کاربرند و با تازه‌شدن کندل پاک نمی‌شوند.
        """
        self._draw_mode = mode if mode in ("", "hline", "trend") else ""
        self._draw_pending: list[tuple[float, float]] = []
        # در حالت خط‌کشی، درگِ ماوس نباید نمودار را جابه‌جا کند
        self.price_plot.setMouseEnabled(
            x=self._draw_mode == "", y=self._draw_mode == ""
        )

    def draw_count(self) -> int:
        """شمار خطوط کشیده‌شده (برای آزمون‌ها و دکمهٔ پاک‌کردن)."""
        return len(self._draw_items)

    def clear_drawings(self) -> None:
        """پاک‌کردن همهٔ خطوط کاربر."""
        for item in self._draw_items:
            try:
                self.price_plot.removeItem(item)
            except Exception:  # noqa: BLE001 - آیتم حذف‌شده
                pass
        self._draw_items = []
        self._draw_pending = []
        self.draw_marker.setVisible(False)

    def _add_hline(self, y: float) -> None:
        """خط افقی در قیمت کلیک‌شده — مثل تریدینگ‌ویو."""
        line = pg.InfiniteLine(
            angle=0,
            movable=True,
            pen=pg.mkPen(self._palette.get("accent", "#a78bfa"), width=2),
        )
        line.setPos(y)
        self.price_plot.addItem(line, ignoreBounds=True)
        self._draw_items.append(line)

    def _add_trend(self, start: tuple[float, float], end: tuple[float, float]) -> None:
        """خط روند بین دو نقطهٔ کلیک‌شده."""
        curve = pg.PlotDataItem(
            [start[0], end[0]], [start[1], end[1]],
            pen=pg.mkPen(self._palette.get("accent", "#a78bfa"), width=2),
        )
        self.price_plot.addItem(curve, ignoreBounds=True)
        self._draw_items.append(curve)

    def _on_chart_clicked(self, position: Any) -> None:
        """کلیک در حالت خط‌کشی."""
        if not self._draw_mode:
            return
        if not self.price_plot.sceneBoundingRect().contains(position):
            return
        point = self.price_plot.getPlotItem().vb.mapSceneToView(position)
        if self._draw_mode == "hline":
            self._add_hline(float(point.y()))
            return
        # trend: دو کلیک
        self._draw_pending.append((float(point.x()), float(point.y())))
        if len(self._draw_pending) == 1:
            self.draw_marker.setPos(point)
            self.draw_marker.setVisible(True)
        else:
            self._add_trend(self._draw_pending[0], self._draw_pending[1])
            self._draw_pending = []
            self.draw_marker.setVisible(False)

    def screenshot_pixmap(self) -> Any:
        """عکس‌لحظه‌ای از کل نمودار (قیمت + حجم) به‌صورت QPixmap."""
        return self.grab()

    def reset_zoom(self) -> None:
        """بازگشت به نمای خودکار (دکمهٔ «تناسب صفحه»)."""
        self._user_zoomed = False
        self.price_plot.enableAutoRange()
        self.volume_plot.enableAutoRange()

    def set_chart_type(self, kind: str) -> None:
        """
        انتخاب نوع نمودار: `candles`، `line` یا `area`.

        تریدینگ‌ویو هر سه را دارد و کاربر همین را خواست.
        """
        self._chart_type = kind if kind in ("candles", "line", "area") else "candles"
        self._apply_chart_type()

    def _apply_chart_type(self) -> None:
        """نمایش کندل یا خط بر اساس انتخاب کاربر."""
        is_candles = self._chart_type == "candles"
        self.candles_item.setVisible(is_candles)
        self._line_curve.setVisible(not is_candles)
        if not is_candles:
            fill = "#38bdf833" if self._chart_type == "area" else None
            self._line_curve.setFillLevel(
                min((float(c.low) for c in self._candles), default=0.0)
                if self._chart_type == "area" else None
            )
            self._line_curve.setBrush(pg.mkBrush(fill) if fill else None)

    def set_live_price(self, price: float | None) -> None:
        """
        جابه‌جاکردن خط قیمت زنده و برچسب آن.

        رنگ برچسب نسبت به آخرین کندل تعیین می‌شود تا در یک نگاه معلوم
        باشد قیمت بالاتر است یا پایین‌تر.
        """
        if price is None or float(price) <= 0:
            self._price_line.setVisible(False)
            self._price_tag.setVisible(False)
            return

        value = float(price)
        self._last_price = value
        self._price_line.setPos(value)
        self._price_line.setVisible(True)

        reference = float(self._candles[-1].open) if self._candles else value
        color = (
            self._palette.get("success", "#22c55e") if value >= reference
            else self._palette.get("danger", "#ef4444")
        )
        self._price_line.setPen(pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine))
        self._price_tag.setText(f" {value:,.6g} ")
        self._price_tag.fill = pg.mkBrush(color)
        if self._candles:
            self._price_tag.setPos(float(self._candles[-1].timestamp), value)
        self._price_tag.setVisible(True)

    def clear(self) -> None:
        """پاک کردن کامل نمودار."""
        self.candles_item.set_data([])
        self.volume_item.setOpts(x=[], height=[], width=1)
        for name in list(self._overlay_curves):
            self.remove_overlay(name)
        self._clear_levels()
        self._clear_signal_lines()
        self._label.setText("")

    def show_placeholder(self) -> None:
        """پیام راهنما وقتی هنوز داده‌ای نیست."""
        self.price_plot.setTitle(
            self.tr_.tr("charts.no_data"), color=self._palette.get("text_muted", "#98a1b3"), size="10pt"
        )

    def apply_palette(self, palette: dict[str, str]) -> None:
        """هماهنگ کردن رنگ نمودار با پوسته برنامه."""
        self._palette = dict(palette or self._palette)
        background = self._palette.get("surface", "#1c212c")
        foreground = self._palette.get("text_muted", "#98a1b3")

        for plot in (self.price_plot, self.volume_plot):
            plot.setBackground(background)
            for axis_name in ("left", "bottom"):
                axis = plot.getAxis(axis_name)
                axis.setPen(pg.mkPen(foreground))
                axis.setTextPen(pg.mkPen(foreground))

        self.candles_item.set_colors(
            self._palette.get("success", "#22c55e"), self._palette.get("danger", "#ef4444")
        )

    def retranslate(self) -> None:
        """به‌روزرسانی متن‌ها هنگام تغییر زبان."""
        if not self.candles_item.candles:
            self.show_placeholder()

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    def _clear_levels(self) -> None:
        """حذف همه خطوط افقی."""
        for line in self._level_lines:
            self.price_plot.removeItem(line)
        self._level_lines.clear()

    def _clear_signal_lines(self) -> None:
        """حذف خطوط سیگنال (ورود/SL/TP) — بدون دست‌زدن به سطوح."""
        for line in self._signal_lines:
            self.price_plot.removeItem(line)
        self._signal_lines.clear()

    def _on_mouse_moved(self, position: Any) -> None:
        """
        حرکت نشانگر متقاطع و نمایش اطلاعات کندل زیر ماوس.
        """
        candles = self.candles_item.candles
        if not candles or not self.price_plot.sceneBoundingRect().contains(position):
            return

        view = self.price_plot.getPlotItem().vb
        point = view.mapSceneToView(position)
        self._crosshair_v.setPos(point.x())
        self._crosshair_h.setPos(point.y())

        # نزدیک‌ترین کندل به مکان ماوس
        nearest = min(candles, key=lambda candle: abs(candle.timestamp - point.x()))
        stamp = datetime.fromtimestamp(nearest.timestamp, UTC).strftime("%Y-%m-%d %H:%M")
        text = (
            f"{stamp}\n"
            f"O {nearest.open:,.4f}  H {nearest.high:,.4f}\n"
            f"L {nearest.low:,.4f}  C {nearest.close:,.4f}\n"
            f"V {nearest.volume:,.2f}"
        )
        self._label.setText(text, color=self._palette.get("text", "#e6e9ef"))
        self._label.setPos(point.x(), point.y())
