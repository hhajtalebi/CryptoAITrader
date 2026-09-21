"""
آزمون‌های وب‌سوکت توبیت و انتخاب کلاینت زنده بر پایهٔ صرافی.

پس‌زمینه: پیش از این، `MarketDataEngine` همیشه `LBankWebSocketClient`
می‌ساخت. توبیت هم `supports_websocket=True` اعلام می‌کرد، پس کاربرِ توبیت
داده زندهٔ **LBank** می‌گرفت. این فایل هم پروتکل توبیت را می‌سنجد و هم
تضمین می‌کند که هر صرافی کلاینت خودش را بسازد.

همهٔ آزمون‌ها آفلاین‌اند و روی فریم‌های واقعیِ ضبط‌شده از سرور توبیت کار
می‌کنند (۱۴۰۴/۰۶/۲۲)، تا نتیجه به اینترنت وابسته نباشد.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.core.constants import ConnectionStatus
from app.core.models import Candle, Ticker
from market.engine import MarketDataEngine
from market.providers.base import ExchangeProvider, MarketWebSocketClient, ProviderCapabilities
from market.providers.lbank.provider import LBankProvider
from market.providers.lbank.websocket_client import LBankWebSocketClient
from market.providers.toobit.parser import ToobitParser
from market.providers.toobit.provider import ToobitProvider
from market.providers.toobit.websocket_client import (
    PING_INTERVAL,
    STALE_TIMEOUT,
    ToobitSubscription,
    ToobitWebSocketClient,
)

# ---------------------------------------------------------------------------
# فریم‌های واقعیِ ضبط‌شده از wss://stream.toobit.com/quote/ws/v1
# ---------------------------------------------------------------------------
WS_TICKER_FRAME = {
    "symbol": "BTCUSDT",
    "symbolName": "BTCUSDT",
    "topic": "realtimes",
    "params": {"realtimeInterval": "24h", "binary": "false"},
    "data": [
        {
            "t": 1789318515328,
            "s": "BTCUSDT",
            "sn": "BTCUSDT",
            "c": "77283.79",
            "h": "77404.37",
            "l": "76532.8",
            "o": "77350.72",
            "v": "3517.47754",
            "qv": "270981641.9663461",
            "m": "-0.0009",
            "e": 301,
        }
    ],
    "f": True,
    "sendTime": 1789318516973,
}

# نکته: سرور در پاسخ `topic` را «kline» می‌دهد نه «kline_1m»
WS_KLINE_FRAME = {
    "symbol": "BTCUSDT",
    "symbolName": "BTCUSDT",
    "klineType": "1m",
    "topic": "kline",
    "params": {"realtimeInterval": "24h", "klineType": "1m", "binary": "false"},
    "data": [
        {
            "t": 1789318500000,
            "s": "BTCUSDT",
            "sn": "BTCUSDT",
            "c": "77284.45",
            "h": "77284.45",
            "l": "77283.78",
            "o": "77283.79",
            "v": "0.19248",
            "st": 0,
        }
    ],
    "f": True,
    "sendTime": 1789318541022,
}

# حالتی که در عمل دیده شد: klineType فقط داخل params می‌آید
WS_KLINE_FRAME_PARAMS_ONLY = {
    "symbol": "BTCUSDT",
    "topic": "kline",
    "params": {"realtimeInterval": "24h", "klineType": "5m", "binary": "false"},
    "data": [
        {
            "t": 1789318500000,
            "s": "BTCUSDT",
            "c": "77284.45",
            "h": "77284.45",
            "l": "77283.78",
            "o": "77283.79",
            "v": "0.19248",
        }
    ],
}

WS_ERROR_FRAME = {"code": "-100010", "desc": "Invalid Symbols!"}


# ---------------------------------------------------------------------------
# ۱) تجزیهٔ فریم‌ها
# ---------------------------------------------------------------------------
def test_ws_ticker_is_parsed() -> None:
    """فریم realtimes باید به مدل Ticker تبدیل شود."""
    ticker = ToobitParser.parse_ws_ticker(WS_TICKER_FRAME)
    assert ticker is not None
    assert ticker.symbol == "BTC/USDT"
    assert ticker.last_price == pytest.approx(77283.79)
    assert ticker.high_24h == pytest.approx(77404.37)
    assert ticker.low_24h == pytest.approx(76532.8)


def test_ws_ticker_converts_fraction_to_percent() -> None:
    """
    فیلد `m` کسری است نه درصد.

    ‎-0.0009‎ یعنی ‎-0.09٪‎. بدون تبدیل، ستون «تغییر» صدبرابر کوچک‌تر
    نشان داده می‌شد — دقیقاً همان اشتباهی که در REST با `pcp` رخ می‌داد.
    """
    ticker = ToobitParser.parse_ws_ticker(WS_TICKER_FRAME)
    assert ticker is not None
    assert ticker.change_percent == pytest.approx(-0.09)


def test_ws_ticker_rejects_empty_payload() -> None:
    """فریم بدون داده نباید استثنا بدهد."""
    assert ToobitParser.parse_ws_ticker({"topic": "realtimes", "data": []}) is None
    assert ToobitParser.parse_ws_ticker({"topic": "realtimes"}) is None
    assert ToobitParser.parse_ws_ticker({"data": ["not-a-dict"]}) is None


def test_ws_kline_is_parsed_with_seconds() -> None:
    """زمان کندل باید از میلی‌ثانیه به ثانیه تبدیل شود."""
    parsed = ToobitParser.parse_ws_kline(WS_KLINE_FRAME)
    assert parsed is not None
    symbol, timeframe, candle = parsed
    assert symbol == "BTC/USDT"
    assert timeframe == "1m"
    assert isinstance(candle, Candle)
    assert candle.timestamp == 1789318500  # نه 1789318500000
    assert candle.open == pytest.approx(77283.79)
    assert candle.high == pytest.approx(77284.45)
    assert candle.low == pytest.approx(77283.78)
    assert candle.close == pytest.approx(77284.45)
    assert candle.volume == pytest.approx(0.19248)


def test_ws_kline_reads_timeframe_from_params() -> None:
    """اگر klineType فقط در params باشد باز هم باید خوانده شود."""
    parsed = ToobitParser.parse_ws_kline(WS_KLINE_FRAME_PARAMS_ONLY)
    assert parsed is not None
    _, timeframe, _ = parsed
    assert timeframe == "5m"


def test_ws_kline_without_timeframe_is_dropped() -> None:
    """کندل بدون تایم‌فریم قابل استفاده نیست و باید دور ریخته شود."""
    frame = {"symbol": "BTCUSDT", "topic": "kline", "data": [{"t": 1, "o": 1, "h": 1, "l": 1, "c": 1}]}
    assert ToobitParser.parse_ws_kline(frame) is None


def test_ws_kline_with_broken_numbers_is_dropped() -> None:
    """داده خراب نباید موتور را بشکند."""
    frame = {
        "symbol": "BTCUSDT",
        "klineType": "1m",
        "topic": "kline",
        "data": [{"t": 1789318500000, "o": "x", "h": "1", "l": "1", "c": "1"}],
    }
    assert ToobitParser.parse_ws_kline(frame) is None


# ---------------------------------------------------------------------------
# ۲) پیام‌های اشتراک
# ---------------------------------------------------------------------------
def test_subscription_message_matches_protocol() -> None:
    """پیام اشتراک باید دقیقاً قالب مستندشدهٔ توبیت را داشته باشد."""
    sub = ToobitSubscription("realtimes", "BTCUSDT")
    message = sub.to_message()
    assert message == {
        "symbol": "BTCUSDT",
        "topic": "realtimes",
        "event": "sub",
        "params": {"binary": False},
    }


def test_cancel_uses_cancel_event() -> None:
    """لغو اشتراک در توبیت `cancel` است، نه `unsub`."""
    sub = ToobitSubscription("kline_1m", "ETHUSDT")
    assert sub.to_message(subscribe=False)["event"] == "cancel"


def test_subscription_is_hashable() -> None:
    """اشتراک باید Hashable باشد تا ثبت مجدد پس از اتصال ممکن شود."""
    a = ToobitSubscription("realtimes", "BTCUSDT")
    b = ToobitSubscription("realtimes", "BTCUSDT")
    assert len({a, b}) == 1


# ---------------------------------------------------------------------------
# ۳) رفتار کلاینت بدون شبکه
# ---------------------------------------------------------------------------
class _FakeConnection:
    """اتصال ساختگی که پیام‌های ارسالی را ضبط می‌کند."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self) -> None:
        return None


