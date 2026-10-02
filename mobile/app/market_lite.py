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

# طول هر کندل به ثانیه — برای محاسبهٔ نقطهٔ شروع درست.
# (اشکال نسخه‌های قبل: شروع همیشه `limit × 3600` ثانیه پیش بود؛ برای ۱۵ دقیقه
# یعنی کندل‌های ۲۰۰ ساعت پیش — دادهٔ کهنه — و برای روزانه فقط ۸ کندل.)
_TIMEFRAME_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
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
            "time": str(candles_start(timeframe, limit)),
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


def candles_start(timeframe: str, limit: int, now: float | None = None) -> int:
    """
    ثانیهٔ شروع، طوری که `limit` کندلِ **آخر** برگردد.

    گرد شده به مرز کندل، تا URL درون یک کندل ثابت بماند و کش کار کند.
    """
    step = _TIMEFRAME_SECONDS.get(timeframe, 3600)
    current = time.time() if now is None else now
    return (int(current) // step - (limit - 1)) * step


def parse_tickers(payload: object, quote: str = "usdt") -> list[dict]:
    """
    پاسخ `ticker/24hr.do?symbol=all` ← فهرست ساده و تمیز.

    فقط جفت‌های با ارز مظنهٔ `quote`؛ جفت‌های بی‌قیمت یا بی‌حجم کنار
    گذاشته می‌شوند (روی صفحهٔ کوچک فقط شلوغی می‌سازند).
    """
    rows: list[dict] = []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return rows
    suffix = "_" + quote.lower()
    for item in data:
        if not isinstance(item, dict):
            continue
        pair = str(item.get("symbol", "")).lower()
        if not pair.endswith(suffix):
            continue
        body = item.get("ticker") or {}
        try:
            price = float(body.get("latest") or 0)
            turnover = float(body.get("turnover") or 0)
            change = float(body.get("change") or 0)
            high = float(body.get("high") or 0)
            low = float(body.get("low") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0 or turnover <= 0:
            continue
        base = pair[: -len(suffix)].upper()
        rows.append({
            "symbol": f"{base}/{quote.upper()}", "base": base, "price": price,
            "change": change, "turnover": turnover, "high": high, "low": low,
        })
    return rows


def fetch_tickers(quote: str = "usdt") -> list[dict]:
    """همهٔ نمادهای بازار با یک درخواست (به‌جای یک درخواست برای هر نماد)."""
    rows = parse_tickers(_get("/v2/ticker/24hr.do", {"symbol": "all"}), quote)
    if not rows:
        raise MarketError("فهرست بازار دریافت نشد")
    return rows


def fetch_price(symbol: str) -> float:
    """آخرین قیمت یک نماد."""
    payload = _get("/v2/ticker/24hr.do", {"symbol": to_lbank_symbol(symbol)})
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list) and data:
            ticker = data[0].get("ticker", {})
            return float(ticker.get("latest", 0.0))
    raise MarketError(f"قیمت {symbol} دریافت نشد")
