"""
ثابت‌های صرافی Toobit.

Toobit یک API سازگار با سبک Binance دارد: نقاط پایانی عمومی زیر
`/quote/v1/` و نقاط پایانی خصوصی زیر `/api/v1/` با امضای HMAC-SHA256.

نکته دربارهٔ قالب پاسخ: Toobit برای صرفه‌جویی در پهنای باند از کلیدهای
تک‌حرفی استفاده می‌کند (`s` نماد، `c` آخرین قیمت، `h` بیشینه و…). این
نگاشت در `parser.py` انجام می‌شود تا بقیهٔ برنامه با نام‌های کامل کار کند.
"""

from __future__ import annotations

#: نشانی پایهٔ REST
TOOBIT_REST_URL = "https://api.toobit.com"

#: نشانی وب‌سوکت داده بازار
TOOBIT_WS_URL = "wss://stream.toobit.com/quote/ws/v1"

#: نام هدر کلید API (سبک Binance ولی با پیشوند اختصاصی)
TOOBIT_API_KEY_HEADER = "X-BB-APIKEY"

#: بیشینهٔ تعداد کندل در هر درخواست
TOOBIT_MAX_KLINE_SIZE = 1000

#: بیشینهٔ عمق دفتر سفارش
TOOBIT_MAX_DEPTH = 100


class ToobitEndpoints:
    """مسیرهای API که این برنامه استفاده می‌کند."""

    # ---- عمومی ----
    PING = "/api/v1/ping"
    TIME = "/api/v1/time"
    EXCHANGE_INFO = "/api/v1/exchangeInfo"
    TICKER_24H = "/quote/v1/ticker/24hr"
    TICKER_PRICE = "/quote/v1/ticker/price"
    BOOK_TICKER = "/quote/v1/ticker/bookTicker"
    KLINES = "/quote/v1/klines"
    DEPTH = "/quote/v1/depth"
    TRADES = "/quote/v1/trades"

    # ---- خصوصی (امضادار) ----
    ACCOUNT = "/api/v1/account"
    OPEN_ORDERS = "/api/v1/spot/openOrders"
    MY_TRADES = "/api/v1/account/trades"
    BALANCE_FUTURES = "/api/v1/futures/balance"


#: نگاشت تایم‌فریم داخلی به کد Toobit. کدها با استاندارد Binance یکی‌اند،
#: ولی صریح نوشته شده‌اند تا اگر صرافی تغییری داد، همین‌جا دیده شود.
TOOBIT_TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1M",
}

#: تایم‌فریم‌هایی که صرافی مستقیماً می‌دهد (بقیه تجمیع می‌شوند)
TOOBIT_NATIVE_TIMEFRAMES: set[str] = set(TOOBIT_TIMEFRAME_MAP)

#: کد خطاهای شناخته‌شده برای پیام‌های گویا
TOOBIT_ERROR_CODES: dict[int, str] = {
    -1107: "کلید API در هدر درخواست نیست یا قالب آن درست نیست",
    -1022: "امضای درخواست نامعتبر است",
    -2014: "قالب کلید API نادرست است",
    -2015: "کلید API نامعتبر، منقضی یا فاقد دسترسی لازم است",
    -1021: "زمان درخواست با ساعت سرور اختلاف دارد",
    -1121: "نماد نامعتبر است",
}
