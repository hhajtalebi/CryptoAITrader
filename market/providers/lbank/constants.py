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

# کدهای خطای LBank که تکرار درخواست برایشان منطقی است.
RETRYABLE_ERROR_CODES: Final[set[int]] = {10000, 10001, 10002}

# کدهای خطای مربوط به احراز هویت (تکرار بی‌فایده است).
AUTH_ERROR_CODES: Final[set[int]] = {10004, 10005, 10006, 10007}

# توضیح کدهای خطای پرکاربرد، برای پیام‌های قابل‌فهم‌تر در لاگ.
LBANK_ERROR_MESSAGES: Final[dict[int, str]] = {
    10000: "Internal error",
    10001: "Parameter error",
    10002: "Authentication failed",
    10003: "Illegal parameter",
    10004: "Invalid signature",
    10005: "Invalid api_key",
    10006: "Request expired",
    10007: "IP not allowed",
    10008: "Trading pair not supported",
    10009: "Missing price or amount",
    10010: "Price or amount must be greater than zero",
    10013: "Amount below minimum",
    10014: "Insufficient balance",
    10016: "Insufficient balance",
}
