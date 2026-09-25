"""
نسخهٔ ۲.۵.۴ — اسکالپ فوق‌سریع، بازشدن واقعی معاملهٔ خودکار و پایداری طولانی.

همهٔ قیمت‌ها و مخزن‌ها بدل آزمونی قطعی‌اند؛ هیچ درخواست شبکه‌ای نیست.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace as NS

import pytest

from trading.auto_trader import (
    HARD_MAX_CONCURRENT,
    PERSIST_INTERVAL_SECONDS,
    AutoTradeConfig,
    AutoTrader,
)
from trading.price_cache import TickEngine
from trading.ultra_scalp import UltraScalpSource, momentum



class Repo:
    def __init__(self):
        self.rows = []
        self.live_updates = 0
        self.protection_updates = 0

    def open_trade(self, **kwargs):
        row = dict(kwargs, id=len(self.rows) + 1, status=kwargs.get("status", "open"))
        self.rows.append(row)
        return row

    def close_trade(self, tid, *, exit_price, fee, **kwargs):
        row = self.rows[tid - 1]
        sign = 1 if row["side"] == "long" else -1
        pnl = (exit_price - row["entry_price"]) * sign * row["quantity"]
        row.update(status="closed", pnl=pnl - row.get("fee", 0) - fee, exit_price=exit_price)
        return row

    def open_trades(self, _user_id=None):
        return [r for r in self.rows if r["status"] == "open"]

    def update_live_pnl(self, *_args, **_kwargs):
        self.live_updates += 1

    def update_protection(self, *_args, **_kwargs):
        self.protection_updates += 1


# ---------------------------------------------------------------------------
# تکانه و منبع نامزد فوق‌سریع
# ---------------------------------------------------------------------------
def test_momentum_measures_one_way_move():
    points = [(1000.0 * i, 100.0 + 0.1 * i) for i in range(10)]
    move, consistency, count = momentum(points, now_ms=9000.0, window_ms=30_000.0)
    assert count == 10
    assert move == pytest.approx(0.9, rel=1e-6)
    assert consistency == pytest.approx(1.0)


def test_momentum_choppy_market_has_low_consistency():
    points = [(1000.0 * i, 100.0 + (0.2 if i % 2 else 0.0)) for i in range(10)]
    _move, consistency, _count = momentum(points, now_ms=9000.0, window_ms=30_000.0)
    assert consistency < 0.2


def test_momentum_needs_enough_recent_points():
    assert momentum([(0.0, 1.0), (1.0, 2.0)], now_ms=1.0, window_ms=30_000.0)[2] == 2
    assert momentum([(0.0, 1.0), (1.0, 2.0)], now_ms=1.0, window_ms=30_000.0)[0] == 0.0


def _ticks_with(series: dict[str, list[float]]) -> TickEngine:
    engine = TickEngine(stale_after_seconds=60)
    for symbol, prices in series.items():
        for price in prices:
            engine.record(symbol, price, source="rest")
    return engine


async def test_ultra_source_ranks_movers_and_skips_quiet_and_excluded():
    engine = _ticks_with({
        "UP/USDT": [100, 100.1, 100.2, 100.3],
        "DOWN/USDT": [50, 49.9, 49.8, 49.7],
        "FLAT/USDT": [10, 10, 10, 10],
        "HELD/USDT": [5, 5.1, 5.2, 5.3],
    })
    source = UltraScalpSource(lambda: engine, settings=lambda key, default: 0 if key == "scalp.min_liquidity" else default)
    result = await source.scan(exclude={"HELD/USDT"}, limit=10)
    by_symbol = {c.symbol: c for c in result}
    assert set(by_symbol) == {"UP/USDT", "DOWN/USDT"}
    assert by_symbol["UP/USDT"].direction == "LONG"
    assert by_symbol["DOWN/USDT"].direction == "SHORT"
    assert all(50 <= c.score <= 99 for c in result)
    # نامزد فوق‌سریع هدف/حد ضرر ندارد؛ موتور از بودجهٔ دلاری می‌سازد
    assert all(c.take_profit == 0 and c.stop_loss == 0 for c in result)
    assert source.last_stats["quiet"] == 1


async def test_ultra_source_filters_illiquid_symbols():
    engine = _ticks_with({"THIN/USDT": [1, 1.01, 1.02, 1.03], "DEEP/USDT": [2, 2.02, 2.04, 2.06]})

    async def tickers():
        return [NS(symbol="THIN/USDT", turnover_24h=1_000.0), NS(symbol="DEEP/USDT", turnover_24h=50_000_000.0)]

    source = UltraScalpSource(lambda: engine, tickers_source=tickers)
    result = await source.scan(limit=10)
    assert [c.symbol for c in result] == ["DEEP/USDT"]
    assert source.last_stats["illiquid"] == 1


async def test_ultra_source_without_tick_engine_is_empty():
    source = UltraScalpSource(lambda: None)
    assert await source.scan() == []


def test_tick_engine_lists_symbols():
    engine = _ticks_with({"A/USDT": [1.0], "B/USDT": [2.0]})
    assert set(engine.symbols()) == {"A/USDT", "B/USDT"}


# ---------------------------------------------------------------------------
# پیکربندی
# ---------------------------------------------------------------------------
def test_concurrency_cap_is_200():
    assert HARD_MAX_CONCURRENT == 200
    assert AutoTradeConfig(max_concurrent=150).validated().max_concurrent == 150
    assert AutoTradeConfig(max_concurrent=999).validated().max_concurrent == 200


def test_ultra_mode_allows_fast_scan_and_short_hold():
    config = AutoTradeConfig(engine_mode="ultra", scan_interval_seconds=0.2, max_hold_seconds=1).validated()
    assert config.engine_mode == "ultra"
    assert config.scan_interval_seconds == 1.0
    assert config.max_hold_seconds == 10
    normal = AutoTradeConfig(engine_mode="scan", scan_interval_seconds=0.2, max_hold_seconds=1).validated()
    assert normal.scan_interval_seconds == 3.0
    assert normal.max_hold_seconds == 30


# ---------------------------------------------------------------------------
# موتور: ورود واقعی، بستن در سود خالص، آمار پویش، محدودکردن نوشتن
# ---------------------------------------------------------------------------
def _trader(repo=None, *, prices=None, candidates=None, balance=1000.0, **config):
    prices = prices if prices is not None else {}

    async def price(symbol):
        await asyncio.sleep(0)
        return prices.get(symbol, 100.0)

    defaults = dict(engine_mode="ultra", margin_per_trade=10, leverage=50, target_profit=2, max_loss=2,
                    max_concurrent=100, fee_rate=0.0006, slippage_percent=0, min_liquidity=0,
                    max_total_margin_percent=100, daily_loss_limit=10_000)
    defaults.update(config)
    repo = repo or Repo()

    def portfolio():
        rows = repo.open_trades()
        used = sum(r["entry_price"] * r["quantity"] / r.get("leverage", 1) for r in rows)
        return {"balance": balance, "used_margin": used, "available_margin": balance - used, "open_count": len(rows)}

    return AutoTrader(config=AutoTradeConfig(**defaults), price_source=price, repository=repo,
                      candidate_source=candidates, portfolio_source=portfolio)


def _ultra(symbol, direction="LONG"):
    return NS(symbol=symbol, direction=direction, score=80.0, price=100.0, take_profit=0.0, stop_loss=0.0,
              observed_at=time.time())


async def test_one_hundred_concurrent_ultra_trades_open_on_1000_balance():
    async def candidates():
        return [_ultra(f"C{i}/USDT") for i in range(120)]

    trader = _trader(candidates=candidates)
    await trader._scan_for_entries()
    assert len(trader.open_trades) == 100
    stats = trader.scan_stats()
    assert stats["opened"] == 100
    assert dict(stats["rejections"]).get("max_concurrent_reached", 0) >= 1 or stats["candidates"] == 120


async def test_ultra_trade_closes_at_user_net_profit_after_fees():
    prices = {"X/USDT": 100.0}
    trader = _trader(prices=prices)
    trade = await trader.open_trade(_ultra("X/USDT"))
    assert trade is not None
    # هدف: سود خالص ۲ دلار پس از کارمزد ورود و خروج
    net_at_target = trade.net_unrealised(trade.target_price)
    assert net_at_target == pytest.approx(2.0, abs=0.01)
    closed = []
    trader.add_listener(lambda event, payload: closed.append(payload) if event == "closed" else None)
    prices["X/USDT"] = trade.target_price
    await trader.check_open_trades()
    assert closed and closed[0]["reason"] == "take_profit"
    assert float(closed[0]["record"]["pnl"]) == pytest.approx(2.0, abs=0.05)


async def test_scan_stats_explain_why_nothing_opened():
    async def candidates():
        return [_ultra("A/USDT"), _ultra("B/USDT")]

    trader = _trader(candidates=candidates, balance=5.0)  # مارجین آزاد برای ۱۰ دلار نیست
    await trader._scan_for_entries()
    stats = trader.scan_stats()
    assert stats["opened"] == 0 and stats["candidates"] == 2
    assert stats["rejections"], stats


async def test_live_pnl_persistence_is_throttled():
    repo = Repo()
    trader = _trader(repo)
    await trader.open_trade(_ultra("P/USDT"))
    for _ in range(10):
        await trader.check_open_trades()
    # نخستین پایش می‌نویسد، بقیه تا ۲ ثانیه نه
    assert repo.live_updates == 1
    assert PERSIST_INTERVAL_SECONDS >= 1.0
    for managed in trader.open_trades:
        managed.last_persist -= PERSIST_INTERVAL_SECONDS + 0.1
    await trader.check_open_trades()
    assert repo.live_updates == 2


# ---------------------------------------------------------------------------
# پایداری: پایش نشست و نشت دسته‌های runner
# ---------------------------------------------------------------------------
def test_session_monitor_detects_unclean_previous_exit(tmp_path):
    from app.diagnostics import SessionMonitor

    first = SessionMonitor(tmp_path)
    assert first.start() is None
    first.set_extra_provider(lambda: {"live_handles": 3})
    first.heartbeat()
    data = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert data["clean"] is False and data["extra"]["live_handles"] == 3

    # بدون mark_clean_exit — مثل فروپاشی یا کشته‌شدن فرایند
    second = SessionMonitor(tmp_path)
    previous = second.start()
    assert previous is not None and previous.extra["live_handles"] == 3
    second.mark_clean_exit()

    third = SessionMonitor(tmp_path)
    assert third.start() is None


def test_crash_handlers_write_into_logs_dir(tmp_path):
    import faulthandler
    import sys
    import threading

    from app.diagnostics import install_crash_handlers

    saved = sys.excepthook, threading.excepthook
    try:
        path = install_crash_handlers(tmp_path)
        assert path.parent == tmp_path and path.exists()
    finally:
        sys.excepthook, threading.excepthook = saved
        faulthandler.disable()
        faulthandler.enable()


def test_memory_probe_returns_positive_number():
    from app.diagnostics import memory_mb

    assert memory_mb() >= 0.0


def test_runner_handles_are_released_after_finishing(qt_application):
    from PySide6.QtCore import QCoreApplication, QObject

    from ui.controllers.async_runner import AsyncRunner

    runner = AsyncRunner()
    runner.start()
    try:
        async def work(value):
            return value

        done = []
        for index in range(200):
            runner.submit(f"job{index}", work(index), on_success=done.append)
        deadline = time.time() + 10
        while len(done) < 200 and time.time() < deadline:
            QCoreApplication.processEvents()
            time.sleep(0.005)
        QCoreApplication.processEvents()
        assert len(done) == 200
        assert runner.live_handles() == 0
        assert runner.submitted_total == 200
        # تمام‌شده‌ها فقط تا مهلت کوتاه نگه داشته می‌شوند، سپس نابود
        assert len(runner.findChildren(QObject)) == runner.pending_release()
        runner.purge_finished(force=True)
        assert len(runner.findChildren(QObject)) == 0
    finally:
        runner.stop()


def test_stopped_runner_submit_does_not_crash_later(qt_application):
    """فروپاشی ۲.۵.۴ در آزمون: دستهٔ کار زمان‌بندی‌نشده نباید فرزند runner باشد."""
    import gc

    from PySide6.QtCore import QCoreApplication, QEvent

    from ui.controllers.async_runner import AsyncRunner

    async def work():
        return 1

    for _ in range(5):
        errors = []
        stopped = AsyncRunner()
        stopped.submit("x", work(), on_error=lambda message, _exc: errors.append(message))
        assert errors
        del stopped
        gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QCoreApplication.processEvents()


# ---------------------------------------------------------------------------
# صفحهٔ معاملات: حالت و پیش‌تنظیم فوق‌سریع
# ---------------------------------------------------------------------------
@pytest.fixture()
def translator():
    from localization import Translator

    instance = Translator("fa")
    instance.load()
    return instance


def test_trades_page_ultra_preset_and_limits(qt_application, translator):
    from tests.conftest import destroy_window
    from ui.pages.trades_page import TradesPage

    page = TradesPage(translator)
    try:
        assert page.auto_engine_mode_combo.findData("ultra") >= 0
        assert page.auto_concurrent_input.maximum() == 200
        assert page.auto_scan_interval_input.minimum() == 1.0
        emitted = []
        page.auto_settings_changed.connect(emitted.append)
        page._emit_ultra_profile()
        assert emitted, "preset must be saved"
        payload = emitted[-1]
        assert payload["scalp.engine_mode"] == "ultra"
        assert payload["scalp.max_concurrent"] == 100
        assert payload["scalp.leverage"] == 50
        assert payload["scalp.target_profit"] == 2.0
        # حالت کاغذی/واقعی و عبارت تأیید هرگز با پیش‌تنظیم عوض نمی‌شوند
        assert "scalp.mode" not in payload and "scalp.live_confirmation" not in payload
        assert page.auto_engine_mode_combo.currentData() == "ultra"
        assert page.auto_hold_input.value() == 180
    finally:
        destroy_window(page, qt_application)
