"""
فهرست صرافی‌های پشتیبانی‌شده و تعویض میان آن‌ها.

کاربر می‌خواهد بتواند صرافی را از تنظیمات عوض کند و کلید/رمز هر صرافی
خودکار از حافظه خوانده شود. این پرونده «چه صرافی‌هایی هست» را توصیف
می‌کند؛ ساخت شیء ارائه‌دهنده بر عهدهٔ `market/providers/` است.

نکتهٔ مهم دربارهٔ دسترسی جغرافیایی: بعضی صرافی‌ها از ایران بسته‌اند.
به‌جای اینکه کاربر با خطای مبهم شبکه روبه‌رو شود، همین‌جا علامت‌گذاری
شده تا رابط کاربری بتواند از قبل هشدار بدهد.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: صرافی‌ای که اگر چیزی تنظیم نشده باشد استفاده می‌شود
DEFAULT_EXCHANGE = "lbank"


@dataclass(frozen=True)
class ExchangePreset:
    """توصیف یک صرافی و نشانی‌های آن."""

    key: str
    display_name: str
    rest_url: str
    ws_url: str = ""
    #: آیا پیاده‌سازی کامل در برنامه وجود دارد؟
    implemented: bool = False
    #: آیا برای دیدن داده عمومی بازار کلید لازم است؟
    requires_key_for_market_data: bool = False
    #: معمولاً از ایران بدون واسط در دسترس نیست
    geo_restricted: bool = False
    quote_currencies: tuple[str, ...] = ("USDT",)
    notes: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def is_selectable(self) -> bool:
        """آیا کاربر می‌تواند همین حالا این صرافی را انتخاب کند؟"""
        return self.implemented


#: صرافی‌های شناخته‌شده. lbank، toobit و bitpin پیاده‌سازی کامل دارند؛ بقیه آماده‌اند
#: تا با افزودن یک کلاس ارائه‌دهنده فعال شوند (docs/ADD_EXCHANGE_FA.md).
EXCHANGE_PRESETS: tuple[ExchangePreset, ...] = (
    ExchangePreset(
        key="lbank",
        display_name="LBank",
        rest_url="https://api.lbkex.com",
        ws_url="wss://www.lbkex.net/ws/V2/",
        implemented=True,
        quote_currencies=("USDT", "BTC", "ETH"),
        notes="صرافی پیش‌فرض؛ کاملاً پیاده‌سازی شده و از ایران در دسترس است.",
    ),
    ExchangePreset(
        key="toobit",
        display_name="Toobit",
        rest_url="https://api.toobit.com",
        ws_url="wss://stream.toobit.com/quote/ws/v1",
        implemented=True,
        quote_currencies=("USDT", "USDC", "BTC", "ETH"),
        notes=(
            "پیاده‌سازی کامل؛ داده بازار و حساب با کلید API. "
            "سبک بایننس با امضای HMAC-SHA256."
        ),
    ),
    ExchangePreset(
        key="bitpin",
        display_name="Bitpin | بیت‌پین",
        rest_url="https://api.bitpin.market",
        implemented=True,
        quote_currencies=("IRT", "USDT"),
        notes=(
            "صرافی ایرانی؛ بازارهای تومانی و نرخ لحظه‌ای تتر/تومان. "
            "ورود با کلید و رمز API و توکن Bearer. "
            "توجه: کندل تاریخی ندارد و کندل‌ها از معاملات اخیر ساخته می‌شوند؛ "
            "همچنین باید IP دستگاه در فهرست مجاز کلید در پنل بیت‌پین ثبت شود."
        ),
        extra={"ip_allowlist": "required", "no_native_ohlc": "true"},
    ),
    ExchangePreset(
        key="kucoin",
        display_name="KuCoin",
        rest_url="https://api.kucoin.com",
        ws_url="wss://ws-api-spot.kucoin.com",
        quote_currencies=("USDT", "USDC", "BTC"),
        notes="از این سندباکس در دسترس بود؛ نیازمند افزودن کلاس ارائه‌دهنده.",
    ),
    ExchangePreset(
        key="okx",
        display_name="OKX",
        rest_url="https://www.okx.com",
        ws_url="wss://ws.okx.com:8443/ws/v5/public",
        quote_currencies=("USDT", "USDC", "BTC"),
    ),
    ExchangePreset(
        key="mexc",
        display_name="MEXC",
        rest_url="https://api.mexc.com",
        ws_url="wss://wbs.mexc.com/ws",
        quote_currencies=("USDT", "USDC"),
    ),
    ExchangePreset(
        key="gate",
        display_name="Gate.io",
        rest_url="https://api.gateio.ws",
        ws_url="wss://api.gateio.ws/ws/v4/",
        quote_currencies=("USDT", "USDC", "BTC"),
    ),
    ExchangePreset(
        key="binance",
        display_name="Binance",
        rest_url="https://api.binance.com",
        ws_url="wss://stream.binance.com:9443/ws",
        geo_restricted=True,
        quote_currencies=("USDT", "FDUSD", "BTC"),
        notes="از ایران مسدود است (پاسخ ۴۵۱)؛ بدون واسط کار نمی‌کند.",
    ),
    ExchangePreset(
        key="bybit",
        display_name="Bybit",
        rest_url="https://api.bybit.com",
        ws_url="wss://stream.bybit.com/v5/public/spot",
        geo_restricted=True,
        quote_currencies=("USDT", "USDC"),
        notes="از ایران مسدود است (پاسخ ۴۰۳).",
    ),
)

#: دسترسی سریع بر اساس کلید
EXCHANGE_MAP: dict[str, ExchangePreset] = {preset.key: preset for preset in EXCHANGE_PRESETS}


def get_exchange(key: str) -> ExchangePreset:
    """
    دریافت توصیف یک صرافی.

    اگر کلید ناشناخته باشد به صرافی پیش‌فرض برمی‌گردیم تا تنظیمات خرابِ
    یک کاربر، جلوی بالا آمدن برنامه را نگیرد.
    """
    preset = EXCHANGE_MAP.get((key or "").strip().lower())
    if preset is None:
        return EXCHANGE_MAP[DEFAULT_EXCHANGE]
    return preset


def exchange_keys() -> list[str]:
    """کلید همه صرافی‌های شناخته‌شده."""
    return [preset.key for preset in EXCHANGE_PRESETS]


def implemented_exchanges() -> list[ExchangePreset]:
    """صرافی‌هایی که همین حالا قابل استفاده‌اند."""
    return [preset for preset in EXCHANGE_PRESETS if preset.implemented]


def selectable_choices() -> list[tuple[str, str]]:
    """
    زوج (کلید، برچسب) برای فهرست کشویی تنظیمات.

    صرافی‌های پیاده‌سازی‌نشده هم نشان داده می‌شوند ولی با برچسب گویا،
    چون پنهان‌کردنشان این توهم را می‌سازد که برنامه فقط یک صرافی دارد.
    """
    choices: list[tuple[str, str]] = []
    for preset in EXCHANGE_PRESETS:
        label = preset.display_name
        if not preset.implemented:
            label = f"{label} (به‌زودی)"
        elif preset.geo_restricted:
            label = f"{label} (نیازمند واسط)"
        choices.append((preset.key, label))
    return choices
