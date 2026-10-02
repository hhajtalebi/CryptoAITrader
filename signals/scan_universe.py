"""
انتخاب هوشمند «جهانِ پویش» — کدام نمادهای صرافی و به چه ترتیبی.

چرا جدا؟
    کاربر خواست پویش هم با «تعداد دستی» کار کند و هم بتواند روی **همهٔ
    نمادهایی که از صرافی لود می‌شوند** بچرخد. پویش کل بازار (مثلاً بیش از
    ۱۳۰۰ نماد LBank) بدون ترتیب و پالایش، وقت را روی بازارهای مرده می‌سوزاند
    و سیگنال‌های مهم را دیر نشان می‌دهد. این ماژول فقط «فهرست» می‌سازد؛ هیچ
    درخواست شبکه‌ای نمی‌فرستد و بدون رابط کاربری آزمودنی است.

راهبرد هوشمند:
    ۱. **پالایش** — نمادهای بی‌معامله (گردش صفر)، جفت‌های «استیبل/استیبل»
       (USDC/USDT و ...) و توکن‌های اهرمی (BTC3L، ETHUP و ...) که تحلیل
       تکنیکال معمولی رویشان معنا ندارد کنار می‌روند؛ کاربر می‌تواند
       کمینهٔ گردش ۲۴ ساعته هم بگذارد.
    ۲. **اولویت** — پرگردش‌ترین و پرنوسان‌ترین‌ها اول پویش می‌شوند تا اگر
       کاربر پویش را نیمه‌کاره متوقف کرد، مهم‌ترین نتایج را داشته باشد.
    ۳. **پوشش کامل** — نمادی که در فهرست صرافی هست ولی هنوز تیکر ندارد،
       حذف نمی‌شود؛ در انتهای صف می‌آید.

هیچ‌کدام از این‌ها سود یا درستی سیگنال را تضمین نمی‌کند؛ فقط ترتیب و
هزینهٔ پویش را معقول می‌کند.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

#: حالت‌های جهان پویش
UNIVERSE_TOP = "top"  # پرگردش‌ترین‌ها با تعداد دستی
UNIVERSE_ALL = "all"  # همهٔ نمادهای صرافی
UNIVERSES = (UNIVERSE_TOP, UNIVERSE_ALL)

#: دارایی‌هایی که قیمتشان به دلار میخ شده؛ جفت دوتایی آن‌ها سیگنال ندارد.
STABLE_ASSETS = frozenset({
    "USDT", "USDC", "BUSD", "TUSD", "FDUSD", "DAI", "USDP", "USDD", "PYUSD",
    "USDE", "USD1", "UST", "GUSD", "FRAX", "LUSD", "EURT", "EURC", "USDS",
})

# توکن‌های اهرمی: BTC3L، ETH5S، XRPUP، BNBDOWN، ADABULL، EOSBEAR
_LEVERAGED_NUMERIC = re.compile(r"^([A-Z0-9]+?)(\d+[LS])$")
_LEVERAGED_WORD = re.compile(r"^([A-Z0-9]{2,}?)(UP|DOWN|BULL|BEAR)$")


def normalize_universe(value: Any) -> str:
    """مقدار نامعتبر به حالت امن «پرگردش‌ترین‌ها» برمی‌گردد."""
    text = str(value or "").strip().lower()
    return text if text in UNIVERSES else UNIVERSE_TOP


def split_symbol(symbol: str) -> tuple[str, str]:
    """BTC/USDT → (BTC, USDT)؛ قالب ناشناخته → (symbol, '')."""
    text = str(symbol or "").strip().upper()
    for separator in ("/", "_", "-"):
        if separator in text:
            base, _, quote = text.partition(separator)
            return base, quote
    return text, ""


def is_stable_pair(symbol: str) -> bool:
    """آیا هر دو طرف جفت استیبل‌کوین هستند؟"""
    base, quote = split_symbol(symbol)
    return bool(quote) and base in STABLE_ASSETS and quote in STABLE_ASSETS


def is_leveraged_token(symbol: str, known_bases: Iterable[str] | None = None) -> bool:
    """
    توکن اهرمی (مثل BTC3L یا ETHUP)؛ نمودارش با بازار پایه همخوان نیست.

    الگوی عددی (3L/5S) همیشه اهرمی است. ولی پسوند واژه‌ای (UP/DOWN/BULL/BEAR)
    با نام توکن‌های واقعی هم‌پوشانی دارد (مثل SYRUP)؛ اگر `known_bases` داده
    شود، فقط وقتی اهرمی حساب می‌شود که پیشوندش خودش یک دارایی بازار باشد
    (BTCUP وقتی BTC هم فهرست شده است).
    """
    base, _quote = split_symbol(symbol)
    if len(base) < 4:
        return False
    numeric = _LEVERAGED_NUMERIC.match(base)
    if numeric and len(numeric.group(1)) >= 2:
        return True
    word = _LEVERAGED_WORD.match(base)
    if not word:
        return False
    if known_bases is None:
        return True
    return word.group(1) in known_bases


@dataclass(frozen=True, slots=True)
class UniverseFilter:
    """پالایش‌هایی که کاربر روی جهان پویش می‌گذارد."""

    #: کمینهٔ گردش ۲۴ ساعته (به ارز مظنه، معمولاً USDT)؛ صفر یعنی بدون حد
    min_turnover: float = 0.0
    #: حذف بازارهای بی‌معامله، استیبل/استیبل و توکن‌های اهرمی
    smart: bool = True
    #: فقط این ارزهای مظنه (خالی = همه)
    quotes: tuple[str, ...] = ()

    @classmethod
    def create(cls, *, min_turnover: Any = 0.0, smart: Any = True,
               quotes: Iterable[str] | None = None) -> UniverseFilter:
        try:
            turnover = max(0.0, float(min_turnover or 0.0))
        except (TypeError, ValueError):
            turnover = 0.0
        clean = tuple(sorted({str(q).strip().upper() for q in (quotes or []) if str(q).strip()}))
        return cls(min_turnover=turnover, smart=bool(smart), quotes=clean)


def priority_score(ticker: Any) -> float:
    """
    امتیاز اولویت پویش.

    لگاریتم گردش (نقدشوندگی) پایهٔ امتیاز است و قدرمطلق درصد تغییر ۲۴ ساعته
    (نوسان) کمی آن را بالا می‌برد؛ بازار پرگردشِ در حرکت زودتر بررسی می‌شود.
    """
    try:
        turnover = max(0.0, float(getattr(ticker, "turnover_24h", 0.0) or 0.0))
    except (TypeError, ValueError):
        turnover = 0.0
    try:
        change = abs(float(getattr(ticker, "change_percent", 0.0) or 0.0))
    except (TypeError, ValueError):
        change = 0.0
    return math.log10(1.0 + turnover) + min(change, 50.0) / 25.0


def build_universe(
    tickers: Iterable[Any] | None,
    symbols: Iterable[Any] | None = None,
    *,
    mode: str = UNIVERSE_ALL,
    limit: int | None = None,
    filters: UniverseFilter | None = None,
) -> list[str]:
    """
    ساخت فهرست مرتب نمادهای پویش.

    tickers : تیکرهای ۲۴ ساعته (برای گردش/نوسان و تشخیص بازار مرده)
    symbols : فهرست نمادهای صرافی (SymbolInfo یا رشته) برای پوشش کامل
    mode    : «top» فقط پرگردش‌ترین‌ها تا `limit`؛ «all» همه (limit نادیده)
    """
    rules = filters or UniverseFilter()
    mode = normalize_universe(mode)
    tickers = list(tickers or [])
    symbols = list(symbols or [])
    known_bases = {
        split_symbol(str(getattr(item, "symbol", item) or ""))[0]
        for item in [*tickers, *symbols]
    }

    def allowed(symbol: str) -> bool:
        if not symbol:
            return False
        if rules.quotes:
            _base, quote = split_symbol(symbol)
            if quote not in rules.quotes:
                return False
        if rules.smart and (
            is_stable_pair(symbol) or is_leveraged_token(symbol, known_bases)
        ):
            return False
        return True

    ranked: list[tuple[float, str]] = []
    seen: set[str] = set()
    for ticker in tickers or []:
        symbol = str(getattr(ticker, "symbol", "") or "").strip().upper()
        if symbol in seen or not allowed(symbol):
            continue
        seen.add(symbol)
        try:
            turnover = float(getattr(ticker, "turnover_24h", 0.0) or 0.0)
            price = float(getattr(ticker, "last_price", 0.0) or 0.0)
        except (TypeError, ValueError):
            turnover, price = 0.0, 0.0
        if rules.smart and (turnover <= 0 or price <= 0):
            continue  # بازار مرده؛ کندل و سیگنالش بی‌معناست
        if rules.min_turnover and turnover < rules.min_turnover:
            continue
        ranked.append((priority_score(ticker), symbol))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    ordered = [symbol for _score, symbol in ranked]

    if mode == UNIVERSE_TOP:
        cap = max(1, int(limit or 60))
        if ordered:
            return ordered[:cap]

    # نمادهای بدون تیکر: گردششان نامعلوم است. اگر تیکرها رسیده‌اند و پالایش
    # هوشمند روشن است، نبودِ تیکر یعنی بازار فعال نیست؛ وگرنه (مثلاً وقتی
    # گرفتن تیکرها شکست خورده) همه در انتهای صف می‌آیند تا پوشش کامل بماند.
    have_tickers = bool(seen)
    tail: list[str] = []
    if not rules.min_turnover and not (have_tickers and rules.smart):
        for item in symbols or []:
            symbol = str(getattr(item, "symbol", item) or "").strip().upper()
            if symbol in seen or not allowed(symbol):
                continue
            seen.add(symbol)
            tail.append(symbol)
    result = ordered + tail
    if mode == UNIVERSE_TOP:
        return result[: max(1, int(limit or 60))]
    return result


__all__ = [
    "STABLE_ASSETS",
    "UNIVERSES",
    "UNIVERSE_ALL",
    "UNIVERSE_TOP",
    "UniverseFilter",
    "build_universe",
    "is_leveraged_token",
    "is_stable_pair",
    "normalize_universe",
    "priority_score",
    "split_symbol",
]
