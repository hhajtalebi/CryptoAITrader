"""
راهبردهای معاملاتی قابل افزودن.

هر راهبرد یک رأی مستقل می‌دهد؛ موتور سیگنال رأی‌ها را وزن‌دهی می‌کند.
"""

from signals.strategies.base import BaseStrategy, StrategyContext, StrategyVote
from signals.strategies.breakout import BreakoutStrategy
from signals.strategies.mean_reversion import MeanReversionStrategy
from signals.strategies.registry import (
    StrategyRegistry,
    register_builtin_strategies,
    strategy_registry,
)
from signals.strategies.trend_following import TrendFollowingStrategy

__all__ = [
    "BaseStrategy",
    "StrategyContext",
    "StrategyVote",
    "BreakoutStrategy",
    "MeanReversionStrategy",
    "TrendFollowingStrategy",
    "StrategyRegistry",
    "strategy_registry",
    "register_builtin_strategies",
]
