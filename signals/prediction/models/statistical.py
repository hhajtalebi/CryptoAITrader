"""
مدل آماری همیشه‌در دسترس — مومنتوم + بازگشت به میانگین.

چرا این مدل باید وجود داشته باشد؟
    قانون ۸ و خواستهٔ ۲۰: «اگر مدل ساده‌تر بهتر عمل کرد، همان را
    انتخاب کن.» این مدل هیچ وابستگی خارجی ندارد و همیشه در دسترس
    است؛ GBM/LSTM فقط وقتی در اعتبارسنجی غلتان از این بهتر باشند
    وزن بیشتری می‌گیرند.

منطق مدل — قابل توضیح، نه جعبهٔ سیاه:
    امتیاز = w₁·tanh(فاصله EMA نرمال)  (مومنتوم روند)
           + w₂·(۵۰−RSI)/۵۰           (بازگشت به میانگین در اشباع)
           + w₃·tanh(MACD هیستوگرام/ATR)
    در رژیم رِنج، وزن بازگشت به میانگین بیشتر و وزن مومنتوم کمتر
    می‌شود — چون در رِنج، تعقیب روند ضرر می‌دهد.
"""

from __future__ import annotations

import math

from app.logging import get_logger
from signals.prediction.models.base import ForecastModel, ModelOutput

logger = get_logger(__name__)

#: جایگاه استاندارد فیچرها در ردیف — باید با FeatureStore.matrix هم‌خوان بماند.
FEATURE_INDEX: dict[str, int] = {
    "price_returns": 0,
    "volume_change": 1,
    "rsi": 2,
    "macd": 3,
    "macd_signal": 4,
    "macd_histogram": 5,
    "atr": 6,
    "atr_percent": 7,
    "ema_distance": 8,
    "bollinger_width": 9,
    "adx": 10,
}

#: وزن‌های اجزای امتیاز.
W_MOMENTUM = 0.45
W_REVERSION = 0.35
W_FLOW = 0.20


class StatisticalModel(ForecastModel):
    """مدل آماری مومنتوم/بازگشت با نرمال‌سازی از دادهٔ آموزش."""

    name = "statistical"

    def __init__(self) -> None:
        self._feature_count = 0
        self._means: list[float] = []
        self._stds: list[float] = []
        self._fitted = False

    def is_available(self) -> bool:
        """این مدل هیچ وابستگی خارجی ندارد — همیشه در دسترس."""
        return True

    def fit(
        self, times: list[int], rows: list[list[float]], labels: list[int | None]
    ) -> "StatisticalModel":
        """آموزش = یادگیری نرمال‌سازی (میانه/پراکندگی هر فیچر)."""
        labeled = [
            (row, label) for row, label in zip(rows, labels, strict=False) if label is not None
        ]
        if not labeled:
            return self
        width = len(labeled[0][0])
        self._feature_count = width
        self._means = []
        self._stds = []
        for index in range(width):
            column = [row[index] for row, _ in labeled]
            mean = sum(column) / len(column)
            std = _std(column)
            self._means.append(mean)
            self._stds.append(std if std > 1e-9 else 1.0)
        self._fitted = True
        return self

    def predict(self, row: list[float]) -> ModelOutput:
        """امتیاز مومنتوم/بازگشت → احتمال صعودی."""
        if not self._fitted or not row:
            return ModelOutput(self.name, 0.5, False, "not_fitted")
        width = min(len(row), self._feature_count)

        def scaled(name: str) -> float:
            index = FEATURE_INDEX.get(name, -1)
            if index < 0 or index >= width:
                return 0.0
            return (row[index] - self._means[index]) / self._stds[index]

        ema_distance = row[FEATURE_INDEX["ema_distance"]] if FEATURE_INDEX["ema_distance"] < width else 0.0
        rsi = row[FEATURE_INDEX["rsi"]] if FEATURE_INDEX["rsi"] < width else 50.0
        macd_histogram = row[FEATURE_INDEX["macd_histogram"]] if FEATURE_INDEX["macd_histogram"] < width else 0.0
        atr = row[FEATURE_INDEX["atr"]] if FEATURE_INDEX["atr"] < width else 0.0
        adx = row[FEATURE_INDEX["adx"]] if FEATURE_INDEX["adx"] < width else 15.0

        # وزن‌ها بر اساس قدرت روند: بازار روندار = مومنتوم، رِنج = بازگشت
        trend_strength = max(0.0, min(1.0, (adx - 15.0) / 20.0))
        w_momentum = W_MOMENTUM * (0.5 + 0.5 * trend_strength)
        w_reversion = W_REVERSION * (1.0 - 0.5 * trend_strength)

        momentum = math.tanh(ema_distance)
        reversion = (50.0 - rsi) / 50.0
        flow = math.tanh(macd_histogram / atr) if atr > 0 else 0.0

        score = w_momentum * momentum + w_reversion * reversion + W_FLOW * flow
        prob = 0.5 + 0.4 * max(-1.0, min(1.0, score))
        return ModelOutput(self.name, prob, True, "")


def _std(values: list[float]) -> float:
    """انحراف معیار نمونه‌ای."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
