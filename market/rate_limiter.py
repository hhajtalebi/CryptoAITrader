"""
محدودکننده نرخ درخواست (Rate Limiter) و کمک‌کننده تلاش مجدد (Retry).

چرا وجود دارد؟
    صرافی‌ها در صورت ارسال درخواست بیش از حد، پاسخ خطا می‌دهند یا IP را
    موقتاً مسدود می‌کنند. این ماژول با الگوریتم «سطل توکن» جریان درخواست‌ها
    را کنترل می‌کند.

ارتباط با ماژول‌های دیگر:
    کلاینت REST هر صرافی پیش از ارسال درخواست، از این کلاس مجوز می‌گیرد.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.exceptions import NetworkError, RateLimitError
from app.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class AsyncRateLimiter:
    """
    محدودکننده نرخ ناهمگام مبتنی بر الگوریتم سطل توکن.

    توکن‌ها با نرخ ثابت پر می‌شوند و هر درخواست یک توکن مصرف می‌کند. اگر
    توکنی نباشد، فراخوان تا زمان آزاد شدن ظرفیت منتظر می‌ماند (به‌صورت
    ناهمگام، بدون مسدود کردن حلقه رویداد).
    """

    def __init__(self, rate_per_second: float = 8.0, burst: int | None = None) -> None:
        self._rate = max(0.1, float(rate_per_second))
        self._capacity = float(burst if burst is not None else max(1, int(rate_per_second)))
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        """
        گرفتن مجوز ارسال درخواست؛ در صورت لزوم منتظر می‌ماند.
        """
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                self._last_refill = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait_time = deficit / self._rate
            await asyncio.sleep(min(wait_time, 1.0))

    def update_rate(self, rate_per_second: float) -> None:
        """تغییر نرخ مجاز در زمان اجرا (وقتی کاربر تنظیمات را عوض می‌کند)."""
        self._rate = max(0.1, float(rate_per_second))
        self._capacity = max(1.0, float(int(rate_per_second)))


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    retry_on: tuple[type[Exception], ...] = (NetworkError,),
    operation_name: str = "operation",
    no_retry_on: tuple[type[Exception], ...] = (),
) -> T:
    """
    اجرای یک عملیات ناهمگام با تلاش مجدد و تأخیر نمایی همراه با نویز.

    چرا نویز (Jitter)؟
        اگر چند درخواست هم‌زمان شکست بخورند، بدون نویز همه دقیقاً با هم
        دوباره تلاش می‌کنند و دوباره صرافی را تحت فشار می‌گذارند.

    خطاهایی که در retry_on نباشند بلافاصله پرتاب می‌شوند (مثلاً خطای
    احراز هویت که تکرار آن بی‌فایده است).
    """
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except retry_on as exc:
            if no_retry_on and isinstance(exc, no_retry_on):
                # مثلاً محدودیت نرخ: تکرار فوری فقط مسدودی را طولانی‌تر می‌کند؛
                # تصمیم مکث با لایهٔ بالاتر (cooldown موتور بازار) است.
                raise
            last_error = exc
            if attempt >= max_attempts:
                break
            # در خطای محدودیت نرخ، صبر بیشتری لازم است.
            multiplier = 3.0 if isinstance(exc, RateLimitError) else 1.0
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)) * multiplier)
            delay += random.uniform(0, delay * 0.25)
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.2fs",
                operation_name, attempt, max_attempts, exc.__class__.__name__, delay,
            )
            await asyncio.sleep(delay)
    assert last_error is not None
    logger.error("%s failed after %d attempts: %s", operation_name, max_attempts, last_error)
    raise last_error
