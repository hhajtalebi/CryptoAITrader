"""
مدل LSTM کوچک با PyTorch — اختیاری و سبک.

چرا LSTM این‌قدر کوچک است؟
    قانون ۸: مدل پیچیده باید «مستنداً» بهتر باشد، نه پرزرق‌وبرق. با
    دادهٔ چندصدرَفیچری، شبکهٔ بزرگ فقط نویز را حفظ می‌کند. پیکربندی
    عمداً حداقلی است: یک لایه LSTM با ۲۴ واحد پنهان + سر خطی.

ورودی توالی‌ای است — نه بردار تکی:
    هر نمونه = L ردیف متوالیِ فیچر (پنجرهٔ زمانی). این تنها شکل
    درستِ استفاده از LSTM است؛ بردار تکی، MLP با نام اشتباه است.

    آموزش با نرمال‌سازی z از خودِ پنجرهٔ آموزش، seed ثابت (تکرارپذیری)
    و سقف epoch. torch نبودن = unavailable صادقانه.
"""

from __future__ import annotations

import math
from typing import Any

from app.logging import get_logger
from signals.prediction.models.base import ForecastModel, ModelOutput

logger = get_logger(__name__)

#: طول پنجرهٔ توالی ورودی.
SEQUENCE_LENGTH = 16

#: ابعاد آموزش.
HIDDEN_SIZE = 24
EPOCHS = 40
BATCH_SIZE = 64
LEARNING_RATE = 0.01
SEED = 42

#: کمینهٔ نمونهٔ آموزشی.
MIN_TRAIN_SAMPLES = 200


class LSTMModel(ForecastModel):
    """پیش‌بینی جهت با توالی فیچرها."""

    name = "lstm"

    def __init__(self) -> None:
        self._model: Any = None
        self._means: list[float] = []
        self._stds: list[float] = []
        self._feature_count = 0
        #: تاریخچهٔ ردیف‌ها برای پنجره‌سازی در پیش‌بینی لحظه‌ای.
        self._history: list[list[float]] = []

    def is_available(self) -> bool:
        """آیا torch نصب است؟ (بدون import واقعی — find_spec)"""
        from importlib.util import find_spec  # noqa: PLC0415

        return find_spec("torch") is not None

    def fit(
        self, times: list[int], rows: list[list[float]], labels: list[int | None]
    ) -> "LSTMModel":
        """ساخت توالی‌ها و آموزش سبک."""
        if not self.is_available():
            return self

        indexed = [
            (i, row, label)
            for i, (row, label) in enumerate(zip(rows, labels, strict=False))
            if label is not None
        ]
        if len(indexed) < MIN_TRAIN_SAMPLES:
            return self

        import torch
        import torch.nn as nn

        torch.manual_seed(SEED)

        feature_count = len(indexed[0][1])
        sequences: list[list[list[float]]] = []
        targets: list[int] = []
        for i, row, label in indexed:
            start = i - SEQUENCE_LENGTH + 1
            if start < 0:
                continue
            window = rows[start:i + 1]
            sequences.append([list(r) for r in window])
            targets.append(int(label))
        if len(sequences) < MIN_TRAIN_SAMPLES or len(set(targets)) < 2:
            return self

        # نرمال‌سازی از کل مجموعهٔ آموزش
        flat = [row for _, row, _ in indexed]
        self._means = [sum(col) / len(col) for col in zip(*flat, strict=False)]
        self._stds = []
        for index in range(feature_count):
            column = [row[index] for row in flat]
            std = _std(column)
            self._stds.append(std if std > 1e-9 else 1.0)
        self._feature_count = feature_count

        def normalized(window: list[list[float]]) -> list[list[float]]:
            return [
                [
                    (row[c] - self._means[c]) / self._stds[c]
                    for c in range(feature_count)
                ]
                for row in window
            ]

        x = torch.tensor([normalized(seq) for seq in sequences], dtype=torch.float32)
        y = torch.tensor(targets, dtype=torch.float32)

        class _Net(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.lstm = nn.LSTM(feature_count, HIDDEN_SIZE, batch_first=True)
                self.head = nn.Linear(HIDDEN_SIZE, 1)

            def forward(self, batch: Any) -> Any:
                out, _ = self.lstm(batch)
                return self.head(out[:, -1, :]).squeeze(-1)

        model = _Net()
        optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)
        loss_fn = nn.BCEWithLogitsLoss()

        model.train()
        for _epoch in range(EPOCHS):
            for start in range(0, len(x), BATCH_SIZE):
                batch_x = x[start:start + BATCH_SIZE]
                batch_y = y[start:start + BATCH_SIZE]
                optimizer.zero_grad()
                logits = model(batch_x)
                loss = loss_fn(logits, batch_y)
                loss.backward()
                optimizer.step()

        model.eval()
        self._model = model
        # پنجرهٔ پیش‌بینی لحظه‌ای با انتهای آموزش شروع می‌شود
        self._history = [list(r) for r in rows[-SEQUENCE_LENGTH:]]
        return self

    def remember(self, row: list[float]) -> None:
        """ثبت ردیف تازه در پنجرهٔ زمانی — پیش‌شرط predict لحظه‌ای."""
        self._history.append(list(row))
        if len(self._history) > SEQUENCE_LENGTH * 4:
            self._history = self._history[-SEQUENCE_LENGTH * 2:]

    def predict(self, row: list[float]) -> ModelOutput:
        """پیش‌بینی از آخرین پنجرهٔ به‌یادسپرده + ردیف فعلی."""
        if self._model is None or not row or self._feature_count == 0:
            return ModelOutput(self.name, 0.5, False, "not_fitted_or_unavailable")

        window = self._history[-(SEQUENCE_LENGTH - 1):] + [list(row)]
        if len(window) < SEQUENCE_LENGTH:
            return ModelOutput(self.name, 0.5, False, "insufficient_sequence")

        import torch

        sequence = [
            [
                (value - self._means[index]) / self._stds[index]
                for index, value in enumerate(row_window[: self._feature_count])
            ]
            for row_window in window
        ]
        tensor = torch.tensor([sequence], dtype=torch.float32)
        with torch.no_grad():
            logit = float(self._model(tensor)[0])
        probability = 1.0 / (1.0 + math.exp(-logit))
        if not math.isfinite(probability):
            return ModelOutput(self.name, 0.5, False, "invalid_probability")
        return ModelOutput(self.name, probability, True, "")


def _std(values: list[float]) -> float:
    """انحراف معیار نمونه‌ای."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
