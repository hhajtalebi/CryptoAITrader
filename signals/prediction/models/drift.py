"""
تشخیص افت عملکرد مدل (Concept Drift) — فاز ۱۰، خواستهٔ ۲۶.

چرا این فایل وجود دارد؟
    بازار رفتار ثابت ندارد؛ مدتی که دیروز ۶۸٪ درست می‌گفت، امروز ممکن
    است ۵۱٪ بگوید. سیستم باید خودش بفهمد «دیگر مثل گذشته کار نمی‌کنم»
    و بازآموزی را «پیشنهاد» دهد — نه اینکه بی‌ضابطه خودش را retrain
    کند (خواستهٔ ۲۲: به‌روزرسانی منضبط).

روش:
    مقایسهٔ دقتِ نیمهٔ قدیمی و نیمهٔ تازهٔ پنجرهٔ نتایج. با نمونهٔ کم،
    «unknown» صادقانه است تا همبستگی تصادفی معنادار جلوه کند.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: وضعیت‌های تشخیص.
STATUS_OK = "ok"
STATUS_WARNING = "drift_warning"
STATUS_RETRAIN_RECOMMENDED = "retraining_recommended"
STATUS_UNKNOWN = "unknown"

#: کمینهٔ نمونه در هر نیمه برای قضاوت.
MIN_SAMPLES_PER_HALF = 15

#: افت دقت (واحد درصد) برای هشدار و برای پیشنهاد بازآموزی.
WARNING_DROP = 8.0
RETRAIN_DROP = 15.0


@dataclass(slots=True)
class DriftReport:
    """گزارش drift یک مدل/افق/نماد."""

    status: str
    previous_accuracy: float    # 0..1
    recent_accuracy: float      # 0..1
    samples: int
    drop_percent: float = 0.0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "status": self.status,
            "previous_accuracy": round(self.previous_accuracy, 4),
            "recent_accuracy": round(self.recent_accuracy, 4),
            "drop_percent": round(self.drop_percent, 2),
            "samples": self.samples,
            "note": self.note,
        }


def assess_drift(outcomes: list[bool], *, window: int = 60) -> DriftReport:
    """
    سنجش drift از توالی درست/غلط بودن پیش‌بینی‌ها (قدیم → جدید).

    پارامترها:
        outcomes: ترتیب زمانیِ «درست بودن جهت» پیش‌بینی‌های حل‌شده.
        window   : فقط آخرین این تعداد نتیجه دیده می‌شود.
    """
    recent_items = outcomes[-window:]
    half = len(recent_items) // 2
    if half < MIN_SAMPLES_PER_HALF:
        return DriftReport(
            status=STATUS_UNKNOWN,
            previous_accuracy=0.0,
            recent_accuracy=0.0,
            samples=len(recent_items),
            note="insufficient_resolved_predictions",
        )

    older = recent_items[:half]
    newer = recent_items[-half:]
    previous_accuracy = sum(1 for o in older if o) / len(older)
    recent_accuracy = sum(1 for o in newer if o) / len(newer)
    drop = (previous_accuracy - recent_accuracy) * 100.0

    if drop >= RETRAIN_DROP:
        status = STATUS_RETRAIN_RECOMMENDED
    elif drop >= WARNING_DROP:
        status = STATUS_WARNING
    else:
        status = STATUS_OK

    return DriftReport(
        status=status,
        previous_accuracy=previous_accuracy,
        recent_accuracy=recent_accuracy,
        samples=len(recent_items),
        drop_percent=drop,
    )
