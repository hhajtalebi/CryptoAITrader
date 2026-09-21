"""
پیکربندی مشترک آزمون‌ها.

نکته مهم: همه آزمون‌ها روی پوشه داده موقت اجرا می‌شوند تا هرگز به داده
واقعی کاربر دست نزنند.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.core.models import Candle, RiskParameters
from app.core.paths import AppPaths
from app.database.session import DatabaseManager
from indicators.registry import indicator_registry, register_builtin_indicators
from signals.strategies.registry import register_builtin_strategies, strategy_registry


@pytest.fixture(scope="session", autouse=True)
def _register_plugins() -> None:
    """ثبت یک‌باره اندیکاتورها و راهبردها برای کل جلسه آزمون."""
    if not indicator_registry.available():
        register_builtin_indicators()
    if not strategy_registry.available():
        register_builtin_strategies()


@pytest.fixture()
def temp_paths(tmp_path: Path) -> AppPaths:
    """مسیرهای برنامه روی پوشه موقت."""
    return AppPaths(tmp_path).ensure()


@pytest.fixture()
def database(temp_paths: AppPaths) -> DatabaseManager:
    """پایگاه داده موقت با جدول‌های ساخته‌شده."""
    manager = DatabaseManager(temp_paths.database_url)
    manager.create_all()
    return manager


@pytest.fixture()
def risk_parameters() -> RiskParameters:
    """پارامترهای ریسک نمونه برای آزمون‌ها."""
    return RiskParameters(
        account_balance=1000.0,
        risk_percent=1.0,
        max_leverage=10,
        min_risk_reward=1.5,
        atr_stop_multiplier=1.5,
        max_stop_distance_percent=10.0,
    )


def make_candles(
    count: int = 260,
    start: float = 100.0,
    drift: float = 0.0,
    noise: float = 0.004,
    seed: int = 42,
    volume_spike_at_end: bool = False,
) -> list[Candle]:
    """
    ساخت کندل مصنوعی با روند و نوفه.

    هشدار: سری کاملاً یکنواخت (بدون نوفه) برای آزمون ساختار بازار مناسب
    نیست، چون هیچ نقطه چرخشی ندارد. به همین دلیل noise پیش‌فرض صفر نیست.
    """
    generator = random.Random(seed)
    candles: list[Candle] = []
    price = start
    timestamp = 1_700_000_000

    for index in range(count):
        price *= 1 + drift + generator.gauss(0, noise)
        high = price * (1 + abs(generator.gauss(0, noise)))
        low = price * (1 - abs(generator.gauss(0, noise)))
        open_price = candles[-1].close if candles else price
        volume = 100 * (1 + abs(generator.gauss(0, 0.4)))
        if volume_spike_at_end and index > count - 4:
            volume *= 3
        candles.append(
            Candle(
                timestamp=timestamp + index * 3600,
                open=open_price,
                high=max(open_price, high, price),
                low=min(open_price, low, price),
                close=price,
                volume=volume,
            )
        )
    return candles


@pytest.fixture()
def uptrend_candles() -> list[Candle]:
    """کندل‌های روند صعودی."""
    return make_candles(drift=0.005, seed=1, volume_spike_at_end=True)


@pytest.fixture()
def downtrend_candles() -> list[Candle]:
    """کندل‌های روند نزولی."""
    return make_candles(drift=-0.005, seed=2, volume_spike_at_end=True)


@pytest.fixture()
def ranging_candles() -> list[Candle]:
    """کندل‌های بازار بدون روند."""
    return make_candles(drift=0.0, noise=0.006, seed=3)


class FakeMarketEngine:
    """
    موتور بازار ساختگی برای آزمون بدون شبکه.

    آزمون‌ها نباید به اینترنت وابسته باشند؛ در غیر این صورت شکست آزمون
    ممکن است ربطی به کد نداشته باشد.
    """

    exchange_name = "test"

    def __init__(self, candles_by_timeframe: dict[str, list[Candle]]) -> None:
        self._data = candles_by_timeframe
        self.calls: list[tuple[str, str, int]] = []

    async def get_candles(self, symbol: str, timeframe: str, limit: int = 250) -> list[Candle]:
        """بازگرداندن کندل‌های از پیش آماده."""
        self.calls.append((symbol, timeframe, limit))
        from app.exceptions import InsufficientDataError

        if timeframe not in self._data:
            raise InsufficientDataError(f"No test data for {timeframe}")
        return self._data[timeframe][-limit:]


@pytest.fixture(scope="session")
def qt_application():
    """
    یک نمونه Qt برای کل جلسه آزمون.

    ساختن بیش از یک QApplication در یک فرایند، مفسر را با خطای مرگبار
    از پا درمی‌آورد؛ پس همه آزمون‌های رابط کاربری باید همین را بگیرند.
    `QApplication` (نه QCoreApplication) لازم است چون ویجت می‌سازیم.
    """
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    return application
