"""
نرخ تبدیل دلار (تتر) به تومان.

چرا این ماژول لازم است: قیمت‌های صرافی جهانی به دلار/تتر است، اما کاربر
ایرانی می‌خواهد معادل تومانی را هم ببیند. نرخ رسمی و نرخ سرویس‌های
بین‌المللی با بازار آزاد ایران اختلاف زیادی دارد، پس نرخ باید از بازار
واقعی ارز دیجیتال ایران (قیمت تتر) گرفته شود.

راهبرد: چند منبع به ترتیب امتحان می‌شوند و اولین پاسخ معتبر برنده است.
اگر همه شکست خوردند (تحریم، فیلترینگ، قطعی)، مقدار دستی کاربر به کار
می‌رود. برنامه هرگز به‌خاطر نبود نرخ ارز نباید از کار بیفتد.

توجه: همه منابع، قیمت تتر را بر حسب **ریال** یا **تومان** می‌دهند؛
مقدار داخلی این ماژول همیشه **تومان** است.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.timeutil import now_utc
from app.logging import get_logger
from market.providers.bitpin.constants import (
    BITPIN_REST_URL,
    BITPIN_USDT_IRT_SYMBOL,
    BitpinEndpoints,
)

logger = get_logger(__name__)

#: مدت اعتبار نرخ پیش از تلاش دوباره (ثانیه)
RATE_TTL_SECONDS = 300.0

#: بازه معقول برای نرخ تتر به تومان — برای رد کردن پاسخ بی‌معنا
MIN_PLAUSIBLE_TOMAN = 10_000.0
MAX_PLAUSIBLE_TOMAN = 10_000_000.0

REQUEST_TIMEOUT = 12.0


@dataclass
class FiatRate:
    """نرخ تبدیل به‌همراه منبع و زمان دریافت."""

    toman: float
    source: str
    fetched_at: datetime
    is_manual: bool = False

    @property
    def age_seconds(self) -> float:
        """قدمت نرخ بر حسب ثانیه."""
        return (now_utc() - self.fetched_at).total_seconds()

    @property
    def is_stale(self) -> bool:
        """آیا نرخ کهنه شده است."""
        return self.age_seconds > RATE_TTL_SECONDS


def _plausible(value: float | None) -> float | None:
    """
    بررسی معقول بودن نرخ.

    برخی سرویس‌ها هنگام خطا مقدار صفر یا نرخ ریالی را جای تومان می‌دهند؛
    بدون این بررسی، قیمت‌های نمایش‌داده‌شده ده برابر غلط می‌شوند.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if MIN_PLAUSIBLE_TOMAN <= number <= MAX_PLAUSIBLE_TOMAN:
        return number
    # اگر عدد در محدوده ریال است، به تومان تبدیل کن
    rial_as_toman = number / 10.0
    if MIN_PLAUSIBLE_TOMAN <= rial_as_toman <= MAX_PLAUSIBLE_TOMAN:
        return rial_as_toman
    return None


