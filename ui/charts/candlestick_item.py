"""
آیتم نمودار شمعی برای pyqtgraph.

pyqtgraph به‌صورت پیش‌فرض نمودار شمعی ندارد؛ این کلاس با ترسیم یک‌باره
همه شمع‌ها روی یک `QPicture` آن را می‌سازد. دلیل این روش کارایی است:
اگر هر شمع یک آیتم گرافیکی جدا باشد، با چند صد کندل نمودار کند می‌شود.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPicture
from PySide6.QtWidgets import QGraphicsItem
from pyqtgraph import GraphicsObject

from app.core.models import Candle


class CandlestickItem(GraphicsObject):
    """
    آیتم ترسیم شمع‌های ژاپنی.

    مثال:
        item = CandlestickItem(candles, interval_seconds=3600)
        plot.addItem(item)
    """

    def __init__(
        self,
        candles: list[Candle] | None = None,
        interval_seconds: int = 3600,
        bullish_color: str = "#22c55e",
        bearish_color: str = "#ef4444",
    ) -> None:
        super().__init__()
        self._candles: list[Candle] = list(candles or [])
        self._interval = max(1, int(interval_seconds))
        self._bullish = QColor(bullish_color)
        self._bearish = QColor(bearish_color)
        self._picture = QPicture()
        self._generate_picture()

    # ------------------------------------------------------------------
    # داده
    # ------------------------------------------------------------------
    def set_data(self, candles: list[Candle], interval_seconds: int | None = None) -> None:
        """جایگزینی داده و بازترسیم نمودار."""
        self._candles = list(candles or [])
        if interval_seconds:
            self._interval = max(1, int(interval_seconds))
        self._generate_picture()
        self.informViewBoundsChanged()
        self.update()

    def set_colors(self, bullish: str, bearish: str) -> None:
        """به‌روزرسانی رنگ‌ها هنگام تغییر پوسته."""
        self._bullish = QColor(bullish)
        self._bearish = QColor(bearish)
        self._generate_picture()
        self.update()

    @property
    def candles(self) -> list[Candle]:
        """کندل‌های جاری."""
        return self._candles

    # ------------------------------------------------------------------
    # ترسیم
    # ------------------------------------------------------------------
    def _generate_picture(self) -> None:
        """
        ترسیم همه شمع‌ها روی یک تصویر برداری.

        عرض بدنه ۷۰٪ فاصله زمانی گرفته می‌شود تا بین شمع‌ها فاصله بماند.
        """
        self._picture = QPicture()
        if not self._candles:
            return

        painter = QPainter(self._picture)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        half_width = self._interval * 0.35

        try:
            for candle in self._candles:
                color = self._bullish if candle.close >= candle.open else self._bearish
                pen = painter.pen()
                pen.setColor(color)
                pen.setWidth(0)  # قلم کیهانی: ضخامت ثابت مستقل از بزرگ‌نمایی
                painter.setPen(pen)
                painter.setBrush(color)

                x = float(candle.timestamp)
                # فتیله
                painter.drawLine(QRectF(x, candle.low, 0, candle.high - candle.low).topLeft(),
                                 QRectF(x, candle.low, 0, candle.high - candle.low).bottomLeft())
                # بدنه — کندل دوجی (باز و بسته برابر) به خط تبدیل می‌شود
                body_height = candle.close - candle.open
                painter.drawRect(QRectF(x - half_width, candle.open, half_width * 2, body_height))
        finally:
            painter.end()

    def paint(self, painter: QPainter, *args: object) -> None:  # noqa: D102 - Qt API
        painter.drawPicture(0, 0, self._picture)

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        """محدوده داده برای بزرگ‌نمایی خودکار."""
        if not self._candles:
            return QRectF()
        first = self._candles[0].timestamp - self._interval
        last = self._candles[-1].timestamp + self._interval
        low = min(candle.low for candle in self._candles)
        high = max(candle.high for candle in self._candles)
        return QRectF(first, low, last - first, high - low)

    def shape(self) -> QGraphicsItem:  # type: ignore[override]  # noqa: D102 - Qt API
        return super().shape()
