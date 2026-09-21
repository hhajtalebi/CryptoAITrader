"""
ثبت‌کننده اندیکاتورها (Factory Pattern).

افزودن اندیکاتور جدید فقط به دو کار نیاز دارد:
    ۱) ساخت کلاس فرزند BaseIndicator
    ۲) ثبت آن در register_builtin_indicators
هیچ بخش دیگری از برنامه نیازی به تغییر ندارد.
"""

from __future__ import annotations

from typing import Any

from app.exceptions import IndicatorError
from app.logging import get_logger
from indicators.base import BaseIndicator, IndicatorCategory

logger = get_logger(__name__)


class IndicatorRegistry:
    """مخزن کلاس‌های اندیکاتور، کلیددار بر اساس نام یکتا."""

    def __init__(self) -> None:
        self._indicators: dict[str, type[BaseIndicator]] = {}

    def register(self, indicator_class: type[BaseIndicator]) -> None:
        """ثبت یک کلاس اندیکاتور."""
        instance = indicator_class()
        key = instance.name.upper()
        if key in self._indicators:
            logger.warning("Indicator '%s' is being re-registered", key)
        self._indicators[key] = indicator_class

    def create(self, name: str, **parameters: Any) -> BaseIndicator:
        """ساخت نمونه یک اندیکاتور با پارامترهای دلخواه."""
        key = name.upper()
        indicator_class = self._indicators.get(key)
        if indicator_class is None:
            raise IndicatorError(
                f"Unknown indicator: {name}", details={"available": self.available()}
            )
        return indicator_class(**parameters)

    def available(self) -> list[str]:
        """فهرست نام تمام اندیکاتورهای ثبت‌شده."""
        return sorted(self._indicators)

    def by_category(self) -> dict[str, list[str]]:
        """گروه‌بندی اندیکاتورها بر اساس دسته (برای نمایش در تنظیمات)."""
        grouped: dict[str, list[str]] = {c.value: [] for c in IndicatorCategory}
        for name, indicator_class in self._indicators.items():
            grouped[indicator_class().metadata.category.value].append(name)
        return {k: sorted(v) for k, v in grouped.items() if v}

    def get_metadata(self, name: str) -> dict[str, Any]:
        """فراداده یک اندیکاتور برای نمایش در راهنما."""
        indicator = self.create(name)
        meta = indicator.metadata
        return {
            "name": meta.name,
            "category": meta.category.value,
            "description_fa": meta.description_fa,
            "description_en": meta.description_en,
            "parameters": meta.default_parameters,
            "outputs": list(meta.output_keys),
            "min_candles": meta.min_candles,
            "overlay": meta.overlay,
        }


indicator_registry = IndicatorRegistry()


def register_builtin_indicators() -> None:
    """
    ثبت تمام اندیکاتورهای داخلی نرم‌افزار.

    این تابع در Bootstrap فراخوانی می‌شود. برای افزودن اندیکاتور جدید کافی
    است کلاس آن ساخته و یک خط register اینجا اضافه شود.
    """
    from indicators.momentum import (  # noqa: PLC0415
        CCIIndicator, MACDIndicator, MFIIndicator, ROCIndicator,
        RSIIndicator, StochasticIndicator, WilliamsRIndicator,
    )
    from indicators.support_resistance import FibonacciIndicator, PivotPointsIndicator  # noqa: PLC0415
    from indicators.trend import (  # noqa: PLC0415
        ADXIndicator, EMAIndicator, HMAIndicator, IchimokuIndicator,
        ParabolicSARIndicator, SMAIndicator, WMAIndicator,
    )
    from indicators.volatility import (  # noqa: PLC0415
        ATRIndicator, BollingerBandsIndicator, DonchianChannelIndicator, KeltnerChannelIndicator,
    )
    from indicators.volume import (  # noqa: PLC0415
        CMFIndicator, OBVIndicator, VolumeSMAIndicator, VWAPIndicator,
    )

    for indicator_class in (
        # روند
        SMAIndicator, EMAIndicator, WMAIndicator, HMAIndicator,
        ADXIndicator, IchimokuIndicator, ParabolicSARIndicator,
        # شتاب
        RSIIndicator, MACDIndicator, StochasticIndicator, CCIIndicator,
        ROCIndicator, WilliamsRIndicator, MFIIndicator,
        # نوسان
        BollingerBandsIndicator, ATRIndicator, KeltnerChannelIndicator, DonchianChannelIndicator,
        # حجم
        OBVIndicator, VWAPIndicator, VolumeSMAIndicator, CMFIndicator,
        # حمایت/مقاومت
        PivotPointsIndicator, FibonacciIndicator,
    ):
        indicator_registry.register(indicator_class)
