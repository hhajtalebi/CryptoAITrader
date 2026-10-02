"""نسخهٔ ۲.۵.۷ — چرا همهٔ اسکالپ‌ها ضرر بودند: اصلاحات اجرای معامله."""

from __future__ import annotations

import asyncio
import math
import random
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_v230_execution import Repo, candidate, make
from trading.auto_trader import AutoTradeConfig, ManagedTrade
from trading.micro_plan import plan_levels
from trading.price_cache import TickEngine
from trading.ultra_scalp import volatility_per_second

ULTRA = dict(engine_mode="ultra", margin_per_trade=10, leverage=50, target_profit=2, max_loss=2,
             fee_rate=0.0006, max_hold_seconds=180, min_liquidity=0, max_total_margin_percent=100,
             daily_loss_limit=10_000, max_concurrent=10)


def _trade(side="long", lock=0.1):
    plan = plan_levels(10, 50, 2, 2, 0.0006)
    entry = 100.0
    sign = 1 if side == "long" else -1
    q = plan.notional / entry
    target = (entry * sign + (2 + plan.entry_fee) / q) / (sign - 0.0006)
    stop = (entry * sign + (plan.entry_fee - 2) / q) / (sign - 0.0006)
    config = AutoTradeConfig(break_even_trigger=1.0, break_even_lock=lock).validated()
    trade = ManagedTrade(trade_id=1, symbol="X", side=side, entry_price=entry, quantity=q, leverage=50,
                         target_price=target, stop_price=stop, opened_at=datetime.now(UTC),
                         extra={"round_trip_fee": plan.round_trip_fee, "entry_fee": plan.entry_fee,
                                "fee_rate": 0.0006})
    return trade, config


# ---------------------------------------------------------------------------
# سر‌به‌سر: دیگر زیان ثبت نمی‌شود
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("side", ["long", "short"])
def test_break_even_exit_locks_small_profit(side):
    trade, config = _trade(side)
    sign = 1 if side == "long" else -1
    trade.mark(100.0 + sign * 0.35, config)  # سود خالص > ۱ دلار
    assert trade.break_even_armed
    assert trade.net_unrealised(trade.effective_stop) == pytest.approx(0.1)
    back = trade.effective_stop
    assert trade.should_close(back, datetime.now(UTC), 180) == "break_even"
    assert trade.net_unrealised(back) > 0


def test_break_even_lock_is_capped_and_zero_keeps_old_behaviour():
    assert AutoTradeConfig(break_even_trigger=0.4, break_even_lock=5).validated().break_even_lock == pytest.approx(0.2)
    trade, config = _trade(lock=0.0)
    trade.mark(100.35, config)
    assert trade.net_unrealised(trade.effective_stop) == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# نوسان ثانیه‌ای و دروازهٔ دسترس‌پذیری هدف
# ---------------------------------------------------------------------------
def test_volatility_per_second_recovers_known_sigma():
    rng = random.Random(7)
    sigma = 0.02  # درصد در ثانیه
    points, price, t = [], 100.0, 0.0
    for _ in range(100):  # هر ۳ ثانیه یک نقطه
        t += 3000.0
        price *= math.exp(rng.gauss(0, sigma / 100 * math.sqrt(3)))
        points.append((t, price))
    measured = volatility_per_second(points, now_ms=t)
    assert measured == pytest.approx(sigma, rel=0.2)
    assert volatility_per_second(points[:4], now_ms=t) == 0.0  # داده ناکافی = نامعلوم


async def test_calm_symbol_is_rejected_as_unreachable():
    trader = make(**{**ULTRA, "engine_mode": "scan"})
    assert await trader.open_trade(candidate(volatility_per_second=0.005)) is None
    assert trader.rejection_reason("BTC/USDT").startswith("target_unreachable")


async def test_volatile_symbol_passes_reach_gate():
    trader = make(**{**ULTRA, "engine_mode": "scan"})
    assert await trader.open_trade(candidate(volatility_per_second=0.08)) is not None


async def test_unknown_volatility_is_not_blocked():
    trader = make(**{**ULTRA, "engine_mode": "scan"})
    assert await trader.open_trade(candidate()) is not None


# ---------------------------------------------------------------------------
# Bid/Ask واقعی پیش از ورود اولترا + اسپرد نسبت به حد ضرر
# ---------------------------------------------------------------------------
async def test_ultra_without_book_prefetches_and_skips_once():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)  # فید کل بازار: بدون Bid/Ask
    calls = []
    trader = make(ticks=ticks, **ULTRA)

    async def refresh(symbol):
        calls.append(symbol)
        ticks.record(symbol, 100.0, bid=99.995, ask=100.005)
        return 100.0

    trader._price_source = refresh
    assert await trader.open_trade(candidate()) is None
    assert trader.rejection_reason("BTC/USDT") == "no_orderbook"
    await asyncio.sleep(0.01)
    assert calls == ["BTC/USDT"]
    trade = await trader.open_trade(candidate())
    assert trade is not None
    assert trade.entry_price == pytest.approx(100.005)  # ورود LONG روی Ask واقعی


async def test_spread_that_eats_the_stop_is_rejected():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0, bid=99.9, ask=100.1)  # اسپرد ۰٫۲٪ در برابر حد ضرر ~۰٫۲۸٪
    trader = make(ticks=ticks, **ULTRA)
    assert await trader.open_trade(candidate()) is None
    assert trader.rejection_reason("BTC/USDT").startswith("spread_eats_stop")


async def test_scan_mode_entry_is_never_delayed_by_book_fetch():
    ticks = TickEngine()
    ticks.record("ETH/USDT", 100.0)
    trader = make(ticks=ticks)

    async def hang(_symbol):
        await asyncio.Event().wait()

    trader._price_source = hang
    fresh = await asyncio.wait_for(trader.open_trade(candidate("ETH/USDT")), timeout=0.2)
    assert fresh is not None


# ---------------------------------------------------------------------------
# آمار دلیل خروج
# ---------------------------------------------------------------------------
async def test_exit_reasons_are_counted():
    trader = make(repo=Repo())
    trade = await trader.open_trade(candidate())
    await trader.close_trade(trade, "timeout")
    stats = trader.edge_stats()
    assert stats["exit_reasons"] == {"timeout": 1}


def test_timeout_after_small_move_is_a_loss_even_in_right_direction():
    """مستندسازی ریشه: حرکت درست ولی کوچک‌تر از هزینه ⇒ زیان خالص."""
    trade, _ = _trade()
    price = 100.0 * (1 + 0.0009)  # ۰٫۰۹٪ در جهت درست
    assert trade.should_close(price, trade.opened_at + timedelta(seconds=181), 180) == "timeout"
    assert trade.net_unrealised(price) < 0
