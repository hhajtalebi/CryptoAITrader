"""
اندیکاتورهای شتاب (Momentum).

این گروه سرعت و قدرت تغییر قیمت را می‌سنجند و برای تشخیص اشباع خرید/فروش
و واگرایی‌ها به کار می‌روند.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.base import BaseIndicator, IndicatorCategory, IndicatorMetadata


class RSIIndicator(BaseIndicator):
    """
    شاخص قدرت نسبی: نسبت میانگین سودها به میانگین زیان‌ها در N دوره.

    بالای ۷۰ اشباع خرید و زیر ۳۰ اشباع فروش تفسیر می‌شود، اما در روندهای
    قوی این سطوح می‌توانند مدت‌ها حفظ شوند.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="RSI",
            category=IndicatorCategory.MOMENTUM,
            description_fa="شاخص قدرت نسبی؛ بالای ۷۰ اشباع خرید و زیر ۳۰ اشباع فروش در نظر گرفته می‌شود.",
            description_en="Relative Strength Index; >70 overbought, <30 oversold.",
            default_parameters={"period": 14, "overbought": 70, "oversold": 30},
            output_keys=("rsi",),
            min_candles=30,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه RSI با هموارسازی وایلدر (معادل EWM با alpha=1/period)."""
        period = int(self._parameters["period"])
        delta = df["close"].diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        # وقتی هیچ زیانی وجود ندارد، RSI برابر ۱۰۰ است
        rsi = rsi.where(avg_loss != 0, 100.0)
        return {"rsi": rsi}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """تفسیر سطح فعلی RSI نسبت به آستانه‌های تنظیم‌شده."""
        rsi = outputs["rsi"].iloc[-1]
        if pd.isna(rsi):
            return "NEUTRAL"
        if rsi >= float(self._parameters["overbought"]):
            return "OVERBOUGHT"
        if rsi <= float(self._parameters["oversold"]):
            return "OVERSOLD"
        return "BULLISH" if rsi > 50 else "BEARISH"


class MACDIndicator(BaseIndicator):
    """
    مکدی: اختلاف دو میانگین نمایی، به‌همراه خط سیگنال و هیستوگرام.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="MACD",
            category=IndicatorCategory.MOMENTUM,
            description_fa="همگرایی/واگرایی میانگین متحرک؛ تقاطع خط مکدی و سیگنال، تغییر شتاب را نشان می‌دهد.",
            description_en="Moving Average Convergence Divergence with signal line and histogram.",
            default_parameters={"fast": 12, "slow": 26, "signal": 9},
            output_keys=("macd", "signal", "histogram"),
            min_candles=40,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه خط مکدی، خط سیگنال و هیستوگرام."""
        fast = int(self._parameters["fast"])
        slow = int(self._parameters["slow"])
        signal_period = int(self._parameters["signal"])
        ema_fast = df["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
        return {"macd": macd, "signal": signal, "histogram": macd - signal}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """
        تشخیص تقاطع‌ها.

        تقاطع تازه (Crossover) سیگنال قوی‌تری از صرفاً بالا/پایین بودن است.
        """
        histogram = outputs["histogram"]
        if len(histogram) < 2 or pd.isna(histogram.iloc[-1]) or pd.isna(histogram.iloc[-2]):
            return "NEUTRAL"
        current, previous = histogram.iloc[-1], histogram.iloc[-2]
        if previous <= 0 < current:
            return "BULLISH_CROSSOVER"
        if previous >= 0 > current:
            return "BEARISH_CROSSOVER"
        return "BULLISH" if current > 0 else "BEARISH"


class StochasticIndicator(BaseIndicator):
    """نوسان‌گر استوکاستیک: موقعیت قیمت بسته‌شدن در دامنه اخیر."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="STOCH",
            category=IndicatorCategory.MOMENTUM,
            description_fa="نوسان‌گر استوکاستیک؛ جایگاه قیمت بسته‌شدن در دامنه سقف/کف اخیر را نشان می‌دهد.",
            description_en="Stochastic Oscillator; position of close within the recent high/low range.",
            default_parameters={"k_period": 14, "d_period": 3, "smooth": 3},
            output_keys=("k", "d"),
            min_candles=30,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه خطوط %K و %D."""
        k_period = int(self._parameters["k_period"])
        d_period = int(self._parameters["d_period"])
        smooth = int(self._parameters["smooth"])
        lowest = df["low"].rolling(k_period, min_periods=k_period).min()
        highest = df["high"].rolling(k_period, min_periods=k_period).max()
        raw_k = 100 * (df["close"] - lowest) / (highest - lowest).replace(0, np.nan)
        k = raw_k.rolling(smooth, min_periods=smooth).mean()
        return {"k": k, "d": k.rolling(d_period, min_periods=d_period).mean()}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """سطوح ۸۰ و ۲۰ مرز متعارف اشباع در استوکاستیک هستند."""
        k = outputs["k"].iloc[-1]
        if pd.isna(k):
            return "NEUTRAL"
        if k >= 80:
            return "OVERBOUGHT"
        if k <= 20:
            return "OVERSOLD"
        return "BULLISH" if k > 50 else "BEARISH"


class CCIIndicator(BaseIndicator):
    """شاخص کانال کالا: انحراف قیمت از میانگین آماری آن."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="CCI",
            category=IndicatorCategory.MOMENTUM,
            description_fa="شاخص کانال کالا؛ بالای ۱۰۰+ قدرت خرید و زیر ۱۰۰− فشار فروش را نشان می‌دهد.",
            description_en="Commodity Channel Index; >+100 strong buying, <-100 strong selling.",
            default_parameters={"period": 20},
            output_keys=("cci",),
            min_candles=30,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه CCI بر پایه قیمت معمول و انحراف مطلق میانگین."""
        period = int(self._parameters["period"])
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        moving_average = typical_price.rolling(period, min_periods=period).mean()
        mean_deviation = typical_price.rolling(period, min_periods=period).apply(
            lambda window: float(np.abs(window - window.mean()).mean()), raw=True
        )
        cci = (typical_price - moving_average) / (0.015 * mean_deviation.replace(0, np.nan))
        return {"cci": cci}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """تفسیر بر اساس عبور از سطوح ±۱۰۰."""
        cci = outputs["cci"].iloc[-1]
        if pd.isna(cci):
            return "NEUTRAL"
        if cci > 100:
            return "OVERBOUGHT"
        if cci < -100:
            return "OVERSOLD"
        return "BULLISH" if cci > 0 else "BEARISH"


class ROCIndicator(BaseIndicator):
    """نرخ تغییر: درصد تغییر قیمت نسبت به N کندل قبل."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="ROC",
            category=IndicatorCategory.MOMENTUM,
            description_fa="نرخ تغییر؛ درصد تغییر قیمت نسبت به N کندل گذشته.",
            description_en="Rate of Change; percentage price change over N candles.",
            default_parameters={"period": 12},
            output_keys=("roc",),
            min_candles=25,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه درصد تغییر."""
        period = int(self._parameters["period"])
        return {"roc": df["close"].pct_change(periods=period) * 100}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """علامت ROC جهت شتاب را نشان می‌دهد."""
        roc = outputs["roc"].iloc[-1]
        if pd.isna(roc):
            return "NEUTRAL"
        return "BULLISH" if roc > 0 else "BEARISH"


class WilliamsRIndicator(BaseIndicator):
    """ویلیامز %R: نسخه معکوس استوکاستیک در بازه ۰ تا ۱۰۰−."""

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="WILLIAMS_R",
            category=IndicatorCategory.MOMENTUM,
            description_fa="ویلیامز %R؛ بالای ۲۰− اشباع خرید و زیر ۸۰− اشباع فروش است.",
            description_en="Williams %R; above -20 overbought, below -80 oversold.",
            default_parameters={"period": 14},
            output_keys=("williams_r",),
            min_candles=25,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه ویلیامز %R."""
        period = int(self._parameters["period"])
        highest = df["high"].rolling(period, min_periods=period).max()
        lowest = df["low"].rolling(period, min_periods=period).min()
        williams = -100 * (highest - df["close"]) / (highest - lowest).replace(0, np.nan)
        return {"williams_r": williams}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """تفسیر بر اساس سطوح ۲۰− و ۸۰−."""
        value = outputs["williams_r"].iloc[-1]
        if pd.isna(value):
            return "NEUTRAL"
        if value > -20:
            return "OVERBOUGHT"
        if value < -80:
            return "OVERSOLD"
        return "BULLISH" if value > -50 else "BEARISH"


