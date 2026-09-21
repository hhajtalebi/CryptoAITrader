"""
ثابت‌های صرافی ایرانی بیت‌پین (Bitpin).

نکته‌های مهمی که با آزمایش زنده روی همین صرافی تأیید شده‌اند:

۱. دامنهٔ `api.bitpin.org` از بیرون ایران مسدود است، ولی
   `api.bitpin.market` پشت Cloudflare قرار دارد و از همه‌جا در دسترس است.
   بنابراین دامنهٔ پیش‌فرض `.market` انتخاب شده و بقیه به‌عنوان جایگزین
   نگهداری می‌شوند.

۲. مسیر ورود که در مستندات رسمی آمده (`/v1/usr/api/login/`) دیگر کار
   نمی‌کند و ۴۰۴ برمی‌گرداند. مسیر واقعیِ فعال `/api/v1/usr/authenticate/`
   است.

۳. بیت‌پین **هیچ endpoint عمومی برای کندل (OHLC) ندارد**؛ همهٔ مسیرهای
   محتمل آزمایش و ۴۰۴ گرفتند. پس کندل‌ها از فهرست معاملات اخیر ساخته
   می‌شوند. این محدودیت واقعی صرافی است، نه ساده‌سازی ما.

۴. احراز هویت مبتنی بر توکن است نه امضای هر درخواست: کلید و رمز یک جفت
   توکن (refresh + access) می‌دهند و access حدود ۱۵ دقیقه اعتبار دارد.
"""

from __future__ import annotations

from typing import Final

#: دامنهٔ پیش‌فرض؛ تنها دامنه‌ای که از خارج ایران هم پاسخ می‌دهد
BITPIN_REST_URL: Final[str] = "https://api.bitpin.market"

#: دامنه‌های جایگزین برای زمانی که کاربر داخل ایران است
BITPIN_FALLBACK_URLS: Final[tuple[str, ...]] = (
    "https://api.bitpin.market",
    "https://api.bitpin.org",
    "https://api.bitpin.ir",
)

#: سقف نرخ درخواست اعلام‌شده در مستندات (هر IP)
BITPIN_RATE_LIMIT_PER_MINUTE: Final[int] = 300

#: عمر تقریبی توکن دسترسی؛ کمی زودتر تازه‌سازی می‌کنیم تا در میانهٔ
#: درخواست منقضی نشود
BITPIN_ACCESS_TOKEN_TTL: Final[int] = 15 * 60
BITPIN_TOKEN_REFRESH_MARGIN: Final[int] = 60


class BitpinEndpoints:
    """مسیرهای API بیت‌پین (همگی با اسلش پایانی)."""

    # --- عمومی ---
    CURRENCIES = "/api/v1/mkt/currencies/"
    MARKETS = "/api/v1/mkt/markets/"
    TICKERS = "/api/v1/mkt/tickers/"
    ORDERBOOK = "/api/v1/mth/orderbook/{symbol}/"
    MATCHES = "/api/v1/mth/matches/{symbol}/"

    # --- احراز هویت ---
    AUTHENTICATE = "/api/v1/usr/authenticate/"
    REFRESH_TOKEN = "/api/v1/usr/refresh_token/"

    # --- خصوصی ---
    WALLETS = "/api/v1/wlt/wallets/"
    ORDERS = "/api/v1/odr/orders/"
    FILLS = "/api/v1/odr/fills/"
    DEPOSITS = "/api/v2/wlt/deposits/"
    WITHDRAWS = "/api/v2/wlt/withdraws/"
    NETWORKS = "/api/v2/wlt/networks/"


#: جداکنندهٔ نماد در بیت‌پین: BTC_USDT
BITPIN_SYMBOL_SEPARATOR: Final[str] = "_"

#: ارزهای مظنه‌ای که بیت‌پین پشتیبانی می‌کند
BITPIN_QUOTE_ASSETS: Final[tuple[str, ...]] = ("IRT", "USDT")

#: نماد بازار تتر/تومان؛ مبنای محاسبهٔ نرخ لحظه‌ای تومان
BITPIN_USDT_IRT_SYMBOL: Final[str] = "USDT_IRT"

#: چون کندل بومی وجود ندارد، تایم‌فریم‌های بومی خالی است و همه‌چیز از
#: معاملات ساخته می‌شود. تنها تایم‌فریم‌های کوتاه منطقی‌اند چون فهرست
#: معاملات حدود ۱۰۰ رکورد (چند ساعت) پوشش می‌دهد.
BITPIN_SYNTHETIC_TIMEFRAMES: Final[tuple[str, ...]] = ("1m", "5m", "15m", "30m", "1h")

#: بیشترین تعداد معامله‌ای که endpoint برمی‌گرداند
BITPIN_MAX_MATCHES: Final[int] = 100

#: نگاشت کد خطاهای شناخته‌شده به پیام قابل فهم
BITPIN_ERROR_CODES: Final[dict[str, str]] = {
    "api_credential_wrong": (
        "Bitpin rejected the API credentials, or this IP address is not in "
        "the key's allow-list"
    ),
    "token_not_valid": "The Bitpin access token is invalid or has expired",
    "not_authenticated": "Bitpin authentication is required for this endpoint",
}

#: پیام خطای ویژهٔ محدودیت IP — رایج‌ترین اشتباه کاربران بیت‌پین
BITPIN_IP_HINT_CODE: Final[str] = "api_credential_wrong"
