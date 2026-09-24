"""
پیاده‌سازی واسط ExchangeProvider برای صرافی LBank.

این کلاس «مغز» ارتباط با LBank است و سه کار انجام می‌دهد:
    ۱) فراخوانی Endpointهای درست از طریق LBankRestClient
    ۲) تبدیل پاسخ‌ها با LBankParser به مدل‌های داخلی
    ۳) جبران محدودیت‌های صرافی (مثلاً ساخت تایم‌فریم ۱۲ ساعته با تجمیع)

ارتباط با ماژول‌های دیگر:
    MarketDataEngine تنها مصرف‌کننده مستقیم است؛ هیچ لایه دیگری نباید
    مستقیماً این کلاس را صدا بزند.
"""

from __future__ import annotations

import time
from typing import Any

from collections.abc import Callable

from app.core.constants import ConnectionStatus
from app.core.models import Candle, OrderBook, SymbolInfo, Ticker
from app.exceptions import ExchangeError, RateLimitError, TimeframeError, ValidationError
from app.logging import get_logger
from market.providers.base import ExchangeProvider, ProviderCapabilities
from market.providers.lbank.constants import (
    LBANK_MAX_KLINE_SIZE,
    LBANK_REST_URL,
    LBANK_TIMEFRAME_MAP,
    LBankEndpoints,
)
from market.providers.lbank.parser import LBankParser
from market.providers.lbank.rest_client import LBankRestClient
from market.timeframes import (
    aggregate_candles,
    candles_needed,
    find_aggregation_source,
    normalize_timeframe,
    timeframe_seconds,
)

logger = get_logger(__name__)


#: نام‌های رایج فیلدهای حساب قرارداد (v2.5.0) — ترتیب، اولویت است
_FUTURES_TOTAL_KEYS = (
    "total", "equity", "accountEquity", "marginBalance", "totalEquity",
    "totalMarginBalance", "balanceTotal",
)
_FUTURES_WALLET_KEYS = ("walletBalance", "balance", "totalWalletBalance", "cashBalance")
_FUTURES_AVAILABLE_KEYS = (
    "available", "availableBalance", "availableMargin", "canUseAmount",
    "maxWithdrawAmount", "free", "usableAmt", "availBal",
)
_FUTURES_FROZEN_KEYS = ("frozen", "frozenMargin", "frozenBalance", "locked", "freezeAmt", "orderMargin")
_FUTURES_MARGIN_KEYS = ("positionMargin", "usedMargin", "margin", "initialMargin", "posMargin")
_FUTURES_UNREALIZED_KEYS = (
    "unrealized", "unrealizedPnl", "unrealisedPnl", "unrealProfit", "unRealizedProfit",
    "profitUnreal", "floatingPnl", "upl",
)


