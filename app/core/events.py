"""
گذرگاه رویداد داخلی (Event Bus) برای ارتباط سست بین ماژول‌ها.

چرا وجود دارد؟
    لایه بازار نباید مستقیماً به لایه UI وابسته باشد. با انتشار رویداد،
    هر شنونده‌ای (نوار وضعیت، اعلان‌ها، لاگ) می‌تواند بدون ایجاد وابستگی
    مستقیم واکنش نشان دهد. این کار اصل Separation of Concerns را حفظ می‌کند.

نکته درباره Thread:
    این کلاس با Lock محافظت شده است، اما شنونده‌ها در همان Thread ناشر
    اجرا می‌شوند. برای به‌روزرسانی رابط کاربری باید از Signal مربوط به Qt
    استفاده شود (پل این کار در ui/widgets پیاده‌سازی شده است).
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """انواع رویدادهای داخلی نرم‌افزار."""

    # اتصال و شبکه
    EXCHANGE_CONNECTED = "exchange.connected"
    EXCHANGE_DISCONNECTED = "exchange.disconnected"
    EXCHANGE_RECONNECTING = "exchange.reconnecting"
    #: گذار وضعیت اتصال کل سیستم از نگاه نگهبان (online/degraded/offline)
    CONNECTIVITY_CHANGED = "system.connectivity_changed"

    # داده بازار
    TICKER_UPDATED = "market.ticker_updated"
    CANDLE_UPDATED = "market.candle_updated"
    ORDERBOOK_UPDATED = "market.orderbook_updated"

    # تحلیل و سیگنال
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETED = "analysis.completed"
    ANALYSIS_FAILED = "analysis.failed"
    SIGNAL_GENERATED = "signal.generated"

    # هوش مصنوعی
    AI_PROVIDER_CHANGED = "ai.provider_changed"
    AI_ERROR = "ai.error"

    # سیستم
    BACKUP_COMPLETED = "system.backup_completed"
    SETTINGS_CHANGED = "system.settings_changed"
    LANGUAGE_CHANGED = "system.language_changed"
    THEME_CHANGED = "system.theme_changed"
    NOTIFICATION = "system.notification"
    CRITICAL_ERROR = "system.critical_error"


@dataclass(slots=True)
class Event:
    """یک رویداد منتشرشده در گذرگاه، همراه با داده‌های همراه آن."""

    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""


EventHandler = Callable[[Event], None]


class EventBus:
    """
    پیاده‌سازی ساده و امن الگوی Publish/Subscribe.

    خطای یک شنونده هرگز نباید انتشار رویداد برای بقیه شنونده‌ها را متوقف
    کند؛ بنابراین خطاها فقط لاگ می‌شوند.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        ثبت یک شنونده برای نوع مشخصی از رویداد.
        """
        with self._lock:
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        حذف یک شنونده؛ در صورت نبود شنونده، خطایی رخ نمی‌دهد.
        """
        with self._lock:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)

    def publish(self, event_type: EventType, payload: dict[str, Any] | None = None, source: str = "") -> None:
        """
        انتشار یک رویداد برای تمام شنونده‌های ثبت‌شده.
        """
        event = Event(type=event_type, payload=payload or {}, source=source)
        with self._lock:
            handlers = list(self._handlers[event_type])
        for handler in handlers:
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - خطای شنونده نباید ناشر را متوقف کند
                logger.exception("Event handler failed for %s", event_type.value)

    def clear(self) -> None:
        """پاک‌سازی تمام شنونده‌ها (عمدتاً برای تست‌ها)."""
        with self._lock:
            self._handlers.clear()


# نمونه سراسری مشترک؛ تزریق وابستگی در سازنده کلاس‌ها ترجیح داده می‌شود،
# اما برای اتصال سریع UI به رویدادها این نمونه در دسترس است.
event_bus = EventBus()
