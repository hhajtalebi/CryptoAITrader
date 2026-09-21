"""آزمون موتور اندیکاتور."""

from __future__ import annotations

import pytest

from app.exceptions import IndicatorError, InsufficientDataError
from indicators import IndicatorEngine
from indicators.registry import indicator_registry
from tests.conftest import make_candles


def test_all_builtin_indicators_are_registered() -> None:
    """هر ۲۴ اندیکاتور باید ثبت شده باشند."""
    available = indicator_registry.available()
    assert len(available) == 24
    for name in ("RSI", "MACD", "ATR", "BBANDS", "ADX", "OBV", "VWAP", "PIVOT"):
        assert name in available


def test_indicator_categories_cover_five_groups() -> None:
    """اندیکاتورها باید در پنج دسته سازمان‌دهی شوند."""
    categories = indicator_registry.by_category()
    assert set(categories) == {"trend", "momentum", "volatility", "volume", "support_resistance"}


def test_sma_matches_manual_calculation(uptrend_candles) -> None:
    """میانگین متحرک ساده باید با محاسبه دستی یکی باشد."""
    engine = IndicatorEngine()
    result = engine.calculate("SMA", uptrend_candles, "1h", period=20)
    expected = sum(c.close for c in uptrend_candles[-20:]) / 20
    assert result.latest["sma"] == pytest.approx(expected, rel=1e-9)


def test_rsi_stays_within_bounds(ranging_candles) -> None:
    """RSI همیشه باید بین صفر و صد بماند."""
    engine = IndicatorEngine()
    result = engine.calculate("RSI", ranging_candles, "1h")
    assert 0.0 <= result.latest["rsi"] <= 100.0


def test_uptrend_produces_bullish_signals(uptrend_candles) -> None:
    """در روند صعودی قوی، ADX باید جهت صعودی گزارش کند."""
    engine = IndicatorEngine()
    result = engine.calculate("ADX", uptrend_candles, "1h")
    assert "BULLISH" in result.signal


def test_insufficient_data_raises(uptrend_candles) -> None:
    """داده کم باید خطای صریح بدهد، نه نتیجه اشتباه."""
    engine = IndicatorEngine()
    with pytest.raises((InsufficientDataError, IndicatorError)):
        engine.calculate("ADX", uptrend_candles[:5], "1h")


def test_invalid_parameter_raises(uptrend_candles) -> None:
    """پارامتر نامعتبر باید رد شود."""
    engine = IndicatorEngine()
    with pytest.raises((IndicatorError, InsufficientDataError, ValueError)):
        engine.calculate("SMA", uptrend_candles, "1h", period=-5)


def test_calculate_many_isolates_failures(uptrend_candles) -> None:
    """خطای یک اندیکاتور نباید بقیه را از بین ببرد."""
    engine = IndicatorEngine()
    results = engine.calculate_many(["RSI", "NOT_A_REAL_INDICATOR", "ATR"], uptrend_candles, "1h")
    assert "RSI" in results and "ATR" in results
    assert "NOT_A_REAL_INDICATOR" not in results


def test_cache_returns_same_values(uptrend_candles) -> None:
    """محاسبه دوباره با همان داده باید نتیجه یکسان بدهد."""
    engine = IndicatorEngine()
    first = engine.calculate("RSI", uptrend_candles, "1h")
    second = engine.calculate("RSI", uptrend_candles, "1h")
    assert first.latest == second.latest


def test_analyze_timeframe_requires_minimum_candles() -> None:
    """تحلیل تایم‌فریم با کندل ناکافی باید خطا بدهد."""
    engine = IndicatorEngine()
    with pytest.raises(InsufficientDataError):
        engine.analyze_timeframe(make_candles(count=20), "1h")
