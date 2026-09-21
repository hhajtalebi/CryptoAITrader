"""
واسط انتزاعی صرافی (Adapter Pattern).

چرا وجود دارد؟
    هسته نرم‌افزار نباید بداند داده از LBank می‌آید یا از صرافی دیگر. هر
    صرافی این واسط را پیاده‌سازی می‌کند و بقیه برنامه فقط با همین امضاها
    کار می‌کند.

ارتباط با ماژول‌های دیگر:
    MarketDataEngine مصرف‌کننده اصلی است؛ ابزارهای عامل هوش مصنوعی نیز
    به‌صورت غیرمستقیم از طریق همان موتور به داده می‌رسند.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.core.constants import ConnectionStatus
from app.core.models import Candle, OrderBook, SymbolInfo, Ticker


@runtime_checkable
class MarketWebSocketClient(Protocol):
    """
    قرارداد مشترک کلاینت‌های وب‌سوکت صرافی‌ها.

    چرا وجود دارد؟
        پیش‌تر `MarketDataEngine` مستقیماً `LBankWebSocketClient` می‌ساخت.
        نتیجه این بود که با انتخاب صرافی دیگر (مثلاً توبیت) همچنان سوکتِ
        LBank باز می‌شد و داده‌های زندهٔ صرافیِ اشتباه به رابط کاربری
        می‌رسید. حالا هر صرافی کلاینت خودش را از راه
        `ExchangeProvider.create_websocket_client()` می‌سازد و موتور فقط
        با همین امضاها کار می‌کند.

    پیاده‌سازی‌ها موظف‌اند اتصال مجدد خودکار داشته باشند و پس از هر
    اتصال، اشتراک‌های قبلی را دوباره ثبت کنند.
    """

    @property
    def status(self) -> ConnectionStatus:
        """وضعیت فعلی اتصال."""
        ...

    async def start(self) -> None:
        """شروع حلقهٔ اتصال در پس‌زمینه."""
        ...

    async def stop(self) -> None:
        """توقف کامل و آزادسازی منابع."""
        ...

    async def subscribe_ticker(self, symbol: str) -> None:
        """اشتراک قیمت لحظه‌ای یک نماد."""
        ...

    async def unsubscribe_ticker(self, symbol: str) -> None:
        """لغو اشتراک قیمت لحظه‌ای."""
        ...

    async def subscribe_candles(self, symbol: str, timeframe: str) -> None:
        """اشتراک کندل زندهٔ یک نماد."""
        ...

    async def unsubscribe_candles(self, symbol: str, timeframe: str) -> None:
        """لغو اشتراک کندل زنده."""
        ...

    async def unsubscribe_all(self) -> None:
        """لغو همهٔ اشتراک‌ها."""
        ...


@dataclass(slots=True)
class ProviderCapabilities:
    """
    توانمندی‌های یک صرافی.

    این ساختار به موتور داده می‌گوید چه چیزی مستقیماً در دسترس است و چه
    چیزی باید ساخته (Aggregate) شود.
    """

    name: str
    supports_websocket: bool = False
    supports_orderbook: bool = False
    supports_private_api: bool = False
    native_timeframes: set[str] = field(default_factory=set)
    max_candles_per_request: int = 1000


class ExchangeProvider(ABC):
    """
    قرارداد مشترک تمام صرافی‌ها.

    نکته: تمام متدها ناهمگام (async) هستند تا رابط کاربری هرگز مسدود نشود.
    """

    name: str = "abstract"
    display_name: str = "Abstract Exchange"

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """توانمندی‌های این صرافی."""

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    @abstractmethod
    async def connect(self) -> None:
        """آماده‌سازی منابع شبکه (ساخت کلاینت HTTP و مانند آن)."""

    @abstractmethod
    async def close(self) -> None:
        """آزادسازی منابع شبکه هنگام خروج."""

    @abstractmethod
    async def ping(self) -> bool:
        """بررسی در دسترس بودن سرویس صرافی."""

    # ------------------------------------------------------------------
    # داده عمومی بازار
    # ------------------------------------------------------------------
    @abstractmethod
    async def get_symbols(self) -> list[SymbolInfo]:
        """فهرست کامل نمادهای قابل معامله."""

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """وضعیت ۲۴ ساعته یک نماد."""

    @abstractmethod
    async def get_all_tickers(self) -> list[Ticker]:
        """وضعیت لحظه‌ای تمام نمادها در یک درخواست (برای فهرست بازارها)."""

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        """قیمت لحظه‌ای یک نماد."""

    @abstractmethod
    async def get_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 300, end_time: int | None = None
    ) -> list[Candle]:
        """
        دریافت کندل‌ها.

        پیاده‌سازی موظف است در صورت پشتیبانی‌نشدن تایم‌فریم، آن را از
        تایم‌فریم پایه تجمیع کند یا خطای TimeframeError بدهد.
        """

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """دریافت دفتر سفارش‌ها."""

    # ------------------------------------------------------------------
    # نگاشت نماد
    # ------------------------------------------------------------------
    @abstractmethod
    def to_exchange_symbol(self, symbol: str) -> str:
        """تبدیل نماد داخلی (BTC/USDT) به قالب صرافی."""

    @abstractmethod
    def from_exchange_symbol(self, exchange_symbol: str) -> str:
        """تبدیل نماد صرافی به قالب داخلی."""

    # ------------------------------------------------------------------
    # داده خصوصی (اختیاری)
    # ------------------------------------------------------------------
    async def get_account_balance(self) -> dict[str, float]:
        """
        موجودی حساب.

        پیاده‌سازی پیش‌فرض خالی است؛ صرافی‌هایی که API خصوصی دارند آن را
        بازنویسی می‌کنند.
        """
        return {}

    async def get_open_orders(self, symbol: str | None = None) -> list[dict]:
        """فهرست سفارش‌های باز (در نسخه اول فقط خواندنی)."""
        return []

    async def get_order_history(self, symbol: str, limit: int = 50) -> list[dict]:
        """تاریخچه سفارش‌ها (در نسخه اول فقط خواندنی)."""
        return []

    async def test_credentials(self) -> tuple[bool, str]:
        """
        آزمایش اعتبار کلیدهای API.

        بازگشتی: (موفقیت، پیام). پیام هرگز نباید شامل خود کلید باشد.
        """
        return False, "Private API is not implemented for this provider"

    # ------------------------------------------------------------------
    # داده زنده (اختیاری)
    # ------------------------------------------------------------------
    def create_websocket_client(
        self,
        *,
        on_ticker: Callable[[Ticker], None] | None = None,
        on_candle: Callable[[str, str, Candle], None] | None = None,
        on_status_change: Callable[[ConnectionStatus], None] | None = None,
    ) -> Any | None:
        """
        ساخت کلاینت وب‌سوکت مخصوص این صرافی.

        پیاده‌سازی پیش‌فرض `None` برمی‌گرداند یعنی «داده زنده ندارم»؛ در
        این حالت موتور به نظرسنجی دوره‌ای REST بسنده می‌کند. صرافی‌هایی که
        `supports_websocket=True` اعلام می‌کنند **باید** این متد را
        بازنویسی کنند، وگرنه موتور هشدار می‌دهد و به REST برمی‌گردد.

        امضای فراخوان‌ها عمداً با آنچه موتور انتظار دارد یکی است تا
        پیاده‌سازی‌ها مجبور به نگاشت دستی نشوند.
        """
        return None

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def supports_timeframe_natively(self, timeframe: str) -> bool:
        """آیا صرافی این تایم‌فریم را مستقیماً ارائه می‌دهد؟"""
        return timeframe in self.capabilities.native_timeframes

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.__class__.__name__} name={self.name}>"
