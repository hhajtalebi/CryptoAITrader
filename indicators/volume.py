"""
اندیکاتورهای حجم (Volume).

حجم، «تأییدکننده» حرکت قیمت است: شکستی که با حجم همراه نباشد اعتبار کمتری
دارد. موتور سیگنال از این گروه برای تأیید یا رد ستاپ استفاده می‌کند.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.base import BaseIndicator, IndicatorCategory, IndicatorMetadata


class OBVIndicator(BaseIndicator):
    """
    حجم متعادل: جمع تجمعی حجم با علامت جهت قیمت.

    واگرایی OBV با قیمت، از نشانه‌های کلاسیک ضعف روند است.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="OBV",
            category=IndicatorCategory.VOLUME,
            description_fa="حجم متعادل؛ جمع تجمعی حجم بر اساس جهت حرکت قیمت.",
            description_en="On-Balance Volume; cumulative volume signed by price direction.",
            default_parameters={"signal_period": 20},
            output_keys=("obv", "obv_ma"),
            min_candles=25,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه OBV و میانگین متحرک آن به‌عنوان خط سیگنال."""
        signal_period = int(self._parameters["signal_period"])
        direction = np.sign(df["close"].diff().fillna(0.0))
        obv = (direction * df["volume"]).cumsum()
        return {"obv": obv, "obv_ma": obv.rolling(signal_period, min_periods=signal_period).mean()}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """مقایسه OBV با میانگین آن، جهت جریان حجم را نشان می‌دهد."""
        obv = outputs["obv"].iloc[-1]
        obv_ma = outputs["obv_ma"].iloc[-1]
        if pd.isna(obv_ma):
            return "NEUTRAL"
        return "BULLISH" if obv > obv_ma else "BEARISH"


class VWAPIndicator(BaseIndicator):
    """
    میانگین قیمت وزنی حجم.

    توجه مهم: VWAP معمولاً روزانه بازنشانی می‌شود. چون بازار ارز دیجیتال
    ۲۴ ساعته است، اینجا از نسخه «پنجره غلتان» استفاده می‌شود که برای همه
    تایم‌فریم‌ها معنادار است. این انتخاب عمدی است و در مستندات ذکر شده.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="VWAP",
            category=IndicatorCategory.VOLUME,
            description_fa="میانگین قیمت وزنی حجم (پنجره غلتان)؛ سطح تعادل خریدار و فروشنده.",
            description_en="Volume Weighted Average Price (rolling window).",
            default_parameters={"period": 20},
            output_keys=("vwap",),
            min_candles=25,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه VWAP غلتان بر پایه قیمت معمول."""
        period = int(self._parameters["period"])
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        price_volume = (typical_price * df["volume"]).rolling(period, min_periods=period).sum()
        total_volume = df["volume"].rolling(period, min_periods=period).sum()
        return {"vwap": price_volume / total_volume.replace(0, np.nan)}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """قیمت بالای VWAP یعنی خریداران کنترل بازار را دارند."""
        vwap = outputs["vwap"].iloc[-1]
        if pd.isna(vwap):
            return "NEUTRAL"
        return "BULLISH" if df["close"].iloc[-1] > vwap else "BEARISH"


class VolumeSMAIndicator(BaseIndicator):
    """میانگین حجم و تشخیص جهش حجمی (Volume Spike)."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="VOLUME_SMA",
            category=IndicatorCategory.VOLUME,
            description_fa="میانگین ساده حجم؛ برای تشخیص جهش حجمی و تأیید شکست‌ها.",
            description_en="Simple moving average of volume; detects volume spikes.",
            default_parameters={"period": 20, "spike_multiplier": 2.0},
            output_keys=("volume_sma", "volume_ratio"),
            min_candles=25,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه میانگین حجم و نسبت حجم فعلی به آن."""
        period = int(self._parameters["period"])
        volume_sma = df["volume"].rolling(period, min_periods=period).mean()
        return {"volume_sma": volume_sma, "volume_ratio": df["volume"] / volume_sma.replace(0, np.nan)}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """تشخیص جهش یا افت غیرعادی حجم."""
        ratio = outputs["volume_ratio"].iloc[-1]
        if pd.isna(ratio):
            return "NEUTRAL"
        if ratio >= float(self._parameters["spike_multiplier"]):
            return "VOLUME_SPIKE"
        if ratio > 1.2:
            return "ABOVE_AVERAGE"
        if ratio < 0.6:
            return "LOW_VOLUME"
        return "NORMAL"


class CMFIndicator(BaseIndicator):
    """جریان پول چایکین: فشار خرید و فروش بر اساس محل بسته‌شدن در کندل."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="CMF",
            category=IndicatorCategory.VOLUME,
            description_fa="جریان پول چایکین؛ مقدار مثبت فشار خرید و منفی فشار فروش را نشان می‌دهد.",
            description_en="Chaikin Money Flow; positive = buying pressure, negative = selling.",
            default_parameters={"period": 20},
            output_keys=("cmf",),
            min_candles=30,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه CMF از روی ضریب موقعیت بسته‌شدن و حجم."""
        period = int(self._parameters["period"])
        price_range = (df["high"] - df["low"]).replace(0, np.nan)
        multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / price_range
        money_flow_volume = (multiplier * df["volume"]).fillna(0.0)
        cmf = money_flow_volume.rolling(period, min_periods=period).sum() / df["volume"].rolling(
            period, min_periods=period
        ).sum().replace(0, np.nan)
        return {"cmf": cmf}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """آستانه ±۰٫۰۵ مرز متعارف تشخیص فشار معنادار است."""
        cmf = outputs["cmf"].iloc[-1]
        if pd.isna(cmf):
            return "NEUTRAL"
        if cmf > 0.05:
            return "BULLISH"
        if cmf < -0.05:
            return "BEARISH"
        return "NEUTRAL"
