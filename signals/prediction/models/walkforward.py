"""
اعتبارسنجی غلتان (Walk-Forward Validation) — خواسته‌های ۴۱ و ۴۲.

چرا این فایل وجود دارد؟
    یک backtest ساده با تقسیم تصادفی، در سری زمانی یعنی تقلب: مدل
    «آینده» را در آموزش دیده و نمره‌اش دروغ است (قانون ۴ — Data
    Leakage). روش درست:

        آموزش تا زمان t  →  پیش‌بینی t..t+k  →  جابه‌جایی پنجره  →  تکرار

    و «گسست» (gap) به اندازهٔ افق بین آموزش و آزمون — چون برچسب‌های
    انتهای آموزش به آینده‌ای نگاه می‌کنند که نباید دیده شوند (purge).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.logging import get_logger

logger = get_logger(__name__)

#: تعداد چین‌های پیش‌فرض.
DEFAULT_FOLDS = 4


@dataclass(slots=True)
class FoldResult:
    """نتیجهٔ یک چین غلتان."""

    train_samples: int
    test_samples: int
    accuracy: float      # 0..1
    brier: float         # هرچه کمتر بهتر

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "train_samples": self.train_samples,
            "test_samples": self.test_samples,
            "accuracy": round(self.accuracy, 4),
            "brier": round(self.brier, 4),
        }


@dataclass(slots=True)
class WalkForwardResult:
    """نتیجهٔ کامل اعتبارسنجی غلتان."""

    folds: list[FoldResult] = field(default_factory=list)
    pooled_accuracy: float = 0.0
    pooled_brier: float = 0.0
    evaluations: int = 0
    note: str = ""

    @property
    def valid(self) -> bool:
        """آیا ارزیابی معنا دارد؟ (حداقل دو چین با پیش‌بینی)"""
        return self.evaluations >= 30 and len(self.folds) >= 2

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "folds": [f.to_dict() for f in self.folds],
            "pooled_accuracy": round(self.pooled_accuracy, 4),
            "pooled_brier": round(self.pooled_brier, 4),
            "evaluations": self.evaluations,
            "note": self.note,
        }


def walk_forward(
    model_factory: Callable[[], Any],
    *,
    times: list[int],
    rows: list[list[float]],
    labels: list[int | None],
    gap_seconds: int,
    folds: int = DEFAULT_FOLDS,
) -> WalkForwardResult:
    """
    اعتبارسنجی غلتان با گسست زمانی.

    پارامترها:
        model_factory: سازندهٔ مدل تازه برای هر چین (بدون نشت مدل آموزش‌دیده).
        times/rows/labels: مجموعهٔ کامل، مرتب بر اساس زمان.
        gap_seconds: گسست purge بین پایان آموزش و شروع آزمون — معمولاً
                     طول افق (چون برچسب آخرین نمونه‌های آموزش جلوتر است).
        folds: تعداد برش‌های زمانی.

    بازگشتی: WalkForwardResult. اگر داده برای هیچ چین کافی نبود،
    `valid` صادقانه False است.
    """
    result = WalkForwardResult()
    indexed = [
        (moment, row, label)
        for moment, row, label in zip(times, rows, labels, strict=False)
        if label is not None
    ]
    if len(indexed) < 100 or folds < 2:
        result.note = "insufficient_data_for_walk_forward"
        return result

    indexed.sort(key=lambda item: item[0])
    fold_size = len(indexed) // (folds + 1)
    if fold_size < 40:
        result.note = "folds_too_small"
        return result

    hits = 0
    total = 0
    brier_sum = 0.0

    for fold in range(1, folds + 1):
        split = fold * fold_size
        train = indexed[:split]
        test = indexed[split:split + fold_size]
        if not test:
            break

        # گسست: نمونه‌های آموزشی‌ای که برچسبشان به پنجرهٔ آزمون می‌رسد
        test_start = test[0][0]
        purged_train = [item for item in train if item[0] < test_start - gap_seconds]
        if len(purged_train) < 40:
            continue

        model = model_factory()
        model.fit(
            [m for m, _, _ in purged_train],
            [r for _, r, _ in purged_train],
            [l for _, _, l in purged_train],
        )

        fold_hits = 0
        fold_total = 0
        fold_brier = 0.0
        for _, row, label in test:
            output = model.predict(row)
            if not output.available:
                continue
            predicted = 1 if output.prob_up > 0.5 else 0
            fold_total += 1
            fold_brier += (output.prob_up - label) ** 2
            if predicted == label:
                fold_hits += 1

        if fold_total == 0:
            continue
        result.folds.append(
            FoldResult(
                train_samples=len(purged_train),
                test_samples=fold_total,
                accuracy=fold_hits / fold_total,
                brier=fold_brier / fold_total,
            )
        )
        hits += fold_hits
        total += fold_total
        brier_sum += fold_brier

    if total == 0:
        result.note = "no_model_produced_predictions"
        return result

    result.evaluations = total
    result.pooled_accuracy = hits / total
    result.pooled_brier = brier_sum / total
    return result
