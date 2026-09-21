"""
آزمون‌های ارائه‌دهنده‌های Toobit و Bitpin.

همه آزمون‌ها آفلاین‌اند و روی پاسخ‌های واقعیِ ضبط‌شده کار می‌کنند، تا
نتیجه به در دسترس بودن اینترنت یا وضعیت بازار وابسته نباشد.
"""

from __future__ import annotations

import asyncio

import pytest

from app.exceptions import AuthenticationError, ExchangeError, TimeframeError
from market.exchange_catalog import EXCHANGE_MAP, selectable_choices
from market.providers.bitpin.parser import BitpinParser
from market.providers.bitpin.provider import BitpinProvider, create_bitpin_provider
from market.providers.registry import exchange_registry, register_builtin_providers
from market.providers.toobit.parser import ToobitParser
from market.providers.toobit.provider import ToobitProvider, create_toobit_provider
from market.providers.toobit.rest_client import ToobitRestClient

# ---------------------------------------------------------------------------
# نمونه پاسخ‌های واقعی (ضبط‌شده از فراخوانی زنده)
# ---------------------------------------------------------------------------
TOOBIT_TICKER = {
    "t": 1789192303239,
    "s": "BTCUSDT",
    "c": "77239.99",
    "h": "79766.44",
    "l": "76101.01",
    "o": "77186.0",
    "b": "77239.0",
    "a": "77241.0",
    "v": "8238.12",
    "qv": "643210987.1",
    "pc": "53.99",
    "pcp": "0.0007",
}

TOOBIT_EXCHANGE_INFO = {
    "timezone": "UTC",
    "serverTime": 1789192303239,
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00001"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
            ],
        }
    ],
}

TOOBIT_KLINES = [
    [1789185600000, "77300.0", "77400.0", "77200.0", "77350.0", "12.5"],
    [1789189200000, "77350.0", "77500.0", "77100.0", "77239.99", "10.1"],
]

BITPIN_MARKETS = [
    {
        "symbol": "BTC_IRT",
        "name": "Bitcoin/Toman",
        "base": "BTC",
        "quote": "IRT",
        "tradable": True,
        "suspended": False,
        "price_precision": 0,
        "base_amount_precision": 8,
    },
    {
        "symbol": "BTC_USDT",
        "name": "Bitcoin/Tether",
        "base": "BTC",
        "quote": "USDT",
        "tradable": True,
        "suspended": False,
        "price_precision": 2,
        "base_amount_precision": 8,
    },
    {
        "symbol": "DEAD_IRT",
        "base": "DEAD",
        "quote": "IRT",
        "tradable": False,
        "suspended": True,
    },
]

BITPIN_TICKERS = [
    {
        "symbol": "BTC_IRT",
        "price": "18322168909",
        "daily_change_price": 0.67,
        "low": "18000927631",
        "high": "18733810344",
        "timestamp": 1789192303.23937,
    },
    {
        "symbol": "USDT_IRT",
        "price": "237749",
        "daily_change_price": 0.8699,
        "low": "234847",
        "high": "237751",
        "timestamp": 1789192466.83,
    },
]

BITPIN_MATCHES = [
    {"id": "1", "price": "77300.00", "base_amount": "0.5", "side": "buy", "time": 1789192000.0},
    {"id": "2", "price": "77400.00", "base_amount": "0.25", "side": "sell", "time": 1789192100.0},
    {"id": "3", "price": "77100.00", "base_amount": "0.25", "side": "sell", "time": 1789192200.0},
    # معامله‌ای در سطل بعدی (۵ دقیقه بعد)
    {"id": "4", "price": "77500.00", "base_amount": "1.0", "side": "buy", "time": 1789192600.0},
]


# ---------------------------------------------------------------------------
# Toobit — تجزیه
# ---------------------------------------------------------------------------
def test_toobit_ticker_converts_fraction_to_percent() -> None:
    """`pcp` کسر است و باید در ۱۰۰ ضرب شود."""
    ticker = ToobitParser.parse_ticker(TOOBIT_TICKER)
    assert ticker.symbol == "BTC/USDT"
    assert ticker.last_price == pytest.approx(77239.99)
    assert ticker.change_percent == pytest.approx(0.07)


