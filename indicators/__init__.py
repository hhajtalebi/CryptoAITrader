"""
موتور اندیکاتورهای تکنیکال.

طراحی این لایه عمداً به هیچ کتابخانه خارجی خاصی وابسته نیست: محاسبات با
Pandas/NumPy انجام می‌شوند و هر اندیکاتور یک کلاس مستقل با واسط مشترک است.
بنابراین می‌توان بعداً یک اندیکاتور را با پیاده‌سازی کتابخانه دیگری جایگزین
کرد بدون آنکه بقیه برنامه تغییر کند (راهنما: docs/ADD_INDICATOR_FA.md).
"""

from indicators.base import BaseIndicator, IndicatorCategory, IndicatorMetadata
from indicators.engine import IndicatorEngine
from indicators.registry import IndicatorRegistry, indicator_registry

__all__ = [
    "BaseIndicator",
    "IndicatorMetadata",
    "IndicatorCategory",
    "IndicatorEngine",
    "IndicatorRegistry",
    "indicator_registry",
]
