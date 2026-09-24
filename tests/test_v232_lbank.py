"""v2.3.2: اتصال LBank — جدول خطای درست، مکث محدودیت نرخ، دامنه‌های جایگزین WS/REST.

همهٔ تست‌ها بدون شبکهٔ واقعی اجرا می‌شوند (MockTransport و اتصال جعلی).
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.core.constants import ConnectionStatus
from app.exceptions import AuthenticationError, ExchangeError, NetworkError, RateLimitError
from market.engine import rate_limit_retry_after
from market.providers.lbank import constants as lbank_constants
from market.providers.lbank import rest_client as rest_module
from market.providers.lbank import websocket_client as ws_module
from market.providers.lbank.provider import LBankProvider
from market.providers.lbank.rest_client import LBankRestClient
from market.providers.lbank.websocket_client import LBankWebSocketClient
from market.rate_limiter import retry_async
from market.redundant_stream import RedundantStream


def _response(status: int = 200, payload=None, headers=None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.lbkex.com/v2/ticker/24hr.do")
    return httpx.Response(status, json=payload if payload is not None else {}, headers=headers, request=request)


# ----------------------------------------------------------------------
# جدول خطا
# ----------------------------------------------------------------------
def test_error_10004_is_rate_limit_not_auth():
    client = LBankRestClient()
    with pytest.raises(RateLimitError) as info:
        client._handle_response(
            _response(payload={"result": "false", "error_code": 10004, "msg": "Request too frequent"}), "/x"
        )
    assert not isinstance(info.value, AuthenticationError)
    assert info.value.details["retry_after"] == lbank_constants.RATE_LIMIT_RETRY_AFTER
    # موتور بازار آن را محدودیت نرخ می‌شناسد و مکث می‌سازد، نه «آفلاین».
    assert rate_limit_retry_after(info.value) == pytest.approx(10.0)


def test_official_auth_and_region_codes():
    client = LBankRestClient()
    with pytest.raises(AuthenticationError):
        client._handle_response(_response(payload={"result": "false", "error_code": 10007}), "/x")
    with pytest.raises(ExchangeError) as info:
        client._handle_response(_response(payload={"result": "false", "error_code": 10205}), "/x")
    assert "region" in str(info.value).lower()
    assert 10004 not in lbank_constants.AUTH_ERROR_CODES
    assert lbank_constants.LBANK_ERROR_MESSAGES[10004] == "Request too frequent"


def test_http_429_and_418_carry_retry_after():
    client = LBankRestClient()
    with pytest.raises(RateLimitError) as info:
        client._handle_response(_response(429, headers={"Retry-After": "7"}), "/x")
    assert info.value.details["retry_after"] == 7.0
    assert rate_limit_retry_after(info.value) == pytest.approx(7.0)
    with pytest.raises(RateLimitError) as info:
        client._handle_response(_response(418), "/x")
    assert info.value.details["status"] == 418
    assert rate_limit_retry_after(info.value) >= 60


def test_success_payload_still_returns_data():
    client = LBankRestClient()
    data = client._handle_response(_response(payload={"result": "true", "error_code": 0, "data": [1]}), "/x")
    assert data == [1]


# ----------------------------------------------------------------------
# تکرار و دامنهٔ جایگزین REST
# ----------------------------------------------------------------------
def test_retry_async_does_not_repeat_excluded_errors():
    calls = []

    async def operation():
        calls.append(1)
        raise RateLimitError("slow down")

    with pytest.raises(RateLimitError):
        asyncio.run(retry_async(operation, max_attempts=3, base_delay=0.01,
                                retry_on=(NetworkError,), no_retry_on=(RateLimitError,)))
    assert len(calls) == 1


def _patch_transport(monkeypatch, handler):
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(rest_module.httpx, "AsyncClient", factory)


def test_rest_rate_limit_is_not_retried(monkeypatch):
    hits = []

    def handler(request):
        hits.append(str(request.url))
        return httpx.Response(200, json={"result": "false", "error_code": 10004, "msg": "Request too frequent"})

    _patch_transport(monkeypatch, handler)
    client = LBankRestClient(rate_limit_per_second=1000)

    async def run():
        try:
            with pytest.raises(RateLimitError):
                await client.get("/v2/ticker/24hr.do", {"symbol": "all"})
        finally:
            await client.close()

    asyncio.run(run())
    assert len(hits) == 1


def test_rest_switches_host_after_connect_error(monkeypatch):
    hosts = []

    def handler(request):
        hosts.append(request.url.host)
        if request.url.host == "api.lbkex.com":
            raise httpx.ConnectError("blocked", request=request)
        return httpx.Response(200, json={"result": "true", "error_code": 0, "data": 123})

    _patch_transport(monkeypatch, handler)
    client = LBankRestClient(rate_limit_per_second=1000)

    async def run():
        try:
            return await client.get("/v2/timestamp.do")
        finally:
            await client.close()

    assert asyncio.run(run()) == 123
    assert hosts[0] == "api.lbkex.com"
    assert hosts[-1] == "api.lbank.info"
    assert client.base_url == "https://api.lbank.info"


def test_custom_rest_url_is_never_rotated():
    client = LBankRestClient("https://my-proxy.example")
    assert client._base_urls == ("https://my-proxy.example",)


def test_provider_ping_propagates_rate_limit():
    provider = LBankProvider()

    async def limited(*_args, **_kwargs):
        raise RateLimitError("too frequent", details={"retry_after": 10})

    provider._client.get = limited
    with pytest.raises(RateLimitError):
        asyncio.run(provider.ping())


# ----------------------------------------------------------------------
# WebSocket
# ----------------------------------------------------------------------
def test_default_ws_urls_start_with_official_domain():
    client = LBankWebSocketClient()
    assert client.urls[0] == "wss://api.lbank.info/ws/V2/"
    assert "wss://www.lbkex.net/ws/V2/" in client.urls
    assert LBankWebSocketClient("wss://only.example/ws").urls == ("wss://only.example/ws",)


def test_provider_gives_each_stream_a_different_first_domain():
    provider = LBankProvider()
    first = provider.create_websocket_client()
    second = provider.create_websocket_client()
    assert first.current_url != second.current_url
    assert set(first.urls) == set(second.urls)


class _FakeConnection:
    def __init__(self, frames):
        self._frames = list(frames)
        self.sent: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, text):
        self.sent.append(json.loads(text))

    async def recv(self):
        if self._frames:
            return self._frames.pop(0)
        from websockets.exceptions import ConnectionClosedOK
        raise ConnectionClosedOK(None, None)

    async def close(self):
        return None


def test_ws_rotates_domain_on_failure_and_answers_ping(monkeypatch):
    attempts: list[str] = []
    connections: list[_FakeConnection] = []
    statuses: list[ConnectionStatus] = []
    client = LBankWebSocketClient(
        urls=("wss://bad.example/ws/V2/", "wss://good.example/ws/V2/"),
        on_status_change=statuses.append,
    )

    def fake_connect(url, **kwargs):
        attempts.append(url)
        assert kwargs.get("ping_interval") is None
        if "bad" in url:
            raise OSError("handshake rejected")
        conn = _FakeConnection([json.dumps({"action": "ping", "ping": "abc"}),
                                json.dumps({"action": "pong", "pong": "cat-1"})])
        connections.append(conn)
        return conn

    monkeypatch.setattr(ws_module.websockets, "connect", fake_connect)
    monkeypatch.setattr(ws_module.random, "uniform", lambda a, b: 0.0)
    real_sleep = asyncio.sleep

    async def fast_sleep(delay, *args, **kwargs):
        await real_sleep(0)

    async def run():
        monkeypatch.setattr(ws_module.asyncio, "sleep", fast_sleep)
        await client.subscribe_ticker("BTC/USDT")
        await client.start()
        for _ in range(200):
            await real_sleep(0)
            if len(attempts) >= 3:
                break
        await client.stop()

    asyncio.run(run())
    assert attempts[0] == "wss://bad.example/ws/V2/"
    assert attempts[1] == "wss://good.example/ws/V2/"
    # دامنهٔ موفق که داده داده، پس از قطع نگه داشته می‌شود.
    assert attempts[2] == "wss://good.example/ws/V2/"
    assert ConnectionStatus.CONNECTED in statuses
    sent = connections[0].sent
    assert {"action": "subscribe", "subscribe": "tick", "pair": "btc_usdt"} in sent
    assert {"action": "pong", "pong": "abc"} in sent
    assert "handshake rejected" in client.last_error or "closed" in client.last_error


def test_proxy_failure_falls_back_to_direct(monkeypatch):
    client = LBankWebSocketClient(urls=("wss://a.example/ws/V2/",))
    monkeypatch.setattr(ws_module, "_connect_supports", lambda name: True)
    assert "proxy" not in client._connect_kwargs()
    assert ws_module._is_proxy_error(ImportError("python-socks is required to use a SOCKS proxy"))
    client._use_proxy = False
    assert client._connect_kwargs()["proxy"] is None


def test_redundant_stream_stats_expose_endpoint_and_error():
    class Client:
        status = ConnectionStatus.DISCONNECTED
        current_url = "wss://api.lbank.info/ws/V2/"
        last_error = "OSError: blocked"

    stream = RedundantStream(lambda **_: Client(), on_ticker=lambda *_: None,
                             on_candle=lambda *_: None, on_status_change=lambda *_: None,
                             connections=1)
    stats = stream.stats()
    assert stats["endpoints"] == ["wss://api.lbank.info/ws/V2/"]
    assert stats["last_error"] == "OSError: blocked"
    assert stats["connections"] == 1