def test_toobit_klines_convert_ms_to_seconds() -> None:
    """زمان کندل باید ثانیه باشد نه میلی‌ثانیه."""
    candles = ToobitParser.parse_candles(TOOBIT_KLINES)
    assert len(candles) == 2
    assert candles[0].timestamp == 1789185600
    assert candles[-1].close == pytest.approx(77239.99)


def test_toobit_symbols_derive_precision_from_filters() -> None:
    """دقت قیمت و مقدار از فیلترها استخراج می‌شود."""
    symbols = ToobitParser.parse_symbols(TOOBIT_EXCHANGE_INFO)
    assert len(symbols) == 1
    btc = symbols[0]
    assert btc.symbol == "BTC/USDT"
    assert btc.exchange_symbol == "BTCUSDT"
    assert btc.price_precision == 2
    assert btc.quantity_precision == 5
    assert btc.min_order_amount == pytest.approx(5.0)


def test_toobit_symbol_roundtrip() -> None:
    """تبدیل نماد باید رفت و برگشت پایدار باشد."""
    assert ToobitParser.to_exchange_symbol("BTC/USDT") == "BTCUSDT"
    assert ToobitParser.to_internal_symbol("BTCUSDT") == "BTC/USDT"
    assert ToobitParser.to_internal_symbol("ETHBTC") == "ETH/BTC"


# ---------------------------------------------------------------------------
# Toobit — امضا
# ---------------------------------------------------------------------------
def test_toobit_signature_is_lowercase_hex() -> None:
    """
    امضا باید HMAC-SHA256 هگز با حروف کوچک باشد.

    مستندات صرافی صریحاً می‌گوید امضا حساس به بزرگی حروف است؛ اگر روزی
    کسی `.upper()` اضافه کند این آزمون جلویش را می‌گیرد.
    """
    client = ToobitRestClient(api_key="key", api_secret="secret")
    signature = client._sign({"symbol": "BTCUSDT", "timestamp": 1789192303239})
    assert signature == signature.lower()
    assert len(signature) == 64
    # مقدار مرجع، محاسبه‌شده از روی همان رشتهٔ پرس‌وجو
    import hashlib
    import hmac
    from urllib.parse import urlencode

    expected = hmac.new(
        b"secret",
        urlencode({"symbol": "BTCUSDT", "timestamp": 1789192303239}).encode(),
        hashlib.sha256,
    ).hexdigest()
    assert signature == expected


def test_toobit_signed_request_requires_credentials() -> None:
    """بدون کلید نباید حتی درخواست شبکه زده شود."""
    client = ToobitRestClient()
    with pytest.raises(AuthenticationError):
        asyncio.run(client.get_signed("/api/v1/account"))


def test_toobit_scrub_removes_secrets_from_log_text() -> None:
    """پاک‌سازی باید امضا و کلید را از متن لاگ حذف کند."""
    from market.providers.toobit.rest_client import _scrub

    text = "GET /api/v1/account?timestamp=1&signature=deadbeefcafe&api_key=SUPERSECRET"
    cleaned = _scrub(text)
    assert "deadbeefcafe" not in cleaned
    assert "SUPERSECRET" not in cleaned


# ---------------------------------------------------------------------------
# Bitpin — تجزیه
# ---------------------------------------------------------------------------
def test_bitpin_markets_skip_untradable() -> None:
    """بازار معلق یا غیرقابل معامله نباید به کاربر پیشنهاد شود."""
    symbols = BitpinParser.parse_symbols(BITPIN_MARKETS)
    names = {s.symbol for s in symbols}
    assert names == {"BTC/IRT", "BTC/USDT"}


def test_bitpin_change_percent_is_not_rescaled() -> None:
    """`daily_change_price` از قبل درصد است و نباید در ۱۰۰ ضرب شود."""
    ticker = BitpinParser.parse_ticker(BITPIN_TICKERS[0])
    assert ticker.change_percent == pytest.approx(0.67)
    assert ticker.last_price == pytest.approx(18322168909.0)