class FiatRateService:
    """
    سرویس نرخ تتر به تومان با چند منبع و جایگزین دستی.

    مثال:
        service = FiatRateService()
        rate = await service.get_rate()
        print(rate.toman, rate.source)
    """

    def __init__(self, manual_rate: float | None = None) -> None:
        self._cached: FiatRate | None = None
        self._manual_rate: float | None = manual_rate
        self._lock = asyncio.Lock()
        self._sources: list[tuple[str, Callable[[httpx.AsyncClient], Awaitable[float | None]]]] = [
            ("nobitex", self._from_nobitex),
            ("wallex", self._from_wallex),
            ("ramzinex", self._from_ramzinex),
            ("bitpin", self._from_bitpin),
        ]

    # ------------------------------------------------------------------
    # پیکربندی دستی
    # ------------------------------------------------------------------
    def set_manual_rate(self, toman: float | None) -> None:
        """
        تعیین نرخ دستی توسط کاربر.

        نرخ دستی بر منابع خودکار **مقدم** است؛ اگر کاربر عددی وارد کرده،
        یعنی به آن بیشتر از سرویس‌ها اعتماد دارد.
        """
        if toman and toman > 0:
            self._manual_rate = float(toman)
            self._cached = FiatRate(
                toman=float(toman), source="manual", fetched_at=now_utc(), is_manual=True
            )
            logger.info("Manual USDT/TOMAN rate set: %s", toman)
        else:
            self._manual_rate = None
            self._cached = None

    @property
    def manual_rate(self) -> float | None:
        """نرخ دستی جاری (اگر تنظیم شده باشد)."""
        return self._manual_rate

    @property
    def cached(self) -> FiatRate | None:
        """آخرین نرخ دریافت‌شده، بدون تلاش برای به‌روزرسانی."""
        return self._cached

    # ------------------------------------------------------------------
    # دریافت نرخ
    # ------------------------------------------------------------------
    async def get_rate(self, *, force: bool = False) -> FiatRate | None:
        """
        دریافت نرخ جاری.

        ترتیب: نرخ دستی → کش معتبر → منابع آنلاین → کش کهنه.
        بازگشت `None` فقط وقتی است که هیچ‌کدام در دسترس نباشند.
        """
        if self._manual_rate:
            return FiatRate(self._manual_rate, "manual", now_utc(), is_manual=True)

        if not force and self._cached is not None and not self._cached.is_stale:
            return self._cached

        async with self._lock:
            # ممکن است در زمان انتظار قفل، درخواست دیگری نرخ را گرفته باشد
            if not force and self._cached is not None and not self._cached.is_stale:
                return self._cached

            rate = await self._fetch_from_sources()
            if rate is not None:
                self._cached = rate
                return rate

        # همه منابع شکست خوردند: نرخ کهنه بهتر از هیچ است
        if self._cached is not None:
            logger.debug("Using stale fiat rate (%.0fs old)", self._cached.age_seconds)
            return self._cached

        logger.warning(
            "No USDT/TOMAN rate available from any source; "
            "the user should set one manually in Settings"
        )
        return None

    async def _fetch_from_sources(self) -> FiatRate | None:
        """امتحان کردن منابع به ترتیب تا اولین پاسخ معتبر."""
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "CryptoAITrader/1.0", "Accept": "application/json"},
            follow_redirects=True,
        ) as client:
            for name, fetcher in self._sources:
                try:
                    value = _plausible(await fetcher(client))
                except Exception as exc:  # noqa: BLE001 - منبع خراب نباید بقیه را متوقف کند
                    logger.debug("Fiat source '%s' failed: %s", name, exc)
                    continue
                if value is not None:
                    logger.info("USDT/TOMAN rate %s from %s", f"{value:,.0f}", name)
                    return FiatRate(value, name, now_utc())
        return None

    # ------------------------------------------------------------------
    # منابع
    # ------------------------------------------------------------------
    @staticmethod
    async def _from_nobitex(client: httpx.AsyncClient) -> float | None:
        """نوبیتکس — قیمت تتر بر حسب ریال."""
        response = await client.post(
            "https://api.nobitex.ir/market/stats",
            json={"srcCurrency": "usdt", "dstCurrency": "rls"},
        )
        response.raise_for_status()
        payload = response.json()
        stats = (payload.get("stats") or {}).get("usdt-rls") or {}
        value = stats.get("latest") or stats.get("bestSell")
        return float(value) / 10.0 if value else None  # ریال → تومان

    @staticmethod
    async def _from_wallex(client: httpx.AsyncClient) -> float | None:
        """والکس — بازار USDTTMN (تومان)."""
        response = await client.get("https://api.wallex.ir/v1/markets")
        response.raise_for_status()
        symbols = (response.json().get("result") or {}).get("symbols") or {}
        market = symbols.get("USDTTMN") or {}
        stats = market.get("stats") or {}
        value = stats.get("lastPrice") or stats.get("bidPrice")
        return float(value) if value else None

    @staticmethod
    async def _from_ramzinex(client: httpx.AsyncClient) -> float | None:
        """رمزینکس — جفت‌ارز تتر/تومان (شناسه ۱۱)."""
        response = await client.get("https://publicapi.ramzinex.com/exchange/api/v1.0/exchange/pairs")
        response.raise_for_status()
        for pair in response.json().get("data") or []:
            base = str(pair.get("base_currency_symbol", {}).get("en", "")).upper()
            quote = str(pair.get("quote_currency_symbol", {}).get("en", "")).upper()
            if base == "USDT" and quote in ("IRR", "TOMAN", "RLS"):
                value = pair.get("financial", {}).get("last", {}).get("price")
                return float(value) / 10.0 if value else None
        return None

    @staticmethod
    async def _from_bitpin(client: httpx.AsyncClient) -> float | None:
        """
        بیت‌پین — بازار USDT_IRT (تومان).

        نکتهٔ مهم: دامنهٔ `api.bitpin.ir` از کار افتاده و مسیر قدیمی
        `/v1/mkt/markets/` با قالب `results`/`code` دیگر وجود ندارد.
        مسیر درست و آزمایش‌شده `api.bitpin.market` با فهرست تیکرهاست که
        آرایه‌ای از `{"symbol": ..., "price": ...}` برمی‌گرداند.
        """
        response = await client.get(f"{BITPIN_REST_URL}{BitpinEndpoints.TICKERS}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return None
        for market in payload:
            if str(market.get("symbol", "")).upper() == BITPIN_USDT_IRT_SYMBOL:
                value = market.get("price")
                return float(value) if value else None
        return None

    # ------------------------------------------------------------------
    # تبدیل
    # ------------------------------------------------------------------
    def to_toman(self, usd_amount: float) -> float | None:
        """تبدیل مبلغ دلاری به تومان با آخرین نرخ موجود."""
        rate = self._cached
        if self._manual_rate:
            return usd_amount * self._manual_rate
        if rate is None:
            return None
        return usd_amount * rate.toman


def format_toman(amount: float | None) -> str:
    """
    قالب‌بندی مبلغ تومانی.

    مبالغ بزرگ به «میلیون» و «میلیارد» خلاصه می‌شوند، چون عدد خام
    ۹٬۸۴۵٬۳۲۱٬۰۰۰ در یک سلول جدول خوانا نیست.
    """
    if amount is None:
        return "—"
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:,.2f} B"
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:,.2f} M"
    if amount >= 1000:
        return f"{amount:,.0f}"
    return f"{amount:,.2f}"
