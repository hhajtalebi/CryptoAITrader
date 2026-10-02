"""
ترتیب «ارزش» بازارها — v2.5.1.

خواستهٔ کاربر: «لیست نمادها را به ترتیب ارزش و حجم معامله نشان بده؛ مثلاً
بیت‌کوین، اتریوم و… نمادهای باارزش هستند».

صرافی ارزش بازار (Market Cap) نمی‌دهد و گرفتنش از سرویس بیرونی یعنی یک
وابستگی شبکه‌ای تازه. پس دو معیار ترکیب می‌شوند:

1. **رتبهٔ ارزش بازار** برای ارزهای شناخته‌شده (فهرست ثابت زیر، تقریبی و
   فقط برای ترتیب — هیچ عددی از آن نمایش داده نمی‌شود)؛
2. **ارزش معاملات ۲۴ ساعته به تتر** (turnover / quote volume) برای بقیه.

یعنی BTC، ETH، XRP، BNB، SOL… همیشه بالای فهرست‌اند و پس از آن‌ها
پرمعامله‌ترین بازارها می‌آیند؛ ارز ارزانی که حجم خام بزرگی دارد (مثلاً
۹۰۰ میلیون واحد × ۰٫۰۰۰۰۱ دلار) دیگر بالای بیت‌کوین نمی‌نشیند.

ماژول خالص است (بدون Qt/شبکه) تا در کنترلر و صفحه و آزمون مشترک باشد.
"""

from __future__ import annotations

from typing import Any

#: ارزهای بزرگ به ترتیب تقریبی ارزش بازار. استیبل‌کوین‌ها عمداً نیستند:
#: جفت USDC/USDT برای معامله‌گر جذاب نیست و نباید جای آلت‌کوین‌ها را بگیرد.
MARKET_CAP_ORDER: tuple[str, ...] = (
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "ADA", "HYPE", "LINK",
    "XLM", "SUI", "BCH", "AVAX", "HBAR", "LTC", "TON", "SHIB", "DOT", "XMR",
    "UNI", "PEPE", "AAVE", "NEAR", "APT", "ICP", "ETC", "ONDO", "POL", "TAO",
    "ARB", "KAS", "VET", "ATOM", "RENDER", "FIL", "ALGO", "OP", "WLD", "ENA",
    "TRUMP", "SEI", "INJ", "IMX", "STX", "BONK", "GRT", "TIA", "FET", "JUP",
    "LDO", "CRV", "THETA", "QNT", "MKR", "SAND", "MANA", "AXS", "FLOW", "EGLD",
    "XTZ", "EOS", "NEO", "IOTA", "ZEC", "DASH", "CAKE", "RUNE", "KAVA", "CHZ",
    "GALA", "1INCH", "COMP", "SNX", "WIF", "FLOKI", "PYTH", "JASMY", "APE", "DYDX",
)

#: نگاشت سریع دارایی → رتبه (۰ = بزرگ‌ترین)
MARKET_CAP_RANK: dict[str, int] = {asset: index for index, asset in enumerate(MARKET_CAP_ORDER)}

#: ارزهای پایه‌ای که قیمتشان به دلار ثابت است
USD_QUOTES: frozenset[str] = frozenset({"USDT", "USD", "USDC", "FDUSD", "BUSD", "DAI", "TUSD"})


def split_symbol(symbol: str) -> tuple[str, str]:
    """«BTC/USDT» → («BTC»، «USDT»)؛ ورودی بدون «/» ← (نماد، «»)."""
    base, _sep, quote = str(symbol or "").upper().partition("/")
    return base.strip(), quote.strip()


