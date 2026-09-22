"""
خط زمانی پیش‌بینی و «چه چیزی عوض شد؟» — خواسته‌های ۲۸ و ۲۹.

چرا این فایل وجود دارد؟
    کاربر باید ببیند نظر مدل چگونه تغییر کرده: «۳۰ دقیقه پیش: Bullish
    ۷۱٪ — الان: Bullish ۵۶٪ — علت: OI↓ حجم↓ …». بدون این، هر تغییرِ
    عدد جادویی به‌نظر می‌رسد و اعتماد خراب می‌شود.

منبع تفاوت‌ها: ستون `contributors` رکوردها (عوامل توضیح‌پذیری با
    علامت) — یعنی «چرا» هم از داده می‌آید نه از حدس LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)


def prediction_timeline(records: list[Any], *, limit: int = 40) -> list[dict[str, Any]]:
    """
    سری زمانی نظر مدل برای یک نماد/افق — قدیم به جدید.

    ورودی: رکوردهای همان نماد (هر افق). خروجی برای UI و عامل AI.
    """
    points: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda r: r.created_at)[-limit:]:
        created = record.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        points.append(
            {
                "at": created.isoformat(),
                "horizon": record.horizon,
                "direction": record.direction,
                "probability": record.probability,
                "confidence_effective": record.confidence_effective,
            }
        )
    return points


def what_changed(previous: Any, current: Any) -> dict[str, Any] | None:
    """
    تفاوت دو پیش‌بینی متوالیِ همان نماد/افق.

    پارامترها: دو رکورد (یا dict هم‌شکل). خروجی: تغییر جهت/احتمال +
    فهرست عوامل تغییرکرده با جهت جدیدشان — یا None اگر تفاوت معنادار
    نباشد.
    """
    if previous is None or current is None:
        return None

    def field(item: Any, name: str, default: Any = None) -> Any:
        if isinstance(item, dict):
            return item.get(name, default)
        return getattr(item, name, default)

    prev_direction = field(previous, "direction")
    curr_direction = field(current, "direction")
    prev_probability = int(field(previous, "probability", 0) or 0)
    curr_probability = int(field(current, "probability", 0) or 0)
    delta = curr_probability - prev_probability

    # عوامل: dict name → contribution
    def contributions(item: Any) -> dict[str, float]:
        result: dict[str, float] = {}
        for entry in field(item, "contributors", []) or []:
            name = str(entry.get("name", ""))
            value = entry.get("contribution")
            if name and isinstance(value, (int, float)):
                result[name] = float(value)
        return result

    prev_factors = contributions(previous)
    curr_factors = contributions(current)
    changed_factors: list[dict[str, Any]] = []
    for name in sorted(set(prev_factors) | set(curr_factors)):
        before = prev_factors.get(name, 0.0)
        after = curr_factors.get(name, 0.0)
        if abs(after - before) >= 0.5:  # آستانهٔ معناداری (واحد: درصد)
            changed_factors.append(
                {
                    "name": name,
                    "before": round(before, 1),
                    "after": round(after, 1),
                    "direction": "up" if after > before else "down",
                }
            )

    if prev_direction == curr_direction and abs(delta) < 5 and not changed_factors:
        return None

    def moment(item: Any) -> str:
        value = field(item, "created_at")
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.isoformat()
        return str(value or "")

    return {
        "previous": {"at": moment(previous), "direction": prev_direction,
                     "probability": prev_probability},
        "current": {"at": moment(current), "direction": curr_direction,
                    "probability": curr_probability},
        "probability_delta": delta,
        "direction_changed": prev_direction != curr_direction,
        "changed_factors": changed_factors,
    }
