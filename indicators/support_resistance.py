"""
سطوح حمایت/مقاومت و تحلیل ساختار بازار.

چرا این ماژول جداست؟
    خروجی آن «عدد اندیکاتور» نیست، بلکه فهرستی از سطوح قیمتی و توصیف
    ساختار بازار است که مستقیماً در تعیین نقطه ورود، حد ضرر و حد سود
    استفاده می‌شود.

روش‌های پیاده‌سازی‌شده:
    • نقاط پیوت کلاسیک
    • اصلاح فیبوناچی
    • سقف/کف نوسانی (Swing) با روش پنجره متقارن
    • سطوح پویا بر پایه خوشه‌بندی قیمت‌های پرتکرار
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.constants import MarketStructureType, TrendDirection
from app.core.models import Candle, MarketStructure, SupportResistanceLevel
from indicators.base import BaseIndicator, IndicatorCategory, IndicatorMetadata, candles_to_dataframe


class PivotPointsIndicator(BaseIndicator):
    """
    نقاط پیوت کلاسیک بر اساس سقف، کف و بسته‌شدن کندل قبل.

    این سطوح در معاملات روزانه بسیار پرکاربردند و مرجع مشترک بسیاری از
    معامله‌گران هستند.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="PIVOT",
            category=IndicatorCategory.SUPPORT_RESISTANCE,
            description_fa="نقاط پیوت کلاسیک؛ سطوح حمایت و مقاومت محاسبه‌شده از کندل قبلی.",
            description_en="Classic Pivot Points; support and resistance from the previous candle.",
            default_parameters={},
            output_keys=("pivot", "r1", "r2", "r3", "s1", "s2", "s3"),
            min_candles=3,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه پیوت مرکزی و سه سطح مقاومت و حمایت."""
        high, low, close = df["high"].shift(), df["low"].shift(), df["close"].shift()
        pivot = (high + low + close) / 3
        return {
            "pivot": pivot,
            "r1": 2 * pivot - low,
            "r2": pivot + (high - low),
            "r3": high + 2 * (pivot - low),
            "s1": 2 * pivot - high,
            "s2": pivot - (high - low),
            "s3": low - 2 * (high - pivot),
        }

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """موقعیت قیمت نسبت به پیوت مرکزی."""
        pivot = outputs["pivot"].iloc[-1]
        if pd.isna(pivot):
            return "NEUTRAL"
        return "BULLISH" if df["close"].iloc[-1] > pivot else "BEARISH"


class FibonacciIndicator(BaseIndicator):
    """
    سطوح اصلاح فیبوناچی بین سقف و کف بازه اخیر.

    جهت محاسبه به‌صورت خودکار تشخیص داده می‌شود: اگر سقف بعد از کف رخ داده
    باشد، روند صعودی فرض شده و سطوح از بالا به پایین محاسبه می‌شوند.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        return IndicatorMetadata(
            name="FIBONACCI",
            category=IndicatorCategory.SUPPORT_RESISTANCE,
            description_fa="سطوح اصلاح فیبوناچی؛ نواحی احتمالی بازگشت قیمت در یک روند.",
            description_en="Fibonacci retracement levels of the recent swing.",
            default_parameters={"lookback": 100},
            output_keys=("level_236", "level_382", "level_500", "level_618", "level_786"),
            min_candles=30,
            overlay=True,
        )

    def _compute(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """محاسبه سطوح فیبوناچی به‌صورت خطوط افقی ثابت."""
        lookback = min(int(self._parameters["lookback"]), len(df))
        window = df.tail(lookback)
        swing_high = float(window["high"].max())
        swing_low = float(window["low"].min())
        high_position = int(window["high"].to_numpy().argmax())
        low_position = int(window["low"].to_numpy().argmin())
        is_uptrend = high_position > low_position
        price_range = swing_high - swing_low

        ratios = {"level_236": 0.236, "level_382": 0.382, "level_500": 0.5, "level_618": 0.618, "level_786": 0.786}
        outputs: dict[str, pd.Series] = {}
        for key, ratio in ratios.items():
            level = swing_high - price_range * ratio if is_uptrend else swing_low + price_range * ratio
            outputs[key] = pd.Series(np.full(len(df), level), index=df.index)
        return outputs

    def interpret(self, outputs: dict[str, pd.Series], df: pd.DataFrame) -> str:
        """
        تشخیص نزدیک‌ترین سطح فیبوناچی به قیمت فعلی.

        «نزدیک» یعنی فاصله کمتر از یک درصد.
        """
        price = float(df["close"].iloc[-1])
        closest_key, closest_distance = "", float("inf")
        for key, series in outputs.items():
            level = float(series.iloc[-1])
            distance = abs(price - level) / price * 100 if price else float("inf")
            if distance < closest_distance:
                closest_key, closest_distance = key, distance
        if closest_distance < 1.0:
            return f"AT_{closest_key.upper()}"
        return "NEUTRAL"


def find_swing_points(
    candles: list[Candle] | pd.DataFrame, window: int = 5
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """
    یافتن سقف‌ها و کف‌های نوسانی با روش پنجره متقارن.

    یک نقطه زمانی «سقف نوسانی» است که سقف آن از تمام کندل‌های window تایی
    چپ و راستش بیشتر باشد. مقدار window بزرگ‌تر یعنی سطوح مهم‌تر و کمتر.

    بازگشتی: (فهرست سقف‌ها، فهرست کف‌ها) که هرکدام زوج (اندیس، قیمت) هستند.
    """
    df = candles_to_dataframe(candles) if not isinstance(candles, pd.DataFrame) else candles
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    length = len(df)

    swing_highs: list[tuple[int, float]] = []
    swing_lows: list[tuple[int, float]] = []
    for i in range(window, length - window):
        left_high = highs[i - window : i]
        right_high = highs[i + 1 : i + window + 1]
        if highs[i] > left_high.max() and highs[i] > right_high.max():
            swing_highs.append((i, float(highs[i])))
        left_low = lows[i - window : i]
        right_low = lows[i + 1 : i + window + 1]
        if lows[i] < left_low.min() and lows[i] < right_low.min():
            swing_lows.append((i, float(lows[i])))
    return swing_highs, swing_lows


def analyze_market_structure(
    candles: list[Candle] | pd.DataFrame, timeframe: str = "", window: int = 5
) -> MarketStructure:
    """
    تحلیل ساختار بازار بر اساس توالی سقف‌ها و کف‌ها.

    منطق:
        • سقف بالاتر (HH) و کف بالاتر (HL) → ساختار صعودی
        • سقف پایین‌تر (LH) و کف پایین‌تر (LL) → ساختار نزولی
        • ترکیب نامنظم → بازار رِنج
        • عبور قیمت از آخرین سقف/کف نوسانی → شکست (Breakout/Breakdown)

    اگر داده کافی برای تشخیص نباشد، UNDEFINED برگردانده می‌شود؛ هیچ ساختار
    ساختگی گزارش نمی‌گردد.
    """
    df = candles_to_dataframe(candles) if not isinstance(candles, pd.DataFrame) else candles
    structure = MarketStructure(timeframe=timeframe)

    if len(df) < window * 4:
        structure.note = "Insufficient candles for structure analysis"
        return structure

    swing_highs, swing_lows = find_swing_points(df, window)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        structure.note = "Not enough swing points detected"
        return structure

    labels: list[str] = []
    for index in range(1, len(swing_highs)):
        labels.append("HH" if swing_highs[index][1] > swing_highs[index - 1][1] else "LH")
    for index in range(1, len(swing_lows)):
        labels.append("HL" if swing_lows[index][1] > swing_lows[index - 1][1] else "LL")

    # ترتیب زمانی برچسب‌ها برای نمایش دقیق‌تر
    ordered: list[tuple[int, str]] = []
    for index in range(1, len(swing_highs)):
        ordered.append((swing_highs[index][0], "HH" if swing_highs[index][1] > swing_highs[index - 1][1] else "LH"))
    for index in range(1, len(swing_lows)):
        ordered.append((swing_lows[index][0], "HL" if swing_lows[index][1] > swing_lows[index - 1][1] else "LL"))
    ordered.sort(key=lambda item: item[0])
    structure.swings = [label for _, label in ordered]

    recent = structure.swings[-6:]
    bullish_count = sum(1 for label in recent if label in {"HH", "HL"})
    bearish_count = sum(1 for label in recent if label in {"LH", "LL"})

    last_high = swing_highs[-1][1]
    last_low = swing_lows[-1][1]
    structure.last_swing_high = last_high
    structure.last_swing_low = last_low
    price = float(df["close"].iloc[-1])

    if price > last_high:
        structure.structure = MarketStructureType.BREAKOUT
        structure.trend = TrendDirection.BULLISH
        structure.note = "Price broke above the last swing high"
    elif price < last_low:
        structure.structure = MarketStructureType.BREAKDOWN
        structure.trend = TrendDirection.BEARISH
        structure.note = "Price broke below the last swing low"
    elif bullish_count >= bearish_count + 2:
        structure.structure = MarketStructureType.BULLISH
        structure.trend = TrendDirection.BULLISH
        structure.note = "Higher highs and higher lows"
    elif bearish_count >= bullish_count + 2:
        structure.structure = MarketStructureType.BEARISH
        structure.trend = TrendDirection.BEARISH
        structure.note = "Lower highs and lower lows"
    else:
        structure.structure = MarketStructureType.RANGING
        structure.trend = TrendDirection.NEUTRAL
        structure.note = "Mixed swing sequence; market is ranging"

    return structure


def find_support_resistance(
    candles: list[Candle] | pd.DataFrame,
    *,
    window: int = 5,
    max_levels: int = 8,
    cluster_tolerance_percent: float = 0.6,
) -> list[SupportResistanceLevel]:
    """
    استخراج سطوح حمایت و مقاومت از نقاط نوسانی.

    روش کار:
        ۱) یافتن تمام سقف/کف‌های نوسانی
        ۲) خوشه‌بندی سطوح نزدیک به هم (چون بازار دقیقاً یک قیمت را لمس نمی‌کند)
        ۳) رتبه‌بندی بر اساس تعداد برخورد: سطحی که چند بار لمس شده، معتبرتر است
        ۴) تفکیک به حمایت (زیر قیمت) و مقاومت (بالای قیمت)

    خروجی بر اساس نزدیکی به قیمت فعلی مرتب می‌شود.
    """
    df = candles_to_dataframe(candles) if not isinstance(candles, pd.DataFrame) else candles
    if len(df) < window * 3:
        return []

    swing_highs, swing_lows = find_swing_points(df, window)
    price = float(df["close"].iloc[-1])
    if price <= 0:
        return []

    raw_points = [value for _, value in swing_highs] + [value for _, value in swing_lows]
    if not raw_points:
        return []

    # خوشه‌بندی ساده: نقاط نزدیک به هم در یک سطح ادغام می‌شوند
    clusters: list[list[float]] = []
    for value in sorted(raw_points):
        if clusters and abs(value - clusters[-1][-1]) / price * 100 <= cluster_tolerance_percent:
            clusters[-1].append(value)
        else:
            clusters.append([value])

    levels: list[SupportResistanceLevel] = []
    for cluster in clusters:
        level_price = float(np.mean(cluster))
        touches = len(cluster)
        distance_percent = (level_price - price) / price * 100
        levels.append(
            SupportResistanceLevel(
                price=level_price,
                kind="resistance" if level_price > price else "support",
                strength="major" if touches >= 3 else ("minor" if touches == 1 else "medium"),
                source="swing",
                distance_percent=distance_percent,
            )
        )

    levels.sort(key=lambda level: abs(level.distance_percent))
    return levels[:max_levels]


def detect_trend(candles: list[Candle] | pd.DataFrame, fast: int = 21, slow: int = 50) -> TrendDirection:
    """
    تشخیص سریع جهت روند با مقایسه دو میانگین نمایی.

    این تابع سبک است و برای نمایش وضعیت در جدول‌ها و ابزار عامل هوش مصنوعی
    به کار می‌رود؛ تحلیل عمیق‌تر بر عهده analyze_market_structure است.
    """
    df = candles_to_dataframe(candles) if not isinstance(candles, pd.DataFrame) else candles
    if len(df) < slow + 2:
        return TrendDirection.NEUTRAL

    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    fast_value = float(ema_fast.iloc[-1])
    slow_value = float(ema_slow.iloc[-1])
    price = float(df["close"].iloc[-1])

    # اختلاف بسیار کم بین میانگین‌ها یعنی بازار جهت مشخصی ندارد
    separation_percent = abs(fast_value - slow_value) / slow_value * 100 if slow_value else 0.0
    if separation_percent < 0.15:
        return TrendDirection.NEUTRAL
    if fast_value > slow_value and price > slow_value:
        return TrendDirection.BULLISH
    if fast_value < slow_value and price < slow_value:
        return TrendDirection.BEARISH
    return TrendDirection.NEUTRAL
