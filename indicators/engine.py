"""
موتور اندیکاتور (Indicator Engine).

چرا وجود دارد؟
    محاسبه تک‌تک اندیکاتورها و مدیریت خطا در هر جای برنامه، منجر به کد
    تکراری می‌شود. این موتور:
        • مجموعه‌ای از اندیکاتورها را یکجا محاسبه می‌کند
        • از حافظه نهان برای پرهیز از محاسبه تکراری استفاده می‌کند
        • خطای یک اندیکاتور را ایزوله می‌کند تا بقیه تحلیل از بین نرود
        • تحلیل کامل یک تایم‌فریم (روند، ساختار، سطوح) را می‌سازد

ارتباط با ماژول‌های دیگر:
    بالادست : موتور سیگنال، ابزارهای عامل هوش مصنوعی، نمودار
    پایین‌دست: MarketDataEngine (برای کندل) و کلاس‌های اندیکاتور
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.constants import MIN_CANDLES_FOR_ANALYSIS, TrendDirection
from app.core.models import Candle, IndicatorResult, TimeframeAnalysis
from app.exceptions import IndicatorError, InsufficientDataError
from app.logging import get_logger
from indicators.base import candles_to_dataframe
from indicators.registry import IndicatorRegistry, indicator_registry
from indicators.support_resistance import (
    analyze_market_structure,
    detect_trend,
    find_support_resistance,
)
from market.cache.memory_cache import MarketCache

logger = get_logger(__name__)


class IndicatorEngine:
    """
    هماهنگ‌کننده محاسبه اندیکاتورها.

    نمونه‌سازی:
        engine = IndicatorEngine()
        result = engine.calculate("RSI", candles, "1h")
    """

    def __init__(
        self,
        registry: IndicatorRegistry | None = None,
        cache: MarketCache | None = None,
        *,
        default_parameters: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._registry = registry or indicator_registry
        self._cache = cache or MarketCache(max_entries=300)
        self._default_parameters = default_parameters or {}

    # ------------------------------------------------------------------
    # پیکربندی
    # ------------------------------------------------------------------
    def set_default_parameters(self, indicator: str, parameters: dict[str, Any]) -> None:
        """
        تعیین پارامتر پیش‌فرض یک اندیکاتور از روی تنظیمات کاربر.

        مثال: اگر کاربر دوره RSI را ۲۱ کند، همه محاسبات بعدی از آن استفاده
        می‌کنند بدون آنکه لازم باشد در هر فراخوانی ذکر شود.
        """
        self._default_parameters[indicator.upper()] = dict(parameters)
        self._cache.invalidate_prefix(f"ind:{indicator.upper()}")

    def available_indicators(self) -> list[str]:
        """فهرست اندیکاتورهای قابل استفاده."""
        return self._registry.available()

    def indicators_by_category(self) -> dict[str, list[str]]:
        """گروه‌بندی اندیکاتورها بر اساس دسته."""
        return self._registry.by_category()

    def get_metadata(self, name: str) -> dict[str, Any]:
        """فراداده یک اندیکاتور برای نمایش در راهنما."""
        return self._registry.get_metadata(name)

    # ------------------------------------------------------------------
    # محاسبه
    # ------------------------------------------------------------------
    @staticmethod
    def _data_fingerprint(
        candles: list[Candle] | pd.DataFrame,
    ) -> tuple[int, float, int] | None:
        """
        اثر انگشت دادهٔ ورودی برای کلید کش: (زمان آخرین کندل، قیمت
        بستهٔ آخر، تعداد).

        هدف این است که بدون ساختن DataFrame بتوان کلید کش را حساب کرد.
        داده‌ای که نه لیست کندل است و نه DataFrame معتبر، `None`
        برمی‌گرداند تا فراخوان مسیر عادی (بدون کش) را برود.
        """
        if isinstance(candles, pd.DataFrame):
            if candles.empty:
                return None
            return (
                int(candles["timestamp"].iloc[-1]),
                float(candles["close"].iloc[-1]),
                len(candles),
            )
        if not candles:
            return None
        last = candles[-1]
        try:
            return (int(last.timestamp), float(last.close), len(candles))
        except (AttributeError, TypeError, ValueError):
            return None

    def calculate(
        self,
        name: str,
        candles: list[Candle] | pd.DataFrame,
        timeframe: str = "",
        *,
        symbol: str = "",
        use_cache: bool = True,
        **parameters: Any,
    ) -> IndicatorResult:
        """
        محاسبه یک اندیکاتور.

        حافظه نهان بر اساس زمان آخرین کندل کلید می‌خورد؛ بنابراین تا زمانی
        که کندل جدیدی نیامده، محاسبه تکرار نمی‌شود.
        """
        indicator_name = name.upper()
        merged_parameters = {**self._default_parameters.get(indicator_name, {}), **parameters}

        # کلید کش پیش از ساخت DataFrame حساب می‌شود.
        #
        # پیش‌تر `candles_to_dataframe()` همیشه اول اجرا می‌شد و تازه بعد
        # کش بررسی می‌گشت. یعنی در یک تحلیل کاملاً کش‌شده، برای هر ۲۴
        # اندیکاتور یک DataFrame از نو ساخته می‌شد: حدود ۱۲ میلی‌ثانیه
        # کار دورریختنی به ازای هر نماد، که در پویش ۱۴۰۰ نمادی به چند
        # ثانیه می‌رسید. تبدیل حالا فقط وقتی انجام می‌شود که واقعاً
        # محاسبه‌ای در کار باشد.
        cache_key = ""
        if use_cache:
            fingerprint = self._data_fingerprint(candles)
            if fingerprint is not None:
                last_timestamp, last_close, length = fingerprint
                parameter_signature = ",".join(
                    f"{k}={v}" for k, v in sorted(merged_parameters.items())
                )
                cache_key = MarketCache.make_key(
                    "ind", indicator_name, symbol, timeframe, last_timestamp,
                    round(last_close, 8), length, parameter_signature,
                )
                cached = self._cache.get(cache_key)
                if cached is not None:
                    return cached

        df = candles_to_dataframe(candles) if not isinstance(candles, pd.DataFrame) else candles
        if df.empty:
            raise InsufficientDataError(
                f"No candles provided for {indicator_name}", details={"indicator": indicator_name}
            )

        indicator = self._registry.create(indicator_name, **merged_parameters)
        result = indicator.calculate(df, timeframe)

        if use_cache and cache_key:
            self._cache.set(cache_key, result, ttl_seconds=120)
        return result

    def calculate_many(
        self,
        names: list[str],
        candles: list[Candle] | pd.DataFrame,
        timeframe: str = "",
        *,
        symbol: str = "",
        parameters: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, IndicatorResult]:
        """
        محاسبه چند اندیکاتور به‌صورت یکجا.

        نکته مهم: خطای یک اندیکاتور (مثلاً داده ناکافی برای ایچیموکو) نباید
        کل تحلیل را از بین ببرد؛ آن اندیکاتور صرفاً از خروجی حذف و خطا لاگ
        می‌شود.
        """
        # تبدیل تنبل: تا وقتی همهٔ اندیکاتورها از کش بیایند، اصلاً
        # DataFrame ساخته نمی‌شود. اولین اندیکاتوری که واقعاً محاسبه
        # لازم دارد، تبدیل را یک بار انجام می‌دهد و بقیه از همان
        # استفاده می‌کنند.
        frame: pd.DataFrame | None = (
            candles if isinstance(candles, pd.DataFrame) else None
        )
        per_indicator = parameters or {}
        results: dict[str, IndicatorResult] = {}

        for name in names:
            try:
                payload: list[Candle] | pd.DataFrame = frame if frame is not None else candles
                results[name.upper()] = self.calculate(
                    name, payload, timeframe, symbol=symbol,
                    **per_indicator.get(name.upper(), {}),
                )
            except (IndicatorError, InsufficientDataError) as exc:
                logger.debug("Indicator %s skipped on %s: %s", name, timeframe, exc.message)
            except Exception:  # noqa: BLE001 - محاسبه غیرمنتظره نباید تحلیل را متوقف کند
                logger.exception("Unexpected error while computing indicator %s", name)
        return results

    # ------------------------------------------------------------------
    # تحلیل کامل یک تایم‌فریم
    # ------------------------------------------------------------------
    def analyze_timeframe(
        self,
        candles: list[Candle],
        timeframe: str,
        *,
        symbol: str = "",
        indicator_names: list[str] | None = None,
        role: str = "",
        swing_window: int = 5,
    ) -> TimeframeAnalysis:
        """
        ساخت تحلیل کامل یک تایم‌فریم.

        شامل: روند، اندیکاتورها، ساختار بازار، سطوح کلیدی و وضعیت حجم.

        اگر تعداد کندل از حداقل لازم کمتر باشد، خطای InsufficientDataError
        پرتاب می‌شود تا مطابق بند ۵۲ سند پروژه، تحلیل بی‌پایه تولید نشود.
        """
        if len(candles) < MIN_CANDLES_FOR_ANALYSIS:
            raise InsufficientDataError(
                f"Timeframe {timeframe} has only {len(candles)} candles "
                f"(minimum {MIN_CANDLES_FOR_ANALYSIS} required)",
                details={"timeframe": timeframe, "available": len(candles)},
            )

        df = candles_to_dataframe(candles)
        names = indicator_names or ["EMA", "SMA", "RSI", "MACD", "ATR", "BBANDS", "ADX", "OBV", "VWAP", "STOCH"]
        indicators = self.calculate_many(names, df, timeframe, symbol=symbol)

        analysis = TimeframeAnalysis(
            timeframe=timeframe,
            role=role,
            candles_count=len(candles),
            last_price=float(df["close"].iloc[-1]),
            trend=detect_trend(df),
            indicators=indicators,
            market_structure=analyze_market_structure(df, timeframe, window=swing_window),
            levels=find_support_resistance(df, window=swing_window),
            volume_note=self._describe_volume(df, indicators),
        )
        return analysis

    def analyze_multi_timeframe(
        self,
        candles_by_timeframe: dict[str, list[Candle]],
        *,
        symbol: str = "",
        indicator_names: list[str] | None = None,
        roles: dict[str, str] | None = None,
    ) -> dict[str, TimeframeAnalysis]:
        """
        تحلیل هم‌زمان چند تایم‌فریم.

        تایم‌فریم‌هایی که داده کافی ندارند، با ثبت هشدار کنار گذاشته می‌شوند
        و بقیه تحلیل ادامه می‌یابد.
        """
        role_map = roles or {}
        analyses: dict[str, TimeframeAnalysis] = {}
        for timeframe, candles in candles_by_timeframe.items():
            try:
                analyses[timeframe] = self.analyze_timeframe(
                    candles,
                    timeframe,
                    symbol=symbol,
                    indicator_names=indicator_names,
                    role=role_map.get(timeframe, ""),
                )
            except InsufficientDataError as exc:
                logger.warning("Skipping timeframe %s: %s", timeframe, exc.message)
        return analyses

    @staticmethod
    def _describe_volume(df: pd.DataFrame, indicators: dict[str, IndicatorResult]) -> str:
        """
        توصیف کوتاه وضعیت حجم برای استفاده در تحلیل و Prompt.

        این توصیف بر پایه داده واقعی است و هیچ فرضی اضافه نمی‌کند.
        """
        if "volume" not in df or len(df) < 20:
            return "Volume data unavailable"

        recent_average = float(df["volume"].tail(20).mean())
        current = float(df["volume"].iloc[-1])
        if recent_average <= 0:
            return "Volume data unavailable"

        ratio = current / recent_average
        if ratio >= 2.0:
            description = "Volume spike (>2x average)"
        elif ratio >= 1.3:
            description = "Above average volume"
        elif ratio <= 0.6:
            description = "Below average volume"
        else:
            description = "Normal volume"

        obv = indicators.get("OBV")
        if obv is not None and obv.signal in {"BULLISH", "BEARISH"}:
            description += f"; OBV {obv.signal.lower()}"
        return description

    @staticmethod
    def summarize_trend(analyses: dict[str, TimeframeAnalysis]) -> TrendDirection:
        """
        استخراج روند غالب از مجموعه تایم‌فریم‌ها.

        تایم‌فریم‌های بزرگ‌تر وزن بیشتری دارند، چون روند کلان مهم‌تر از نوسان
        کوتاه‌مدت است.
        """
        weights = {"1m": 0.5, "3m": 0.6, "5m": 0.7, "15m": 1.0, "30m": 1.2, "1h": 1.5,
                   "2h": 1.7, "4h": 2.0, "6h": 2.2, "8h": 2.3, "12h": 2.5, "1d": 3.0, "1w": 3.5}
        score = 0.0
        total = 0.0
        for timeframe, analysis in analyses.items():
            weight = weights.get(timeframe, 1.0)
            total += weight
            if analysis.trend is TrendDirection.BULLISH:
                score += weight
            elif analysis.trend is TrendDirection.BEARISH:
                score -= weight
        if total == 0:
            return TrendDirection.NEUTRAL
        normalized = score / total
        if normalized > 0.3:
            return TrendDirection.BULLISH
        if normalized < -0.3:
            return TrendDirection.BEARISH
        return TrendDirection.NEUTRAL
