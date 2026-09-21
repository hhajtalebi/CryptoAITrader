"""
پیاده‌سازی ExchangeProvider برای صرافی Toobit.

Toobit تایم‌فریم‌های فراوانی به‌صورت بومی می‌دهد، پس تجمیع کمتری نسبت به
LBank لازم است؛ ولی همان مسیر تجمیع برای تایم‌فریم‌های غیراستاندارد حفظ
شده تا رفتار برنامه میان صرافی‌ها یکسان بماند.
"""

from __future__ import annotations

import asyncio
from typing import Any

from collections.abc import Callable

from app.core.constants import ConnectionStatus
from app.core.models import Candle, OrderBook, SymbolInfo, Ticker
from app.exceptions import ExchangeError, TimeframeError, ValidationError
from app.logging import get_logger
from market.providers.base import ExchangeProvider, ProviderCapabilities
from market.providers.toobit.constants import (
    TOOBIT_MAX_DEPTH,
    TOOBIT_MAX_KLINE_SIZE,
    TOOBIT_NATIVE_TIMEFRAMES,
    TOOBIT_REST_URL,
    TOOBIT_TIMEFRAME_MAP,
    ToobitEndpoints,
)
from market.providers.toobit.parser import ToobitParser
from market.providers.toobit.rest_client import ToobitRestClient
from market.timeframes import (
    aggregate_candles,
    candles_needed,
    find_aggregation_source,
    normalize_timeframe,
)

logger = get_logger(__name__)


