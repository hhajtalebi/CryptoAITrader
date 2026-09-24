"""
واسط پایه تمام اندیکاتورها.

هر اندیکاتور طبق بند ۱۴ سند پروژه باید شش چیز داشته باشد:
    Name، Description، Parameters، Calculation، Output، Signal Interpretation

این کلاس پایه، پنج مورد اول را استاندارد می‌کند و مورد ششم (تفسیر سیگنال)
را به‌عنوان متد قابل بازنویسی در اختیار فرزندان می‌گذارد.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from app.core.models import Candle, IndicatorResult
from app.exceptions import IndicatorError
from app.logging import get_logger

logger = get_logger(__name__)


class IndicatorCategory(str, Enum):
    """دسته‌بندی اندیکاتورها برای نمایش گروه‌بندی‌شده در رابط کاربری."""

    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SUPPORT_RESISTANCE = "support_resistance"


@dataclass(slots=True)
class IndicatorMetadata:
    """
    فراداده یک اندیکاتور: آنچه در راهنما و تنظیمات نمایش داده می‌شود.

    description_fa و description_en برای پشتیبانی دوزبانه جدا نگهداری
    می‌شوند تا هیچ متنی در کد Hard-Code نشود.
    """

    name: str
    category: IndicatorCategory
    description_fa: str
    description_en: str
    default_parameters: dict[str, Any] = field(default_factory=dict)
    output_keys: tuple[str, ...] = ()
    min_candles: int = 30
    overlay: bool = False  # آیا روی نمودار قیمت رسم می‌شود یا در پنل جدا؟


class BaseIndicator(ABC):
    """
    کلاس پایه اندیکاتورها.

    قرارداد:
        • ورودی همیشه DataFrame با ستون‌های open/high/low/close/volume است.
        • خروجی یک IndicatorResult استاندارد است.
        • در نبود داده کافی، خطای IndicatorError پرتاب می‌شود؛ هرگز عدد
          ساختگی تولید نمی‌گردد.
    """

    def __init__(self, **parameters: Any) -> None:
        self._parameters = {**self.metadata.default_parameters, **parameters}
        self._validate_parameters()

    # ------------------------------------------------------------------
    # فراداده و پارامترها
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def metadata(self) -> IndicatorMetadata:
        """فراداده این اندیکاتور."""

    @property
    def name(self) -> str:
        """نام یکتای اندیکاتور."""
        return self.metadata.name

    @property
    def parameters(self) -> dict[str, Any]:
        """پارامترهای فعال (ترکیب پیش‌فرض و مقادیر کاربر)."""
        return dict(self._parameters)

    def _validate_parameters(self) -> None:
        """
        اعتبارسنجی پارامترها.

        پیاده‌سازی پیش‌فرض بررسی می‌کند که تمام دوره‌های زمانی عددی مثبت
        باشند؛ فرزندان می‌توانند قواعد بیشتری اضافه کنند.
        """
        for key, value in self._parameters.items():
            if "period" in key or key in {"fast", "slow", "signal"}:
                if not isinstance(value, (int, float)) or value <= 0:
                    raise IndicatorError(
                        f"Parameter '{key}' of {self.name} must be a positive number",
                        details={"parameter": key, "value": value},
                    )

    # ------------------------------------------------------------------
    # محاسبه
    # ------------------------------------------------------------------
    @abstractmethod
    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """
        محاسبه اصلی اندیکاتور.

        بازگشتی: نگاشت «نام خروجی → سری زمانی».
        """

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """
        تفسیر سیگنال اندیکاتور.

        مقدار بازگشتی یکی از رشته‌های استاندارد است، مثل BULLISH، BEARISH،
        OVERBOUGHT، OVERSOLD یا NEUTRAL. پیاده‌سازی پیش‌فرض خنثی است.
        """
        return "NEUTRAL"

    def calculate(self, candles: list[Candle] | pd.DataFrame, timeframe: str = "") -> IndicatorResult:
        """
        اجرای کامل محاسبه و ساخت خروجی استاندارد.

        این متد چرخه کامل را مدیریت می‌کند: اعتبارسنجی داده، محاسبه، تفسیر
        و بسته‌بندی نتیجه.
        """
        df = candles_to_dataframe(candles) if not isinstance(candles, pd.DataFrame) else candles

        if len(df) < self.metadata.min_candles:
            raise IndicatorError(
                f"{self.name} requires at least {self.metadata.min_candles} candles, got {len(df)}",
                details={"indicator": self.name, "available": len(df), "required": self.metadata.min_candles},
            )

        try:
            outputs = self._compute(df)
        except IndicatorError:
            raise
        except Exception as exc:  # noqa: BLE001 - خطای محاسبه نباید کل تحلیل را متوقف کند
            raise IndicatorError(
                f"Failed to compute {self.name}: {exc.__class__.__name__}",
                details={"indicator": self.name},
            ) from exc

        latest: dict[str, float | None] = {}
        values: dict[str, list[float | None]] = {}
        for key, series in outputs.items():
            clean = series.astype(float)
            # بردار numpy به‌جای pd.isna روی تک‌تک مقدارها (۲.۴.۱): همان خروجی،
            # ولی بدون صدها هزار فراخوان تابع در پویش کل بازار.
            raw = clean.to_numpy(dtype=float, na_value=np.nan)
            missing = np.isnan(raw).tolist()
            values[key] = [
                None if gap else value for value, gap in zip(raw.tolist(), missing)
            ]
            last_value = clean.iloc[-1] if len(clean) else None
            latest[key] = None if last_value is None or pd.isna(last_value) else float(last_value)

        return IndicatorResult(
            name=self.name,
            timeframe=timeframe,
            values=values,
            latest=latest,
            signal=self.interpret(outputs, df),
            description=self.metadata.description_fa,
            parameters=self.parameters,
        )


def candles_to_dataframe(candles: list[Candle]) -> pd.DataFrame:
    """
    تبدیل فهرست کندل به DataFrame استاندارد.

    ستون‌ها: timestamp, open, high, low, close, volume
    ردیف‌ها بر اساس زمان مرتب می‌شوند تا محاسبات سری‌زمانی درست باشند.
    """
    if not candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(
        {
            "timestamp": [c.timestamp for c in candles],
            "open": [c.open for c in candles],
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
            "volume": [c.volume for c in candles],
        }
    )
    return frame.sort_values("timestamp").reset_index(drop=True)
