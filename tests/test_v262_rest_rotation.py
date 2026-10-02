"""
۲.۶.۲ — طوفان تعویض دامنهٔ REST.

لاگ کاربر: هر ~۰٫۳ ثانیه «host unreachable (ConnectError); switching…» روی هر سه
دامنه، همراه ClosedResourceError در ping و درخواست‌ها، در حالی که WebSocket
وصل بود. علت: هر خطای اتصال کلاینتِ HTTPِ مشترک را فوراً می‌بست (زیر پای همهٔ
درخواست‌های هم‌زمان) و هر شکستِ هم‌زمان دوباره دامنه را می‌چرخاند.
"""

from __future__ import annotations

import asyncio

import anyio
import httpx
import pytest

from app.exceptions import NetworkError
from market.providers.lbank import rest_client as module
from market.providers.lbank.rest_client import LBankRestClient


def _client_with(handler, monkeypatch):
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)
    return LBankRestClient(max_retries=3, rate_limit_per_second=1000)


def _ok(request):
    return httpx.Response(200, json={"result": "true", "data": 1790000000000, "error_code": 0})


async def test_stale_failure_does_not_rotate_again(monkeypatch):
    client = _client_with(_ok, monkeypatch)
    first = client.base_url
    await client._rotate_base_url(httpx.ConnectError("x"), failed_host=first)
    second = client.base_url
    assert second != first
    # شکستِ دیرهنگامِ درخواستی که هنوز روی دامنهٔ قبلی بود
    await client._rotate_base_url(httpx.ConnectError("x"), failed_host=first)
    assert client.base_url == second
    await client.close()


async def test_rotation_does_not_close_client_under_inflight_requests(monkeypatch):
    client = _client_with(_ok, monkeypatch)
    await client.open()
    old = client._client
    await client._rotate_base_url(httpx.ConnectError("x"), failed_host=client.base_url)
    assert old is not None and not old.is_closed  # بعداً با تأخیر بسته می‌شود
    await client.close()
    assert old.is_closed


async def test_concurrent_connect_errors_rotate_only_once(monkeypatch):
    calls = {"n": 0}

    async def handler(request):
        if request.url.host == "api.lbkex.com":
            await asyncio.sleep(0.01)
            raise httpx.ConnectError("blocked", request=request)
        return _ok(request)

    client = _client_with(handler, monkeypatch)
    hosts = []
    real_rotate = client._rotate_base_url

    async def spy(exc, *, failed_host=None):
        before = client.base_url
        await real_rotate(exc, failed_host=failed_host)
        if client.base_url != before:
            hosts.append(client.base_url)

    client._rotate_base_url = spy
    results = await asyncio.gather(*(client.get("/v2/timestamp.do") for _ in range(12)))
    assert results == [1790000000000] * 12
    assert hosts == ["https://api.lbank.info"]  # یک تعویض، نه طوفان
    await client.close()


async def test_closed_resource_error_is_retried_as_network_error(monkeypatch):
    state = {"n": 0}

    def handler(request):
        state["n"] += 1
        if state["n"] == 1:
            raise anyio.ClosedResourceError()
        return _ok(request)

    client = _client_with(handler, monkeypatch)
    assert await client.get("/v2/timestamp.do") == 1790000000000
    assert client.base_url == "https://api.lbkex.com"  # دامنه عوض نشد
    await client.close()


async def test_closed_resource_error_maps_to_network_error_when_persistent(monkeypatch):
    def handler(request):
        raise anyio.ClosedResourceError()

    client = _client_with(handler, monkeypatch)
    with pytest.raises(NetworkError):
        await client.get("/v2/timestamp.do")
    await client.close()
