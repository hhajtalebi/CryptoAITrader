"""
آزمون‌های نسخهٔ ۲.۶.۲ — ساعت ویندوز ~۱۰٫۵ ساعت جلوتر از صرافی.

لاگ کاربر: `2026-10-01T20:44:51-07:00` (= 03:44 UTC روز بعد) در حالی که زمان
واقعی صرافی 17:14 UTC بود؛ ساعت ایران با منطقهٔ زمانی Pacific. سقف قبلی
اصلاح (۶ ساعت) این اختلاف را «نامعقول» می‌دانست و هیچ اصلاحی اعمال نمی‌شد:
۱۰۳۸ نماد stale_data و دفتر سفارش همیشه no_orderbook.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace as NS

import pytest

from market.engine import MarketDataEngine
from trading.price_cache import TickEngine
from trading.ultra_scalp import UltraScalpSource

from tests.test_v230_execution import candidate, make

USER_SKEW_MS = 10.4 * 3600 * 1000  # ساعت محلی جلوتر


def _now_ms() -> float:
    return time.time() * 1000.0


def _book(bid, ask, timestamp):
    return NS(best_bid=bid, best_ask=ask, bids=[NS(price=bid, quantity=3.0)],
              asks=[NS(price=ask, quantity=3.0)], timestamp=timestamp)


def test_user_skew_is_now_calibrated():
    ticks = TickEngine()
    exchange_now = _now_ms() - USER_SKEW_MS
    assert ticks.observe_exchange_clock(exchange_now, _now_ms()) == pytest.approx(USER_SKEW_MS, abs=1000)
    ticks.record("ETH/USDT", 2689.0, source="rest", exchange_ts=exchange_now)
    assert not ticks.is_stale("ETH/USDT")


def test_user_skew_book_is_accepted_after_calibration():
    ticks = TickEngine()
    exchange_now = _now_ms() - USER_SKEW_MS
    ticks.observe_exchange_clock(exchange_now, _now_ms())
    ticks.record("BNB/USDT", 769.7, source="rest", exchange_ts=exchange_now)
    quote = ticks.record_book("BNB/USDT", _book(769.69, 769.71, exchange_now))
    assert quote is not None and quote.book_fresh and quote.spread > 0


def test_without_calibration_the_bug_reproduces():
    ticks = TickEngine()
    exchange_now = _now_ms() - USER_SKEW_MS
    ticks.record("BNB/USDT", 769.7, source="websocket")  # WS: بدون مهر، تازه
    ticks.record("ETH/USDT", 2689.0, source="rest", exchange_ts=exchange_now)
    assert ticks.is_stale("ETH/USDT")
    ticks.record_book("BNB/USDT", _book(769.69, 769.71, exchange_now))
    assert ticks.get("BNB/USDT").bid == 0.0  # همان no_orderbook لاگ


async def test_ultra_enters_under_user_skew_end_to_end():
    ticks = TickEngine()
    exchange_now = _now_ms() - USER_SKEW_MS
    ticks.observe_exchange_clock(exchange_now, _now_ms())
    ticks.record("BNB/USDT", 769.7, source="rest", exchange_ts=exchange_now)
    ticks.record_book("BNB/USDT", _book(769.69, 769.71, exchange_now))
    trader = make(ticks=ticks, engine_mode="ultra", margin_per_trade=10, leverage=50,
                  target_profit=2, max_loss=2, fee_rate=0.0006, max_hold_seconds=180,
                  min_liquidity=0, max_total_margin_percent=100, daily_loss_limit=10_000,
                  max_concurrent=10)
    trade = await trader.open_trade(candidate("BNB/USDT"))
    assert trade is not None, trader.rejection_reason("BNB/USDT")
    assert trade.entry_price == pytest.approx(769.71)


async def test_ultra_scan_counts_rest_symbols_fresh_under_user_skew():
    ticks = TickEngine()
    now = _now_ms()
    exchange_now = now - USER_SKEW_MS
    ticks.observe_exchange_clock(exchange_now, now)
    for i in range(30):
        ticks.record(f"S{i}/USDT", 1.0 + i, source="rest", exchange_ts=exchange_now)
    source = UltraScalpSource(lambda: ticks, settings=lambda k, d: {"scalp.min_liquidity": 0}.get(k, d))
    await source.scan()
    assert source.last_stats["stale"] == 0


def test_market_engine_measures_offset_from_full_batch():
    engine = MarketDataEngine.__new__(MarketDataEngine)
    stamp = int(_now_ms() - USER_SKEW_MS)
    engine._observe_clock([NS(timestamp=stamp - i * 50) for i in range(40)])
    assert engine.exchange_clock_offset_ms == pytest.approx(USER_SKEW_MS, abs=2000)
    fresh = NS(timestamp=stamp)
    assert engine._ticker_is_fresh(fresh, 15.0, engine._offset_seconds())
    assert not engine._ticker_is_fresh(fresh, 15.0)


def test_market_engine_ignores_tiny_batches_and_sync_clocks():
    engine = MarketDataEngine.__new__(MarketDataEngine)
    engine.exchange_clock_offset_ms = 0.0
    engine._observe_clock([NS(timestamp=int(_now_ms() - USER_SKEW_MS))] * 5)
    assert engine.exchange_clock_offset_ms == 0.0
    engine._observe_clock([NS(timestamp=int(_now_ms() - 300))] * 30)
    assert engine.exchange_clock_offset_ms == 0.0


async def test_execution_quote_uses_engine_offset_when_tick_engine_uncalibrated():
    engine = MarketDataEngine.__new__(MarketDataEngine)
    engine.exchange_clock_offset_ms = USER_SKEW_MS
    stamp = int(_now_ms() - USER_SKEW_MS)

    async def get_ticker(symbol, max_age_seconds=0):
        return NS(last_price=770.0, timestamp=stamp, change_percent=0.0)

    async def get_orderbook(symbol, depth=5):
        return _book(769.99, 770.01, stamp)

    engine.get_ticker = get_ticker
    engine._provider = NS(get_orderbook=get_orderbook)
    ticks = TickEngine()
    assert await engine.refresh_execution_quote("BNB/USDT", ticks) == pytest.approx(770.0)


def _controller(offset_ms):
    from ui.controllers.main_controller import MainController

    controller = MainController.__new__(MainController)
    controller._tick_engine = NS(clock_offset_ms=offset_ms)
    controller.app = NS(market=None)
    shown = []
    controller.tr_ = NS(tr=lambda key, **kw: f"{key}|{kw.get('hours', '')}|{kw.get('direction', '')}")
    controller.status = lambda message: None
    controller._toast = lambda message, level="info": shown.append((message, level))
    return controller, shown


def test_clock_warning_shown_once():
    controller, shown = _controller(USER_SKEW_MS)
    controller._check_clock_skew()
    controller._check_clock_skew()
    assert len(shown) == 1
    message, level = shown[0]
    assert level == "warning" and "+10.4" in message and "common.clock_ahead" in message


def test_no_warning_for_small_offsets():
    controller, shown = _controller(20_000)
    controller._check_clock_skew()
    assert shown == []


def test_warning_texts_exist_in_both_languages():
    import json

    for lang in ("fa", "en"):
        data = json.load(open(f"localization/{lang}/common.json", encoding="utf-8"))
        assert {"clock_skew_warning", "clock_ahead", "clock_behind"} <= set(data)
        assert "{hours}" in data["clock_skew_warning"] and "{direction}" in data["clock_skew_warning"]
