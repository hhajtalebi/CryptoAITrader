"""2.3.0 execution regressions. All prices/orders are deterministic test doubles."""
import asyncio
import time
from types import SimpleNamespace as NS

import pytest

from app.database.repositories.trade_repository import PaperTradeRepository
from trading.auto_trader import AutoTrader, AutoTradeConfig, LiveTradingNotEnabledError
from trading.paper_execution import close_paper_position
from trading.price_cache import TickEngine
from trading.trade_monitor import position_from_record


class Repo:
    def __init__(self):
        self.rows = {}
        self.closes = []

    def open_trade(self, **data):
        row = dict(data, id=len(self.rows) + 1, status="open")
        self.rows[row["id"]] = row
        return row

    def get_by_id(self, tid):
        return self.rows.get(tid)

    def open_trades(self, user_id=None):
        return [r for r in self.rows.values() if r["status"] == "open"]

    def close_trade(self, tid, *, exit_price, fee, **kwargs):
        row = self.rows[tid]
        if row["status"] != "open":
            return None
        pnl = (exit_price - row["entry_price"]) * (1 if row["side"] == "long" else -1) * row["quantity"]
        row.update(status="closed", pnl=pnl-row["fee"]-fee, exit_price=exit_price, exit_fee=fee)
        self.closes.append(tid)
        return row


def candidate(symbol="BTC/USDT", **values):
    return NS(**dict({"symbol": symbol, "direction": "LONG", "score": 80.0}, **values))


def make(repo=None, ticks=None, **config):
    async def price(symbol):
        await asyncio.sleep(0)
        return 100.0
    trader = AutoTrader(config=AutoTradeConfig(slippage_percent=0, **config),
                        price_source=price, repository=repo or Repo())
    if ticks is not None:
        trader.attach_tick_engine(ticks)
    return trader


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
async def test_planned_levels_are_net_dollars_and_metadata_reaches_managed(direction):
    trader = make(fee_rate=.001, target_profit=3, max_loss=2, leverage=20)
    trade = await trader.open_trade(candidate(direction=direction))
    assert trade is not None
    assert trade.extra["entry_fee"] == pytest.approx(.2)
    assert trade.net_unrealised(trade.target_price) == pytest.approx(3)
    assert trade.net_unrealised(trade.stop_price) == pytest.approx(-2)
    assert trade.net_unrealised(trade.entry_price) == pytest.approx(-.4)
    price = trade.entry_price + trade.direction_sign * 2
    trade.mark(price, trader.config)
    assert trade.break_even_armed
    assert trade.net_unrealised(trade.effective_stop) == pytest.approx(0)


async def test_breakeven_waits_for_net_trigger_and_never_weakens_stop():
    trader = make(fee_rate=.001, leverage=100, max_loss=4, target_profit=4)
    trade = await trader.open_trade(candidate())
    trade.mark(100.15, trader.config)  # gross 1.5, net negative
    assert not trade.break_even_armed
    trade.effective_stop = 100.25
    trade.mark(100.5, trader.config)
    assert trade.break_even_armed
    assert trade.effective_stop >= 100.25


async def test_costs_larger_than_loss_budget_reject_instead_of_tiny_stop():
    trader = make(fee_rate=.001, leverage=200, max_loss=3)
    assert await trader.open_trade(candidate()) is None
    assert trader.rejection_reason("BTC/USDT") == "fees_exceed_loss_budget"


@pytest.mark.parametrize("values,reason", [
    ({"take_profit": 99}, "invalid_risk_levels"),
    ({"stop_loss": 90}, "risk_exceeds_loss_budget"),
    ({"take_profit": 100.01}, "poor_net_reward_risk"),
    ({"direction": "WAIT"}, "invalid_candidate"),
    ({"observed_at": time.time()-1000}, "stale_candidate"),
])
async def test_bad_candidate_has_explicit_reason(values, reason):
    trader = make()
    assert await trader.open_trade(candidate(**values)) is None
    assert trader.rejection_reason("BTC/USDT") == reason


async def test_manual_and_scanner_cannot_duplicate_symbol_after_await():
    trader = make()
    results = await asyncio.gather(*(trader.open_trade(candidate()) for _ in range(8)))
    assert sum(r is not None for r in results) == 1
    assert len(trader._repo.rows) == 1


async def test_capacity_is_checked_inside_entry_lock():
    trader = make(max_concurrent=1)
    results = await asyncio.gather(trader.open_trade(candidate()), trader.open_trade(candidate("ETH/USDT")))
    assert sum(r is not None for r in results) == 1


async def test_existing_repository_positions_prevent_duplicate():
    repo = Repo()
    repo.open_trade(symbol="BTC/USDT", status="open")
    trader = make(repo=repo)
    assert await trader.open_trade(candidate()) is None


async def test_close_is_single_flight_and_uses_exit_notional_fee():
    trader = make(fee_rate=.001)
    trade = await trader.open_trade(candidate())
    async def price(symbol):
        await asyncio.sleep(.01)
        return 101.0
    trader._price_source = price
    await asyncio.gather(*(trader.close_trade(trade, "manual") for _ in range(8)))
    assert trader._repo.closes == [trade.trade_id]
    assert trader._repo.rows[trade.trade_id]["exit_fee"] == pytest.approx(trade.quantity*101*.001)