class LBankProvider(ExchangeProvider):
    """
    ارائه‌دهنده داده بازار صرافی LBank.

    توانمندی‌ها بر اساس آزمایش واقعی API تعیین شده‌اند؛ به‌ویژه فهرست
    تایم‌فریم‌های بومی که با مستندات قدیمی تفاوت دارد.
    """

    name = "lbank"
    display_name = "LBank"

    def __init__(
        self,
        *,
        base_url: str = LBANK_REST_URL,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        rate_limit_per_second: float = 8.0,
    ) -> None:
        self._client = LBankRestClient(
            base_url=base_url,
            api_key=api_key,
            api_secret=api_secret,
            timeout=timeout,
            max_retries=max_retries,
            rate_limit_per_second=rate_limit_per_second,
        )
        self._capabilities = ProviderCapabilities(
            name=self.name,
            supports_websocket=True,
            supports_orderbook=True,
            supports_private_api=True,
            native_timeframes=set(LBANK_TIMEFRAME_MAP),
            max_candles_per_request=LBANK_MAX_KLINE_SIZE,
        )
        self._symbol_cache: dict[str, SymbolInfo] = {}
        self._ws_client_counter = 0
        #: جزئیات آخرین همگام‌سازی موجودی (v2.5.0 — زبانه‌های کیف پول)
        self.last_spot_details: dict[str, dict[str, float]] = {}
        self.last_futures_details: dict[str, dict[str, float]] = {}

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    @property
    def capabilities(self) -> ProviderCapabilities:
        """توانمندی‌های صرافی LBank."""
        return self._capabilities

    @property
    def rest_client(self) -> LBankRestClient:
        """دسترسی به کلاینت REST (برای تنظیم کلید از لایه سرویس)."""
        return self._client

    async def connect(self) -> None:
        """آماده‌سازی کلاینت HTTP."""
        await self._client.open()

    async def close(self) -> None:
        """بستن کلاینت HTTP."""
        await self._client.close()

    async def ping(self) -> bool:
        """
        بررسی در دسترس بودن صرافی با فراخوانی Endpoint زمان سرور.

        این سبک‌ترین درخواست ممکن است و برای نمایش وضعیت اتصال کافی است.
        """
        try:
            data = await self._client.get(LBankEndpoints.TIMESTAMP)
            return data is not None
        except RateLimitError:
            # محدودیت نرخ یعنی صرافی در دسترس است؛ موتور بازار باید مکث کند،
            # نه اینکه اتصال را «مرده» اعلام کند.
            raise
        except Exception as exc:  # noqa: BLE001 - وضعیت اتصال نباید برنامه را متوقف کند
            logger.warning("LBank ping failed: %s", exc.__class__.__name__)
            return False

    async def get_server_time(self) -> int:
        """زمان سرور صرافی بر حسب میلی‌ثانیه."""
        data = await self._client.get(LBankEndpoints.TIMESTAMP)
        return int(data or 0)

    # ------------------------------------------------------------------
    # نگاشت نماد
    # ------------------------------------------------------------------
    def to_exchange_symbol(self, symbol: str) -> str:
        """تبدیل BTC/USDT به btc_usdt."""
        return LBankParser.to_exchange_symbol(symbol)

    def from_exchange_symbol(self, exchange_symbol: str) -> str:
        """تبدیل btc_usdt به BTC/USDT."""
        return LBankParser.to_internal_symbol(exchange_symbol)

    # ------------------------------------------------------------------
    # داده عمومی
    # ------------------------------------------------------------------
    async def get_symbols(self) -> list[SymbolInfo]:
        """
        دریافت فهرست کامل نمادها همراه با دقت قیمت و مقدار.

        اگر Endpoint دقت در دسترس نباشد، فهرست نمادها همچنان برگردانده
        می‌شود (با دقت پیش‌فرض) تا برنامه از کار نیفتد.
        """
        pairs = await self._client.get(LBankEndpoints.CURRENCY_PAIRS)
        if not isinstance(pairs, list):
            raise ExchangeError("Unexpected currencyPairs response", details={"type": type(pairs).__name__})

        accuracy: list[dict] = []
        try:
            accuracy_data = await self._client.get(LBankEndpoints.ACCURACY)
            if isinstance(accuracy_data, list):
                accuracy = accuracy_data
        except Exception as exc:  # noqa: BLE001 - دقت، داده اختیاری است
            logger.warning("Fetching symbol accuracy failed: %s", exc.__class__.__name__)

        symbols = LBankParser.parse_symbols(pairs, accuracy)
        self._symbol_cache = {s.symbol: s for s in symbols}
        logger.info("Fetched %d symbols from LBank", len(symbols))
        return symbols

    async def get_ticker(self, symbol: str) -> Ticker:
        """دریافت وضعیت ۲۴ ساعته یک نماد."""
        data = await self._client.get(
            LBankEndpoints.TICKER_24HR, {"symbol": self.to_exchange_symbol(symbol)}
        )
        if not isinstance(data, list) or not data:
            raise ValidationError(f"Empty ticker response for {symbol}", details={"symbol": symbol})
        return LBankParser.parse_ticker(data[0])

    async def get_all_tickers(self) -> list[Ticker]:
        """
        دریافت وضعیت ۲۴ ساعته تمام نمادها در یک درخواست.

        این روش به‌جای هزاران درخواست جداگانه، فقط یک درخواست می‌فرستد و
        فشار روی API را به حداقل می‌رساند.
        """
        data = await self._client.get(LBankEndpoints.TICKER_24HR, {"symbol": "all"})
        if not isinstance(data, list):
            raise ExchangeError("Unexpected all-tickers response")
        return LBankParser.parse_tickers(data)

    async def get_all_prices(self) -> dict[str, float]:
        """
        دریافت قیمت لحظه‌ای تمام نمادها (سبک‌ترین درخواست ممکن).

        برای به‌روزرسانی مکرر فهرست بازارها مناسب است، چون حجم پاسخ آن از
        ticker/24hr کمتر است.
        """
        data = await self._client.get(LBankEndpoints.PRICE)
        if not isinstance(data, list):
            raise ExchangeError("Unexpected price list response")
        return LBankParser.parse_price_list(data)

    async def get_current_price(self, symbol: str) -> float:
        """
        قیمت لحظه‌ای یک نماد.

        از Endpoint سبک price.do استفاده می‌شود و در صورت خالی بودن پاسخ،
        خطای صریح داده می‌شود (هرگز قیمت حدسی برگردانده نمی‌شود).
        """
        data = await self._client.get(
            LBankEndpoints.PRICE, {"symbol": self.to_exchange_symbol(symbol)}
        )
        if isinstance(data, list) and data:
            price = LBankParser._safe_float(data[0].get("price"), None)
            if price is not None:
                return price
        raise ValidationError(f"Could not fetch current price for {symbol}", details={"symbol": symbol})

    async def get_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 300, end_time: int | None = None
    ) -> list[Candle]:
        """
        دریافت کندل‌ها با پشتیبانی خودکار از تایم‌فریم‌های غیربومی.

        منطق کار:
            • اگر LBank تایم‌فریم را مستقیماً بدهد، همان گرفته می‌شود.
            • در غیر این صورت، بهترین تایم‌فریم پایه انتخاب و داده لازم
              دریافت و سپس تجمیع می‌شود.

        پارامتر time در LBank «زمان شروع» بازه است؛ بنابراین برای گرفتن
        آخرین کندل‌ها، زمان شروع را از روی تعداد درخواستی عقب می‌بریم.
        """
        normalized = normalize_timeframe(timeframe)

        if normalized in LBANK_TIMEFRAME_MAP:
            return await self._fetch_native_klines(symbol, normalized, limit, end_time)

        source = find_aggregation_source(normalized, set(LBANK_TIMEFRAME_MAP))
        if source is None:
            raise TimeframeError(
                f"Timeframe {timeframe} cannot be provided or aggregated by LBank",
                details={"native": sorted(LBANK_TIMEFRAME_MAP)},
            )

        source_limit = min(candles_needed(normalized, source, limit), LBANK_MAX_KLINE_SIZE)
        logger.debug(
            "Aggregating %s from %s (%d source candles)", normalized, source, source_limit
        )
        base_candles = await self._fetch_native_klines(symbol, source, source_limit, end_time)
        aggregated = aggregate_candles(base_candles, source, normalized)
        return aggregated[-limit:] if limit else aggregated

    async def _fetch_native_klines(
        self, symbol: str, timeframe: str, limit: int, end_time: int | None
    ) -> list[Candle]:
        """
        دریافت کندل‌های یک تایم‌فریم بومی، با پشتیبانی از صفحه‌بندی.

        نکته مهم درباره رفتار واقعی API (آزمایش‌شده):
            پارامتر time «زمان شروع» بازه است و size حداکثر تعداد کندلی است
            که از آن نقطه به «جلو» برگردانده می‌شود. بنابراین اگر size دقیقاً
            برابر تعداد بازه‌های بین شروع و اکنون باشد، کندل در حال شکل‌گیری
            جا می‌ماند. برای همین چند بازه حاشیه اطمینان اضافه می‌کنیم و در
            پایان، خروجی را به تعداد درخواستی می‌بریم.

        اگر تعداد درخواستی از سقف مجاز صرافی بیشتر باشد، داده در چند مرحله
        دریافت و به هم چسبانده می‌شود.
        """
        exchange_symbol = self.to_exchange_symbol(symbol)
        lbank_type = LBANK_TIMEFRAME_MAP[timeframe]
        interval = timeframe_seconds(timeframe)
        end = end_time if end_time is not None else int(time.time())

        remaining = max(1, limit)
        collected: dict[int, Candle] = {}
        margin = 2  # حاشیه اطمینان برای دربرگرفتن کندل جاری

        while remaining > 0:
            chunk = min(remaining, LBANK_MAX_KLINE_SIZE - margin)
            start_time = end - chunk * interval
            data = await self._client.get(
                LBankEndpoints.KLINE,
                {
                    "symbol": exchange_symbol,
                    "size": min(chunk + margin, LBANK_MAX_KLINE_SIZE),
                    "type": lbank_type,
                    "time": max(0, start_time),
                },
            )
            if not isinstance(data, list) or not data:
                break
            candles = LBankParser.parse_klines(data)
            if not candles:
                break
            for candle in candles:
                collected[candle.timestamp] = candle
            remaining -= chunk
            end = candles[0].timestamp - interval
            if len(candles) < chunk:
                break  # داده تاریخی بیشتری موجود نیست
            if end_time is not None and candles[-1].timestamp > end_time:
                # از بازه درخواستی کاربر عبور کرده‌ایم
                collected = {ts: c for ts, c in collected.items() if ts <= end_time}

        result = [collected[key] for key in sorted(collected)]
        return result[-limit:] if limit else result

    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """
        دریافت دفتر سفارش‌ها.

        LBank حداکثر ۶۰ سطح می‌دهد؛ مقادیر بزرگ‌تر محدود می‌شوند.
        """
        size = max(1, min(int(depth), 60))
        data = await self._client.get(
            LBankEndpoints.DEPTH, {"symbol": self.to_exchange_symbol(symbol), "size": size}
        )
        if not isinstance(data, dict):
            raise ValidationError(f"Invalid depth response for {symbol}")
        return LBankParser.parse_orderbook(symbol, data)

    # ------------------------------------------------------------------
    # داده خصوصی (فقط خواندنی)
    # ------------------------------------------------------------------
    async def get_account_balance(self) -> dict[str, float]:
        """
        دریافت موجودی حساب.

        فقط دارایی‌هایی که موجودی غیرصفر دارند برگردانده می‌شوند تا خروجی
        سبک بماند.
        """
        data = await self._client.post_signed(LBankEndpoints.USER_INFO)
        # v2.5.0: جزئیات آزاد/قفل برای زبانهٔ «اسپات» کیف پول نگه داشته می‌شود
        self.last_spot_details = self._parse_spot_details(data)
        return self._parse_balances(data)

    @staticmethod
    def _parse_spot_details(data: Any) -> dict[str, dict[str, float]]:
        """دارایی → {free, locked, total} از پاسخ user_info.do (v2.5.0)."""
        rows: Any = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get("balances") or data.get("data") or data.get("info") or []
        details: dict[str, dict[str, float]] = {}
        if not isinstance(rows, list):
            return details
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset") or row.get("coin") or "").upper()
            free = LBankParser._safe_float(row.get("free", row.get("usableAmt")), 0.0) or 0.0
            locked = LBankParser._safe_float(row.get("locked", row.get("freezeAmt")), 0.0) or 0.0
            if asset and free + locked > 0:
                details[asset] = {"free": free, "locked": locked, "total": free + locked}
        return details

    @staticmethod
    def _parse_balances(data: Any) -> dict[str, float]:
        """
        تبدیل پاسخ خام user_info.do به نگاشت «دارایی → موجودی».

        نکتهٔ مهم: این نقطهٔ پایانی **فهرست** برمی‌گرداند، نه دیکشنری.
        پیش‌تر فقط حالت دیکشنری خوانده می‌شد، پس موجودی همیشه خالی
        درمی‌آمد؛ اتصال «موفق» بود ولی کیف پول چیزی نشان نمی‌داد.
        هر دو حالت پشتیبانی می‌شود تا اگر صرافی قالب را عوض کرد نشکند.

        جدا از متد شبکه نگه داشته شده تا بدون تماس با صرافی آزمون شود.
        """
        rows: Any = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get("balances") or data.get("data") or data.get("info") or []

        balances: dict[str, float] = {}
        if not isinstance(rows, list):
            return balances

        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset") or row.get("coin") or "").upper()
            # از الگوی «a or b» استفاده نمی‌کنیم: مقدار صفرِ معتبر در کلید
            # اول باعث می‌شود مقدار کلید دوم اشتباهاً جایش بنشیند.
            free = LBankParser._safe_float(row.get("free", row.get("usableAmt")), 0.0) or 0.0
            locked = LBankParser._safe_float(row.get("locked", row.get("freezeAmt")), 0.0) or 0.0
            total = free + locked
            if asset and total > 0:
                balances[asset] = total
        return balances

    async def get_futures_balance(self) -> dict[str, float]:
        """
        موجودی حساب قراردادهای آتی.

        جدا از اسپات است: کاربر ممکن است سرمایه‌اش را به کیف پول فیوچرز
        منتقل کرده باشد و در آن حالت کیف پول اسپات تقریباً خالی است.

        نبودِ دسترسی قرارداد روی کلید، خطا نیست — دیکشنری خالی برمی‌گردد
        تا موجودی اسپات همچنان نمایش داده شود.
        """
        try:
            return await self.fetch_futures_balance()
        except Exception as exc:  # noqa: BLE001 - نبود دسترسی فیوچرز عادی است
            logger.info("Futures balance unavailable: %s", exc.__class__.__name__)
            return {}

    async def fetch_futures_balance(self) -> dict[str, float]:
        """
        همان موجودی فیوچرز، ولی **بدون** مهار خطا.

        نسخهٔ مهارشده (`get_futures_balance`) برای همگام‌سازی است که نباید
        به‌خاطر نبود دسترسی قرارداد کل کیف پول را از کار بیندازد؛ این
        نسخه برای «آزمایش اتصال» است که باید علت واقعی را نشان دهد.

        هر دارایی جداگانه پرسیده می‌شود چون `prv/account` پارامتر `asset`
        را لازم دارد. یک دارایی که موجودی ندارد خطا می‌دهد یا خالی
        برمی‌گردد، و این نباید بقیه را از بین ببرد؛ پس خطای تک‌دارایی
        نادیده گرفته می‌شود و فقط وقتی خطا پرتاب می‌شود که **هیچ**
        دارایی‌ای پاسخ ندهد — آن حالت یعنی کلید واقعاً دسترسی قرارداد
        ندارد و «آزمایش اتصال» باید آن را بگوید.
        """
        from market.providers.lbank.constants import (
            CONTRACT_ASSETS,
            CONTRACT_PRODUCT_GROUP,
            LBankContractEndpoints,
        )

        balances: dict[str, float] = {}
        details: dict[str, dict[str, float]] = {}
        last_error: Exception | None = None
        answered = False
        for asset in CONTRACT_ASSETS:
            try:
                data = await self._client.post_contract_signed(
                    LBankContractEndpoints.ACCOUNT,
                    {"productGroup": CONTRACT_PRODUCT_GROUP, "asset": asset},
                )
            except Exception as exc:  # noqa: BLE001 - نبود یک دارایی خطای کلی نیست
                last_error = exc
                continue
            answered = True
            for name, info in self._parse_futures_details(data, asset).items():
                balances[name] = balances.get(name, 0.0) + float(info.get("total") or 0.0)
                merged = details.setdefault(name, {})
                for key, value in info.items():
                    merged[key] = merged.get(key, 0.0) + float(value or 0.0)

        if not answered and last_error is not None:
            raise last_error
        self.last_futures_details = details
        return balances

    @staticmethod
    def _parse_futures_balances(data: Any, default_asset: str = "") -> dict[str, float]:
        """
        تبدیل پاسخ حساب قرارداد به نگاشت «دارایی → موجودی کل».

        مثل اسپات، هم فهرست و هم دیکشنری پذیرفته می‌شود چون قالب پاسخ
        بین نسخه‌ها فرق می‌کند. جزئیات در `_parse_futures_details` است.
        """
        return {
            asset: float(info.get("total") or 0.0)
            for asset, info in LBankProvider._parse_futures_details(data, default_asset).items()
        }

    @staticmethod
    def _parse_futures_details(
        data: Any, default_asset: str = ""
    ) -> dict[str, dict[str, float]]:
        """
        دارایی → {total, available, frozen, margin, unrealized} (v2.5.0).

        فیلدهای پاسخ `prv/account` در مستندات رسمی ذکر نشده‌اند، پس
        نام‌های رایج (LBank، شبه‌Binance و شبه‌Bybit) همه پذیرفته می‌شوند.
        «موجودی کل» اولویت با equity/marginBalance است (شامل سود شناور)،
        وگرنه walletBalance/balance، وگرنه آزاد + درگیر.
        """
        rows: Any = data
        if isinstance(data, dict):
            nested = data.get("data") or data.get("assets") or data.get("list")
            if nested is None and any(
                key in data for key in _FUTURES_TOTAL_KEYS + _FUTURES_AVAILABLE_KEYS
            ):
                nested = data
            rows = nested or []
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            return {}

        def pick(row: dict, keys: tuple[str, ...]) -> float:
            for key in keys:
                if key in row and row.get(key) not in (None, ""):
                    value = LBankParser._safe_float(row.get(key), None)
                    if value is not None:
                        return float(value)
            return 0.0

        details: dict[str, dict[str, float]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            # وقتی موجودی یک دارایی مشخص پرسیده می‌شود، پاسخ گاهی نام آن
            # دارایی را تکرار نمی‌کند. بدون این پیش‌فرض، ردیف بی‌نام دور
            # انداخته می‌شد و موجودی فیوچرز صفر به نظر می‌رسید.
            asset = str(
                row.get("asset")
                or row.get("currency")
                or row.get("symbol")
                or row.get("coin")
                or default_asset
            ).upper()
            available = pick(row, _FUTURES_AVAILABLE_KEYS)
            frozen = pick(row, _FUTURES_FROZEN_KEYS)
            margin = pick(row, _FUTURES_MARGIN_KEYS)
            unrealized = pick(row, _FUTURES_UNREALIZED_KEYS)
            total = pick(row, _FUTURES_TOTAL_KEYS)
            wallet = pick(row, _FUTURES_WALLET_KEYS)
            if total <= 0:
                total = wallet + unrealized if wallet > 0 else available + frozen + margin
            if not asset or total <= 0 and available <= 0:
                continue
            item = details.setdefault(asset, {
                "total": 0.0, "available": 0.0, "frozen": 0.0,
                "margin": 0.0, "unrealized": 0.0, "wallet": 0.0,
            })
            item["total"] += max(total, available)
            item["available"] += available
            item["frozen"] += frozen
            item["margin"] += margin
            item["unrealized"] += unrealized
            item["wallet"] += wallet if wallet > 0 else max(total - unrealized, 0.0)
        return details

    async def test_credentials(self) -> tuple[bool, str]:
        """
        آزمایش کلیدهای API با یک درخواست خصوصی فقط‌خواندنی.

        پیام بازگشتی هرگز حاوی کلید نیست.
        """
        if not self._client.has_credentials:
            return False, "API key and secret are not configured"
        try:
            await self._client.post_signed(LBankEndpoints.USER_INFO)
            return True, "Credentials verified successfully"
        except Exception as exc:  # noqa: BLE001 - نتیجه آزمایش باید همیشه برگردد
            message = getattr(exc, "message", str(exc))
            return False, f"{exc.__class__.__name__}: {message}"


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
        """ساخت کلاینت وب‌سوکت LBank (درون‌ریزی تنبل)."""
        from market.providers.lbank.constants import LBANK_WS_URLS
        from market.providers.lbank.websocket_client import LBankWebSocketClient

        # هر کلاینت (مثلاً دو اتصال موازی RedundantStream) از دامنهٔ متفاوتی
        # شروع می‌کند تا فیلتر/خرابی یک دامنه هر دو را هم‌زمان نخواباند.
        counter = int(getattr(self, "_ws_client_counter", 0))
        offset = counter % len(LBANK_WS_URLS)
        self._ws_client_counter = counter + 1
        urls = LBANK_WS_URLS[offset:] + LBANK_WS_URLS[:offset]
        return LBankWebSocketClient(
            urls=urls,
            on_ticker=on_ticker,
            on_candle=on_candle,
            on_status_change=on_status_change,
        )


def create_lbank_provider(**kwargs) -> LBankProvider:
    """
    کارخانه ساخت LBankProvider برای ثبت در ExchangeRegistry.
    """
    return LBankProvider(**kwargs)
