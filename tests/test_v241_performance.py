"""
آزمون‌های نسخهٔ ۲.۴.۱ — سبک‌سازی پویش کل بازار.

گزارش کاربر: «سیستم خیلی سنگین شده، هنگ می‌کند و کل سیستم را درگیر می‌کند.»
پوشش:
    * سقف سهم CPU (`CpuGovernor`) و انتظار در مکث محدودیت نرخ
    * حالت «درخواست انبوه»: کندل پویش نه در پایگاه داده نوشته می‌شود نه
      حافظهٔ نهان مشترک را پر می‌کند
    * ساخت یک‌بارهٔ DataFrame در `calculate_many` (همان خروجی)
    * دروازهٔ محاسبهٔ موتور سیگنال: حلقه بین محاسبه‌ها آزاد می‌شود
    * سقف ردیف‌های جدول پویش
"""

from __future__ import annotations

import asyncio
import random
import time
import types
from datetime import datetime, timedelta, timezone

import pytest

from app.core.constants import SignalDirection
from app.core.models import Candle, TradingSignal
from market.engine import MarketDataEngine, bulk_fetch, is_bulk_fetch
from signals.scanner import (
    BACKGROUND_CPU_DUTY,
    DEFAULT_CPU_DUTY,
    MAX_PACE_SLEEP,
    CpuGovernor,
    MarketScanner,
)


def _candles(count: int = 250, seed: int = 7) -> list[Candle]:
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    out = []
    for index in range(count):
        opened = price
        price *= 1 + rng.gauss(0, 0.01)
        out.append(Candle(
            timestamp=start + timedelta(hours=index), open=opened,
            high=max(opened, price) * 1.003, low=min(opened, price) * 0.997,
            close=price, volume=rng.random() * 1000,
        ))
    return out


# ================================================================ سقف CPU
class _Clock:
    def __init__(self) -> None:
        self.wall = 0.0
        self.cpu = 0.0


def test_governor_sleeps_to_respect_duty() -> None:
    clock = _Clock()
    governor = CpuGovernor(0.5, clock=lambda: clock.wall, cpu_clock=lambda: clock.cpu)
    clock.wall, clock.cpu = 1.0, 1.0  # ۱۰۰٪ مشغول
    # برای سهم ۵۰٪، یک ثانیه CPU به دو ثانیه زمان دیواری نیاز دارد
    assert governor.delay() == pytest.approx(1.0)


def test_governor_no_sleep_when_under_budget_and_caps_sleep() -> None:
    clock = _Clock()
    governor = CpuGovernor(0.6, clock=lambda: clock.wall, cpu_clock=lambda: clock.cpu)
    clock.wall, clock.cpu = 2.0, 0.5
    assert governor.delay() == 0.0
    clock.wall, clock.cpu = 2.0, 30.0
    assert governor.delay() == MAX_PACE_SLEEP


def test_governor_full_duty_never_sleeps_and_sanitises() -> None:
    assert CpuGovernor(None).delay() == 0.0
    assert CpuGovernor(1.0).delay() == 0.0
    assert CpuGovernor("bad").duty == DEFAULT_CPU_DUTY
    assert CpuGovernor(0.0).duty == 0.05
    assert 0 < BACKGROUND_CPU_DUTY < DEFAULT_CPU_DUTY < 1


def test_governor_window_resets_after_idle() -> None:
    clock = _Clock()
    governor = CpuGovernor(0.5, clock=lambda: clock.wall, cpu_clock=lambda: clock.cpu)
    clock.wall, clock.cpu = 20.0, 1.0
    assert governor.delay() == 0.0  # پنجره بازنشانی شد
    clock.wall, clock.cpu = 21.0, 2.0
    assert governor.delay() == pytest.approx(1.0)


# ================================================================ پویشگر
def _signal(symbol: str) -> TradingSignal:
    return TradingSignal(symbol=symbol, exchange="t", direction=SignalDirection.LONG,
                         confidence=70, risk_reward=2.0, leverage=2)


class _Engine:
    def __init__(self) -> None:
        self.bulk_seen: list[bool] = []

    async def generate(self, symbol, frames=None):
        self.bulk_seen.append(is_bulk_fetch())
        return _signal(symbol)


def test_scan_marks_requests_as_bulk_only_inside_scan() -> None:
    engine = _Engine()
    scanner = MarketScanner(types.SimpleNamespace(), engine, concurrency=2)
    asyncio.run(scanner.scan(["A/USDT", "B/USDT", "C/USDT"]))
    assert engine.bulk_seen == [True, True, True]
    assert is_bulk_fetch() is False


def test_scan_waits_for_rate_limit_cooldown() -> None:
    class Market:
        def __init__(self) -> None:
            self.until = time.monotonic() + 0.2

        @property
        def rest_cooldown_remaining(self) -> float:
            return max(0.0, self.until - time.monotonic())

    scanner = MarketScanner(Market(), _Engine(), concurrency=1)
    started = time.monotonic()
    result = asyncio.run(scanner.scan(["A/USDT"]))
    assert time.monotonic() - started >= 0.18
    assert result.scanned == 1


def test_scan_ignores_non_numeric_cooldown_attribute() -> None:
    from unittest.mock import MagicMock

    scanner = MarketScanner(MagicMock(), _Engine(), concurrency=1)
    started = time.monotonic()
    asyncio.run(scanner.scan(["A/USDT"]))
    assert time.monotonic() - started < 1.0


