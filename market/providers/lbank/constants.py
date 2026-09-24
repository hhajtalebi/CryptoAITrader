"""
ثابت‌ها و نگاشت‌های اختصاصی صرافی LBank.

منبع: مستندات رسمی LBank API نسخه ۲.
راستی‌آزمایی: تمام مقادیر زیر با فراخوانی واقعی API آزمایش شده‌اند؛ به‌ویژه
فهرست تایم‌فریم‌های پشتیبانی‌شده که با مستندات قدیمی تفاوت دارد.
"""

from __future__ import annotations

from typing import Final

# نشانی پایه REST (مطابق مستندات رسمی و آزمایش عملی)
LBANK_REST_URL: Final[str] = "https://api.lbkex.com"

# نشانی WebSocket نسخه ۲
LBANK_WS_URL: Final[str] = "wss://www.lbkex.net/ws/V2/"

# نسخهٔ ۲.۳.۲: مستندات فعلی LBank (www.lbank.com/docs) نشانی رسمی را
# api.lbank.info اعلام می‌کند و www.lbkex.net نشانی قدیمی است. اگر یک دامنه در
# شبکهٔ کاربر مسدود/فیلتر باشد یا دست‌دادن را رد کند، کلاینت به ترتیب سراغ
# بعدی می‌رود؛ دامنهٔ موفق تا قطع بعدی حفظ می‌شود.
LBANK_WS_URLS: Final[tuple[str, ...]] = (
    "wss://api.lbank.info/ws/V2/",
    LBANK_WS_URL,
    "wss://api.lbkex.com/ws/V2/",
)

# دامنه‌های جایگزین REST؛ فقط هنگام خطای «اتصال» (DNS/TCP/TLS) عوض می‌شوند.
LBANK_REST_URLS: Final[tuple[str, ...]] = (
    LBANK_REST_URL,
    "https://api.lbank.info",
    "https://www.lbkex.net",
)

# سقف تعداد کندل در هر درخواست (آزمایش شد: ۲۰۰۰ مجاز، ۳۰۰۰ خطای پارامتر)
LBANK_MAX_KLINE_SIZE: Final[int] = 2000


class LBankEndpoints:
    """
    مسیرهای REST مورد استفاده.

    همه مسیرها با پیشوند /v2 و پسوند .do هستند که قرارداد نام‌گذاری LBank است.
    """

    TIMESTAMP: Final[str] = "/v2/timestamp.do"
    CURRENCY_PAIRS: Final[str] = "/v2/currencyPairs.do"
    ACCURACY: Final[str] = "/v2/accuracy.do"
    TICKER_24HR: Final[str] = "/v2/ticker/24hr.do"
    KLINE: Final[str] = "/v2/kline.do"
    DEPTH: Final[str] = "/v2/depth.do"
    TRADES: Final[str] = "/v2/trades.do"
    PRICE: Final[str] = "/v2/supplement/ticker/price.do"
    BOOK_TICKER: Final[str] = "/v2/supplement/ticker/bookTicker.do"

    # مسیرهای خصوصی (نیازمند امضا) — فقط خواندنی در نسخه اول
    USER_INFO: Final[str] = "/v2/supplement/user_info.do"
    ORDERS_INFO: Final[str] = "/v2/supplement/orders_info.do"
    ORDERS_INFO_HISTORY: Final[str] = "/v2/supplement/orders_info_history.do"


# ---------------------------------------------------------------------------
# قراردادهای آتی (Futures/Perpetual)
# ---------------------------------------------------------------------------
# نکتهٔ مهم: بخش قراردادها روی **دامنهٔ جداگانه** و با پیشوند /cfd است؛
# نقاط پایانی اسپات (api.lbkex.com) هیچ موجودی فیوچرزی برنمی‌گردانند.
# به همین دلیل کیف پول فقط موجودی اسپات را نشان می‌داد.
LBANK_CONTRACT_URL: Final[str] = "https://lbkperp.lbank.com"


class LBankContractEndpoints:
    """مسیرهای REST بخش قراردادهای آتی."""

    TIME: Final[str] = "/cfd/openApi/v1/pub/getTime"
    INSTRUMENT: Final[str] = "/cfd/openApi/v1/pub/instrument"
    # موجودی حساب قرارداد؛ productGroup=SwapU یعنی قراردادهای مبتنی بر USDT
    ACCOUNT: Final[str] = "/cfd/openApi/v1/prv/account"
    POSITIONS: Final[str] = "/cfd/openApi/v1/prv/positions"


