"""
مدیریت پلکانی اهداف سود — نسخهٔ ۲.۵.۰.

خواستهٔ کاربر: «اقدام به معامله» باید با ورود، حد ضرر و TP1 تا TP3 همان
سیگنال باز شود و با رسیدن قیمت به اهداف بسته شود. تصمیم کاربر (پرسش
۲.۵.۰): **پلکانی** —

    • TP1 → یک‌سوم حجم اولیه بسته می‌شود و حد ضرر به نقطهٔ ورود می‌رود
      (Break-even)، یعنی از این لحظه باقی معامله دیگر ضرر خالص نمی‌دهد
      (جز لغزش قیمت و کارمزد).
    • TP2 → یک‌سوم دیگر بسته می‌شود.
    • TP3 (یا آخرین هدف موجود) → باقی‌مانده بسته می‌شود.

اگر سیگنال فقط یک یا دو هدف داشته باشد، سهم‌ها بر همان تعداد پخش
می‌شوند (دو هدف: نصف/نصف؛ یک هدف: کل حجم).

این ماژول منطق خالص است — بدون Qt و پایگاه داده — تا کامل آزمون شود.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

#: بیشترین شمار اهداف مدیریت‌شده
MAX_TARGETS = 3


def clean_targets(values: Any, *, entry: float, side: str, limit: int = MAX_TARGETS) -> list[float]:
    """
    اهداف معتبر، مرتب از نزدیک به دور، حداکثر `limit` عدد.

    هدفی که در سمت اشتباه ورود باشد (مثلاً زیر ورود در خرید) کنار گذاشته
    می‌شود؛ چنین هدفی یا خطای داده است یا بلافاصله «برخورد» می‌کند.
    """
    if isinstance(values, (int, float, str)):
        values = [values]
    numbers: list[float] = []
    for raw in values or []:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0 or value != value:  # صفر یا NaN
            continue
        numbers.append(value)
    is_long = str(side or "long").lower() in ("long", "buy")
    if entry and entry > 0:
        numbers = [v for v in numbers if (v > entry if is_long else v < entry)]
    numbers = sorted(set(numbers), reverse=not is_long)
    return numbers[: max(0, int(limit))]


def stage_fractions(count: int) -> list[float]:
    """
    سهم هر هدف از حجم **اولیه**.

    سه هدف → [⅓، ⅓، باقی]؛ دو هدف → [½، باقی]؛ یک هدف → [کل].
    جمع همیشه دقیقاً ۱ است (آخرین سهم، باقی‌مانده است).
    """
    count = max(0, min(int(count), MAX_TARGETS))
    if count == 0:
        return []
    share = 1.0 / count
    fractions = [share] * (count - 1)
    fractions.append(1.0 - sum(fractions))
    return fractions


def target_crossed(price: float, target: float, side: str) -> bool:
    """آیا قیمت به هدف رسیده یا از آن گذشته است؟"""
    if price <= 0 or target <= 0:
        return False
    if str(side or "long").lower() in ("long", "buy"):
        return price >= target
    return price <= target


def stop_crossed(price: float, stop: float | None, side: str) -> bool:
    """آیا قیمت حد ضرر را زده است؟"""
    if price <= 0 or not stop or stop <= 0:
        return False
    if str(side or "long").lower() in ("long", "buy"):
        return price <= stop
    return price >= stop


def next_step(
    *,
    price: float,
    side: str,
    stop_loss: float | None,
    targets: Iterable[float],
    targets_hit: int,
    original_quantity: float,
    remaining_quantity: float,
    entry: float,
) -> dict[str, Any] | None:
    """
    اقدام بعدی برای یک موقعیت پلکانی در این قیمت، یا `None`.

    بازگشتی یکی از این‌هاست:
        {"action": "stop", "reason": "stop_loss" | "breakeven"}
        {"action": "partial", "index": i, "quantity": q, "new_stop": s | None}
        {"action": "final", "index": i, "reason": "take_profit"}

    ترتیب بررسی: حد ضرر **اول** (محتاطانه‌ترین فرض برای کندلی که هر دو
    را لمس کند)، سپس هدف بعدی. در هر تیک فقط یک گام برگردانده می‌شود؛
    اگر قیمت با یک جهش از دو هدف بگذرد، تیک بعدی گام دوم را می‌گیرد.
    """
    levels = list(targets or [])
    if stop_crossed(price, stop_loss, side):
        at_entry = bool(entry) and stop_loss is not None and abs(float(stop_loss) - float(entry)) <= abs(entry) * 1e-9
        return {"action": "stop", "reason": "breakeven" if (targets_hit > 0 and at_entry) else "stop_loss"}
    if not levels or targets_hit >= len(levels):
        return None
    index = int(targets_hit)
    target = float(levels[index])
    if not target_crossed(price, target, side):
        return None
    if index >= len(levels) - 1:
        return {"action": "final", "index": index, "reason": "take_profit"}
    fractions = stage_fractions(len(levels))
    quantity = min(remaining_quantity, original_quantity * fractions[index])
    if quantity <= 0 or quantity >= remaining_quantity * (1 - 1e-9):
        return {"action": "final", "index": index, "reason": "take_profit"}
    return {
        "action": "partial",
        "index": index,
        "quantity": quantity,
        # پس از TP1 حد ضرر به نقطهٔ ورود می‌رود (خواستهٔ صریح کاربر)
        "new_stop": float(entry) if index == 0 and entry > 0 else None,
    }


def targets_text(targets: Iterable[float], formatter: Any = None) -> str:
    """«TP1 x | TP2 y | TP3 z» برای پیام‌ها و جدول."""
    fmt = formatter or (lambda value: f"{value:,.8g}")
    return " | ".join(f"TP{i} {fmt(v)}" for i, v in enumerate(targets or [], start=1))


__all__ = [
    "MAX_TARGETS",
    "clean_targets",
    "next_step",
    "stage_fractions",
    "stop_crossed",
    "target_crossed",
    "targets_text",
]
