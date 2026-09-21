"""
لایه تولید سیگنال.

اصل بنیادین این لایه: **موتور سیگنال به هوش مصنوعی وابسته نیست.**
تصمیم‌گیری بر پایه قواعد شفاف و اندیکاتورهای واقعی انجام می‌شود؛ هوش
مصنوعی تنها یک لایه «غنی‌سازی و توضیح» است که اگر در دسترس نباشد، سیگنال
پایه بدون هیچ خطایی تولید می‌شود.

**چرا وارد‌کردن‌ها تنبل‌اند؟**

‏`SignalEngine` به `indicators` وابسته است و آن هم به pandas؛ روی هم
حدود نیم ثانیه بارگذاری. تا پیش از این، همین فایل آن زنجیره را برای هر
کسی که چیزی از بستهٔ `signals` می‌خواست اجرا می‌کرد — از جمله
`app.database.repositories` که فقط `signals.outcome_tracker` را لازم
دارد و آن ماژول جز `dataclass` و `datetime` هیچ وابستگی‌ای ندارد.
نتیجه این بود که **خواندن یک تنظیم ساده از پایگاه داده، pandas را بار
می‌کرد** و نیم ثانیه به راه‌اندازی برنامه اضافه می‌شد.

با `__getattr__` سطح ماژول (PEP 562)، نام‌های سنگین تنها در نخستین
دسترسی واقعی ساخته می‌شوند. `from signals import SignalEngine` دقیقاً
مثل گذشته کار می‌کند، ولی `import signals.outcome_tracker` دیگر pandas
را نمی‌کشد.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - فقط برای ابزار نوع‌سنجی
    from signals.engine import SignalEngine
    from signals.risk_engine import RiskEngine
    from signals.strategies.base import BaseStrategy, StrategyContext, StrategyVote
    from signals.strategies.registry import (
        StrategyRegistry,
        register_builtin_strategies,
        strategy_registry,
    )

#: نگاشت «نام عمومی → ماژولی که در آن تعریف شده»
_LAZY_EXPORTS: dict[str, str] = {
    "SignalEngine": "signals.engine",
    "RiskEngine": "signals.risk_engine",
    "BaseStrategy": "signals.strategies.base",
    "StrategyVote": "signals.strategies.base",
    "StrategyContext": "signals.strategies.base",
    "StrategyRegistry": "signals.strategies.registry",
    "strategy_registry": "signals.strategies.registry",
    "register_builtin_strategies": "signals.strategies.registry",
}


def __getattr__(name: str) -> Any:
    """
    بارگذاری تنبل نام‌های سنگین بسته.

    پایتون این تابع را تنها وقتی صدا می‌زند که نام در فضای نام ماژول
    پیدا نشود؛ پس هزینهٔ وارد‌کردن دقیقاً یک بار و فقط در صورت نیاز
    واقعی پرداخت می‌شود.
    """
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module 'signals' has no attribute '{name}'")

    from importlib import import_module

    value = getattr(import_module(module_path), name)
    # در فضای نام ماژول کش می‌شود تا دسترسی‌های بعدی از این تابع نگذرند
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """کامل‌کنندهٔ خودکار باید نام‌های تنبل را هم ببیند."""
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


__all__ = [
    "BaseStrategy",
    "RiskEngine",
    "SignalEngine",
    "StrategyContext",
    "StrategyRegistry",
    "StrategyVote",
    "register_builtin_strategies",
    "strategy_registry",
]
