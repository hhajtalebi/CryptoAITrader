"""
اندیکاتورهای روند (Trend).

این اندیکاتورها جهت و قدرت حرکت بازار را می‌سنجند: میانگین‌های متحرک،
ADX، ایچیموکو و پارابولیک سار.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.constants import TrendDirection
from indicators.base import BaseIndicator, IndicatorCategory, IndicatorMetadata


class SMAIndicator(BaseIndicator):
    """میانگین متحرک ساده: میانگین قیمت بسته‌شدن در N دوره اخیر."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="SMA",
            category=IndicatorCategory.TREND,
            description_fa="میانگین متحرک ساده؛ میانگین حسابی قیمت بسته‌شدن در N کندل اخیر.",
            description_en="Simple Moving Average of the closing price over N candles.",
            default_parameters={"period": 20},
            output_keys=("sma",),
            min_candles=25,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه میانگین ساده با پنجره غلتان."""
        period = int(self._parameters["period"])
        return {"sma": df["close"].rolling(window=period, min_periods=period).mean()}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """قیمت بالای میانگین صعودی و پایین آن نزولی تفسیر می‌شود."""
        sma = outputs["sma"].iloc[-1]
        price = df["close"].iloc[-1]
        if pd.isna(sma):
            return "NEUTRAL"
        return TrendDirection.BULLISH.value if price > sma else TrendDirection.BEARISH.value


class EMAIndicator(BaseIndicator):
    """میانگین متحرک نمایی: وزن بیشتر به داده‌های جدیدتر می‌دهد."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="EMA",
            category=IndicatorCategory.TREND,
            description_fa="میانگین متحرک نمایی؛ نسبت به SMA سریع‌تر به تغییر قیمت واکنش نشان می‌دهد.",
            description_en="Exponential Moving Average; reacts faster to recent price changes.",
            default_parameters={"period": 21},
            output_keys=("ema",),
            min_candles=25,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه میانگین نمایی با ضریب هموارسازی استاندارد."""
        period = int(self._parameters["period"])
        return {"ema": df["close"].ewm(span=period, adjust=False, min_periods=period).mean()}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """موقعیت قیمت نسبت به میانگین، جهت روند را نشان می‌دهد."""
        ema = outputs["ema"].iloc[-1]
        price = df["close"].iloc[-1]
        if pd.isna(ema):
            return "NEUTRAL"
        return TrendDirection.BULLISH.value if price > ema else TrendDirection.BEARISH.value


class WMAIndicator(BaseIndicator):
    """میانگین متحرک وزنی: وزن به‌صورت خطی با تازگی داده افزایش می‌یابد."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="WMA",
            category=IndicatorCategory.TREND,
            description_fa="میانگین متحرک وزنی؛ وزن هر کندل به‌صورت خطی با تازگی آن زیاد می‌شود.",
            description_en="Weighted Moving Average with linearly increasing weights.",
            default_parameters={"period": 20},
            output_keys=("wma",),
            min_candles=25,
            overlay=True,
        )

    @staticmethod
    def _wma(series: pd.Series, period: int) -> pd.Series:
        """محاسبه میانگین وزنی خطی روی یک سری."""
        weights = np.arange(1, period + 1, dtype=float)
        return series.rolling(window=period, min_periods=period).apply(
            lambda window: float(np.dot(window, weights) / weights.sum()), raw=True
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """اجرای محاسبه WMA روی قیمت بسته‌شدن."""
        period = int(self._parameters["period"])
        return {"wma": self._wma(df["close"], period)}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """مقایسه قیمت با میانگین وزنی."""
        wma = outputs["wma"].iloc[-1]
        if pd.isna(wma):
            return "NEUTRAL"
        return (
            TrendDirection.BULLISH.value
            if df["close"].iloc[-1] > wma
            else TrendDirection.BEARISH.value
        )


class HMAIndicator(BaseIndicator):
    """
    میانگین متحرک هال: تأخیر کمتر و نرمی بیشتر نسبت به میانگین‌های معمول.

    فرمول: HMA = WMA(2×WMA(n/2) − WMA(n), sqrt(n))
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="HMA",
            category=IndicatorCategory.TREND,
            description_fa="میانگین متحرک هال؛ تأخیر بسیار کم همراه با حذف نویز.",
            description_en="Hull Moving Average; very low lag with smooth output.",
            default_parameters={"period": 21},
            output_keys=("hma",),
            min_candles=40,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """پیاده‌سازی سه‌مرحله‌ای فرمول هال."""
        period = int(self._parameters["period"])
        half = max(1, period // 2)
        sqrt_period = max(1, int(np.sqrt(period)))
        wma_half = WMAIndicator._wma(df["close"], half)
        wma_full = WMAIndicator._wma(df["close"], period)
        raw = 2 * wma_half - wma_full
        return {"hma": WMAIndicator._wma(raw, sqrt_period)}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """جهت شیب HMA در دو کندل اخیر ملاک است."""
        hma = outputs["hma"]
        if len(hma) < 2 or pd.isna(hma.iloc[-1]) or pd.isna(hma.iloc[-2]):
            return "NEUTRAL"
        return (
            TrendDirection.BULLISH.value
            if hma.iloc[-1] > hma.iloc[-2]
            else TrendDirection.BEARISH.value
        )


class ADXIndicator(BaseIndicator):
    """
    شاخص میانگین جهت‌دار: «قدرت» روند را می‌سنجد، نه جهت آن.

    تفسیر متعارف: زیر ۲۰ بی‌روند، بالای ۲۵ روند معتبر، بالای ۵۰ روند بسیار قوی.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="ADX",
            category=IndicatorCategory.TREND,
            description_fa="شاخص میانگین جهت‌دار؛ قدرت روند را می‌سنجد. بالای ۲۵ یعنی روند معتبر.",
            description_en="Average Directional Index; measures trend strength (>25 = trending).",
            default_parameters={"period": 14},
            output_keys=("adx", "plus_di", "minus_di"),
            min_candles=40,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه ADX به همراه خطوط جهت‌دار مثبت و منفی."""
        period = int(self._parameters["period"])
        high, low, close = df["high"], df["low"], df["close"]

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
        minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

        true_range = pd.concat(
            [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
        ).max(axis=1)

        # هموارسازی وایلدر معادل EWM با alpha = 1/period است
        atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        return {"adx": adx, "plus_di": plus_di, "minus_di": minus_di}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """ترکیب قدرت روند با جهت خطوط DI."""
        adx = outputs["adx"].iloc[-1]
        plus_di = outputs["plus_di"].iloc[-1]
        minus_di = outputs["minus_di"].iloc[-1]
        if pd.isna(adx) or pd.isna(plus_di) or pd.isna(minus_di):
            return "NEUTRAL"
        if adx < 20:
            return "NO_TREND"
        if plus_di > minus_di:
            return "STRONG_BULLISH" if adx > 25 else TrendDirection.BULLISH.value
        return "STRONG_BEARISH" if adx > 25 else TrendDirection.BEARISH.value


class IchimokuIndicator(BaseIndicator):
    """
    ابر ایچیموکو: سیستم کاملی برای تشخیص روند، حمایت/مقاومت و شتاب.

    اجزا: تنکان‌سن، کیجون‌سن، سنکو A و B (ابر) و چیکو اسپن.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="ICHIMOKU",
            category=IndicatorCategory.TREND,
            description_fa="ابر ایچیموکو؛ سیستم جامع روند، حمایت/مقاومت و شتاب حرکت.",
            description_en="Ichimoku Cloud; complete trend, support/resistance and momentum system.",
            default_parameters={"conversion": 9, "base": 26, "span_b": 52, "displacement": 26},
            output_keys=("tenkan", "kijun", "senkou_a", "senkou_b"),
            min_candles=60,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """
        محاسبه اجزای ایچیموکو.

        توجه: سنکو A و B عمداً «جابه‌جا نشده» برگردانده می‌شوند تا مقایسه با
        قیمت فعلی ساده باشد؛ جابه‌جایی رو به جلو کار لایه نمودار است.
        """
        conversion = int(self._parameters["conversion"])
        base = int(self._parameters["base"])
        span_b_period = int(self._parameters["span_b"])
        high, low = df["high"], df["low"]

        def _midpoint(period: int) -> pd.Series:
            """میانگین بیشترین سقف و کمترین کف در یک دوره."""
            return (
                high.rolling(period, min_periods=period).max()
                + low.rolling(period, min_periods=period).min()
            ) / 2

        tenkan = _midpoint(conversion)
        kijun = _midpoint(base)
        return {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": (tenkan + kijun) / 2,
            "senkou_b": _midpoint(span_b_period),
        }

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """موقعیت قیمت نسبت به ابر، مهم‌ترین سیگنال ایچیموکو است."""
        price = df["close"].iloc[-1]
        senkou_a = outputs["senkou_a"].iloc[-1]
        senkou_b = outputs["senkou_b"].iloc[-1]
        if pd.isna(senkou_a) or pd.isna(senkou_b):
            return "NEUTRAL"
        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)
        if price > cloud_top:
            return TrendDirection.BULLISH.value
        if price < cloud_bottom:
            return TrendDirection.BEARISH.value
        return "IN_CLOUD"


