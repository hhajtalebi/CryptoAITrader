"""
ثبت‌کننده صرافی‌ها (Factory Pattern).

چرا وجود دارد؟
    برای افزودن صرافی جدید نباید کد هسته تغییر کند؛ کافی است کلاس جدید در
    این ثبت‌کننده معرفی شود و بقیه برنامه آن را از طریق نام پیدا کند.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.exceptions import ConfigurationError
from app.logging import get_logger
from market.providers.base import ExchangeProvider

logger = get_logger(__name__)

ProviderFactory = Callable[..., ExchangeProvider]


class ExchangeRegistry:
    """مخزن سازنده‌های صرافی، کلیددار بر اساس نام یکتا."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, name: str, factory: ProviderFactory) -> None:
        """
        ثبت یک صرافی جدید.

        ثبت دوباره با همان نام، سازنده قبلی را جایگزین می‌کند و هشدار
        می‌دهد تا خطای پیکربندی پنهان نماند.
        """
        key = name.lower()
        if key in self._factories:
            logger.warning("Exchange provider '%s' is being re-registered", key)
        self._factories[key] = factory
        logger.debug("Exchange provider registered: %s", key)

    def create(self, name: str, **kwargs: Any) -> ExchangeProvider:
        """ساخت یک نمونه صرافی از روی نام آن."""
        key = name.lower()
        factory = self._factories.get(key)
        if factory is None:
            raise ConfigurationError(
                f"Unknown exchange provider: {name}",
                details={"available": self.available()},
            )
        return factory(**kwargs)

    def available(self) -> list[str]:
        """فهرست نام صرافی‌های ثبت‌شده."""
        return sorted(self._factories)

    def is_registered(self, name: str) -> bool:
        """آیا این صرافی ثبت شده است؟"""
        return name.lower() in self._factories


# ثبت‌کننده مشترک برنامه
exchange_registry = ExchangeRegistry()


def register_builtin_providers() -> None:
    """
    ثبت صرافی‌های داخلی نرم‌افزار.

    این تابع در Bootstrap فراخوانی می‌شود. برای افزودن صرافی جدید کافی است
    یک خط register اینجا اضافه شود.
    """
    from market.providers.bitpin.provider import create_bitpin_provider  # noqa: PLC0415
    from market.providers.lbank.provider import create_lbank_provider  # noqa: PLC0415
    from market.providers.toobit.provider import create_toobit_provider  # noqa: PLC0415

    exchange_registry.register("lbank", create_lbank_provider)
    exchange_registry.register("toobit", create_toobit_provider)
    exchange_registry.register("bitpin", create_bitpin_provider)