async def test_failed_close_keeps_position_retryable():
    trader = make()
    trade = await trader.open_trade(candidate())
    async def broken(symbol):
        raise RuntimeError("network")
    trader._price_source = broken
    with pytest.raises(RuntimeError):
        await trader.close_trade(trade, "manual")
    assert trade in trader.open_trades
    assert not trader._closing


async def test_stale_quote_cannot_be_refreshed_by_reading_it():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100)
    trader = make(ticks=ticks)
    trade = await trader.open_trade(candidate())
    quote = ticks.get("BTC/USDT")
    quote.processed_ts_ms -= 60_000
    assert await trader.close_trade(trade, "manual") is None
    assert trade in trader.open_trades


async def test_rest_fallback_must_populate_tick_cache():
    ticks = TickEngine()
    trader = make(ticks=ticks)
    assert await trader.open_trade(candidate()) is None
    async def fresh(symbol):
        ticks.record(symbol, 100, source="rest")
        return 100
    trader._price_source = fresh
    assert await trader.open_trade(candidate()) is not None


async def test_slow_scan_does_not_block_monitor_and_stop_cancels_scan():
    trader = make(poll_seconds=.25)
    scan_started = asyncio.Event()
    scan_cancelled = asyncio.Event()
    checks = []
    async def scan():
        scan_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            scan_cancelled.set()
    async def monitor():
        checks.append(time.monotonic())
    trader._candidate_source = scan
    trader.check_open_trades = monitor
    await trader.start()
    await asyncio.wait_for(scan_started.wait(), .5)
    await asyncio.sleep(.6)
    await trader.stop()
    assert len(checks) >= 3
    assert scan_cancelled.is_set()


async def test_manual_position_still_monitored_with_auto_entries_off():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100)
    trader = make(ticks=ticks)
    trade = await trader.open_trade(candidate())
    assert not trader.is_running
    await trader.stop()
    ticks.record("BTC/USDT", 90)
    await asyncio.sleep(.03)
    assert trade not in trader.open_trades


async def test_live_entry_without_confirmation_never_becomes_paper():
    trader = make(mode="live", live_confirmation="wrong")
    with pytest.raises(LiveTradingNotEnabledError):
        await trader.open_trade(candidate())
    assert not trader._repo.rows


async def test_candidate_margin_cannot_bypass_portfolio_cap():
    trader = make()
    trader._portfolio_source = lambda: dict(balance=20, used_margin=10, open_count=0)
    assert await trader.open_trade(candidate(margin=10)) is None
    assert trader.rejection_reason("BTC/USDT") == "no_available_margin"


@pytest.mark.parametrize("side,expected", [("long", 99), ("short", 101)])
async def test_unmanaged_paper_close_uses_fresh_side_aware_price(side, expected):
    repo = Repo()
    row = repo.open_trade(symbol="BTC/USDT", mode="paper", side=side, quantity=2,
                          entry_price=100, fee=.2, extra={"fee_rate": .001})
    ticks = TickEngine()
    async def refresh(symbol):
        ticks.record(symbol, 100, bid=99, ask=101, source="rest")
    result = await close_paper_position(repo, row["id"], ticks, refresh)
    assert result["exit_price"] == expected
    assert result["exit_fee"] == pytest.approx(2*expected*.001)


async def test_unmanaged_live_close_is_never_simulated():
    repo = Repo()
    row = repo.open_trade(symbol="BTC/USDT", mode="live")
    with pytest.raises(RuntimeError, match="Live"):
        await close_paper_position(repo, row["id"], TickEngine(), None)


def test_repository_percent_and_monitor_both_use_net_margin_return(database):
    repo = PaperTradeRepository(database)
    row = repo.open_trade(symbol="BTC/USDT", side="long", quantity=2, entry_price=100,
                          leverage=10, fee=1, extra={"fee_rate": .001})
    position = position_from_record(row)
    assert position.unrealised(101)[0] == pytest.approx(.798)
    result = repo.close_trade(row["id"], exit_price=101, fee=.202)
    assert result["pnl_percent"] == pytest.approx(result["pnl"] / 20 * 100)


async def test_daily_limit_survives_new_engine(database):
    repo = PaperTradeRepository(database)
    row = repo.open_trade(symbol="BTC/USDT", side="long", quantity=1, entry_price=100)
    repo.close_trade(row["id"], exit_price=90)
    assert repo.daily_realised_pnl() == -10
    trader = make(repo=repo, daily_loss_limit=5)
    assert await trader.open_trade(candidate()) is None
    assert trader.rejection_reason("BTC/USDT") == "daily_loss_limit"


async def test_slow_quote_fetch_does_not_delay_another_fresh_manual_entry():
    ticks = TickEngine()
    ticks.record("ETH/USDT", 100)
    trader = make(ticks=ticks)
    started = asyncio.Event()
    async def slow(symbol):
        started.set()
        await asyncio.Event().wait()
    trader._price_source = slow
    pending = asyncio.create_task(trader.open_trade(candidate("BTC/USDT")))
    await started.wait()
    fresh = await asyncio.wait_for(trader.open_trade(candidate("ETH/USDT")), timeout=.2)
    assert fresh is not None
    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
