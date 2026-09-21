"""
دریافت دادهٔ بازار روی موبایل — فقط با کتابخانهٔ استاندارد.

چرا `urllib` و نه `httpx`؟
    هر وابستگی اضافه یک دستور ساخت (recipe) تازه روی اندروید است و هر
    recipe یک جای شکستن. `urllib` داخل خود پایتون است و روی اندروید
    همیشه هست.

نقطهٔ پایانی عمومی LBank است: کلید API نمی‌خواهد، پس نسخهٔ موبایل
هیچ رازی روی گوشی نگه نمی‌دارد — که خودش یک مزیت امنیتی است.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

LBANK_BASE = "https://api.lbkex.com"
REQUEST_TIMEOUT = 15

# نگاشت تایم‌فریم به شکلی که LBank می‌فهمد.
_LBANK_TIMEFRAMES = {
    "1m": "minute1",
    "5m": "minute5",
    "15m": "minute15",
    "30m": "minute30",
    "1h": "hour1",
    "4h": "hour4",
    "1d": "day1",
}

# چند ثانیه یک پاسخ تازه بماند. روی موبایل، هم باتری و هم مصرف داده
# اهمیت دارد؛ درخواست تکراری پشت سر هم هیچ ارزشی ندارد.
_CACHE_SECONDS = 20
_cache: dict[str, tuple[float, object]] = {}


class MarketError(Exception):
    """خطای دریافت داده، با پیام فارسیِ قابل نمایش به کاربر."""


def _get(path: str, params: dict[str, str]) -> object:
    """درخواست GET با کش کوتاه‌مدت."""
    url = f"{LBANK_BASE}{path}?{urllib.parse.urlencode(params)}"
    now = time.time()
    cached = _cache.get(url)
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]

    request = urllib.request.Request(  # noqa: S310
        url, headers={"User-Agent": "CryptoAITrader-Mobile"}
    )
    try:
        context = ssl.create_default_context()
        with urllib.request.urlopen(  # noqa: S310
            request, timeout=REQUEST_TIMEOUT, context=context
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise MarketError("اتصال به اینترنت برقرار نشد") from exc
    except (ValueError, TimeoutError) as exc:
        raise MarketError("پاسخ نامعتبر از صرافی") from exc

    _cache[url] = (now, payload)
    return payload


def to_lbank_symbol(symbol: str) -> str:
    """`BTC/USDT` را به `btc_usdt` تبدیل می‌کند."""
    return symbol.replace("/", "_").lower()


def fetch_candles(
    symbol: str, timeframe: str = "1h", limit: int = 200
) -> tuple[list[float], list[float], list[float]]:
    """
    دریافت کندل‌ها؛ خروجی سه فهرست موازی (high, low, close).

    قالب LBank: `[timestamp, open, high, low, close, volume]`
    """
    payload = _get(
        "/v2/kline.do",
        {
            "symbol": to_lbank_symbol(symbol),
            "size": str(limit),
            "type": _LBANK_TIMEFRAMES.get(timeframe, "hour1"),
            "time": str(int(time.time()) - limit * 3600),
        },
    )
    if not isinstance(payload, dict) or not payload.get("data"):
        raise MarketError(f"دادهٔ کندل برای {symbol} پیدا نشد")

    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for row in payload["data"]:
        if not isinstance(row, list) or len(row) < 5:
            continue
        highs.append(float(row[2]))
        lows.append(float(row[3]))
        closes.append(float(row[4]))
    if not closes:
        raise MarketError(f"دادهٔ کندل برای {symbol} خالی بود")
    return highs, lows, closes


def fetch_price(symbol: str) -> float:
    """آخرین قیمت یک نماد."""
    payload = _get("/v2/ticker/24hr.do", {"symbol": to_lbank_symbol(symbol)})
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list) and data:
            ticker = data[0].get("ticker", {})
            return float(ticker.get("latest", 0.0))
    raise MarketError(f"قیمت {symbol} دریافت نشد")
