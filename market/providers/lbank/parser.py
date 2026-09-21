"""
مبدل پاسخ خام LBank به مدل‌های داخلی نرم‌افزار.

چرا جدا از Provider؟
    جداسازی «تجزیه داده» از «ارتباط شبکه» باعث می‌شود بتوان بدون هیچ
    درخواست شبکه‌ای، منطق تجزیه را تست کرد (tests/test_lbank_parser.py).

قالب‌های ورودی (راستی‌آزمایی‌شده با API واقعی):
    kline : [[time, open, high, low, close, volume], ...]
    ticker: {"symbol": "...", "ticker": {"high","vol","low","change","turnover","latest"}, "timestamp": ...}
    depth : {"asks": [[price, qty], ...], "bids": [[...]], "timestamp": ...}
"""

from __future__ import annotations

from typing import Any

from app.core.models import Candle, OrderBook, OrderBookLevel, SymbolInfo, Ticker
from app.exceptions import ValidationError
from app.logging import get_logger

logger = get_logger(__name__)


class LBankParser:
    """
    مجموعه توابع ایستا برای تبدیل پاسخ LBank به مدل‌های داخلی.

    اصل مهم: هیچ داده‌ای ساخته نمی‌شود؛ اگر فیلدی موجود نباشد یا نامعتبر
    باشد، رکورد نامعتبر نادیده گرفته می‌شود یا خطا پرتاب می‌گردد.
    """

    # ------------------------------------------------------------------
    # نگاشت نماد
    # ------------------------------------------------------------------
    @staticmethod
    def to_internal_symbol(exchange_symbol: str) -> str:
        """
        تبدیل نماد LBank به قالب داخلی: btc_usdt → BTC/USDT
        """
        if "_" not in exchange_symbol:
            return exchange_symbol.upper()
        base, _, quote = exchange_symbol.partition("_")
        return f"{base.upper()}/{quote.upper()}"

    @staticmethod
    def to_exchange_symbol(symbol: str) -> str:
        """
        تبدیل نماد داخلی به قالب LBank: BTC/USDT → btc_usdt
        """
        return symbol.replace("/", "_").lower()

    # ------------------------------------------------------------------
    # نمادها
    # ------------------------------------------------------------------
    @staticmethod
    def parse_symbols(pairs: list[Any], accuracy: list[dict[str, Any]] | None = None) -> list[SymbolInfo]:
        """
        ساخت فهرست نمادها از پاسخ currencyPairs.do و accuracy.do.

        داده دقت قیمت/مقدار اختیاری است؛ در نبود آن مقادیر پیش‌فرض به کار
        می‌رود، اما هیچ عدد ساختگی به‌عنوان «دقت واقعی» گزارش نمی‌شود.
        """
        accuracy_map: dict[str, dict[str, Any]] = {}
        for item in accuracy or []:
            symbol_key = str(item.get("symbol", "")).lower()
            if symbol_key:
                accuracy_map[symbol_key] = item

        symbols: list[SymbolInfo] = []
        for raw_pair in pairs:
            if not isinstance(raw_pair, str) or "_" not in raw_pair:
                continue
            base, _, quote = raw_pair.partition("_")
            precision = accuracy_map.get(raw_pair.lower(), {})
            symbols.append(
                SymbolInfo(
                    symbol=LBankParser.to_internal_symbol(raw_pair),
                    exchange_symbol=raw_pair.lower(),
                    base_asset=base.upper(),
                    quote_asset=quote.upper(),
                    price_precision=LBankParser._safe_int(precision.get("priceAccuracy"), 8),
                    quantity_precision=LBankParser._safe_int(precision.get("quantityAccuracy"), 8),
                    min_order_amount=LBankParser._safe_float(precision.get("minOrderAmount"), 0.0),
                )
            )
        return symbols

    # ------------------------------------------------------------------
    # کندل‌ها
    # ------------------------------------------------------------------
    @staticmethod
    def parse_klines(data: list[Any]) -> list[Candle]:
        """
        تبدیل آرایه کندل‌های LBank به فهرست Candle.

        هر عنصر باید آرایه‌ای شش‌تایی باشد:
            [open_time_seconds, open, high, low, close, volume]
        رکوردهای ناقص یا خراب نادیده گرفته و در سطح DEBUG لاگ می‌شوند.
        """
        candles: list[Candle] = []
        skipped = 0
        for row in data or []:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                skipped += 1
                continue
            try:
                candle = Candle(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            except (TypeError, ValueError):
                skipped += 1
                continue
            # اعتبارسنجی منطقی: سقف نباید کمتر از کف باشد
            if candle.high < candle.low or candle.timestamp <= 0:
                skipped += 1
                continue
            candles.append(candle)

        if skipped:
            logger.debug("Skipped %d malformed kline rows", skipped)
        candles.sort(key=lambda c: c.timestamp)
        return candles

    # ------------------------------------------------------------------
    # تیکر
    # ------------------------------------------------------------------
    @staticmethod
    def parse_ticker(item: dict[str, Any]) -> Ticker:
        """
        تبدیل یک رکورد ticker/24hr.do به مدل Ticker.

        ساختار واقعی پاسخ:
            {"symbol": "btc_usdt",
             "ticker": {"high","vol","low","change","turnover","latest"},
             "timestamp": 1788851626760}
        """
        if not isinstance(item, dict) or "ticker" not in item:
            raise ValidationError("Invalid LBank ticker payload", details={"keys": list(item or {})})

        body = item.get("ticker") or {}
        symbol_raw = str(item.get("symbol", ""))
        return Ticker(
            symbol=LBankParser.to_internal_symbol(symbol_raw),
            last_price=LBankParser._safe_float(body.get("latest"), 0.0),
            high_24h=LBankParser._safe_float(body.get("high"), 0.0),
            low_24h=LBankParser._safe_float(body.get("low"), 0.0),
            volume_24h=LBankParser._safe_float(body.get("vol"), 0.0),
            turnover_24h=LBankParser._safe_float(body.get("turnover"), 0.0),
            change_percent=LBankParser._safe_float(body.get("change"), 0.0),
            timestamp=int(LBankParser._safe_float(item.get("timestamp"), 0.0)),
        )

    @staticmethod
    def parse_tickers(data: list[Any]) -> list[Ticker]:
        """تبدیل فهرست تیکرها؛ رکوردهای خراب نادیده گرفته می‌شوند."""
        tickers: list[Ticker] = []
        for item in data or []:
            try:
                tickers.append(LBankParser.parse_ticker(item))
            except ValidationError:
                continue
        return tickers

    @staticmethod
    def parse_price_list(data: list[Any]) -> dict[str, float]:
        """
        تبدیل پاسخ supplement/ticker/price.do به نگاشت «نماد → قیمت».

        این Endpoint سبک‌ترین راه برای گرفتن قیمت همه نمادها در یک درخواست
        است و برای به‌روزرسانی فهرست بازارها استفاده می‌شود.
        """
        prices: dict[str, float] = {}
        for item in data or []:
            if not isinstance(item, dict):
                continue
            symbol_raw = str(item.get("symbol", ""))
            if not symbol_raw:
                continue
            price = LBankParser._safe_float(item.get("price"), None)
            if price is not None:
                prices[LBankParser.to_internal_symbol(symbol_raw)] = price
        return prices

    # ------------------------------------------------------------------
    # دفتر سفارش
    # ------------------------------------------------------------------
    @staticmethod
    def parse_orderbook(symbol: str, data: dict[str, Any]) -> OrderBook:
        """تبدیل پاسخ depth.do به مدل OrderBook."""
        if not isinstance(data, dict):
            raise ValidationError("Invalid LBank depth payload")

        def _levels(rows: Any) -> list[OrderBookLevel]:
            """تبدیل آرایه [[price, qty], ...] به فهرست سطوح معتبر."""
            levels: list[OrderBookLevel] = []
            for row in rows or []:
                if not isinstance(row, (list, tuple)) or len(row) < 2:
                    continue
                price = LBankParser._safe_float(row[0], None)
                quantity = LBankParser._safe_float(row[1], None)
                if price is None or quantity is None:
                    continue
                levels.append(OrderBookLevel(price=price, quantity=quantity))
            return levels

        bids = sorted(_levels(data.get("bids")), key=lambda x: x.price, reverse=True)
        asks = sorted(_levels(data.get("asks")), key=lambda x: x.price)
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=int(LBankParser._safe_float(data.get("timestamp"), 0.0)),
        )

    # ------------------------------------------------------------------
    # پیام‌های WebSocket
    # ------------------------------------------------------------------
    @staticmethod
    def parse_ws_tick(message: dict[str, Any]) -> Ticker | None:
        """
        تبدیل پیام لحظه‌ای WebSocket از نوع tick به مدل Ticker.

        ساختار واقعی:
            {"tick": {"high","vol","low","change","turnover","latest",...},
             "type": "tick", "pair": "btc_usdt", "TS": "..."}
        """
        tick = message.get("tick")
        pair = message.get("pair")
        if not isinstance(tick, dict) or not pair:
            return None
        return Ticker(
            symbol=LBankParser.to_internal_symbol(str(pair)),
            last_price=LBankParser._safe_float(tick.get("latest"), 0.0),
            high_24h=LBankParser._safe_float(tick.get("high"), 0.0),
            low_24h=LBankParser._safe_float(tick.get("low"), 0.0),
            volume_24h=LBankParser._safe_float(tick.get("vol"), 0.0),
            turnover_24h=LBankParser._safe_float(tick.get("turnover"), 0.0),
            change_percent=LBankParser._safe_float(tick.get("change"), 0.0),
            timestamp=0,
        )

    @staticmethod
    def parse_ws_kbar(message: dict[str, Any]) -> tuple[str, Candle] | None:
        """
        تبدیل پیام کندل زنده WebSocket به (نماد، Candle).

        ساختار واقعی:
            {"kbar": {"a","c","t","v","h","slot","l","n","o"}, "pair": "...", "type": "kbar"}
        که در آن o/h/l/c قیمت‌ها، v حجم و t زمان به قالب ISO است.
        """
        kbar = message.get("kbar")
        pair = message.get("pair")
        if not isinstance(kbar, dict) or not pair:
            return None
        timestamp = LBankParser._parse_iso_seconds(kbar.get("t"))
        if timestamp is None:
            return None
        try:
            candle = Candle(
                timestamp=timestamp,
                open=float(kbar["o"]),
                high=float(kbar["h"]),
                low=float(kbar["l"]),
                close=float(kbar["c"]),
                volume=float(kbar.get("v", 0.0)),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return LBankParser.to_internal_symbol(str(pair)), candle

    @staticmethod
    def parse_ws_depth(symbol: str, message: dict[str, Any]) -> OrderBook | None:
        """تبدیل پیام depth زنده WebSocket به مدل OrderBook."""
        depth = message.get("depth")
        if not isinstance(depth, dict):
            return None
        try:
            return LBankParser.parse_orderbook(symbol, depth)
        except ValidationError:
            return None

    # ------------------------------------------------------------------
    # کمکی‌ها
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_float(value: Any, default: float | None) -> float | None:
        """تبدیل امن به عدد اعشاری؛ در صورت شکست مقدار پیش‌فرض."""
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int) -> int:
        """تبدیل امن به عدد صحیح."""
        if value is None:
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_iso_seconds(value: Any) -> int | None:
        """
        تبدیل زمان ISO ارسالی WebSocket (مثل 2026-09-08T15:14:00.000) به ثانیه UTC.
        """
        if not isinstance(value, str) or not value:
            return None
        from datetime import datetime, timezone  # noqa: PLC0415 - فقط در همین مسیر لازم است

        try:
            cleaned = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
        except ValueError:
            return None
