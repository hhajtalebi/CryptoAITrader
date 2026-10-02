"""
نسخهٔ ۲.۷.۰ — رفع خطاهای لاگ اجرای ویندوز کاربر (پایتون ۳.۱۴):

1. «Risk/reward 1.50 is below the minimum 1.5» برای ستاپی که خود موتور روی ۱٫۵R ساخته.
2. BBANDS با بازار تخت: TypeError ... not 'NAType'.
3. AttributeError 'recv_messages' کتابخانهٔ websockets پس از شکست دست‌دهی TLS به‌عنوان ERROR.
4. طوفان تعویض دامنهٔ REST وقتی همهٔ دامنه‌ها در دسترس نیستند + لاگ بدون علت خطا.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from app.core.models import RiskParameters, SignalDirection
from market.providers.lbank import rest_client as rc
from signals.risk_engine import RiskEngine


# ---------------------------------------------------------------------------
# 1) RR
# ---------------------------------------------------------------------------
def _assess(entry: float, stop: float, tp: float):
    engine = RiskEngine(RiskParameters(min_risk_reward=1.5, max_stop_distance_percent=50.0))
    return engine.assess(SignalDirection.LONG, entry, stop, [tp])


def test_rr_rounding_artifact_is_not_rejected():
    # RR واقعی 1.4985 → نمایش 1.50؛ قبلاً رد می‌شد.
    result = _assess(0.2, 0.198, 0.2 + 0.002 * 1.4985)
    assert "Risk/reward" not in (result.rejection_reason or "")
    assert result.risk_reward == pytest.approx(1.5)


def test_engine_built_target_on_cheap_coin_passes_rr():
    engine = RiskEngine(RiskParameters(min_risk_reward=1.5, max_stop_distance_percent=50.0))
    entry, stop = 0.123456789, 0.123406789  # ریسک بسیار کوچک → خطای گرد کردن ۸ رقمی نسبتاً بزرگ
    tp = round(entry + (entry - stop) * 1.5, 8)
    result = engine.assess(SignalDirection.LONG, entry, stop, [tp])
    assert "Risk/reward" not in (result.rejection_reason or "")


def test_rr_genuinely_below_minimum_still_rejected():
    result = _assess(0.2, 0.198, 0.2 + 0.002 * 1.49)
    assert not result.approved
    assert "Risk/reward 1.49" in result.rejection_reason


# ---------------------------------------------------------------------------
# 2) BBANDS در بازار تخت
# ---------------------------------------------------------------------------
def _flat_candles(n: int = 60, price: float = 0.0042):
    from app.core.models import Candle

    start = 1_790_000_000
    return [
        Candle(timestamp=start + 900 * i, open=price, high=price, low=price, close=price, volume=0.0)
        for i in range(n)
    ]


def test_bbands_flat_market_does_not_crash():
    from indicators.volatility import BollingerBandsIndicator

    result = BollingerBandsIndicator().calculate(_flat_candles(), "15m")
    assert result.latest["percent_b"] is None
    assert result.latest["middle"] == pytest.approx(0.0042)


def test_base_indicator_tolerates_object_series_with_na():
    import pandas as pd

    from indicators.volatility import BollingerBandsIndicator

    indicator = BollingerBandsIndicator()
    original = indicator._compute

    def _with_na(df):
        outputs = original(df)
        outputs["percent_b"] = pd.Series([pd.NA] * len(df), index=df.index, dtype=object)
        return outputs

    indicator._compute = _with_na  # type: ignore[method-assign]
    result = indicator.calculate(_flat_candles(), "15m")
    assert result.latest["percent_b"] is None
    assert all(v is None for v in result.values["percent_b"])


# ---------------------------------------------------------------------------
# 3) نویز websockets
# ---------------------------------------------------------------------------
def test_websockets_handshake_cleanup_bug_logged_as_debug(caplog):
    from ui.controllers.async_runner import _log_loop_exception

    exc = AttributeError("'ClientConnection' object has no attribute 'recv_messages'")
    context = {
        "message": "Exception in callback _SelectorTransport._call_connection_lost(ConnectionResetError())"
        " ... websockets/asyncio/connection.py connection_lost",
        "exception": exc,
    }
    with caplog.at_level(logging.DEBUG):
        _log_loop_exception(asyncio.new_event_loop(), context)
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_other_attribute_errors_still_logged_as_error(caplog):
    from ui.controllers.async_runner import _log_loop_exception

    with caplog.at_level(logging.DEBUG):
        _log_loop_exception(
            asyncio.new_event_loop(),
            {"message": "Task exception was never retrieved", "exception": AttributeError("boom")},
        )
    assert [r for r in caplog.records if r.levelno >= logging.ERROR]


# ---------------------------------------------------------------------------
# 4) REST: علت خطا، تعویض پراکسی/مستقیم، مکث
# ---------------------------------------------------------------------------
def test_describe_connect_error_includes_cause_text():
    try:
        try:
            raise OSError("[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate")
        except OSError as inner:
            raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate") from inner
    except httpx.ConnectError as exc:
        text = rc.describe_connect_error(exc)
    assert text.startswith("ConnectError: ")
    assert "CERTIFICATE_VERIFY_FAILED" in text


class _Counter:
    def __init__(self) -> None:
        self.calls = 0
        self.trust_env: list[bool] = []


def _failing_client(monkeypatch, counter: _Counter, *, succeed_when_direct: bool = False):
    client = rc.LBankRestClient(max_retries=1, rate_limit_per_second=1000)

    def handler(request: httpx.Request) -> httpx.Response:
        counter.calls += 1
        if succeed_when_direct and not client._trust_env:
            return httpx.Response(200, json={"result": "true", "data": {"ok": 1}, "error_code": 0})
        raise httpx.ConnectError("All connection attempts failed", request=request)

    async def fake_open() -> None:
        if client._client is None or client._client.is_closed:
            counter.trust_env.append(client._trust_env)
            client._client = httpx.AsyncClient(
                base_url=client._base_url, transport=httpx.MockTransport(handler)
            )

    monkeypatch.setattr(client, "open", fake_open)
    return client


def test_all_hosts_failing_pauses_rest_without_proxy(monkeypatch, caplog):
    monkeypatch.setattr(rc, "system_proxy", lambda: "")
    counter = _Counter()
    client = _failing_client(monkeypatch, counter)
    hosts = len(client._base_urls)
    assert hosts >= 2

    async def run():
        for _ in range(hosts):
            with pytest.raises(rc.NetworkError):
                await client.get("/v2/timestamp.do")
        assert client.paused
        calls_before = counter.calls
        for _ in range(20):
            with pytest.raises(rc.RestPausedError):
                await client.get("/v2/depth.do")
        # در زمان مکث هیچ درخواست شبکه‌ای فرستاده نمی‌شود
        assert counter.calls == calls_before

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    paused_logs = [r for r in caplog.records if "pausing REST" in r.getMessage()]
    assert len(paused_logs) == 1
    assert "All connection attempts failed" in paused_logs[0].getMessage()


def test_pause_expires_and_backoff_doubles(monkeypatch):
    monkeypatch.setattr(rc, "system_proxy", lambda: "")
    counter = _Counter()
    client = _failing_client(monkeypatch, counter)
    hosts = len(client._base_urls)

    async def fail_cycle():
        for _ in range(hosts):
            with pytest.raises(rc.NetworkError):
                await client.get("/x")

    async def run():
        await fail_cycle()
        assert client._pause_seconds == rc.REST_PAUSE_MIN * 2
        client._paused_until = 0.0  # مکث تمام شد
        await fail_cycle()
        assert client.paused
        assert client._pause_seconds == min(rc.REST_PAUSE_MIN * 4, rc.REST_PAUSE_MAX)

    asyncio.run(run())


def test_system_proxy_failure_retries_direct_and_sticks(monkeypatch, caplog):
    monkeypatch.setattr(rc, "system_proxy", lambda: "http://127.0.0.1:10809")
    counter = _Counter()
    client = _failing_client(monkeypatch, counter, succeed_when_direct=True)
    hosts = len(client._base_urls)

    async def run():
        for _ in range(hosts):
            with pytest.raises(rc.NetworkError):
                await client.get("/x")
        assert not client.paused  # هنوز مکث نه؛ اول مسیر مستقیم امتحان می‌شود
        assert client._trust_env is False
        data = await client.get("/x")
        assert data == {"ok": 1}
        assert client._mode_toggled is False  # موفقیت شمارنده‌ها را صفر کرد
        assert client._trust_env is False  # حالت سالم حفظ می‌شود

    with caplog.at_level(logging.INFO):
        asyncio.run(run())
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "retrying directly (bypassing the system proxy)" in text
    assert "reachable again" in text


def test_success_resets_failure_counter(monkeypatch):
    monkeypatch.setattr(rc, "system_proxy", lambda: "")
    client = rc.LBankRestClient()
    client._cycle_failures = 2
    client._pause_seconds = 20.0
    client._mark_reachable()
    assert client._cycle_failures == 0
    assert client._pause_seconds == rc.REST_PAUSE_MIN


def test_rest_client_passes_trust_env_flag():
    client = rc.LBankRestClient()
    client._trust_env = False

    async def run():
        await client.open()
        try:
            assert client._client is not None
            assert client._client._trust_env is False
        finally:
            await client.close()

    asyncio.run(run())