class ToobitProvider(ExchangeProvider):
    """ارائه‌دهندهٔ داده بازار و حساب صرافی Toobit."""

    name = "toobit"
    display_name = "Toobit"

    def __init__(
        self,
        *,
        base_url: str = TOOBIT_REST_URL,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        **_extra: Any,
    ) -> None:
        self._client = ToobitRestClient(
            base_url=base_url,
            api_key=api_key,
            api_secret=api_secret,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._symbol_cache: list[SymbolInfo] = []
        self._symbol_lookup: dict[str, str] = {}

    # ------------------------------------------------------------------
    # توانمندی‌ها و چرخه عمر
    # ------------------------------------------------------------------
    @property
    def capabilities(self) -> ProviderCapabilities:
        """توانمندی‌های این صرافی."""
        return ProviderCapabilities(
            name=self.name,
            supports_websocket=True,
            supports_orderbook=True,
            supports_private_api=True,
            native_timeframes=set(TOOBIT_NATIVE_TIMEFRAMES),
            max_candles_per_request=TOOBIT_MAX_KLINE_SIZE,
        )

    async def connect(self) -> None:
        """آماده‌سازی کلاینت شبکه."""
        await self._client.connect()

    async def close(self) -> None:
        """آزادسازی منابع."""
        await self._client.close()

    async def ping(self) -> bool:
        """بررسی در دسترس بودن صرافی."""
        try:
            await self._client.get(ToobitEndpoints.PING)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Toobit ping failed: %s", type(exc).__name__)
            return False

    # ------------------------------------------------------------------
    # نگاشت نماد
    # ------------------------------------------------------------------
    def to_exchange_symbol(self, symbol: str) -> str:
        """تبدیل نماد داخلی به قالب صرافی."""
        return ToobitParser.to_exchange_symbol(symbol)

    def from_exchange_symbol(self, exchange_symbol: str) -> str:
        """تبدیل نماد صرافی به قالب داخلی."""
        known = self._symbol_lookup.get((exchange_symbol or "").upper())
        if known:
            return known
        return ToobitParser.to_internal_symbol(exchange_symbol)

    # ------------------------------------------------------------------
    # داده عمومی
    # ------------------------------------------------------------------
    async def get_symbols(self) -> list[SymbolInfo]:
        """فهرست نمادهای قابل معامله."""
        payload = await self._client.get(ToobitEndpoints.EXCHANGE_INFO)
        symbols = ToobitParser.parse_symbols(payload)
        if not symbols:
            raise ExchangeError("Unexpected Toobit exchangeInfo response")
        self._symbol_cache = symbols
        # جدول جست‌وجو ساخته می‌شود تا تبدیل نماد به حدس‌زدن نیاز نداشته
        # باشد؛ نمادهایی مثل BTTCUSDT با حدس اشتباه جدا می‌شوند.
        self._symbol_lookup = {item.exchange_symbol: item.symbol for item in symbols}
        return symbols

    async def get_ticker(self, symbol: str) -> Ticker:
        """وضعیت ۲۴ ساعتهٔ یک نماد."""
        if not symbol:
            raise ValidationError("Symbol is required", user_key="errors.validation")
        exchange_symbol = self.to_exchange_symbol(symbol)
        payload = await self._client.get(
            ToobitEndpoints.TICKER_24H, {"symbol": exchange_symbol}
        )
        ticker = ToobitParser.parse_ticker(payload, symbol=symbol)
        if ticker.last_price <= 0:
            raise ExchangeError(
                f"Toobit returned no price for {symbol}",
                user_key="errors.symbol_not_found",
            )
        return ticker

    async def get_all_tickers(self) -> list[Ticker]:
        """وضعیت همهٔ نمادها در یک درخواست."""
        payload = await self._client.get(ToobitEndpoints.TICKER_24H)
        tickers = ToobitParser.parse_tickers(payload)
        if not tickers:
            raise ExchangeError("Unexpected Toobit all-tickers response")
        return tickers

    async def get_current_price(self, symbol: str) -> float:
        """قیمت لحظه‌ای یک نماد."""
        exchange_symbol = self.to_exchange_symbol(symbol)
        payload = await self._client.get(
            ToobitEndpoints.TICKER_PRICE, {"symbol": exchange_symbol}
        )
        prices = ToobitParser.parse_price_map(payload)
        price = prices.get(symbol) or next(iter(prices.values()), 0.0)
        if price <= 0:
            raise ExchangeError(
                f"Toobit returned no price for {symbol}",
                user_key="errors.symbol_not_found",
            )
        return price

    async def get_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 300, end_time: int | None = None
    ) -> list[Candle]:
        """
        دریافت کندل‌ها با تجمیع خودکار برای تایم‌فریم‌های غیربومی.
        """
        normalized = normalize_timeframe(timeframe)
        exchange_symbol = self.to_exchange_symbol(symbol)

        if normalized in TOOBIT_TIMEFRAME_MAP:
            return await self._fetch_candles(
                exchange_symbol, TOOBIT_TIMEFRAME_MAP[normalized], limit, end_time
            )

        source = find_aggregation_source(normalized, set(TOOBIT_TIMEFRAME_MAP))
        if source is None:
            raise TimeframeError(
                f"Timeframe {timeframe} cannot be provided or aggregated by Toobit",
                user_key="errors.timeframe",
                details={"native": sorted(TOOBIT_TIMEFRAME_MAP)},
            )
        source_limit = min(candles_needed(normalized, source, limit), TOOBIT_MAX_KLINE_SIZE)
        logger.debug(
            "Aggregating %s from %s (%d source candles)", normalized, source, source_limit
        )
        raw = await self._fetch_candles(
            exchange_symbol, TOOBIT_TIMEFRAME_MAP[source], source_limit, end_time
        )
        aggregated = aggregate_candles(raw, source, normalized)
        return aggregated[-limit:] if limit else aggregated

    async def _fetch_candles(
        self, exchange_symbol: str, interval: str, limit: int, end_time: int | None
    ) -> list[Candle]:
        """فراخوانی خام endpoint کندل."""
        params: dict[str, Any] = {
            "symbol": exchange_symbol,
            "interval": interval,
            "limit": min(max(1, int(limit)), TOOBIT_MAX_KLINE_SIZE),
        }
        if end_time:
            # مدل داخلی ثانیه است ولی صرافی میلی‌ثانیه می‌خواهد
            params["endTime"] = int(end_time) * 1000
        payload = await self._client.get(ToobitEndpoints.KLINES, params)
        return ToobitParser.parse_candles(payload)

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """دریافت دفتر سفارش."""
        exchange_symbol = self.to_exchange_symbol(symbol)
        payload = await self._client.get(
            ToobitEndpoints.DEPTH,
            {"symbol": exchange_symbol, "limit": min(max(1, int(depth)), TOOBIT_MAX_DEPTH)},
        )
        return ToobitParser.parse_orderbook(payload, symbol=symbol)

    # ------------------------------------------------------------------
    # داده خصوصی
    # ------------------------------------------------------------------
    async def fetch_account(self) -> Any:
        """
        فراخوانی خام حساب، **بدون** مهار خطا.

        برای آزمایش اتصال لازم است؛ نسخهٔ مهارشده علت شکست را می‌بلعد.
        """
        return await self._client.get_signed(ToobitEndpoints.ACCOUNT)

    async def get_account_balance(self) -> dict[str, float]:
        """
        موجودی حساب.

        خطا مهار می‌شود تا نبود دسترسی، کل کیف پول را از کار نیندازد؛
        همان تفکیکی که در LBank هم رعایت شده است.
        """
        try:
            payload = await self.fetch_account()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Toobit balance fetch failed: %s", type(exc).__name__)
            return {}
        return ToobitParser.parse_balances(payload)

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """سفارش‌های باز (فقط خواندنی)."""
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = self.to_exchange_symbol(symbol)
        try:
            payload = await self._client.get_signed(ToobitEndpoints.OPEN_ORDERS, params)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Toobit open orders failed: %s", type(exc).__name__)
            return []
        return payload if isinstance(payload, list) else []

    async def get_order_history(self, symbol: str, limit: int = 50) -> list[dict]:
        """تاریخچهٔ معاملات کاربر (فقط خواندنی)."""
        try:
            payload = await self._client.get_signed(
                ToobitEndpoints.MY_TRADES,
                {"symbol": self.to_exchange_symbol(symbol), "limit": int(limit)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Toobit order history failed: %s", type(exc).__name__)
            return []
        return payload if isinstance(payload, list) else []

    async def test_credentials(self) -> tuple[bool, str]:
        """
        آزمایش کلید و رمز.

        پیام بازگشتی هرگز شامل خود کلید نیست.
        """
        if not self._client.has_credentials:
            return False, "exchange.error.credentials_required"
        try:
            await self.fetch_account()
        except Exception as exc:  # noqa: BLE001
            from app.exceptions import AuthenticationError

            if isinstance(exc, AuthenticationError):
                return False, "exchange.error.toobit_rejected"
            return False, f"exchange.error.connection_failed|{type(exc).__name__}"
        return True, "exchange.error.verified"


    # ------------------------------------------------------------------
    # داده زنده
    # ------------------------------------------------------------------
    def create_websocket_client(
        self,
        *,
        on_ticker: Callable[[Ticker], None] | None = None,
        on_candle: Callable[[str, str, Candle], None] | None = None,
        on_status_change: Callable[[ConnectionStatus], None] | None = None,
    ) -> Any | None:
        """
        ساخت کلاینت وب‌سوکت توبیت.

        درون‌ریزی تنبل است تا وارد کردن این ماژول، کتابخانهٔ websockets را
        اجباری نکند؛ نصب‌های بدون داده زنده هم باید بالا بیایند.
        """
        from market.providers.toobit.websocket_client import ToobitWebSocketClient

        return ToobitWebSocketClient(
            on_ticker=on_ticker,
            on_candle=on_candle,
            on_status_change=on_status_change,
        )


def create_toobit_provider(**kwargs: Any) -> ToobitProvider:
    """کارخانهٔ ساخت ToobitProvider برای ثبت در ExchangeRegistry."""
    return ToobitProvider(**kwargs)