def test_subscriptions_are_queued_before_connection() -> None:
    """
    اشتراک پیش از اتصال نباید گم شود.

    کاربر ممکن است نمادی را قبل از برقراری اتصال انتخاب کند؛ باید پس از
    اتصال خودکار ثبت شود.
    """
    client = ToobitWebSocketClient()
    asyncio.run(client.subscribe_ticker("BTC/USDT"))
    assert client.subscription_count == 1


def test_resubscribe_sends_every_subscription() -> None:
    """پس از اتصال مجدد باید همهٔ اشتراک‌ها دوباره ارسال شوند."""
    client = ToobitWebSocketClient()

    async def scenario() -> _FakeConnection:
        await client.subscribe_ticker("BTC/USDT")
        await client.subscribe_candles("ETH/USDT", "1m")
        connection = _FakeConnection()
        client._connection = connection  # noqa: SLF001 - تزریق عمدی برای آزمون
        await client._resubscribe_all()  # noqa: SLF001
        return connection

    connection = asyncio.run(scenario())
    topics = {m["topic"] for m in connection.sent}
    assert topics == {"realtimes", "kline_1m"}
    assert all(m["event"] == "sub" for m in connection.sent)


def test_unsubscribe_all_clears_and_cancels() -> None:
    """لغو همگانی باید هم مجموعه را خالی کند هم پیام لغو بفرستد."""
    client = ToobitWebSocketClient()

    async def scenario() -> _FakeConnection:
        await client.subscribe_ticker("BTC/USDT")
        connection = _FakeConnection()
        client._connection = connection  # noqa: SLF001
        await client.unsubscribe_all()
        return connection

    connection = asyncio.run(scenario())
    assert client.subscription_count == 0
    assert connection.sent[-1]["event"] == "cancel"


