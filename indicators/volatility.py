"""
اندیکاتورهای نوسان (Volatility).

این گروه دامنه حرکت قیمت را می‌سنجند. خروجی آن‌ها — به‌ویژه ATR — پایه
محاسبه حد ضرر و اندازه موقعیت در موتور ریسک است.
"""

from __future__ import annotations

import pandas as pd

from indicators.base import BaseIndicator, IndicatorCategory, IndicatorMetadata


def true_range(df: pd.DataFrame) -> pd.Series:
    """
    محاسبه دامنه واقعی (True Range).

    بیشینه سه مقدار: دامنه کندل، فاصله سقف تا بسته‌شدن قبلی و فاصله کف تا
    بسته‌شدن قبلی. این تعریف شکاف قیمتی (Gap) را نیز لحاظ می‌کند.
    """
    high, low, previous_close = df["high"], df["low"], df["close"].shift()
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)


class ATRIndicator(BaseIndicator):
    """
    میانگین دامنه واقعی: سنجه استاندارد نوسان.

    کاربرد اصلی در این نرم‌افزار: تعیین فاصله منطقی حد ضرر بر اساس نوسان
    واقعی بازار، نه درصد ثابت دلخواه.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="ATR",
            category=IndicatorCategory.VOLATILITY,
            description_fa="میانگین دامنه واقعی؛ معیار نوسان بازار و مبنای تعیین حد ضرر.",
            description_en="Average True Range; volatility measure used for stop-loss placement.",
            default_parameters={"period": 14},
            output_keys=("atr", "atr_percent"),
            min_candles=30,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه ATR و نسبت آن به قیمت (برای مقایسه بین نمادها)."""
        period = int(self._parameters["period"])
        atr = true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        return {"atr": atr, "atr_percent": atr / df["close"] * 100}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """
        دسته‌بندی سطح نوسان.

        این تفسیر به موتور ریسک کمک می‌کند در بازار پرنوسان، اهرم کمتری
        پیشنهاد دهد.
        """
        atr_percent = outputs["atr_percent"].iloc[-1]
        if pd.isna(atr_percent):
            return "NEUTRAL"
        if atr_percent > 5:
            return "VERY_HIGH_VOLATILITY"
        if atr_percent > 2.5:
            return "HIGH_VOLATILITY"
        if atr_percent < 0.8:
            return "LOW_VOLATILITY"
        return "NORMAL_VOLATILITY"


class BollingerBandsIndicator(BaseIndicator):
    """
    باندهای بولینگر: میانگین متحرک به‌همراه دو باند انحراف معیار.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="BBANDS",
            category=IndicatorCategory.VOLATILITY,
            description_fa="باندهای بولینگر؛ باریک شدن باندها معمولاً پیش‌درآمد حرکت شارپ است.",
            description_en="Bollinger Bands; band squeeze often precedes a sharp move.",
            default_parameters={"period": 20, "std_dev": 2.0},
            output_keys=("upper", "middle", "lower", "bandwidth", "percent_b"),
            min_candles=30,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه باندها به‌همراه پهنای باند و موقعیت نسبی قیمت."""
        period = int(self._parameters["period"])
        std_multiplier = float(self._parameters["std_dev"])
        middle = df["close"].rolling(period, min_periods=period).mean()
        deviation = df["close"].rolling(period, min_periods=period).std(ddof=0)
        upper = middle + std_multiplier * deviation
        lower = middle - std_multiplier * deviation
        band_range = (upper - lower).replace(0, pd.NA)
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": (upper - lower) / middle * 100,
            "percent_b": (df["close"] - lower) / band_range * 100,
        }

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """
        تفسیر موقعیت قیمت نسبت به باندها و تشخیص فشردگی.
        """
        percent_b = outputs["percent_b"].iloc[-1]
        bandwidth = outputs["bandwidth"]
        if pd.isna(percent_b):
            return "NEUTRAL"

        # فشردگی: پهنای باند فعلی در پایین‌ترین ناحیه ۵۰ کندل اخیر
        recent = bandwidth.tail(50).dropna()
        if len(recent) >= 20 and bandwidth.iloc[-1] <= recent.quantile(0.15):
            return "SQUEEZE"
        if percent_b > 100:
            return "ABOVE_UPPER_BAND"
        if percent_b < 0:
            return "BELOW_LOWER_BAND"
        if percent_b > 80:
            return "OVERBOUGHT"
        if percent_b < 20:
            return "OVERSOLD"
        return "NEUTRAL"


class KeltnerChannelIndicator(BaseIndicator):
    """کانال کلتنر: میانگین نمایی به‌همراه باندهای مبتنی بر ATR."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="KELTNER",
            category=IndicatorCategory.VOLATILITY,
            description_fa="کانال کلتنر؛ باندهایی بر پایه ATR که نسبت به بولینگر نرم‌تر هستند.",
            description_en="Keltner Channel; ATR-based bands, smoother than Bollinger.",
            default_parameters={"period": 20, "atr_period": 10, "multiplier": 2.0},
            output_keys=("upper", "middle", "lower"),
            min_candles=35,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه خط میانی نمایی و باندهای مبتنی بر ATR."""
        period = int(self._parameters["period"])
        atr_period = int(self._parameters["atr_period"])
        multiplier = float(self._parameters["multiplier"])
        middle = df["close"].ewm(span=period, adjust=False, min_periods=period).mean()
        atr = true_range(df).ewm(alpha=1 / atr_period, adjust=False, min_periods=atr_period).mean()
        return {
            "upper": middle + multiplier * atr,
            "middle": middle,
            "lower": middle - multiplier * atr,
        }

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """عبور از باندها نشانه شتاب قوی است."""
        price = df["close"].iloc[-1]
        upper, lower = outputs["upper"].iloc[-1], outputs["lower"].iloc[-1]
        if pd.isna(upper) or pd.isna(lower):
            return "NEUTRAL"
        if price > upper:
            return "BREAKOUT_UP"
        if price < lower:
            return "BREAKOUT_DOWN"
        return "IN_CHANNEL"


class DonchianChannelIndicator(BaseIndicator):
    """کانال دونچیان: بیشترین سقف و کمترین کف در N کندل اخیر."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="DONCHIAN",
            category=IndicatorCategory.VOLATILITY,
            description_fa="کانال دونچیان؛ سقف و کف N کندل اخیر، ابزار کلاسیک تشخیص شکست.",
            description_en="Donchian Channel; highest high and lowest low over N candles.",
            default_parameters={"period": 20},
            output_keys=("upper", "middle", "lower"),
            min_candles=25,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه سقف، کف و خط میانی کانال."""
        period = int(self._parameters["period"])
        upper = df["high"].rolling(period, min_periods=period).max()
        lower = df["low"].rolling(period, min_periods=period).min()
        return {"upper": upper, "middle": (upper + lower) / 2, "lower": lower}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """
        تشخیص شکست کانال.

        برای پرهیز از سیگنال کاذب، سقف/کف تا کندل قبل محاسبه می‌شود.
        """
        if len(df) < 2:
            return "NEUTRAL"
        price = df["close"].iloc[-1]
        upper_prev = outputs["upper"].iloc[-2]
        lower_prev = outputs["lower"].iloc[-2]
        if pd.isna(upper_prev) or pd.isna(lower_prev):
            return "NEUTRAL"
        if price > upper_prev:
            return "BREAKOUT_UP"
        if price < lower_prev:
            return "BREAKOUT_DOWN"
        return "IN_RANGE"
