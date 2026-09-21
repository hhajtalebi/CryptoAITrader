"""
پیاده‌سازی ExchangeProvider برای صرافی ایرانی بیت‌پین.

دو تفاوت مهم با صرافی‌های جهانی که در سراسر این کلاس دیده می‌شود:

۱. **کندل بومی وجود ندارد.** کندل‌ها از معاملات اخیر ساخته می‌شوند، پس
   عمق تاریخی محدود است. این را در `capabilities` صادقانه اعلام می‌کنیم
   تا موتور تحلیل بداند با داده کم‌عمق سروکار دارد.

۲. **بازارهای تومانی (IRT)** وجود دارند که در صرافی‌های جهانی نیستند؛
   نرخ تتر/تومان از همین‌جا خوانده می‌شود و به سرویس نرخ تومان برنامه
   خوراک می‌دهد.
"""

from __future__ import annotations

from typing import Any

from app.core.models import Candle, OrderBook, SymbolInfo, Ticker
from app.exceptions import ExchangeError, TimeframeError, ValidationError
from app.logging import get_logger
from market.providers.base import ExchangeProvider, ProviderCapabilities
from market.providers.bitpin.constants import (
    BITPIN_MAX_MATCHES,
    BITPIN_REST_URL,
    BITPIN_SYNTHETIC_TIMEFRAMES,
    BITPIN_USDT_IRT_SYMBOL,
    BitpinEndpoints,
)
from market.providers.bitpin.parser import BitpinParser
from market.providers.bitpin.rest_client import BitpinRestClient
from market.timeframes import normalize_timeframe, timeframe_seconds

logger = get_logger(__name__)


