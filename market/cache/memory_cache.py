"""
حافظه نهان درون‌حافظه‌ای برای داده بازار.

چرا وجود دارد؟
    بدون حافظه نهان، هر بار باز کردن یک صفحه یا محاسبه یک اندیکاتور باعث
    درخواست جدید به صرافی می‌شود. این ماژول با نگهداری کوتاه‌مدت داده،
    هم سرعت را بالا می‌برد و هم از برخورد با محدودیت نرخ جلوگیری می‌کند.

سیاست انقضا:
    هر ورودی زمان انقضای خودش را دارد (TTL). داده تایم‌فریم بزرگ‌تر عمر
    طولانی‌تری دارد، چون دیرتر تغییر می‌کند.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from app.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass(slots=True)
class CacheEntry(Generic[T]):
    """یک ورودی حافظه نهان به همراه زمان انقضا."""

    value: T
    expires_at: float

    @property
    def is_expired(self) -> bool:
        """آیا این ورودی منقضی شده است؟"""
        return time.monotonic() >= self.expires_at


class MarketCache:
    """
    حافظه نهان امن برای دسترسی هم‌زمان از چند Thread.

    ظرفیت محدود است تا مصرف حافظه کنترل شود؛ در صورت پر شدن، قدیمی‌ترین
    ورودی‌ها حذف می‌شوند.
    """

    def __init__(self, max_entries: int = 500) -> None:
        self._store: dict[str, CacheEntry[Any]] = {}
        self._lock = threading.RLock()
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    @staticmethod
    def make_key(*parts: Any) -> str:
        """ساخت کلید یکتا از اجزای مختلف، مثلاً candles:lbank:BTC/USDT:1h:300"""
        return ":".join(str(part) for part in parts)

    def get(self, key: str) -> Any | None:
        """
        خواندن مقدار در صورت وجود و منقضی نشدن.

        ورودی منقضی بلافاصله حذف می‌شود تا حافظه آزاد گردد.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """ذخیره یک مقدار با طول عمر مشخص."""
        with self._lock:
            if len(self._store) >= self._max_entries:
                self._evict()
            self._store[key] = CacheEntry(value=value, expires_at=time.monotonic() + max(0.1, ttl_seconds))

    def invalidate(self, key: str) -> None:
        """حذف یک کلید مشخص."""
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> int:
        """
        حذف تمام کلیدهایی که با پیشوند مشخص شروع می‌شوند.

        کاربرد: وقتی کندل جدیدی از WebSocket می‌رسد، تمام حافظه نهان مربوط
        به آن نماد باطل می‌شود.
        """
        with self._lock:
            keys = [key for key in self._store if key.startswith(prefix)]
            for key in keys:
                del self._store[key]
            return len(keys)

    def clear(self) -> None:
        """پاک‌سازی کامل حافظه نهان."""
        with self._lock:
            self._store.clear()

    def _evict(self) -> None:
        """
        آزادسازی فضا: ابتدا موارد منقضی و در صورت نیاز، نزدیک‌ترین به انقضا.
        """
        expired = [key for key, entry in self._store.items() if entry.is_expired]
        for key in expired:
            del self._store[key]
        if len(self._store) >= self._max_entries:
            oldest = sorted(self._store.items(), key=lambda item: item[1].expires_at)
            for key, _ in oldest[: max(1, self._max_entries // 10)]:
                del self._store[key]

    @property
    def stats(self) -> dict[str, Any]:
        """آمار کارایی حافظه نهان (برای بخش عیب‌یابی)."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total * 100, 1) if total else 0.0,
            }