CONTRACT_PRODUCT_GROUP: Final[str] = "SwapU"

# دارایی‌هایی که موجودی قراردادشان پرسیده می‌شود.
#
# چرا فهرست و نه یک درخواست «همه»؟
#     مستند رسمی LBank برای `prv/account` پارامتر `asset` را در رشتهٔ
#     امضا آورده است (`api_key=…&asset=USDT&echostr=…&productGroup=SwapU`).
#     بدون آن، درخواست با «Illegal parameter» رد می‌شد و چون خطای فیوچرز
#     عمداً بلعیده می‌شود، کاربر فقط موجودی اسپات را می‌دید — همان گزارشِ
#     «دارایی فیوچرز نمایش داده نمی‌شود».
#     قراردادهای USDT-margined روی LBank با همین چند دارایی تسویه می‌شوند.
CONTRACT_ASSETS: Final[tuple[str, ...]] = ("USDT", "USDC", "BTC", "ETH")


# نگاشت تایم‌فریم داخلی به نام مورد انتظار LBank.
# نکته مهم (آزمایش‌شده): تایم‌فریم‌های 3m، 2h، 6h، 8h و 12h توسط LBank
# پشتیبانی نمی‌شوند و پاسخ خطا برمی‌گردانند؛ بنابراین در این نگاشت نیستند و
# موتور تایم‌فریم آن‌ها را از داده پایه تجمیع می‌کند.
LBANK_TIMEFRAME_MAP: Final[dict[str, str]] = {
    "1m": "minute1",
    "5m": "minute5",
    "15m": "minute15",
    "30m": "minute30",
    "1h": "hour1",
    "4h": "hour4",
    "1d": "day1",
    "1w": "week1",
    "1M": "month1",
}

# تایم‌فریم‌هایی که باید با تجمیع ساخته شوند (کلید: مقصد، مقدار: مبدأ پیشنهادی)
LBANK_AGGREGATED_TIMEFRAMES: Final[dict[str, str]] = {
    "3m": "1m",
    "2h": "1h",
    "6h": "1h",
    "8h": "4h",
    "12h": "4h",
}

# کدهای خطای LBank مطابق جدول رسمی (www.lbank.com/docs → Error code).
# تا نسخهٔ ۲.۳.۱ این جدول جابه‌جا بود: 10004 («درخواست بیش از حد») به‌اشتباه
# «امضای نامعتبر» و خطای احراز هویت شمرده می‌شد، پس محدودیت نرخ LBank به‌جای
# مکث، اتصال REST را «مرده» اعلام می‌کرد.
RATE_LIMIT_ERROR_CODES: Final[set[int]] = {10004}
# ثانیهٔ مکث پیش‌فرض پس از 10004 (صرافی Retry-After نمی‌فرستد).
RATE_LIMIT_RETRY_AFTER: Final[float] = 10.0
# کدهای خطای LBank که تکرار درخواست برایشان منطقی است.
RETRYABLE_ERROR_CODES: Final[set[int]] = {10000, 10017, 10116}
AUTH_ERROR_CODES: Final[set[int]] = {10005, 10006, 10007, 10022, 10201, 10202, 10203}
# محدودیت منطقه‌ای؛ تکرار بی‌فایده است و پیام روشن لازم دارد.
REGION_BLOCKED_ERROR_CODES: Final[set[int]] = {10205}

LBANK_ERROR_MESSAGES: Final[dict[int, str]] = {
    10000: "Internal error",
    10001: "Parameter can not be null",
    10002: "Validation failed",
    10003: "Invalid parameter",
    10004: "Request too frequent",
    10005: "Secret key does not exist",
    10006: "User does not exist",
    10007: "Invalid signature",
    10008: "Currency pair not supported",
    10009: "Limit orders need price and quantity",
    10010: "Price or quantity must be greater than the minimum",
    10013: "Order quantity below minimum",
    10014: "Insufficient balance",
    10016: "Insufficient balance",
    10017: "Server exception",
    10022: "API key permission denied, invalid IP or permissions",
    10116: "Upgrading, please try again later",
    10201: "api_key and sign can not be null",
    10202: "timestamp, signature_method and echostr can not be null",
    10203: "Wrong signature method",
    10205: "LBank is not available in your country/region",
    10600: "Request timeout; check the difference between local and server time",
}