def test_bitpin_symbol_roundtrip() -> None:
    """نماد بیت‌پین با زیرخط جدا می‌شود."""
    assert BitpinParser.to_exchange_symbol("BTC/USDT") == "BTC_USDT"
    assert BitpinParser.to_internal_symbol("USDT_IRT") == "USDT/IRT"


def test_bitpin_candles_built_from_matches() -> None:
    """
    کندل‌سازی از معاملات باید سطل‌بندی زمانی درست بدهد.

    بیت‌پین endpoint کندل ندارد، پس این مسیر تنها راه رسم نمودار است.
    """
    candles = BitpinParser.candles_from_matches(BITPIN_MATCHES, interval_seconds=300)
    # سه سطل ۵ دقیقه‌ای: دو معامله در اولی، یکی در دومی، یکی در سومی
    assert len(candles) == 3
    first = candles[0]
    assert first.timestamp == 1789191900
    assert first.open == pytest.approx(77300.0)
    assert first.high == pytest.approx(77400.0)
    assert first.low == pytest.approx(77300.0)
    assert first.close == pytest.approx(77400.0)
    assert first.volume == pytest.approx(0.75)
    assert candles[-1].close == pytest.approx(77500.0)
    # کندل‌ها باید به ترتیب زمانی و هم‌تراز با مرز تایم‌فریم باشند
    assert [c.timestamp for c in candles] == sorted(c.timestamp for c in candles)
    for candle in candles:
        assert candle.timestamp % 300 == 0
    # ثابت بنیادی کندل
    for candle in candles:
        assert candle.low <= candle.open <= candle.high
        assert candle.low <= candle.close <= candle.high


def test_bitpin_balances_accept_paginated_payload() -> None:
    """موجودی هم به‌صورت لیست و هم درون results پذیرفته می‌شود."""
    rows = [{"asset": "BTC", "balance": "0.5"}, {"currency": "usdt", "balance": "100"}]
    assert BitpinParser.parse_balances(rows) == {"BTC": 0.5, "USDT": 100.0}
    assert BitpinParser.parse_balances({"results": rows}) == {"BTC": 0.5, "USDT": 100.0}
    # موجودی صفر نباید شلوغی ایجاد کند
    assert BitpinParser.parse_balances([{"asset": "XRP", "balance": "0"}]) == {}


def test_bitpin_rejects_long_timeframes() -> None:
    """
    تایم‌فریم بلند باید خطای روشن بدهد نه داده ناقص.

    صرافی تاریخچهٔ کندل ندارد؛ ساختن «۱ روزه» از ۱۰۰ معاملهٔ اخیر
    گمراه‌کننده است.
    """
    provider = BitpinProvider()
    with pytest.raises(TimeframeError):
        asyncio.run(provider.get_ohlcv("BTC/USDT", "1d"))


def test_bitpin_orderbook_is_sorted() -> None:
    """خریدها نزولی و فروش‌ها صعودی مرتب می‌شوند."""
    payload = {
        "bids": [["100", "1"], ["102", "2"], ["101", "1"]],
        "asks": [["105", "1"], ["103", "2"], ["104", "1"]],
    }
    book = BitpinParser.parse_orderbook(payload, symbol="BTC/USDT")
    assert [level.price for level in book.bids] == [102.0, 101.0, 100.0]
    assert [level.price for level in book.asks] == [103.0, 104.0, 105.0]
    assert book.bids[0].price < book.asks[0].price


# ---------------------------------------------------------------------------
# ثبت و فهرست صرافی‌ها
# ---------------------------------------------------------------------------
def test_both_exchanges_are_registered() -> None:
    """هر دو صرافی باید از طریق ثبت‌کننده ساخته شوند."""
    register_builtin_providers()
    assert exchange_registry.is_registered("toobit")
    assert exchange_registry.is_registered("bitpin")
    toobit = exchange_registry.create("toobit", api_key="k", api_secret="s")
    bitpin = exchange_registry.create("bitpin", api_key="k", api_secret="s")
    assert isinstance(toobit, ToobitProvider)
    assert isinstance(bitpin, BitpinProvider)


def test_factories_build_providers() -> None:
    """کارخانه‌ها باید همان نوع درست را بسازند."""
    assert isinstance(create_toobit_provider(), ToobitProvider)
    assert isinstance(create_bitpin_provider(), BitpinProvider)