# ================================================================ موتور بازار
class _Provider:
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    async def get_ohlcv(self, symbol, timeframe, limit=300):
        self.calls += 1
        return _candles(50)


class _Repo:
    def __init__(self) -> None:
        self.saved: list[str] = []

    def save_candles(self, exchange, symbol, timeframe, candles):
        self.saved.append(symbol)


def test_bulk_fetch_skips_persistence_and_shared_cache() -> None:
    provider, repo = _Provider(), _Repo()
    engine = MarketDataEngine(provider, candle_repository=repo, websocket_enabled=False)

    async def run() -> None:
        with bulk_fetch():
            await engine.get_candles("SCAN/USDT", "1h", 50)
        await engine.get_candles("SCAN/USDT", "1h", 50)  # کش نشده بود → دوباره شبکه
        await engine.get_candles("CHART/USDT", "1h", 50)
        await engine.get_candles("CHART/USDT", "1h", 50)  # از کش

    asyncio.run(run())
    assert repo.saved == ["SCAN/USDT", "CHART/USDT"]
    assert provider.calls == 3


def test_bulk_flag_propagates_to_child_tasks() -> None:
    async def child() -> bool:
        return is_bulk_fetch()

    async def run():
        with bulk_fetch():
            inside = await asyncio.gather(child(), child())
        outside = await asyncio.gather(child())
        return inside, outside

    inside, outside = asyncio.run(run())
    assert inside == [True, True]
    assert outside == [False]


# ================================================================ اندیکاتورها
def test_calculate_many_matches_individual_results(monkeypatch) -> None:
    from indicators import base
    from indicators.engine import IndicatorEngine
    from signals.engine import REQUIRED_INDICATORS, SIGNAL_INDICATOR_PARAMETERS

    candles = _candles(260)
    many = IndicatorEngine().calculate_many(
        REQUIRED_INDICATORS, candles, "1h", symbol="X", parameters=SIGNAL_INDICATOR_PARAMETERS
    )
    single_engine = IndicatorEngine()
    for name, result in many.items():
        single = single_engine.calculate(
            name, candles, "1h", symbol="Y", **SIGNAL_INDICATOR_PARAMETERS.get(name, {})
        )
        assert result.latest == single.latest, name
        assert result.values == single.values, name

    calls = []
    original = base.candles_to_dataframe

    def counting(data):
        calls.append(1)
        return original(data)

    import indicators.engine as engine_module

    monkeypatch.setattr(engine_module, "candles_to_dataframe", counting)
    IndicatorEngine().calculate_many(REQUIRED_INDICATORS, candles, "4h", symbol="Z")
    assert len(calls) == 1  # یک تبدیل برای همهٔ اندیکاتورها


def test_indicator_values_keep_none_for_missing() -> None:
    from indicators.engine import IndicatorEngine

    result = IndicatorEngine().calculate("SMA", _candles(60), "1h", period=20)
    values = next(iter(result.values.values()))
    assert values[0] is None
    assert isinstance(values[-1], float)


# ================================================================ دروازهٔ محاسبه
def test_signal_engine_yields_loop_between_timeframes() -> None:
    """حلقه باید بین محاسبهٔ تایم‌فریم‌ها آزاد شود (تأخیر کوتاه تایمرها)."""
    from indicators.engine import IndicatorEngine
    from signals.engine import SignalEngine

    class Market:
        exchange_name = "fake"

        async def get_candles(self, symbol, timeframe, limit=None):
            await asyncio.sleep(0)
            return _candles(limit or 250, seed=hash((symbol, timeframe)) % 1000)

    engine = SignalEngine(Market(), IndicatorEngine())
    ticks: list[int] = []

    async def run() -> None:
        stop = False

        async def heartbeat() -> None:
            while not stop:
                ticks.append(1)
                await asyncio.sleep(0)

        beat = asyncio.create_task(heartbeat())
        await asyncio.gather(*(
            engine.generate(f"S{i}/USDT", ["1d", "4h", "1h", "15m"]) for i in range(4)
        ))
        stop = True
        await beat

    asyncio.run(run())
    # ۱۶ محاسبه؛ بدون دروازه ضربان فقط چند بار فرصت اجرا داشت
    assert len(ticks) >= 16


# ================================================================ جدول
@pytest.fixture()
def signals_page(qt_application):
    from localization import Translator
    from ui.pages.signals_page import SignalsPage

    return SignalsPage(Translator("fa"))


def test_scan_table_caps_rows_and_shows_note(signals_page) -> None:
    page = signals_page
    rows = [{"symbol": f"S{i}/USDT", "direction": "LONG", "confidence": 90 - i % 50}
            for i in range(page.SCAN_MAX_ROWS + 50)]
    page.set_scan_results(rows)
    assert page.scan_table.rowCount() == page.SCAN_MAX_ROWS
    assert not page.scan_cap_note.isHidden()
    assert str(page.SCAN_MAX_ROWS + 50) in page.scan_cap_note.text()
    assert page.scan_table.updatesEnabled()

    page.set_scan_results(rows[:5])
    assert page.scan_table.rowCount() == 5
    assert page.scan_cap_note.isHidden()


def test_locale_has_cap_note() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "localization"
    for lang in ("fa", "en"):
        data = json.loads((root / lang / "signals.json").read_text(encoding="utf-8"))
        assert "{shown}" in data["scan_rows_capped"] and "{total}" in data["scan_rows_capped"]
