"""Offline regressions: redundancy, quote age, same-provider routing, rotation."""
import asyncio
import time
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from app.core.constants import ConnectionStatus as Status
from app.core.models import Ticker, OrderBook, OrderBookLevel
from market.engine import MarketDataEngine
from market.live_feed import LivePriceFeed
from market.redundant_stream import RedundantStream
from trading.confidence_source import ConfidenceCandidateSource
from trading.price_cache import TickEngine
from trading.universe import RotatingUniverse


def ticker(symbol="BTC/USDT", price=100, turnover=9e6, stamp=None):
    return Ticker(symbol, price, price, price, 100, turnover, 0,
                  stamp if stamp is not None else int(time.time()))


class Socket:
    def __init__(self, **callbacks):
        self.callbacks = callbacks
        self.status = Status.DISCONNECTED
        self.started = self.stopped = 0
        self.tickers = set()
        self.candles = set()

    async def start(self):
        self.started += 1
        self.status = Status.CONNECTED
        self.callbacks["on_status_change"](self.status)

    async def stop(self):
        self.stopped += 1
        self.status = Status.DISCONNECTED
        self.callbacks["on_status_change"](self.status)

    async def subscribe_ticker(self, symbol):
        self.tickers.add(symbol)

    async def unsubscribe_ticker(self, symbol):
        self.tickers.discard(symbol)

    async def subscribe_candles(self, symbol, timeframe):
        self.candles.add((symbol, timeframe))

    async def unsubscribe_candles(self, symbol, timeframe):
        self.candles.discard((symbol, timeframe))

    async def unsubscribe_all(self):
        self.tickers.clear()
        self.candles.clear()


class Provider:
    name = "same-exchange"
    capabilities = NS(supports_websocket=True)
    def __init__(self):
        self.sockets = []
        self.rest_calls = 0

    def create_websocket_client(self, **callbacks):
        client = Socket(**callbacks)
        self.sockets.append(client)
        return client

    async def get_ticker(self, symbol):
        self.rest_calls += 1
        return ticker(symbol, 101)

    async def get_all_tickers(self):
        self.rest_calls += 1
        return [ticker()]

    async def get_orderbook(self, symbol, depth=5):
        return OrderBook(symbol, [OrderBookLevel(100.9, 2)], [OrderBookLevel(101.1, 3)], int(time.time()))


async def test_two_same_provider_sockets_keep_serving_after_one_disconnects():
    provider = Provider()
    received = []
    engine = MarketDataEngine(provider)
    engine.add_ticker_listener(received.append)
    await engine.ensure_streaming()
    await engine.subscribe_symbol("BTC/USDT", "1m")
    assert len(provider.sockets) == 2
    a, b = provider.sockets
    assert a.tickers == b.tickers == {"BTC/USDT"}
    assert a.candles == b.candles == {("BTC/USDT", "1m")}
    a.status = Status.RECONNECTING
    a.callbacks["on_status_change"](a.status)
    b.callbacks["on_ticker"](ticker())
    assert engine.websocket_status is Status.CONNECTED
    assert len(received) == 1
    await engine._websocket.stop()
    assert a.stopped == b.stopped == 1


async def test_dedup_and_out_of_order_frames_cannot_roll_price_back():
    p = Provider()
    got = []
    stream = RedundantStream(p.create_websocket_client, on_ticker=got.append,
                             on_candle=lambda *a: None, on_status_change=lambda s: None)
    await stream.start()
    item = ticker(stamp=int(time.time()))
    p.sockets[0].callbacks["on_ticker"](item)
    p.sockets[1].callbacks["on_ticker"](item)
    p.sockets[1].callbacks["on_ticker"](replace(item, timestamp=item.timestamp-1, last_price=90))
    assert got == [item]
    p.sockets[1].callbacks["on_ticker"](replace(item, timestamp=item.timestamp+1, last_price=102))
    assert len(got) == 2
    await stream.stop()


async def test_watchdog_recovers_only_silent_socket_and_restores_subscriptions():
    p = Provider()
    stream = RedundantStream(p.create_websocket_client, on_ticker=lambda t: None,
                             on_candle=lambda *a: None, on_status_change=lambda s: None)
    await stream.start()
    await stream.subscribe_ticker("BTC/USDT")
    stream._last_data[0] -= 61
    await stream._check_health()
    assert p.sockets[0].started == 2
    assert p.sockets[0].stopped == 1
    assert p.sockets[1].started == 1
    assert stream.status is Status.CONNECTED
    await stream.stop()
    assert stream._task is None


async def test_watchlist_diff_does_not_unsubscribe_chart_or_unchanged_symbols():
    p = Provider()
    engine = MarketDataEngine(p)
    await engine.ensure_streaming()
    await engine.subscribe_symbol("BTC/USDT", "1m")
    await engine.set_watchlist_subscriptions(["BTC/USDT", "ETH/USDT"])
    await engine.set_watchlist_subscriptions(["SOL/USDT"])
    for client in p.sockets:
        assert client.tickers == {"BTC/USDT", "SOL/USDT"}
        assert client.candles == {("BTC/USDT", "1m")}
    await engine._websocket.stop()


