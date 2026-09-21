"""
رجیستری راهبردها.

مشابه رجیستری اندیکاتورها: افزودن راهبرد جدید فقط یک سطر ثبت لازم دارد و
موتور سیگنال به‌صورت خودکار آن را در جمع‌بندی لحاظ می‌کند.
"""

from __future__ import annotations

from app.exceptions import SignalEngineError
from app.logging import get_logger
from signals.strategies.base import BaseStrategy

logger = get_logger(__name__)


class StrategyRegistry:
    """نگهدارنده راهبردهای ثبت‌شده."""

    def __init__(self) -> None:
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, strategy_class: type[BaseStrategy]) -> None:
        """ثبت یک راهبرد (نمونه‌سازی یک‌باره)."""
        instance = strategy_class()
        if not instance.name or instance.name == "base":
            raise SignalEngineError(f"Strategy {strategy_class.__name__} must define a unique name")
        self._strategies[instance.name] = instance
        logger.debug("Strategy registered: %s (weight=%.2f)", instance.name, instance.weight)

    def get(self, name: str) -> BaseStrategy:
        """دریافت یک راهبرد بر اساس نام."""
        strategy = self._strategies.get(name)
        if strategy is None:
            raise SignalEngineError(
                f"Strategy not found: {name}", details={"available": self.available()}
            )
        return strategy

    def all(self) -> list[BaseStrategy]:
        """فهرست همه راهبردهای ثبت‌شده."""
        return list(self._strategies.values())

    def available(self) -> list[str]:
        """نام همه راهبردها."""
        return sorted(self._strategies)

    def clear(self) -> None:
        """پاک کردن رجیستری (برای تست)."""
        self._strategies.clear()


#: رجیستری سراسری راهبردها
strategy_registry = StrategyRegistry()


def register_builtin_strategies(registry: StrategyRegistry | None = None) -> int:
    """
    ثبت راهبردهای پیش‌فرض برنامه.

    بازگشتی: تعداد راهبردهای ثبت‌شده.
    """
    from signals.strategies.breakout import BreakoutStrategy
    from signals.strategies.mean_reversion import MeanReversionStrategy
    from signals.strategies.momentum import MomentumStrategy
    from signals.strategies.trend_following import TrendFollowingStrategy
    from signals.strategies.volatility_regime import VolatilityRegimeStrategy

    target = registry or strategy_registry
    # پنج راهبرد با منطق‌های مستقل. با سه راهبرد، در بازار روندی عملاً
    # فقط یکی رأی می‌داد و اطمینان صادقانه هرگز از ۴۵٪ بالاتر نمی‌رفت.
    for strategy_class in (
        TrendFollowingStrategy,
        MeanReversionStrategy,
        BreakoutStrategy,
        MomentumStrategy,
        VolatilityRegimeStrategy,
    ):
        target.register(strategy_class)
    logger.info("Registered %d built-in strategies", len(target.available()))
    return len(target.available())