def test_unknown_timeframe_falls_back_to_rest() -> None:
    """
    تایم‌فریم پشتیبانی‌نشده نباید خطا بدهد.

    قرار است سیستم بی‌صدا به نظرسنجی REST برگردد، نه اینکه بشکند.
    """
    client = ToobitWebSocketClient()
    asyncio.run(client.subscribe_candles("BTC/USDT", "7m"))
    assert client.subscription_count == 0


def test_error_frame_does_not_crash_the_client() -> None:
    """پاسخ «نماد نامعتبر» فقط باید لاگ شود."""
    received: list[Ticker] = []
    client = ToobitWebSocketClient(on_ticker=received.append)
    connection = _FakeConnection()
    asyncio.run(client._handle_message(json.dumps(WS_ERROR_FRAME), connection))  # noqa: SLF001
    assert received == []


def test_ticker_frame_reaches_the_callback() -> None:
    """فریم تیکر باید به شنونده برسد."""
    received: list[Ticker] = []
    client = ToobitWebSocketClient(on_ticker=received.append)
    connection = _FakeConnection()
    asyncio.run(client._handle_message(json.dumps(WS_TICKER_FRAME), connection))  # noqa: SLF001
    assert len(received) == 1
    assert received[0].symbol == "BTC/USDT"


def test_kline_frame_reaches_the_callback() -> None:
    """فریم کندل باید با نماد و تایم‌فریم به شنونده برسد."""
    received: list[tuple] = []
    client = ToobitWebSocketClient(on_candle=lambda *a: received.append(a))
    connection = _FakeConnection()
    asyncio.run(client._handle_message(json.dumps(WS_KLINE_FRAME), connection))  # noqa: SLF001
    assert len(received) == 1
    symbol, timeframe, candle = received[0]
    assert (symbol, timeframe) == ("BTC/USDT", "1m")
    assert candle.close == pytest.approx(77284.45)


