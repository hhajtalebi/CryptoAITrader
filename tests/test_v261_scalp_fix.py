"""
آزمون‌های نسخهٔ ۲.۶.۱ — رفع «اسکالپ معامله باز نمی‌کند».

ریشه‌ها (از لاگ واقعی کاربر):
1. اختلاف ساعت سیستم با صرافی → همهٔ تیک‌های REST «کهنه» و همهٔ دفترها رد.
2. دفتر سالم وقتی تیکر شکست می‌خورد دور ریخته می‌شد → no_orderbook دائمی.
3. AsyncRunner کوروتینِ در حال اجرا را می‌بست → «cannot reuse already
   awaited coroutine» و دفتر ترمینال هرگز ثبت نمی‌شد.
4. پیش‌خوانی دو درخواست (تیکر + دفتر) می‌فرستاد → PoolTimeout.
5. گردش ۲۴ساعتهٔ اولترا هر ثانیه منتظر REST بود → پویش تا ۳۱ ثانیه.

هیچ آستانه‌ای پایین نیامده؛ آزمون‌ها همین را هم قفل می‌کنند.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from types import SimpleNamespace as NS

import pytest

from app.logging import audit
from market.engine import MarketDataEngine
from trading.auto_trader import AutoTradeConfig
from trading.price_cache import CLOCK_SKEW_TOLERANCE_MS, TickEngine
from trading.ultra_scalp import UltraScalpSource

from tests.test_v230_execution import Repo, candidate, make

ULTRA = dict(engine_mode="ultra", margin_per_trade=10, leverage=50, target_profit=2, max_loss=2,
             fee_rate=0.0006, max_hold_seconds=180, min_liquidity=0, max_total_margin_percent=100,
             daily_loss_limit=10_000, max_concurrent=10)


def _now_ms() -> float:
    return time.time() * 1000.0


def _book(bid: float, ask: float, timestamp: float | None = None):
    return NS(best_bid=bid, best_ask=ask, bids=[NS(price=bid, quantity=5.0)],
              asks=[NS(price=ask, quantity=5.0)], timestamp=timestamp)


# ---------------------------------------------------------------------------
# ۱) اختلاف ساعت
# ---------------------------------------------------------------------------
def test_skewed_clock_made_every_rest_tick_stale_before_calibration():
    """بازتولید باگ: ساعت محلی ۳۰ ثانیه جلوتر → تیک تازهٔ REST «کهنه»."""
    ticks = TickEngine(stale_after_seconds=10)
    exchange_now = _now_ms() - 30_000  # ساعت صرافی ۳۰ ثانیه عقب‌تر از ساعت محلی
    ticks.record("ETH/USDT", 2000.0, source="rest", exchange_ts=exchange_now)
    assert ticks.is_stale("ETH/USDT")


def test_clock_calibration_keeps_fresh_rest_ticks_fresh():
    ticks = TickEngine(stale_after_seconds=10)
    exchange_now = _now_ms() - 30_000
    offset = ticks.observe_exchange_clock(exchange_now, _now_ms())
    assert offset == pytest.approx(30_000, abs=500)
    ticks.record("ETH/USDT", 2000.0, source="rest", exchange_ts=exchange_now)
    assert not ticks.is_stale("ETH/USDT")
    assert ticks.stats()["clock_offset_ms"] == pytest.approx(30_000, abs=500)


def test_genuinely_old_symbol_stays_stale_after_calibration():
    """اصلاح ساعت آستانه را پایین نمی‌آورد: نماد بی‌معامله همچنان کهنه است."""
    ticks = TickEngine(stale_after_seconds=10)
    exchange_now = _now_ms() - 30_000
    ticks.observe_exchange_clock(exchange_now, _now_ms())
    ticks.record("DEAD/USDT", 1.0, source="rest", exchange_ts=exchange_now - 120_000)
    assert ticks.is_stale("DEAD/USDT")
    assert ticks.stale_after_ms == 10_000


def test_clock_behind_exchange_no_longer_drops_ticks():
    """ساعت محلی عقب‌تر: قبلاً تیک «از آینده» کامل دور ریخته می‌شد."""
    ticks = TickEngine()
    exchange_now = _now_ms() + 20_000
    assert ticks.record("SOL/USDT", 150.0, source="rest", exchange_ts=exchange_now) is None
    ticks.observe_exchange_clock(exchange_now, _now_ms())
    assert ticks.record("SOL/USDT", 150.0, source="rest", exchange_ts=exchange_now) is not None
    assert not ticks.is_stale("SOL/USDT")


def test_small_offsets_are_ignored_so_synced_clocks_behave_as_before():
    ticks = TickEngine()
    assert ticks.observe_exchange_clock(_now_ms() - (CLOCK_SKEW_TOLERANCE_MS - 600), _now_ms()) == 0.0
    assert ticks.clock_offset_ms == 0.0


def test_absurd_offset_is_ignored():
    ticks = TickEngine()
    assert ticks.observe_exchange_clock(_now_ms() - 3 * 86_400_000, _now_ms()) == 0.0


def test_offset_uses_median_of_recent_batches():
    ticks = TickEngine()
    now = _now_ms()
    for sample in (5000, 5100, 4900, 60_000, 5050):
        ticks.observe_exchange_clock(now - sample, now)
    assert ticks.clock_offset_ms == pytest.approx(5050, abs=1)


# ---------------------------------------------------------------------------
# ۲) دفتر سفارش
# ---------------------------------------------------------------------------
def test_book_with_skewed_exchange_stamp_is_accepted():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    quote = ticks.record_book("BTC/USDT", _book(99.99, 100.01, timestamp=_now_ms() - 15_000))
    assert quote is not None and quote.book_fresh
    assert quote.bid == pytest.approx(99.99) and quote.ask == pytest.approx(100.01)


def test_truly_old_book_snapshot_is_still_rejected():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    ticks.record_book("BTC/USDT", _book(99.99, 100.01, timestamp=_now_ms() - 120_000))
    assert ticks.get("BTC/USDT").bid == 0.0


def test_spread_is_computed_from_real_bid_ask():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    quote = ticks.record_book("BTC/USDT", _book(99.95, 100.05))
    assert quote.spread == pytest.approx(0.10)
    assert quote.spread_percent == pytest.approx(0.10 / 100.0 * 100.0)
    assert quote.entry_price("long") == pytest.approx(100.05)
    assert quote.entry_price("short") == pytest.approx(99.95)


def _bare_engine(*, ticker=None, ticker_error=None, book=None):
    engine = MarketDataEngine.__new__(MarketDataEngine)

    async def get_ticker(symbol, max_age_seconds=0):
        if ticker_error is not None:
            raise ticker_error
        return ticker

    calls = []

    async def get_orderbook(symbol, depth=5):
        calls.append(symbol)
        return book

    engine.get_ticker = get_ticker
    engine._provider = NS(get_orderbook=get_orderbook)
    engine.book_calls = calls
    return engine


async def test_ticker_failure_no_longer_discards_a_good_book():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    engine = _bare_engine(ticker_error=TimeoutError("pool timeout"), book=_book(99.99, 100.01))
    with pytest.raises(TimeoutError):
        await engine.refresh_execution_quote("BTC/USDT", ticks)
    assert ticks.get("BTC/USDT").book_fresh and ticks.get("BTC/USDT").bid == pytest.approx(99.99)


async def test_stale_looking_ticker_no_longer_discards_a_good_book():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    old = NS(last_price=100.0, timestamp=int(_now_ms() - 60_000), change_percent=0.0)
    engine = _bare_engine(ticker=old, book=_book(99.99, 100.01))
    assert await engine.refresh_execution_quote("BTC/USDT", ticks) == 0.0
    assert ticks.get("BTC/USDT").ask == pytest.approx(100.01)


async def test_ticker_freshness_respects_calibrated_clock():
    ticks = TickEngine()
    skew = 30_000
    ticks.observe_exchange_clock(_now_ms() - skew, _now_ms())
    ticks.record("BTC/USDT", 100.0)
    ticker = NS(last_price=101.0, timestamp=int(_now_ms() - skew), change_percent=0.0)
    engine = _bare_engine(ticker=ticker, book=_book(100.99, 101.01))
    assert await engine.refresh_execution_quote("BTC/USDT", ticks) == pytest.approx(101.0)
    assert ticks.price("BTC/USDT") == pytest.approx(101.0)


async def test_refresh_execution_book_sends_one_request():
    ticks = TickEngine()
    ticks.record("ETH/USDT", 2000.0)
    engine = _bare_engine(ticker_error=AssertionError("ticker must not be called"),
                          book=_book(1999.9, 2000.1))
    assert await engine.refresh_execution_book("ETH/USDT", ticks) is True
    assert engine.book_calls == ["ETH/USDT"]
    assert ticks.get("ETH/USDT").book_fresh


# ---------------------------------------------------------------------------
# ۳) AutoTrader: پیش‌خوانی و ورود اولترا
# ---------------------------------------------------------------------------
async def test_prefetch_uses_book_only_source():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    trader = make(ticks=ticks, **ULTRA)
    price_calls, book_calls = [], []

    async def price(symbol):
        price_calls.append(symbol)
        return 100.0

    async def book(symbol):
        book_calls.append(symbol)
        ticks.record_book(symbol, _book(99.995, 100.005))
        return True

    trader._price_source = price
    trader.set_book_source(book)
    assert await trader.open_trade(candidate()) is None
    assert trader.rejection_reason("BTC/USDT") == "no_orderbook"
    await asyncio.sleep(0.01)
    assert book_calls == ["BTC/USDT"] and price_calls == []
    trade = await trader.open_trade(candidate())
    assert trade is not None
    assert trade.entry_price == pytest.approx(100.005)  # LONG روی Ask واقعی


async def test_failed_prefetch_is_not_hammered_every_scan():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    trader = make(ticks=ticks, **ULTRA)
    calls = []

    async def failing(symbol):
        calls.append(symbol)
        raise TimeoutError("pool")

    trader.set_book_source(failing)
    for _ in range(3):
        assert await trader.open_trade(candidate()) is None
        await asyncio.sleep(0.01)
    assert calls == ["BTC/USDT"]


async def test_healthy_ultra_candidate_with_ready_book_opens():
    """نامزد سالم + دفتر آماده → AutoTrader رد نمی‌کند."""
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    ticks.record_book("BTC/USDT", _book(99.995, 100.005))
    trader = make(ticks=ticks, **ULTRA)
    trade = await trader.open_trade(candidate(volatility_per_second=0.08))
    assert trade is not None, trader.rejection_reason("BTC/USDT")
    assert trade.entry_price == pytest.approx(100.005)
    assert trade.extra.get("spread_percent", trade.extra.get("execution", {}).get("spread_percent", 0.01)) \
        == pytest.approx(0.01, rel=0.05)


async def test_short_enters_on_real_bid():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    ticks.record_book("BTC/USDT", _book(99.995, 100.005))
    trader = make(ticks=ticks, **ULTRA)
    trade = await trader.open_trade(candidate(direction="SHORT"))
    assert trade is not None and trade.entry_price == pytest.approx(99.995)


async def test_target_unreachable_only_when_volatility_cannot_cover_cost():
    trader = make(**{**ULTRA, "engine_mode": "scan"})
    # σ×√180 ≈ 0.067٪ < ۲×هزینهٔ ۰٫۱۲٪ → واقعاً دست‌نیافتنی
    assert await trader.open_trade(candidate(volatility_per_second=0.005)) is None
    assert trader.rejection_reason("BTC/USDT").startswith("target_unreachable")
    # σ×√180 ≈ 0.40٪ کافی است → رد نمی‌شود
    trader2 = make(**{**ULTRA, "engine_mode": "scan"})
    assert await trader2.open_trade(candidate(volatility_per_second=0.03)) is not None


async def test_negative_edge_inactive_before_minimum_sample():
    trader = make(edge_guard_enabled=True, edge_guard_min_trades=50)
    trader.edge_stats = lambda: {"trades": 49, "mean": -1.0, "upper95": -0.5}
    assert await trader.open_trade(candidate()) is not None
    trader2 = make(edge_guard_enabled=True, edge_guard_min_trades=50)
    trader2.edge_stats = lambda: {"trades": 60, "mean": -1.0, "upper95": -0.5}
    assert await trader2.open_trade(candidate()) is None
    assert trader2.rejection_reason("BTC/USDT") == "negative_edge"


def test_thresholds_were_not_lowered():
    config = AutoTradeConfig().validated()
    assert config.reach_ratio == 0.5
    assert config.max_spread_stop_fraction == 0.33
    assert config.max_spread_percent == 0.25
    assert config.stale_after_seconds == 10.0
    assert config.edge_guard_min_trades == 50
    assert config.diagnostic_only is False


# ---------------------------------------------------------------------------
# ۴) حالت تشخیصی (بدون سفارش)
# ---------------------------------------------------------------------------
async def test_diagnostic_mode_runs_every_gate_but_never_opens():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)
    ticks.record_book("BTC/USDT", _book(99.995, 100.005))
    repo = Repo()
    trader = make(repo=repo, ticks=ticks, diagnostic_only=True, **ULTRA)
    events = []
    trader._emit = lambda kind, payload=None: events.append((kind, payload))
    assert await trader.open_trade(candidate()) is None
    assert trader.rejection_reason("BTC/USDT") == "diagnostic_only"
    assert repo.rows == {} and trader.open_trades == []
    passed = [p for kind, p in events if kind == "diagnostic_pass"]
    assert passed and passed[0]["entry"] == pytest.approx(100.005)
    assert audit.normalize_reason("diagnostic_only") == "diagnostic_only"


async def test_diagnostic_mode_still_reports_the_real_blocking_reason():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0, bid=99.9, ask=100.1)  # اسپرد بزرگ
    trader = make(ticks=ticks, diagnostic_only=True, **ULTRA)
    assert await trader.open_trade(candidate()) is None
    assert trader.rejection_reason("BTC/USDT").startswith("spread_eats_stop")


def test_diagnostic_setting_flows_into_engine_config():
    from trading.scalp_service import ScalpService

    class Settings:
        def get(self, key, default=None):
            return {"scalp.diagnostic_only": "true"}.get(key, default)

    config = ScalpService(NS(settings=Settings())).build_trader_config()
    assert config.diagnostic_only is True


# ---------------------------------------------------------------------------
# ۵) اولترا: نامزد و کش گردش
# ---------------------------------------------------------------------------
def _moving_engine(symbol="BTC/USDT", *, skew_ms=0.0):
    ticks = TickEngine(stale_after_seconds=10)
    now = _now_ms()
    if skew_ms:
        ticks.observe_exchange_clock(now - skew_ms, now)
    for i in range(8):
        stamp = now - (7 - i) * 1000
        ticks._history.setdefault(symbol, __import__("collections").deque(maxlen=600)).append(
            (stamp, 100.0 * (1 + 0.0002 * i)))
    ticks.record(symbol, 100.0 * (1 + 0.0002 * 8), source="rest", exchange_ts=now - skew_ms)
    return ticks


async def test_ultra_generates_candidate_from_rest_ticks_under_clock_skew():
    ticks = _moving_engine(skew_ms=25_000)
    source = UltraScalpSource(lambda: ticks, settings=lambda k, d: {"scalp.min_liquidity": 0}.get(k, d))
    found = await source.scan()
    assert [c.symbol for c in found] == ["BTC/USDT"]
    assert found[0].direction == "LONG"
    assert source.last_stats["stale"] == 0


async def test_ultra_scan_does_not_wait_on_tickers_every_second():
    ticks = _moving_engine()
    calls = []

    async def tickers():
        calls.append(1)
        return [NS(symbol="BTC/USDT", turnover_24h=5e7)]

    source = UltraScalpSource(lambda: ticks, tickers_source=tickers)
    for _ in range(5):
        await source.scan()
    assert len(calls) == 1


async def test_slow_tickers_never_block_scan_after_first_load():
    ticks = _moving_engine()
    gate = asyncio.Event()
    calls = []

    async def tickers():
        calls.append(1)
        if len(calls) > 1:
            await gate.wait()
        return [NS(symbol="BTC/USDT", turnover_24h=5e7)]

    source = UltraScalpSource(lambda: ticks, tickers_source=tickers)
    await source.scan()
    source._turnover_at -= 3600  # کش منقضی
    started = time.monotonic()
    found = await asyncio.wait_for(source.scan(), timeout=1.0)
    assert time.monotonic() - started < 0.5
    assert found and found[0].turnover_24h == 5e7  # از کش قبلی
    gate.set()
    await asyncio.sleep(0)


async def test_unavailable_tickers_do_not_break_scan():
    ticks = _moving_engine()

    async def tickers():
        raise TimeoutError("pool")

    source = UltraScalpSource(lambda: ticks, tickers_source=tickers,
                              settings=lambda k, d: d)
    assert await source.scan()


# ---------------------------------------------------------------------------
# ۶) AsyncRunner: کار در حال اجرا بسته نمی‌شود
# ---------------------------------------------------------------------------
@pytest.fixture()
def runner(qt_application):
    pytest.importorskip("PySide6")
    from ui.controllers.async_runner import AsyncRunner

    instance = AsyncRunner()
    instance.start()
    yield instance
    instance.stop()


def _pump(qt_application, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qt_application.processEvents()
        time.sleep(0.01)


def test_superseding_a_running_task_cancels_it_cleanly(qt_application, runner):
    started = threading.Event()
    outcome: dict[str, str] = {}

    async def slow():
        started.set()
        try:
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            outcome["first"] = "cancelled"
            raise
        except GeneratorExit:
            outcome["first"] = "closed_from_outside"
            raise

    errors: list[str] = []
    runner.submit("terminal-orderbook", slow(), on_error=lambda m, e=None: errors.append(m))
    assert started.wait(2)
    done: list[object] = []
    runner.submit("terminal-orderbook", asyncio.sleep(0, result="ok"), on_success=done.append)
    _pump(qt_application, 0.4)
    assert outcome.get("first") == "cancelled"
    assert done == ["ok"]
    assert not any("reuse" in m for m in errors)


def test_unstarted_superseded_coroutine_is_closed(qt_application, runner):
    async def never():
        return 1

    coro = never()
    runner._close_if_unstarted(coro)
    _pump(qt_application, 0.1)
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED


def test_shielded_network_error_is_not_logged_as_error(caplog):
    from ui.controllers.async_runner import _log_loop_exception

    caplog.set_level(logging.DEBUG)
    _log_loop_exception(None, {"message": "exception in shielded future", "exception": TimeoutError()})
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    _log_loop_exception(None, {"message": "boom", "exception": ValueError("bug")})
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]