async def test_stale_websocket_cache_is_not_a_permanent_rest_replacement():
    p = Provider()
    engine = MarketDataEngine(p)
    engine._live_tickers["BTC/USDT"] = ticker(stamp=int(time.time())-120)
    assert (await engine.get_ticker("BTC/USDT")).last_price == 101
    assert p.rest_calls == 1
    await engine.get_ticker("BTC/USDT", max_age_seconds=0)
    assert p.rest_calls == 2


async def test_real_rest_snapshot_updates_execution_cache_including_book():
    p = Provider()
    ticks = TickEngine()
    await MarketDataEngine(p).refresh_execution_quote("BTC/USDT", ticks)
    quote = ticks.get("BTC/USDT")
    assert quote.source == "rest"
    assert quote.entry_price("long") == 101.1
    assert quote.exit_price("long") == 100.9
    assert quote.bid_depth == 2
    assert not ticks.is_stale("BTC/USDT")


def test_exchange_timestamp_age_and_order_are_respected():
    ticks = TickEngine(stale_after_seconds=10)
    old = int(time.time())-60
    ticks.record("BTC/USDT", 100, exchange_ts=old)
    assert ticks.is_stale("BTC/USDT")
    ticks.record("BTC/USDT", 101, exchange_ts=int(time.time()))
    assert not ticks.is_stale("BTC/USDT")
    assert ticks.record("BTC/USDT", 90, exchange_ts=old) is None
    assert ticks.price("BTC/USDT") == 101


def test_fresh_book_survives_last_only_tick_but_old_book_is_not_used():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100, bid=99, ask=101)
    quote = ticks.record("BTC/USDT", 100.1)
    assert quote.entry_price("long") == 101
    quote.book_ts_ms -= 20_000
    assert quote.entry_price("long") == 100.1
    quote = ticks.record("BTC/USDT", 100.2)
    assert quote.bid == quote.ask == 0


def test_nonfinite_prices_do_not_enter_cache():
    ticks = TickEngine()
    for value in (float("nan"), float("inf"), -1, 0):
        assert ticks.record("BTC/USDT", value) is None


def test_unchanged_real_price_update_renews_freshness():
    feed = LivePriceFeed(MarketDataEngine(Provider()))
    a = feed._store(ticker(), source="rest")
    b = feed._store(ticker(), source="rest")
    assert b is not None
    assert b.updated_at >= a.updated_at
    assert b.exchange_ts > 0


def test_clear_drops_exchange_quotes_and_history():
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100)
    ticks.clear()
    assert ticks.get("BTC/USDT") is None
    assert ticks.history("BTC/USDT") == []


def test_rotation_covers_market_and_prioritizes_favorites():
    universe = RotatingUniverse()
    items = [ticker(f"C{i}/USDT", turnover=1e7-i) for i in range(12)]
    seen = set()
    for _ in range(6):
        batch = universe.select(items, limit=4, favorites=["C11/USDT"], min_turnover=2e6)
        assert batch[0] == "C11/USDT"
        assert len(set(batch)) == 4
        seen.update(batch)
    assert seen == {t.symbol for t in items}


def test_selected_list_rotates_without_leaking_other_markets():
    universe = RotatingUniverse()
    selected = ["A/USDT", "B/USDT", "C/USDT"]
    first = universe.select([ticker()], selected=selected, limit=2)
    second = universe.select([ticker()], selected=selected, limit=2)
    assert set(first+second) == set(selected)
    assert universe.select([ticker()], selected=[], limit=2) == []


def test_low_liquidity_is_not_rescued_by_favorite_status():
    universe = RotatingUniverse()
    assert universe.select([ticker(turnover=1)], limit=5, favorites=["BTC/USDT"], min_turnover=100) == []


async def test_selected_confidence_scan_analyzes_selected_before_filtering():
    calls = []
    class Settings:
        def get_int(self, key, default):
            return default
        def get(self, key, default):
            return default
    async def scan(**kwargs):
        calls.append(kwargs)
        return NS(signals=[])
    app = NS(settings=Settings(), market=Provider(), scan_market=scan)
    source = ConfidenceCandidateSource(app)
    await source.scan(symbols=["ETH/USDT"])
    assert calls[0]["symbols"] == ["ETH/USDT"]
    await source.scan(symbols=[])
    assert len(calls) == 1


def test_confidence_candidates_keep_signal_risk_levels():
    source = ConfidenceCandidateSource(NS())
    signal = NS(symbol="BTC/USDT", direction="LONG", confidence=80,
                entry_min=99, entry_max=101, stop_loss=97, take_profits=[104, 106])
    candidate = source._to_candidate(signal, 75)
    assert candidate.stop_loss == 97
    assert candidate.take_profit == 104


async def test_cancelled_waiter_does_not_duplicate_inflight_rest_request():
    engine = MarketDataEngine(Provider())
    gate = asyncio.Event()
    calls = []
    async def fetch():
        calls.append(1)
        await gate.wait()
        return 42
    first = asyncio.create_task(engine._deduplicated("price", fetch))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    second = asyncio.create_task(engine._deduplicated("price", fetch))
    gate.set()
    assert await second == 42
    assert calls == [1]
    assert not engine._inflight
