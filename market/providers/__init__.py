"""
ارائه‌دهندگان صرافی.

هر صرافی در زیرپوشه مخصوص خود پیاده‌سازی می‌شود و واسط ExchangeProvider را
پیاده می‌کند. برای افزودن صرافی جدید، هسته نرم‌افزار نیازی به تغییر ندارد
(راهنما: docs/ADD_EXCHANGE_FA.md).
"""

from market.providers.base import ExchangeProvider, ProviderCapabilities
from market.providers.registry import ExchangeRegistry, exchange_registry

__all__ = ["ExchangeProvider", "ProviderCapabilities", "ExchangeRegistry", "exchange_registry"]