class ParabolicSARIndicator(BaseIndicator):
    """
    پارابولیک سار: نقاط احتمالی بازگشت روند و سطح حد ضرر متحرک.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="PSAR",
            category=IndicatorCategory.TREND,
            description_fa="پارابولیک سار؛ نقاط بازگشت روند و حد ضرر دنباله‌رو را مشخص می‌کند.",
            description_en="Parabolic SAR; identifies trend reversals and trailing stop levels.",
            default_parameters={"step": 0.02, "max_step": 0.2},
            output_keys=("psar",),
            min_candles=30,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """
        پیاده‌سازی تکرارشونده الگوریتم وایلدر.

        متغیرها: af ضریب شتاب، ep نقطه انتهایی، sar مقدار خود اندیکاتور.
        """
        step = float(self._parameters["step"])
        max_step = float(self._parameters["max_step"])
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        length = len(df)

        sar = np.full(length, np.nan)
        if length < 2:
            return {"psar": pd.Series(sar, index=df.index)}

        rising = high[1] >= high[0]
        acceleration = step
        extreme_point = high[0] if rising else low[0]
        sar[0] = low[0] if rising else high[0]

        for i in range(1, length):
            sar[i] = sar[i - 1] + acceleration * (extreme_point - sar[i - 1])
            if rising:
                sar[i] = min(sar[i], low[i - 1], low[max(0, i - 2)])
                if low[i] < sar[i]:  # بازگشت روند به نزولی
                    rising = False
                    sar[i] = extreme_point
                    extreme_point = low[i]
                    acceleration = step
                elif high[i] > extreme_point:
                    extreme_point = high[i]
                    acceleration = min(max_step, acceleration + step)
            else:
                sar[i] = max(sar[i], high[i - 1], high[max(0, i - 2)])
                if high[i] > sar[i]:  # بازگشت روند به صعودی
                    rising = True
                    sar[i] = extreme_point
                    extreme_point = high[i]
                    acceleration = step
                elif low[i] < extreme_point:
                    extreme_point = low[i]
                    acceleration = min(max_step, acceleration + step)

        return {"psar": pd.Series(sar, index=df.index)}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """قیمت بالاتر از SAR یعنی روند صعودی."""
        psar = outputs["psar"].iloc[-1]
        if pd.isna(psar):
            return "NEUTRAL"
        return (
            TrendDirection.BULLISH.value
            if df["close"].iloc[-1] > psar
            else TrendDirection.BEARISH.value
        )
