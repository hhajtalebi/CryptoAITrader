"""2.3.1 — «چند ثانیه آنلاین، بعد قطع دائمی».

علت: از 2.3.0 حلقهٔ قیمت فهرست همهٔ نمادها را هر ۲ ثانیه بدون کش می‌خواند
و کش مشترک را هم ۰٫۱ ثانیه‌ای می‌کرد؛ ترافیک سنگین‌ترین endpoint چند برابر
شد، صرافی محدودیت نرخ (429/418) داد و شاخص آنلاین فقط به REST وابسته بود.
این آزمون‌ها بدون شبکه، رفتار اصلاح‌شده را قفل می‌کنند.
"""
import asyncio
import time
from types import SimpleNamespace as NS

import httpx
import pytest

from app.core.models import Ticker
from app.exceptions import ExchangeError, RateLimitError
from market import engine as engine_module
from market.engine import MarketDataEngine, rate_limit_retry_after
from market.live_feed import LivePriceFeed
from market.resilience import ConnectionSupervisor, ConnectivityState


def ticker(symbol="BTC/USDT", price=100.0, change=0.0):
    return Ticker(symbol, price, price, price, 100, 9e6, change, int(time.time() * 1000))


class Provider:
    name = "toobit"
    capabilities = NS(supports_websocket=False)

    def __init__(self):
        self.calls = 0
        self.fail_with = None
        self.price = 100.0

    async def connect(self):
        return None

    async def ping(self):
        return True

    async def close(self):
        return None

    async def get_all_tickers(self):
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with
        return [ticker(price=self.price), ticker("ETH/USDT", 10.0)]

    async def get_ticker(self, symbol):
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with
        return ticker(symbol, self.price)


async def test_uncached_request_still_feeds_shared_cache():
    provider = Provider()
    market = MarketDataEngine(provider)
    await market.get_all_tickers(max_age_seconds=0)
    # صفحهٔ دیگری بلافاصله همان داده را می‌خواهد: نباید درخواست دوم برود.
    await market.get_all_tickers()
    await market.get_ticker("BTC/USDT", max_age_seconds=0)
    await market.get_ticker("BTC/USDT")
    assert provider.calls == 2


async def test_rate_limit_starts_global_cooldown_without_going_offline():
    provider = Provider()
    market = MarketDataEngine(provider)
    await market.get_all_tickers()
    assert market.is_online
    provider.fail_with = RateLimitError("slow down", details={"status": 429, "retry_after": 12})
    with pytest.raises(RateLimitError):
        await market.get_all_tickers(max_age_seconds=0)
    calls = provider.calls
    assert 11 <= market.rest_cooldown_remaining <= 12
    # در مدت مکث هیچ درخواستی به صرافی نمی‌رود و برنامه آفلاین نمی‌شود.
    for _ in range(5):
        with pytest.raises(RateLimitError) as info:
            await market.get_ticker("ETH/USDT", max_age_seconds=0)
        assert info.value.details["retry_after"] > 0
    assert provider.calls == calls
    assert market.is_online
    assert market.rest_health()["rate_limit_events"] == 1
    # keepalive هم در مدت مکث پینگ نمی‌فرستد.
    provider.ping = lambda: (_ for _ in ()).throw(AssertionError("ping during cooldown"))
    assert await market.keepalive() is True


def test_rate_limit_detection_covers_status_and_exchange_codes():
    assert rate_limit_retry_after(RateLimitError("x")) == engine_module.RATE_LIMIT_COOLDOWN_SECONDS
    assert rate_limit_retry_after(ExchangeError("x", details={"status": 418})) == engine_module.IP_BAN_COOLDOWN_SECONDS
    assert rate_limit_retry_after(ExchangeError("x", details={"code": -1003})) == 30.0
    assert rate_limit_retry_after(ExchangeError("x", details={"status": 429, "retry_after": 9999})) == 300.0
    assert rate_limit_retry_after(ExchangeError("x", details={"status": 500})) is None
    assert rate_limit_retry_after(ValueError("x")) is None


async def test_snapshot_persistence_is_throttled():
    saved = []
    repo = NS(save_ticker_snapshot=lambda *a, **k: saved.append(a))
    provider = Provider()
    market = MarketDataEngine(provider, candle_repository=repo)
    await market.get_all_tickers(max_age_seconds=0)
    first = len(saved)
    market._cache._store.clear()
    await market.get_all_tickers(max_age_seconds=0)
    assert first == 2 and len(saved) == first


async def test_feed_is_fresh_from_websocket_while_rest_is_rate_limited():
    provider = Provider()
    provider.fail_with = RateLimitError("slow down", details={"status": 429})
    market = MarketDataEngine(provider)
    feed = LivePriceFeed(market, poll_interval=0.5)
    await feed.start()
    await asyncio.sleep(0.05)
    assert not feed.is_fresh
    feed._on_live_ticker(ticker(price=101))
    assert feed.is_fresh
    assert feed.data_age_seconds is not None and feed.data_age_seconds < 1
    supervisor = ConnectionSupervisor(feed, sleep=lambda _s: asyncio.sleep(3600))
    supervisor._evaluate()
    assert supervisor.state is ConnectivityState.ONLINE
    assert feed.status()["last_error"] == "RateLimitError"
    await feed.stop()


async def test_feed_does_not_hammer_or_reingest_cached_snapshot(monkeypatch):
    provider = Provider()
    market = MarketDataEngine(provider)
    feed = LivePriceFeed(market, poll_interval=0.5)
    batches = []
    feed.add_listener(batches.append)
    await feed.start()
    await asyncio.sleep(1.3)  # سه دور نظرسنجی
    await feed.stop()
    # کش مشترک ۵ ثانیه‌ای: فقط یک درخواست واقعی، یک بار ثبت.
    assert provider.calls == 1
    assert len(batches) == 1
    stamp = market.all_tickers_fetched_at
    assert feed.get("BTC/USDT").updated_at == stamp


async def test_unchanged_rest_ticks_are_fresh_but_not_marked_changed():
    provider = Provider()
    market = MarketDataEngine(provider)
    feed = LivePriceFeed(market)
    first = feed._store(ticker(price=100), "rest")
    second = feed._store(ticker(price=100), "rest")
    third = feed._store(ticker(price=101), "rest")
    assert first.changed and not second.changed and third.changed


def test_toobit_429_is_not_retried_and_carries_retry_after():
    from market.providers.toobit.rest_client import ToobitRestClient

    hits = []

    def handler(request):
        hits.append(request)
        return httpx.Response(429, headers={"Retry-After": "17"}, json={"code": -1003, "msg": "Too many requests"})

    client = ToobitRestClient()
    client._http = httpx.AsyncClient(base_url="https://api.toobit.com", transport=httpx.MockTransport(handler))
    with pytest.raises(RateLimitError) as info:
        asyncio.run(client.get("/quote/v1/ticker/24hr"))
    assert len(hits) == 1
    assert info.value.details == {"status": 429, "retry_after": 17.0}