def _number(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0  # NaN → 0


def turnover_usdt(row: dict[str, Any], quote_price: float | None = None) -> float:
    """
    ارزش معاملات ۲۴ ساعته به تتر.

    اولویت با `quote_volume`/`turnover` صرافی است؛ وگرنه قیمت × حجم. برای
    جفت‌های غیرتتری (مثل ETH/BTC) با قیمت تتری ارز مرجع تبدیل می‌شود.
    """
    raw = 0.0
    for key in ("quote_volume", "turnover", "value"):
        raw = _number(row.get(key))
        if raw > 0:
            break
    if raw <= 0:
        raw = _number(row.get("price")) * _number(row.get("volume"))
    _base, quote = split_symbol(str(row.get("symbol", "")))
    if quote and quote not in USD_QUOTES:
        raw *= _number(quote_price) if quote_price else 0.0
    return raw


def rank_key(row: dict[str, Any], quote_price: float | None = None) -> tuple[int, float]:
    """
    کلید مرتب‌سازی «ارزش بازار + حجم»: (گروه/رتبه، −ارزش معاملات).

    ارزهای فهرست بالا با رتبهٔ خودشان؛ بقیه پس از همه، بر پایهٔ ارزش
    معاملات نزولی.
    """
    base, _quote = split_symbol(str(row.get("symbol", "")))
    rank = MARKET_CAP_RANK.get(base, len(MARKET_CAP_ORDER))
    return rank, -turnover_usdt(row, quote_price)


def sort_by_market_value(rows: list[dict[str, Any]], quote_prices: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """مرتب‌سازی ردیف‌ها بر پایهٔ `rank_key` (ردیف‌ها دست نمی‌خورند)."""
    prices = quote_prices or {}

    def key(row: dict[str, Any]) -> tuple[int, float]:
        _base, quote = split_symbol(str(row.get("symbol", "")))
        return rank_key(row, prices.get(quote))

    return sorted(rows, key=key)


def quote_usdt_prices(rows: list[dict[str, Any]]) -> dict[str, float]:
    """قیمت تتری ارزهای مرجع (BTC، ETH، …) از روی جفت‌های X/USDT همان فهرست."""
    prices: dict[str, float] = {quote: 1.0 for quote in USD_QUOTES}
    for row in rows:
        base, quote = split_symbol(str(row.get("symbol", "")))
        if quote == "USDT" and base:
            price = _number(row.get("price"))
            if price > 0:
                prices[base] = price
    return prices


def price_decimals(price: float, precision: int | None = None) -> int:
    """
    تعداد رقم اعشار «دقیق» برای نمایش قیمت تتری.

    اگر صرافی دقت قیمت نماد را داده باشد همان به کار می‌رود (قیمت دقیقاً
    همان‌طور که در دفتر سفارش صرافی است). وگرنه دست‌کم چهار رقم معنادار:
    ۶۴٬۲۳۱٫۵۰ ← ۲ رقم، ۰٫۶۱۲۳ ← ۴ رقم، ۰٫۰۰۰۰۱۲۳۴ ← ۸ رقم.
    """
    if precision is not None:
        try:
            value = int(precision)
        except (TypeError, ValueError):
            value = -1
        if 0 <= value <= 12:
            return value
    number = abs(_number(price))
    if number <= 0:
        return 2
    if number >= 1000:
        return 2
    if number >= 1:
        return 4
    decimals = 4
    probe = number
    while probe < 1 and decimals < 12:
        probe *= 10
        decimals += 1
    return min(max(decimals - 1, 4), 12)


def compact_number(value: float) -> tuple[float, str]:
    """۱٬۲۵۰٬۰۰۰٬۰۰۰ ← (۱٫۲۵، «B»)؛ برای ستون ارزش معاملات."""
    number = _number(value)
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(number) >= divisor:
            return number / divisor, suffix
    return number, ""


__all__ = [
    "MARKET_CAP_ORDER",
    "MARKET_CAP_RANK",
    "USD_QUOTES",
    "compact_number",
    "price_decimals",
    "quote_usdt_prices",
    "rank_key",
    "sort_by_market_value",
    "split_symbol",
    "turnover_usdt",
]