class BitpinProvider(ExchangeProvider):
    """ارائه‌دهندهٔ داده بازار و حساب صرافی بیت‌پین."""

    name = "bitpin"
    display_name = "Bitpin"

    def __init__(
        self,
        *,
        base_url: str = BITPIN_REST_URL,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        **_extra: Any,
    ) -> None:
        self._client = BitpinRestClient(
            base_url=base_url,
            api_key=api_key,
            api_secret=api_secret,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._symbol_cache: list[SymbolInfo] = []

    # ------------------------------------------------------------------
    # توانمندی‌ها و چرخه عمر
    # ------------------------------------------------------------------
    @property
    def capabilities(self) -> ProviderCapabilities:
        """توانمندی‌های بیت‌پین."""
        return ProviderCapabilities(
            name=self.name,
            # بیت‌پین WebSocket عمومی مستندشده ندارد
            supports_websocket=False,
            supports_orderbook=True,
            supports_private_api=True,
            # کندل‌ها ساختگی‌اند ولی برای موتور در دسترس‌اند
            native_timeframes=set(BITPIN_SYNTHETIC_TIMEFRAMES),
            max_candles_per_request=BITPIN_MAX_MATCHES,
        )

    async def connect(self) -> None:
        """آماده‌سازی کلاینت."""
        await self._client.connect()

    async def close(self) -> None:
        """آزادسازی منابع و پاک‌کردن توکن."""
        await self._client.close()

    async def ping(self) -> bool:
        """بررسی در دسترس بودن صرافی."""
        try:
            await self._client.get(BitpinEndpoints.CURRENCIES)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug("Bitpin ping failed: %s", type(exc).__name__)
            return False

    # ------------------------------------------------------------------
    # نگاشت نماد
    # ------------------------------------------------------------------
    def to_exchange_symbol(self, symbol: str) -> str:
        """تبدیل نماد داخلی به قالب بیت‌پین."""
        return BitpinParser.to_exchange_symbol(symbol)

    def from_exchange_symbol(self, exchange_symbol: str) -> str:
        """تبدیل نماد بیت‌پین به قالب داخلی."""
        return BitpinParser.to_internal_symbol(exchange_symbol)

    # ------------------------------------------------------------------
    # داده عمومی
    # ------------------------------------------------------------------
    async def get_symbols(self) -> list[SymbolInfo]:
        """فهرست بازارهای قابل معامله."""
        payload = await self._client.get(BitpinEndpoints.MARKETS)
        symbols = BitpinParser.parse_symbols(payload)
        if not symbols:
            raise ExchangeError("Unexpected Bitpin markets response")
        self._symbol_cache = symbols
        return symbols

    async def get_ticker(self, symbol: str) -> Ticker:
        """
        تیکر یک نماد.

        بیت‌پین فیلتر تک‌نمادی ندارد، پس کل فهرست گرفته و همین‌جا فیلتر
        می‌شود.
        """
        if not symbol:
            raise ValidationError("Symbol is required", user_key="errors.validation")
        exchange_symbol = self.to_exchange_symbol(symbol)
        payload = await self._client.get(BitpinEndpoints.TICKERS)
        row = BitpinParser.find_ticker(payload, exchange_symbol)
        if row is None:
            raise ExchangeError(
                f"Bitpin does not list {symbol}",
                user_key="errors.symbol_not_found",
                details={"symbol": symbol},
            )
        return BitpinParser.parse_ticker(row, symbol=symbol)

    async def get_all_tickers(self) -> list[Ticker]:
        """تیکر همهٔ بازارها."""
        payload = await self._client.get(BitpinEndpoints.TICKERS)
        tickers = BitpinParser.parse_tickers(payload)
        if not tickers:
            raise ExchangeError("Unexpected Bitpin tickers response")
        return tickers

    async def get_current_price(self, symbol: str) -> float:
        """قیمت لحظه‌ای."""
        ticker = await self.get_ticker(symbol)
        if ticker.last_price <= 0:
            raise ExchangeError(
                f"Bitpin returned no price for {symbol}",
                user_key="errors.symbol_not_found",
            )
        return ticker.last_price

    async def get_usdt_irt_rate(self) -> float:
        """
        نرخ لحظه‌ای تتر به تومان.

        این همان چیزی است که سرویس «نرخ تومان» برنامه لازم دارد؛ چون
        بیت‌پین ایرانی است، نرخ واقعی بازار داخلی را می‌دهد نه نرخ
        تبدیلی صرافی‌های جهانی.
        """
        payload = await self._client.get(BitpinEndpoints.TICKERS)
        row = BitpinParser.find_ticker(payload, BITPIN_USDT_IRT_SYMBOL)
        if row is None:
            return 0.0
        return BitpinParser.parse_ticker(row).last_price

    async def get_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 300, end_time: int | None = None
    ) -> list[Candle]:
        """
        کندل‌های ساخته‌شده از معاملات اخیر.

        صرافی endpoint کندل ندارد؛ تنها تایم‌فریم‌های کوتاه معنا دارند
        چون فهرست معاملات تنها چند ساعت را پوشش می‌دهد.
        """
        normalized = normalize_timeframe(timeframe)
        interval = timeframe_seconds(normalized)
        if normalized not in BITPIN_SYNTHETIC_TIMEFRAMES:
            raise TimeframeError(
                f"Bitpin can only provide short timeframes ({', '.join(BITPIN_SYNTHETIC_TIMEFRAMES)}); "
                f"{timeframe} needs historical candles the exchange does not expose",
                user_key="errors.timeframe",
                details={"available": list(BITPIN_SYNTHETIC_TIMEFRAMES)},
            )
        exchange_symbol = self.to_exchange_symbol(symbol)
        payload = await self._client.get(
            BitpinEndpoints.MATCHES.format(symbol=exchange_symbol)
        )
        candles = BitpinParser.candles_from_matches(
            payload, interval_seconds=interval, limit=limit
        )
        if not candles:
            raise ExchangeError(
                f"Bitpin returned no trades to build candles for {symbol}",
                details={"symbol": symbol},
            )
        return candles

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """دفتر سفارش."""
        exchange_symbol = self.to_exchange_symbol(symbol)
        payload = await self._client.get(
            BitpinEndpoints.ORDERBOOK.format(symbol=exchange_symbol)
        )
        return BitpinParser.parse_orderbook(payload, symbol=symbol, depth=depth)

    # ------------------------------------------------------------------
    # داده خصوصی
    # ------------------------------------------------------------------
    async def fetch_wallets(self) -> Any:
        """فراخوانی خام کیف پول، بدون مهار خطا (برای آزمایش اتصال)."""
        return await self._client.get_private(BitpinEndpoints.WALLETS)

    async def get_account_balance(self) -> dict[str, float]:
        """موجودی حساب؛ خطا مهار می‌شود تا کیف پول از کار نیفتد."""
        try:
            payload = await self.fetch_wallets()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Bitpin balance fetch failed: %s", type(exc).__name__)
            return {}
        return BitpinParser.parse_balances(payload)

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """سفارش‌های باز (فقط خواندنی)."""
        params: dict[str, Any] = {"state": "active"}
        if symbol:
            params["symbol"] = self.to_exchange_symbol(symbol)
        try:
            payload = await self._client.get_private(BitpinEndpoints.ORDERS, params)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Bitpin open orders failed: %s", type(exc).__name__)
            return []
        return _as_rows(payload)

    async def get_order_history(self, symbol: str, limit: int = 50) -> list[dict]:
        """تاریخچهٔ معاملات کاربر (فقط خواندنی)."""
        try:
            payload = await self._client.get_private(
                BitpinEndpoints.FILLS,
                {"symbol": self.to_exchange_symbol(symbol), "limit": int(limit)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Bitpin order history failed: %s", type(exc).__name__)
            return []
        return _as_rows(payload)[:limit]

    async def test_credentials(self) -> tuple[bool, str]:
        """
        آزمایش کلید و رمز.

        پیام خطای بیت‌پین برای IP غیرمجاز و کلید غلط یکی است، پس در پیام
        بازگشتی هر دو احتمال را یادآوری می‌کنیم.
        """
        if not self._client.has_credentials:
            return False, "exchange.error.credentials_required"
        try:
            await self._client.authenticate()
        except Exception as exc:  # noqa: BLE001
            from app.exceptions import AuthenticationError

            if isinstance(exc, AuthenticationError):
                return False, "exchange.error.bitpin_rejected"
            return False, f"exchange.error.connection_failed|{type(exc).__name__}"
        return True, "exchange.error.verified"


def _as_rows(payload: Any) -> list[dict]:
    """بیرون کشیدن فهرست رکوردها از پاسخ‌های صفحه‌بندی‌شده یا ساده."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "orders"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def create_bitpin_provider(**kwargs: Any) -> BitpinProvider:
    """کارخانهٔ ساخت BitpinProvider برای ثبت در ExchangeRegistry."""
    return BitpinProvider(**kwargs)