def test_callback_error_does_not_break_the_stream() -> None:
    """خطای مصرف‌کننده نباید اتصال را قطع کند."""

    def boom(_ticker: Ticker) -> None:
        raise RuntimeError("consumer exploded")

    client = ToobitWebSocketClient(on_ticker=boom)
    connection = _FakeConnection()
    # نباید استثنا بیرون بزند
    asyncio.run(client._handle_message(json.dumps(WS_TICKER_FRAME), connection))  # noqa: SLF001


def test_non_json_frame_is_ignored() -> None:
    """فریم غیر-JSON نباید استثنا بدهد."""
    client = ToobitWebSocketClient()
    connection = _FakeConnection()
    asyncio.run(client._handle_message("<<not json>>", connection))  # noqa: SLF001


def test_client_answers_ping_if_server_ever_sends_one() -> None:
    """
    سرور توبیت ping نمی‌فرستد، ولی اگر بفرستد باید pong بگیرد.

    این بیمهٔ ارزانی است در برابر یک قطعیِ مرموز.
    """
    client = ToobitWebSocketClient()
    connection = _FakeConnection()
    asyncio.run(client._handle_message(json.dumps({"ping": 12345}), connection))  # noqa: SLF001
    assert connection.sent == [{"pong": 12345}]


def test_status_starts_disconnected() -> None:
    """وضعیت اولیه باید قطع باشد."""
    assert ToobitWebSocketClient().status is ConnectionStatus.DISCONNECTED


def test_keepalive_is_enabled_because_server_is_silent() -> None:
    """
    سرور توبیت ping نمی‌فرستد، پس کلاینت باید خودش اتصال را زنده نگه دارد.

    اگر این عددها صفر/None شوند، اتصال پس از مدتی بی‌صدا می‌میرد.
    """
    assert PING_INTERVAL > 0
    assert STALE_TIMEOUT > PING_INTERVAL


# ---------------------------------------------------------------------------
# ۴) انتخاب کلاینت بر پایهٔ صرافی — اصل ماجرا
# ---------------------------------------------------------------------------
def test_toobit_builds_its_own_client() -> None:
    """توبیت باید کلاینت توبیت بسازد، نه LBank."""
    client = ToobitProvider().create_websocket_client()
    assert isinstance(client, ToobitWebSocketClient)


def test_lbank_builds_its_own_client() -> None:
    """LBank باید کلاینت خودش را بسازد."""
    client = LBankProvider().create_websocket_client()
    assert isinstance(client, LBankWebSocketClient)


def test_both_clients_satisfy_the_shared_contract() -> None:
    """
    هر دو کلاینت باید قرارداد مشترک را برآورده کنند.

    موتور فقط با همین امضاها کار می‌کند؛ اگر یکی عقب بماند، تعویض صرافی
    در زمان اجرا می‌شکند.
    """
    for client in (ToobitWebSocketClient(), LBankWebSocketClient()):
        assert isinstance(client, MarketWebSocketClient)


def test_default_provider_has_no_live_client() -> None:
    """
    صرافی‌ای که داده زنده ندارد باید None بدهد.

    پیاده‌سازی پیش‌فرض یعنی «من وب‌سوکت ندارم» و موتور به REST برمی‌گردد.
    """

    class _Bare(ExchangeProvider):
        name = "bare"

        @property
        def capabilities(self) -> ProviderCapabilities:
            return ProviderCapabilities(name="bare")

        async def connect(self) -> None: ...
        async def close(self) -> None: ...
        async def ping(self) -> bool:
            return True

        async def get_symbols(self): return []
        async def get_ticker(self, symbol): raise NotImplementedError
        async def get_all_tickers(self): return []
        async def get_current_price(self, symbol): return 0.0
        async def get_ohlcv(self, symbol, timeframe, limit=300, end_time=None): return []
        async def get_orderbook(self, symbol, depth=20): raise NotImplementedError
        def to_exchange_symbol(self, symbol): return symbol
        def from_exchange_symbol(self, exchange_symbol): return exchange_symbol

    assert _Bare().create_websocket_client() is None


