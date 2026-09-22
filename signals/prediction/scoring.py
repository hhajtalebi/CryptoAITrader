"""
امتیازدهی و کالیبراسیون — خواسته‌های ۲۴ و ۲۵، فاز ۹.

چرا این فایل وجود دارد؟
    خواستهٔ ۲۵ صریح است: «Probability نباید صرفاً یک عدد تزئینی باشد.
    اگر سیستم می‌گوید ۷۰٪، در بلندمدت باید ~۷۰٪ مواقع مشابه رخ داده
    باشند.» دو ابزار استاندارد سنجش این ادعا:
    • Brier score — کمتر بهتر؛ ۰٫۲۵ یعنی شانس، ۰ یعنی قطعیتِ درست.
    • منحنی/سطل‌های کالیبراسیون — در هر سطل احتمالی، نرخ رخداد واقعی.

    همهٔ محاسبات از رکوردهای **حل‌شده** می‌آیند؛ پیش‌بینی باز هرگز
    شمرده نمی‌شود (آمارِ دروغ ممنوع).
"""

from __future__ import annotations

from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: پهنای سطل‌های کالیبراسیون (درصد).
BUCKET_WIDTH = 10

#: کمینهٔ نمونهٔ هر سطل برای قضاوت معنادار.
MIN_BUCKET_SAMPLES = 5


def brier_score(records: list[Any]) -> float | None:
    """
    Brier score جهت‌ها: (p - outcome)² که p احتمال اعلامی صعود است.

    outcome = ۱ اگر قیمت بالاتر رفت (جهت bullish درست) وگرنه ۰ — برای
    پیش‌بینی‌های bearish احتمال معکوس می‌شود تا همه با هم قابل‌مقایسه
    باشند.
    """
    total = 0.0
    count = 0
    for record in records:
        if getattr(record, "actual_price", None) is None or record.last_price <= 0:
            continue
        went_up = record.actual_price > record.last_price
        if record.direction == "bearish":
            probability = (100 - record.probability) / 100.0
        else:
            probability = record.probability / 100.0
        total += (probability - (1.0 if went_up else 0.0)) ** 2
        count += 1
    return total / count if count else None


def calibration_buckets(records: list[Any]) -> dict[str, dict[str, Any]]:
    """سطل‌های ۱۰درصدی: احتمال اعلامی در برابر نرخ رخداد واقعی."""
    buckets: dict[int, list[int]] = {}
    for record in records:
        if getattr(record, "actual_price", None) is None or record.last_price <= 0:
            continue
        went_up = record.actual_price > record.last_price
        if record.direction == "bearish":
            # به «احتمال صعود» معکوس می‌کنیم تا سطل‌ها هم‌معنا باشند
            probability = 100 - record.probability
        else:
            probability = record.probability
        index = min(9, int(probability // BUCKET_WIDTH))
        buckets.setdefault(index, []).append(1 if went_up else 0)

    result: dict[str, dict[str, Any]] = {}
    for index in sorted(buckets):
        outcomes = buckets[index]
        low = index * BUCKET_WIDTH
        high = low + BUCKET_WIDTH
        hit_rate = sum(outcomes) / len(outcomes)
        result[f"{low}-{high}"] = {
            "samples": len(outcomes),
            "predicted_midpoint": low + BUCKET_WIDTH / 2,
            "actual_rate": round(hit_rate * 100, 1),
            "calibrated": (
                abs(hit_rate * 100 - (low + BUCKET_WIDTH / 2)) <= BUCKET_WIDTH
                if len(outcomes) >= MIN_BUCKET_SAMPLES
                else None
            ),
        }
    return result


def accuracy_summary(records: list[Any]) -> dict[str, Any]:
    """خلاصهٔ دقت: جهت، بازه، به تفکیک bullish/bearish/neutral."""
    resolved = [
        record for record in records if getattr(record, "actual_price", None) is not None
    ]
    if not resolved:
        return {"resolved": 0}

    def rate(values: list[bool | None]) -> float:
        real = [v for v in values if v is not None]
        return round(sum(1 for v in real if v) / len(real) * 100, 1) if real else 0.0

    by_direction: dict[str, list[bool | None]] = {}
    for record in resolved:
        by_direction.setdefault(record.direction, []).append(record.direction_correct)

    return {
        "resolved": len(resolved),
        "direction_accuracy": rate([r.direction_correct for r in resolved]),
        "range_accuracy": rate([r.range_correct for r in resolved]),
        "by_direction": {
            direction: {"samples": len(values), "accuracy": rate(values)}
            for direction, values in by_direction.items()
        },
        "brier": (lambda b: round(b, 4) if b is not None else None)(brier_score(resolved)),
    }


def model_health(records: list[Any]) -> dict[str, dict[str, Any]]:
    """
    سلامت مدل‌ها به تفکیک نام — خواستهٔ ۴۸.

    هر رکورد، خروجی مدل‌های عضو را در ستون JSON `models` دارد؛ دقت هر
    مدل از پیش‌بینی‌های خودش محاسبه می‌شود (جهت مدل با جهت نهایی
    مقاینه نمی‌شود — هر مدل با واقعیت سنجیده می‌شود).
    """
    stats: dict[str, dict[int, int]] = {}
    for record in records:
        if getattr(record, "actual_price", None) is None or record.last_price <= 0:
            continue
        went_up = record.actual_price > record.last_price
        for entry in record.models or []:
            name = str(entry.get("name", ""))
            if not name:
                continue
            prob = float(entry.get("prob_up", 0.5))
            predicted_up = prob > 0.5
            bucket = stats.setdefault(name, {"hits": 0, "total": 0})
            bucket["total"] += 1
            if predicted_up == went_up:
                bucket["hits"] += 1

    health: dict[str, dict[str, Any]] = {}
    for name, bucket in stats.items():
        accuracy = bucket["hits"] / bucket["total"] if bucket["total"] else 0.0
        if accuracy >= 0.60:
            status = "good"
        elif accuracy >= 0.52:
            status = "stable"
        elif accuracy >= 0.45:
            status = "weak"
        else:
            status = "retraining_suggested"
        health[name] = {
            "samples": bucket["total"],
            "accuracy": round(accuracy * 100, 1),
            "status": status,
        }
    return health
