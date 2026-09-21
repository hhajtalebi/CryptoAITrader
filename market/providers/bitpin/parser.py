"""
تبدیل پاسخ‌های بیت‌پین به مدل‌های داخلی برنامه.

قالب‌های واقعی (تأییدشده با فراخوانی زنده):
    markets   : [{"symbol":"BTC_IRT","name":"Bitcoin/Toman","base":"BTC",
                  "quote":"IRT","tradable":true,"suspended":false,
                  "price_precision":0,"base_amount_precision":8,
                  "quote_amount_precision":0}, ...]
    tickers   : [{"symbol":"BTC_IRT","price":"18322168909",
                  "daily_change_price":0.67,"low":"...","high":"...",
                  "timestamp":1789192303.23937}, ...]
    orderbook : {"asks":[["price","amount"],...],"bids":[[...]]}
    matches   : [{"id":"...","price":"77303.88","base_amount":"0.0039",
                  "quote_amount":"304.43","side":"buy","time":1789192066.69}]

نکته: `daily_change_price` همین حالا درصد است (۰٫۶۷ یعنی ۰٫۶۷٪) و نباید
در ۱۰۰ ضرب شود — برخلاف Toobit که کسر می‌دهد.
"""

from __future__ import annotations

from typing import Any

from app.core.models import Candle, OrderBook, OrderBookLevel, SymbolInfo, Ticker
from market.providers.bitpin.constants import (
    BITPIN_QUOTE_ASSETS,
    BITPIN_SYMBOL_SEPARATOR,
)