def test_presets_are_selectable_in_settings() -> None:
    """
    هر دو صرافی باید در تنظیمات قابل انتخاب باشند.

    اگر `implemented` جا بماند، کاربر برچسب «به‌زودی» می‌بیند و نمی‌تواند
    انتخاب کند — دقیقاً همان چیزی که کاربر خواسته رفع شود.
    """
    keys = [key for key, _ in selectable_choices()]
    assert "toobit" in keys
    assert "bitpin" in keys
    for key in ("toobit", "bitpin"):
        preset = EXCHANGE_MAP[key]
        assert preset.implemented is True
        assert "به‌زودی" not in dict(selectable_choices())[key]
    # بیت‌پین ایرانی است و باید بازار تومانی داشته باشد
    assert "IRT" in EXCHANGE_MAP["bitpin"].quote_currencies


def test_provider_capabilities_are_honest() -> None:
    """
    توانمندی‌های اعلام‌شده باید با واقعیت بخوانند.

    بیت‌پین WebSocket عمومی ندارد و نباید ادعایش را بکند.
    """
    toobit = ToobitProvider().capabilities
    assert toobit.supports_private_api is True
    assert toobit.supports_websocket is True
    assert "1h" in toobit.native_timeframes

    bitpin = BitpinProvider().capabilities
    assert bitpin.supports_websocket is False
    assert bitpin.supports_orderbook is True
    assert "1d" not in bitpin.native_timeframes


def test_credential_errors_never_echo_the_secret() -> None:
    """پیام خطای اتصال هرگز نباید کلید یا رمز را برگرداند."""
    secret = "SUPER-SECRET-VALUE-9999"
    key = "SUPER-KEY-VALUE-1111"
    for provider in (
        ToobitProvider(api_key=key, api_secret=secret),
        BitpinProvider(api_key=key, api_secret=secret),
    ):
        ok, message = asyncio.run(provider.test_credentials())
        assert ok is False
        assert secret not in message
        assert key not in message


def test_missing_credentials_are_reported_before_network() -> None:
    """بدون کلید، پیام باید کلید ترجمهٔ روشن باشد نه خطای شبکه."""
    for provider in (ToobitProvider(), BitpinProvider()):
        ok, message = asyncio.run(provider.test_credentials())
        assert ok is False
        assert message == "exchange.error.credentials_required"


def test_connection_messages_are_translation_keys() -> None:
    """
    پیام‌های آزمایش اتصال باید کلید ترجمه باشند نه متن انگلیسی ثابت.

    رابط کاربری فارسی است؛ اگر ارائه‌دهنده متن انگلیسی برگرداند، کاربر
    فارسی‌زبان پیام نامفهوم می‌بیند.
    """
    from localization import Translator

    for language in ("fa", "en"):
        translator = Translator(language)
        for key in (
            "exchange.error.credentials_required",
            "exchange.error.verified",
            "exchange.error.connection_failed",
            "exchange.error.toobit_rejected",
            "exchange.error.bitpin_rejected",
            "exchange.error.account_not_found",
            "exchange.error.no_credentials",
        ):
            assert translator.has(key), f"{key} missing in {language}"

    # کلیدهایی که ارائه‌دهنده واقعاً برمی‌گرداند باید ترجمه داشته باشند
    translator = Translator("fa")
    for provider in (ToobitProvider(), BitpinProvider()):
        _, message = asyncio.run(provider.test_credentials())
        assert translator.has(message.partition("|")[0])


def test_exchange_hints_exist_for_new_exchanges() -> None:
    """
    راهنمای هر صرافی باید در هر دو زبان موجود باشد.

    بیت‌پین بدون ثبت IP در فهرست مجاز کار نمی‌کند؛ کاربر باید این را
    پیش از تلاش ناموفق بداند.
    """
    from localization import Translator

    for language in ("fa", "en"):
        translator = Translator(language)
        for key in ("settings.exchange_hint.bitpin", "settings.exchange_hint.toobit"):
            assert translator.has(key), f"{key} missing in {language}"
        assert translator.has("settings.accounts.no_account_selected")