def test_bitpin_declares_no_websocket() -> None:
    """بیت‌پین وب‌سوکت ندارد و نباید ادعایش را بکند."""
    from market.providers.bitpin.provider import BitpinProvider

    assert BitpinProvider().capabilities.supports_websocket is False


# ---------------------------------------------------------------------------
# ۵) یکپارچگی با موتور بازار
# ---------------------------------------------------------------------------
class _StubClient:
    """کلاینت ساختگی برای دنبال‌کردن فراخوانی‌های موتور."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.tickers: list[str] = []
        self.candles: list[tuple[str, str]] = []

    @property
    def status(self) -> ConnectionStatus:
        return ConnectionStatus.CONNECTED if self.started else ConnectionStatus.DISCONNECTED

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def subscribe_ticker(self, symbol: str) -> None:
        self.tickers.append(symbol)

    async def unsubscribe_ticker(self, symbol: str) -> None:
        if symbol in self.tickers:
            self.tickers.remove(symbol)

    async def subscribe_candles(self, symbol: str, timeframe: str) -> None:
        self.candles.append((symbol, timeframe))

    async def unsubscribe_candles(self, symbol: str, timeframe: str) -> None:
        if (symbol, timeframe) in self.candles:
            self.candles.remove((symbol, timeframe))

    async def unsubscribe_all(self) -> None:
        self.tickers.clear()
        self.candles.clear()


class _StubProvider(ExchangeProvider):
    """صرافی ساختگی که کلاینت ما را برمی‌گرداند."""

    name = "stub"

    def __init__(self, client: _StubClient | None, *, supports_ws: bool = True) -> None:
        self._client = client
        self._supports_ws = supports_ws

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(name="stub", supports_websocket=self._supports_ws)

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool:
        return True

    async def get_symbols(self): return []
    async def get_ticker(self, symbol): raise NotImplementedError
    async def get_all_tickers(self): return []
    async def get_current_price(self, symbol): return 0.0
    async def get_ohlcv(self, symbol, timeframe, limit=300, end_time=None): return []
    async def get_orderbook(self, symbol, depth=20): raise NotImplementedError
    def to_exchange_symbol(self, symbol): return symbol
    def from_exchange_symbol(self, exchange_symbol): return exchange_symbol

    def create_websocket_client(self, **kwargs):
        return self._client


def test_engine_uses_the_client_the_provider_supplies() -> None:
    """
    موتور باید کلاینتِ صرافی را بردارد، نه کلاینت LBank را.

    این همان رگرسیونی است که کاربر توبیت را به داده LBank وصل می‌کرد.
    """
    client = _StubClient()
    engine = MarketDataEngine(_StubProvider(client), websocket_enabled=True)

    async def scenario() -> None:
        await engine.start()
        await engine.subscribe_symbol("BTC/USDT", "1m")
        await engine.stop()

    asyncio.run(scenario())
    assert client.started is True
    assert client.stopped is True
    assert "BTC/USDT" in client.tickers
    assert ("BTC/USDT", "1m") in client.candles


def test_engine_survives_a_provider_that_lies_about_websocket() -> None:
    """
    اگر صرافی وب‌سوکت ادعا کند ولی کلاینت ندهد، موتور نباید بشکند.

    باید هشدار بدهد و به REST برگردد — همان وضعی که توبیت پیش از این
    نسخه داشت.
    """
    engine = MarketDataEngine(_StubProvider(None, supports_ws=True), websocket_enabled=True)

    async def scenario() -> None:
        await engine.start()
        await engine.stop()

    asyncio.run(scenario())
    assert engine.websocket_status is ConnectionStatus.DISCONNECTED


def test_engine_skips_websocket_when_disabled() -> None:
    """با خاموش بودن کلید، نباید هیچ اتصالی باز شود."""
    client = _StubClient()
    engine = MarketDataEngine(_StubProvider(client), websocket_enabled=False)

    async def scenario() -> None:
        await engine.start()
        await engine.stop()

    asyncio.run(scenario())
    assert client.started is False