def _to_float(value: Any, default: float = 0.0) -> float:
    """تبدیل امن به عدد اعشاری؛ بیت‌پین اعداد را رشته‌ای می‌فرستد."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    """تبدیل امن به عدد صحیح."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class BitpinParser:
    """مبدل داده‌های بیت‌پین."""

    # ------------------------------------------------------------------
    # نماد
    # ------------------------------------------------------------------
    @staticmethod
    def to_exchange_symbol(symbol: str) -> str:
        """`BTC/USDT` → `BTC_USDT`."""
        return (symbol or "").replace("/", BITPIN_SYMBOL_SEPARATOR).upper().strip()

    @staticmethod
    def to_internal_symbol(exchange_symbol: str) -> str:
        """`BTC_USDT` → `BTC/USDT`."""
        return (exchange_symbol or "").replace(BITPIN_SYMBOL_SEPARATOR, "/").upper().strip()

    # ------------------------------------------------------------------
    # نمادها
    # ------------------------------------------------------------------
    @staticmethod
    def parse_symbols(payload: Any) -> list[SymbolInfo]:
        """تبدیل فهرست بازارها به SymbolInfo."""
        if not isinstance(payload, list):
            return []
        symbols: list[SymbolInfo] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            exchange_symbol = str(row.get("symbol") or "").upper()
            if not exchange_symbol:
                continue
            # بازارهای غیرقابل معامله یا معلق نباید به کاربر پیشنهاد شوند
            if row.get("tradable") is False or row.get("suspended") is True:
                continue
            base = str(row.get("base") or "").upper()
            quote = str(row.get("quote") or "").upper()
            if not base or not quote:
                parts = exchange_symbol.split(BITPIN_SYMBOL_SEPARATOR)
                if len(parts) != 2:
                    continue
                base, quote = parts
            symbols.append(
                SymbolInfo(
                    symbol=f"{base}/{quote}",
                    exchange_symbol=exchange_symbol,
                    base_asset=base,
                    quote_asset=quote,
                    price_precision=_to_int(row.get("price_precision"), 8),
                    quantity_precision=_to_int(row.get("base_amount_precision"), 8),
                    min_order_amount=0.0,
                )
            )
        return symbols

    # ------------------------------------------------------------------
    # تیکر
    # ------------------------------------------------------------------
    @staticmethod
    def parse_ticker(row: dict[str, Any], *, symbol: str | None = None) -> Ticker:
        """تبدیل یک ردیف تیکر."""
        exchange_symbol = str(row.get("symbol") or "")
        internal = symbol or BitpinParser.to_internal_symbol(exchange_symbol)
        return Ticker(
            symbol=internal,
            last_price=_to_float(row.get("price")),
            high_24h=_to_float(row.get("high")),
            low_24h=_to_float(row.get("low")),
            # بیت‌پین حجم ۲۴ ساعته را در تیکر نمی‌دهد
            volume_24h=_to_float(row.get("volume")),
            turnover_24h=_to_float(row.get("quote_volume")),
            # این مقدار از قبل درصد است
            change_percent=_to_float(row.get("daily_change_price")),
            timestamp=_to_int(row.get("timestamp")),
        )

    @staticmethod
    def parse_tickers(payload: Any) -> list[Ticker]:
        """تبدیل کل فهرست تیکرها."""
        if not isinstance(payload, list):
            return []
        return [
            BitpinParser.parse_ticker(row)
            for row in payload
            if isinstance(row, dict) and row.get("symbol")
        ]

    @staticmethod
    def find_ticker(payload: Any, exchange_symbol: str) -> dict[str, Any] | None:
        """
        یافتن یک نماد در فهرست تیکرها.

        بیت‌پین فیلتر تک‌نمادی ندارد (پارامتر symbol نادیده گرفته می‌شود)،
        پس ناچار کل فهرست را می‌گیریم و همین‌جا جست‌وجو می‌کنیم.
        """
        if not isinstance(payload, list):
            return None
        target = exchange_symbol.upper()
        for row in payload:
            if isinstance(row, dict) and str(row.get("symbol", "")).upper() == target:
                return row
        return None

    # ------------------------------------------------------------------
    # دفتر سفارش
    # ------------------------------------------------------------------
    @staticmethod
    def parse_orderbook(payload: Any, *, symbol: str, depth: int = 20) -> OrderBook:
        """تبدیل دفتر سفارش."""
        bids: list[OrderBookLevel] = []
        asks: list[OrderBookLevel] = []
        if isinstance(payload, dict):
            for raw in (payload.get("bids") or [])[:depth]:
                level = BitpinParser._parse_level(raw)
                if level is not None:
                    bids.append(level)
            for raw in (payload.get("asks") or [])[:depth]:
                level = BitpinParser._parse_level(raw)
                if level is not None:
                    asks.append(level)
        import time as _time

        return OrderBook(
            symbol=symbol,
            bids=sorted(bids, key=lambda x: x.price, reverse=True),
            asks=sorted(asks, key=lambda x: x.price),
            timestamp=int(_time.time()),
        )

    @staticmethod
    def _parse_level(raw: Any) -> OrderBookLevel | None:
        """تبدیل یک سطح دفتر سفارش."""
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            price = _to_float(raw[0])
            quantity = _to_float(raw[1])
            if price > 0:
                return OrderBookLevel(price=price, quantity=quantity)
        return None

    # ------------------------------------------------------------------
    # ساخت کندل از معاملات
    # ------------------------------------------------------------------
    @staticmethod
    def candles_from_matches(
        payload: Any, *, interval_seconds: int, limit: int = 300
    ) -> list[Candle]:
        """
        ساخت کندل از فهرست معاملات اخیر.

        بیت‌پین endpoint کندل ندارد؛ تنها راه بازسازی، سطل‌بندی زمانی
        معاملات است. کندل‌ها فقط تا جایی عقب می‌روند که فهرست معاملات
        پوشش می‌دهد (معمولاً چند ساعت)، بنابراین برای تحلیل بلندمدت
        مناسب نیستند و موتور باید این را بداند.
        """
        if not isinstance(payload, list) or interval_seconds <= 0:
            return []

        buckets: dict[int, list[tuple[float, float, float]]] = {}
        for row in payload:
            if not isinstance(row, dict):
                continue
            price = _to_float(row.get("price"))
            if price <= 0:
                continue
            amount = _to_float(row.get("base_amount"))
            timestamp = _to_float(row.get("time"))
            if timestamp <= 0:
                continue
            bucket = int(timestamp) // interval_seconds * interval_seconds
            buckets.setdefault(bucket, []).append((timestamp, price, amount))

        candles: list[Candle] = []
        for bucket in sorted(buckets):
            trades = sorted(buckets[bucket], key=lambda item: item[0])
            prices = [item[1] for item in trades]
            candles.append(
                Candle(
                    timestamp=bucket,
                    open=prices[0],
                    high=max(prices),
                    low=min(prices),
                    close=prices[-1],
                    volume=sum(item[2] for item in trades),
                )
            )
        return candles[-limit:] if limit else candles

    # ------------------------------------------------------------------
    # موجودی
    # ------------------------------------------------------------------
    @staticmethod
    def parse_balances(payload: Any) -> dict[str, float]:
        """
        تبدیل کیف پول‌ها به نگاشت دارایی → موجودی.

        پاسخ ممکن است مستقیم لیست باشد یا درون کلید `results` (قالب
        صفحه‌بندی Django REST) بیاید؛ هر دو پشتیبانی می‌شود.
        """
        rows: list[Any] = []
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            for key in ("results", "data", "wallets"):
                value = payload.get(key)
                if isinstance(value, list):
                    rows = value
                    break

        balances: dict[str, float] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = str(
                row.get("asset") or row.get("currency") or row.get("code") or ""
            ).upper()
            if not asset:
                continue
            total = _to_float(row.get("balance"))
            if total <= 0:
                # بعضی پاسخ‌ها موجودی را تفکیک‌شده می‌دهند
                total = _to_float(row.get("free")) + _to_float(row.get("frozen"))
            if total > 0:
                balances[asset] = balances.get(asset, 0.0) + total
        return balances
