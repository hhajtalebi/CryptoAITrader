"""
ثابت‌های سراسری نرم‌افزار.

هرچیزی که «مقدار جادویی» است و در چند جا استفاده می‌شود، اینجا تعریف
می‌گردد تا از Hard-Code شدن جلوگیری شود.
"""

from __future__ import annotations

from enum import Enum

APP_NAME = "Crypto AI Trader"
APP_VERSION = "2.4.2"

#: نام فهرست دیده‌بانی پیش‌فرض.
#:
#: کاربری که هرگز فهرستی نساخته هم باید جایی برای ستاره‌زدن داشته باشد.
#: اینجا تعریف می‌شود نه در لایهٔ مخزن، چون هم رابط کاربری و هم پایگاه
#: داده به آن نیاز دارند و ویجت نباید برای یک رشته، کل لایهٔ داده و
#: SQLAlchemy را بار کند.
DEFAULT_WATCHLIST = "default"

#: نام تولیدکننده که در پایین برنامه نمایش داده می‌شود
PRODUCER_NAME = "حسین حاج طالبی"
APP_ORG = "CryptoAITrader"

# نام سرویس برای ذخیره امن کلیدها در Windows Credential Manager / Keyring
KEYRING_SERVICE_NAME = "CryptoAITrader"

# حداقل تعداد کندل لازم برای یک تحلیل قابل اتکا.
# اگر کمتر از این مقدار داده موجود باشد، وضعیت INSUFFICIENT_DATA برمی‌گردد.
MIN_CANDLES_FOR_ANALYSIS = 60

# حداکثر تعداد کندلی که در یک درخواست از صرافی گرفته می‌شود (محدودیت LBank).
MAX_CANDLES_PER_REQUEST = 2000


class Language(str, Enum):
    """زبان‌های پشتیبانی‌شده رابط کاربری."""

    FA = "fa"
    EN = "en"

    @property
    def is_rtl(self) -> bool:
        """آیا این زبان راست‌به‌چپ است؟"""
        return self is Language.FA


class Theme(str, Enum):
    """
    پوسته‌های ظاهری پشتیبانی‌شده.

    نه مقدار نخست پوسته‌های نام‌دار هستند. سه مقدار پایانی
    برای سازگاری با تنظیمات ذخیره‌شدهٔ نسخه‌های پیشین نگه داشته شده‌اند و
    هنگام بارگذاری به پوستهٔ متناظر نگاشت می‌شوند؛ حذفشان یعنی از دست
    رفتن انتخاب کاربران فعلی.
    """

    GLASS_DARK = "glass_dark"
    GOLD_DARK = "gold_dark"
    CARBON_NEON = "carbon_neon"
    ORCHID_INDIGO = "orchid_indigo"
    ROYAL_SILK = "royal_silk"
    MIDNIGHT_AURORA = "midnight_aurora"
    MINIMAL_LIGHT = "minimal_light"
    CORPORATE_NAVY = "corporate_navy"
    VIOLET_LIGHT = "violet_light"

    # --- نام‌های قدیمی (منسوخ ولی پذیرفته‌شده) ---
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


class ConnectionStatus(str, Enum):
    """وضعیت اتصال به سرویس‌های بیرونی (صرافی، هوش مصنوعی)."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class SignalDirection(str, Enum):
    """
    جهت سیگنال معاملاتی.

    وجود WAIT حیاتی است: سیستم مجاز است اعلام کند «شرایط مناسب نیست».
    """

    LONG = "LONG"
    SHORT = "SHORT"
    WAIT = "WAIT"


class TrendDirection(str, Enum):
    """جهت روند بازار در یک تایم‌فریم مشخص."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class MarketStructureType(str, Enum):
    """
    نوع ساختار بازار بر اساس تحلیل سقف‌ها و کف‌ها.

    HH: High Higher, HL: Higher Low, LH: Lower High, LL: Lower Low
    """

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    UNDEFINED = "UNDEFINED"


class AnalysisStatus(str, Enum):
    """وضعیت نهایی یک فرآیند تحلیل."""

    OK = "OK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class NotificationLevel(str, Enum):
    """سطح اهمیت اعلان‌های داخل برنامه."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# نگاشت نقش تایم‌فریم‌ها در تحلیل چند تایم‌فریمی (قابل تغییر از تنظیمات)
DEFAULT_TIMEFRAME_ROLES: dict[str, str] = {
    "15m": "entry",
    "1h": "short_trend",
    "4h": "medium_trend",
    "12h": "major_trend",
    "1d": "macro_trend",
}