class MFIIndicator(BaseIndicator):
    """
    شاخص جریان پول: مانند RSI اما با در نظر گرفتن حجم معاملات.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="MFI",
            category=IndicatorCategory.MOMENTUM,
            description_fa="شاخص جریان پول؛ نسخه حجم‌محور RSI. بالای ۸۰ اشباع خرید و زیر ۲۰ اشباع فروش.",
            description_en="Money Flow Index; volume-weighted RSI. >80 overbought, <20 oversold.",
            default_parameters={"period": 14},
            output_keys=("mfi",),
            min_candles=30,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه MFI از روی جریان پول مثبت و منفی."""
        period = int(self._parameters["period"])
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        money_flow = typical_price * df["volume"]
        price_diff = typical_price.diff()
        positive_flow = money_flow.where(price_diff > 0, 0.0).rolling(period, min_periods=period).sum()
        negative_flow = money_flow.where(price_diff < 0, 0.0).rolling(period, min_periods=period).sum()
        ratio = positive_flow / negative_flow.replace(0, np.nan)
        mfi = 100 - (100 / (1 + ratio))
        return {"mfi": mfi.where(negative_flow != 0, 100.0)}

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """تفسیر بر اساس سطوح ۸۰ و ۲۰."""
        mfi = outputs["mfi"].iloc[-1]
        if pd.isna(mfi):
            return "NEUTRAL"
        if mfi >= 80:
            return "OVERBOUGHT"
        if mfi <= 20:
            return "OVERSOLD"
        return "BULLISH" if mfi > 50 else "BEARISH"
