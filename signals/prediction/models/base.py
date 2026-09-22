"""
قرارداد پایهٔ مدل‌های پیش‌بینی.

چرا این فایل وجود دارد؟
    آنسامبل باید بتواند مدل‌های آماری، GBM و LSTM را یکسان ببیند؛ بدون
    قرارداد مشترک، هر مدل API خودش را می‌ساخت و فیوژن به کد چسبندهٔ
    شرطی تبدیل می‌شد.

برچسب‌گذاری سه‌مانعی (triple-barrier-lite):
    برچسب = ۱ اگر بازدهٔ آینده از «حباب مثبت» بالاتر، ۰ اگر از حباب
    منفی پایین‌تر، و None در ناحیهٔ خنثی — ردیف‌های خنثی از آموزش حذف
    می‌شوند چون «نمی‌دانم» واقعی است و آموزش روی آن فقط نویز می‌آموزد.
    حباب از خودِ داده می‌آید (کسری از سیگمای افق)، نه عدد ثابت غیرواقعی.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ModelOutput:
    """خروجی یک مدل برای یک ردیف فیچر."""

    name: str
    prob_up: float          # 0..1 احتمال حرکت صعودی معنادار
    available: bool = True
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "name": self.name,
            "prob_up": round(self.prob_up, 4),
            "available": self.available,
            "note": self.note,
        }


class ForecastModel(ABC):
    """
    قرارداد هر مدل پیش‌بینی جهت.

    پیاده‌سازی‌ها باید:
        • `fit(times, rows, labels)` — آموزش بر ماتریس فیچر مرتب‌به‌زمان
        • `predict(row)` — احتمال صعودی برای یک ردیف
        • `is_available()` — آیا وابستگی‌هایش (torch/lgbm) موجود است
    """

    name: str = "base"

    @abstractmethod
    def fit(self, times: list[int], rows: list[list[float]], labels: list[int | None]) -> "ForecastModel":
        """آموزش؛ ردیف‌های برچسب None نادیده گرفته می‌شوند."""

    @abstractmethod
    def predict(self, row: list[float]) -> ModelOutput:
        """پیش‌بینی یک ردیف فیچر."""

    @abstractmethod
    def is_available(self) -> bool:
        """آیا وابستگی‌های بیرونی این مدل موجود است؟"""

    def predict_direction(self, row: list[float]) -> str:
        """جهت متنی از احتمال — برای راحتی مصرف‌کننده‌ها."""
        output = self.predict(row)
        if output.prob_up > 0.55:
            return "bullish"
        if output.prob_up < 0.45:
            return "bearish"
        return "neutral"


def forward_labels(
    *,
    rows: list[list[float]],
    times: list[int],
    forward_returns: list[float | None],
    deadband: float | None = None,
) -> tuple[list[list[float]], list[int], list[int], list[float | None]]:
    """
    آماده‌سازی مجموعهٔ آموزش: ردیف‌ها + برچسب‌های سه‌مانعی.

    پارامترها:
        rows            : ماتریس فیچر (هر ردیف هم‌زمان با times).
        times           : مهر «زمان دانستنی‌بودن» هر ردیف.
        forward_returns : بازدهٔ آیندهٔ متناظر با هر ردیف (None برای
                          آخرین ردیف‌ها که آینده‌شان نیامده).
        deadband        : حباب خنثی؛ None یعنی از سیگمای داده ساخته شود.

    بازگشتی: (ردیف‌های برچسب‌دار، برچسب‌ها، زمان‌ها، بازده‌های متناظر)
    """
    values = [r for r in forward_returns if r is not None and math.isfinite(r)]
    if deadband is None:
        sigma = _std(values) if values else 0.0
        deadband = 0.25 * sigma if sigma > 0 else 0.001

    kept_rows: list[list[float]] = []
    kept_labels: list[int] = []
    kept_times: list[int] = []
    kept_returns: list[float | None] = []
    for row, moment, ahead in zip(rows, times, forward_returns, strict=False):
        if ahead is None or not math.isfinite(ahead):
            continue
        if ahead > deadband:
            label = 1
        elif ahead < -deadband:
            label = 0
        else:
            continue  # ناحیهٔ خنثی — آموزش نمی‌بیند
        kept_rows.append(list(row))
        kept_labels.append(label)
        kept_times.append(moment)
        kept_returns.append(ahead)
    return kept_rows, kept_labels, kept_times, kept_returns


def _std(values: list[float]) -> float:
    """انحراف معیار نمونه‌ای."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
