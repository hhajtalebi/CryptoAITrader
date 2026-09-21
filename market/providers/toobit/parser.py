"""
تبدیل پاسخ‌های Toobit به مدل‌های داخلی برنامه.

Toobit کلیدهای تک‌حرفی می‌فرستد؛ این پرونده تنها جایی است که آن قالب
فشرده شناخته می‌شود. قالب‌ها با پاسخ واقعی صرافی تطبیق داده شده‌اند:

    24hr ticker: {"t":…,"s":"BTCUSDT","c":"77240","h":…,"l":…,"o":…,
                  "b":bid,"a":ask,"v":volume,"qv":turnover,
                  "pc":priceChange,"pcp":priceChangePercent}
    klines     : [[openTime, open, high, low, close, volume, …], …]
    depth      : {"t":…,"b":[[price,qty],…],"a":[[price,qty],…]}

نکتهٔ مهم دربارهٔ `pcp`: صرافی این مقدار را به‌صورت **کسری** می‌دهد
(`0.0006` یعنی ۰٫۰۶٪)، نه درصد. بدون ضرب در ۱۰۰ همهٔ درصدهای تغییر در
رابط کاربری هزار برابر کوچک‌تر دیده می‌شوند.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.models import Candle, OrderBook, OrderBookLevel, SymbolInfo, Ticker
from app.logging import get_logger

logger = get_logger(__name__)


def _as_float(value: Any, default: float = 0.0) -> float:
    """تبدیل امن به عدد اعشاری؛ مقدار نامعتبر صفر می‌شود."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    """تبدیل امن به عدد صحیح."""
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


class ToobitParser:
    """مترجم پاسخ‌های Toobit به مدل‌های داخلی."""

    @staticmethod
    def to_internal_symbol(exchange_symbol: str) -> str:
        """
        تبدیل `BTCUSDT` به `BTC/USDT`.

        چون Toobit جداکننده ندارد، از فهرست ارزهای مظنه استفاده می‌کنیم و
        طولانی‌ترین تطابق را برمی‌داریم تا `ETHUSDT` با `USDT` جدا شود نه
        با `T`.
        """
        raw = (exchange_symbol or "").strip().upper()
        if not raw or "/" in raw:
            return raw
        quotes = ("USDT", "USDC", "TUSD", "BTC", "ETH", "USD")
        for quote in sorted(quotes, key=len, reverse=True):
            if raw.endswith(quote) and len(raw) > len(quote):
                return f"{raw[: -len(quote)]}/{quote}"
        return raw

    @staticmethod
    def to_exchange_symbol(symbol: str) -> str:
        """تبدیل `BTC/USDT` به `BTCUSDT`."""
        return (symbol or "").replace("/", "").replace("-", "").strip().upper()

    # ------------------------------------------------------------------
    # نمادها
    # ------------------------------------------------------------------
    @classmethod
    def parse_symbols(cls, payload: Any) -> list[SymbolInfo]:
        """
        استخراج نمادها از پاسخ `exchangeInfo`.

        فقط نمادهای در حال معامله برگردانده می‌شوند؛ نماد متوقف‌شده در
        فهرست بازار جز سردرگمی چیزی اضافه نمی‌کند.
        """
        if not isinstance(payload, dict):
            return []
        results: list[SymbolInfo] = []
        for item in payload.get("symbols") or []:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).upper()
            if status and status not in ("TRADING", "1", "ENABLED"):
                continue
            exchange_symbol = str(item.get("symbol") or "").upper()
            if not exchange_symbol:
                continue
            base = str(item.get("baseAsset") or "").upper()
            quote = str(item.get("quoteAsset") or "").upper()
            if not base or not quote:
                internal = cls.to_internal_symbol(exchange_symbol)
                if "/" not in internal:
                    continue
                base, quote = internal.split("/", 1)
            price_precision, qty_precision, min_amount = cls._precisions(item)
            results.append(
                SymbolInfo(
                    symbol=f"{base}/{quote}",
                    exchange_symbol=exchange_symbol,
                    base_asset=base,
                    quote_asset=quote,
                    price_precision=price_precision,
                    quantity_precision=qty_precision,
                    min_order_amount=min_amount,
                )
            )
        return results

    @staticmethod
    def _precisions(item: dict[str, Any]) -> tuple[int, int, float]:
        """
        استخراج دقت قیمت/مقدار و حداقل سفارش از فیلترهای نماد.

        Toobit دقت را مانند Binance در قالب `tickSize`/`stepSize` می‌دهد
        (مثلاً `0.01` یعنی دو رقم اعشار).
        """
        price_precision = _as_int(item.get("quotePrecision"), 8)
        qty_precision = _as_int(item.get("baseAssetPrecision"), 8)
        min_amount = 0.0
        for flt in item.get("filters") or []:
            if not isinstance(flt, dict):
                continue
            kind = str(flt.get("filterType", ""))
            if kind == "PRICE_FILTER" and flt.get("tickSize"):
                price_precision = _decimals(flt["tickSize"])
            elif kind == "LOT_SIZE" and flt.get("stepSize"):
                qty_precision = _decimals(flt["stepSize"])
            elif kind == "MIN_NOTIONAL":
                min_amount = _as_float(flt.get("minNotional"), min_amount)
        return price_precision, qty_precision, min_amount

    # ------------------------------------------------------------------
    # تیکر
    # ------------------------------------------------------------------
    @classmethod
    def parse_ticker(cls, payload: Any, *, symbol: str = "") -> Ticker:
        """تبدیل یک ردیف تیکر ۲۴ ساعته به مدل داخلی."""
        data = payload
        if isinstance(payload, list):
            data = payload[0] if payload else {}
        if not isinstance(data, dict):
            data = {}
        exchange_symbol = str(data.get("s") or data.get("symbol") or "")
        internal = cls.to_internal_symbol(exchange_symbol) if exchange_symbol else symbol
        return Ticker(
            symbol=internal or symbol,
            last_price=_as_float(data.get("c") or data.get("lastPrice")),
            high_24h=_as_float(data.get("h") or data.get("highPrice")),
            low_24h=_as_float(data.get("l") or data.get("lowPrice")),
            volume_24h=_as_float(data.get("v") or data.get("volume")),
            turnover_24h=_as_float(data.get("qv") or data.get("quoteVolume")),
            change_percent=cls._change_percent(data),
            timestamp=_as_int(data.get("t") or data.get("time"), int(time.time() * 1000)),
        )

    @staticmethod
    def _change_percent(data: dict[str, Any]) -> float:
        """
        درصد تغییر ۲۴ ساعته.

        `pcp` کسری است (`0.0006` = ۰٫۰۶٪) پس در ۱۰۰ ضرب می‌شود. اگر این
        فیلد نبود، از قیمت باز و بسته حساب می‌کنیم تا ستون تغییر خالی
        نماند.
        """
        raw = data.get("pcp")
        if raw not in (None, ""):
            return _as_float(raw) * 100.0
        open_price = _as_float(data.get("o") or data.get("openPrice"))
        close_price = _as_float(data.get("c") or data.get("lastPrice"))
        if open_price > 0:
            return (close_price - open_price) / open_price * 100.0
        return 0.0

    @classmethod
    def parse_tickers(cls, payload: Any) -> list[Ticker]:
        """تبدیل پاسخ تیکر همهٔ نمادها."""
        rows = payload if isinstance(payload, list) else payload.get("data", [])
        tickers: list[Ticker] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            ticker = cls.parse_ticker(row)
            if ticker.symbol:
                tickers.append(ticker)
        return tickers

    # ------------------------------------------------------------------
    # داده زنده (WebSocket)
    # ------------------------------------------------------------------
    @classmethod
    def parse_ws_ticker(cls, message: dict[str, Any]) -> Ticker | None:
        """
        تبدیل فریم زندهٔ `realtimes` به مدل Ticker.

        ساختار واقعی (راستی‌آزمایی‌شده با سرور):
            {"symbol":"BTCUSDT","topic":"realtimes","data":[{"t":...,
             "s":"BTCUSDT","c":"77283.79","h":...,"l":...,"o":...,
             "v":...,"qv":...,"m":"-0.0009"}]}

        نکتهٔ مهم: فیلد درصد تغییر اینجا `m` است (نه `pcp` که در REST
        می‌آید) و کسری است — ‎-0.0009‎ یعنی ‎-0.09٪‎. بدون تبدیل، ستون
        «تغییر» صدبرابر کوچک نشان داده می‌شد.
        """
        rows = message.get("data")
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0]
        if not isinstance(row, dict):
            return None

        # `m` را به `pcp` نگاشت می‌کنیم تا از همان منطق مشترک استفاده شود
        # و دو جای مختلف برای «درصد تغییر» نداشته باشیم.
        data = dict(row)
        if "pcp" not in data and data.get("m") not in (None, ""):
            data["pcp"] = data["m"]

        symbol = str(data.get("s") or message.get("symbol") or "")
        ticker = cls.parse_ticker(data, symbol=cls.to_internal_symbol(symbol))
        return ticker if ticker.symbol else None

    @classmethod
    def parse_ws_kline(cls, message: dict[str, Any]) -> tuple[str, str, Candle] | None:
        """
        تبدیل فریم زندهٔ کندل به (نماد داخلی، تایم‌فریم، Candle).

        ساختار واقعی:
            {"symbol":"BTCUSDT","klineType":"1m","topic":"kline",
             "params":{"klineType":"1m",...},
             "data":[{"t":1789318500000,"o":...,"h":...,"l":...,"c":...,"v":...}]}

        دو نکته که در آزمون زنده دیده شد:
        ۱. `topic` در پاسخ `kline` است نه `kline_1m`؛ نوع بازه جدا می‌آید.
        ۲. کلید `klineType` گاهی فقط داخل `params` هست، پس هر دو جا
           خوانده می‌شود وگرنه کندل بدون تایم‌فریم می‌ماند و دور ریخته
           می‌شود.
        """
        rows = message.get("data")
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0]
        if not isinstance(row, dict):
            return None

        params = message.get("params")
        timeframe = str(
            message.get("klineType")
            or (params.get("klineType") if isinstance(params, dict) else "")
            or ""
        ).strip()
        if not timeframe:
            return None

        symbol = cls.to_internal_symbol(
            str(row.get("s") or message.get("symbol") or "")
        )
        if not symbol:
            return None

        # زمان به میلی‌ثانیه می‌آید ولی مدل داخلی ثانیه می‌خواهد.
        timestamp = _as_int(row.get("t"), 0)
        if timestamp <= 0:
            return None
        try:
            candle = Candle(
                timestamp=timestamp // 1000,
                open=float(row["o"]),
                high=float(row["h"]),
                low=float(row["l"]),
                close=float(row["c"]),
                volume=_as_float(row.get("v")),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return symbol, timeframe, candle

    @classmethod
    def parse_price_map(cls, payload: Any) -> dict[str, float]:
        """تبدیل پاسخ `ticker/price` به نگاشت نماد → قیمت."""
        rows = payload if isinstance(payload, list) else [payload]
        prices: dict[str, float] = {}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            symbol = cls.to_internal_symbol(str(row.get("s") or row.get("symbol") or ""))
            price = _as_float(row.get("p") or row.get("price"))
            if symbol and price > 0:
                prices[symbol] = price
        return prices

    # ------------------------------------------------------------------
    # کندل
    # ------------------------------------------------------------------
    @staticmethod
    def parse_candles(payload: Any) -> list[Candle]:
        """
        تبدیل آرایهٔ کندل‌ها.

        زمان از میلی‌ثانیه به ثانیه تبدیل می‌شود چون مدل داخلی ثانیه
        می‌خواهد؛ اختلاط این دو باعث می‌شود نمودارها به سال ۱۹۷۰ بروند.
        """
        if not isinstance(payload, list):
            return []
        candles: list[Candle] = []
        for row in payload:
            if not isinstance(row, (list, tuple)) or len(row) < 6:
                continue
            candles.append(
                Candle(
                    timestamp=_as_int(row[0]) // 1000,
                    open=_as_float(row[1]),
                    high=_as_float(row[2]),
                    low=_as_float(row[3]),
                    close=_as_float(row[4]),
                    volume=_as_float(row[5]),
                )
            )
        candles.sort(key=lambda item: item.timestamp)
        return candles

    # ------------------------------------------------------------------
    # دفتر سفارش
    # ------------------------------------------------------------------
    @classmethod
    def parse_orderbook(cls, payload: Any, *, symbol: str) -> OrderBook:
        """تبدیل دفتر سفارش."""
        data = payload if isinstance(payload, dict) else {}
        bids = [
            OrderBookLevel(price=_as_float(row[0]), quantity=_as_float(row[1]))
            for row in (data.get("b") or data.get("bids") or [])
            if isinstance(row, (list, tuple)) and len(row) >= 2
        ]
        asks = [
            OrderBookLevel(price=_as_float(row[0]), quantity=_as_float(row[1]))
            for row in (data.get("a") or data.get("asks") or [])
            if isinstance(row, (list, tuple)) and len(row) >= 2
        ]
        bids.sort(key=lambda level: level.price, reverse=True)
        asks.sort(key=lambda level: level.price)
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=_as_int(data.get("t"), int(time.time() * 1000)),
        )

    # ------------------------------------------------------------------
    # موجودی
    # ------------------------------------------------------------------
    @staticmethod
    def parse_balances(payload: Any) -> dict[str, float]:
        """
        تبدیل پاسخ حساب به نگاشت دارایی → موجودی کل.

        مانند LBank، شکل پاسخ ممکن است لیست یا دیکشنری باشد؛ هر دو
        پذیرفته می‌شوند تا تغییر جزئی صرافی کیف پول را خالی نکند.
        """
        rows: Any = payload
        if isinstance(payload, dict):
            rows = payload.get("balances") or payload.get("data") or payload.get("list")
            if rows is None:
                rows = [payload]
        if not isinstance(rows, list):
            return {}
        balances: dict[str, float] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = str(
                row.get("asset") or row.get("coin") or row.get("currency") or ""
            ).upper()
            if not asset:
                continue
            free = _as_float(row.get("free") or row.get("available"))
            locked = _as_float(row.get("locked") or row.get("frozen"))
            total = _as_float(row.get("total"))
            amount = total if total > 0 else free + locked
            if amount > 0:
                balances[asset] = balances.get(asset, 0.0) + amount
        return balances


def _decimals(step: Any) -> int:
    """
    شمارش رقم اعشار یک گام قیمت/مقدار.

    `0.01` → ۲ و `1` → ۰. قالب نمایی (`1E-8`) هم پشتیبانی می‌شود چون
    بعضی صرافی‌ها آن را برمی‌گردانند.
    """
    text = str(step).strip()
    if not text:
        return 8
    if "e" in text.lower():
        try:
            from decimal import Decimal

            exponent = Decimal(text).as_tuple().exponent
            return max(0, -int(exponent))
        except Exception:  # noqa: BLE001
            return 8
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1].rstrip("0"))
