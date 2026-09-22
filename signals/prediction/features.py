"""
خزانهٔ فیچر (Feature Store).

چرا این فایل وجود دارد؟
    ۱. ضد look-ahead (قانون حیاتی ۳): هر فیچر به «زمان بسته‌شدن کندل»
       مهر زمانی می‌خورد — یعنی اولین لحظه‌ای که در دنیای واقعی می‌شد
       آن مقدار را دانست. هیچ مدلی اجازه ندارد فیچری زودتر از این زمان
       ببیند.
    ۲. استانداردسازی: مدل‌ها (آماری، GBM، LSTM) همیشه با همین نام‌ها و
       همین ترتیب فیچر کار می‌کنند؛ اضافه/کم‌شدن فیچر یک تصمیم مرکزی
       است نه پراکنده در کد مدل‌ها.
    ۳. عدم جعل (قانون ۲): ردیفی که فیچرش موجود نیست، از ماتریس مدل حذف
       می‌شود — هرگز با میانگین/صفر پر نمی‌شود.

فیچرهای پایه (همیشه از کندل‌های بسته‌شده محاسبه می‌شوند):
    price_returns   بازده لگاریتمی قیمت
    volume_change   تغییر نسبی حجم
    rsi             قدرت نسبی (از موتور اندیکاتور موجود)
    macd            خط MACD
    macd_signal     خط سیگنال MACD
    macd_histogram  هیستوگرام MACD
    atr             نوسان واقعی میانگین
    atr_percent     ATR نسبت به قیمت
    ema_distance    فاصلهٔ قیمت از EMA20 «بر حسب ATR» — چرا نرمال‌شده؟
                    تا بین نمادهای ۶۰ دلاری و ۱۱۰ هزار دلاری قابل مقایسه باشد
    bollinger_width پهنای باندهای بولینگر
    adx             قدرت روند

فیچرهای آینده (OI، funding، CVD، …) وقتی منبع داده اضافه شد از طریق
پارامتر `extra` به همین ساختار وصل می‌شوند — معماری از امروز آماده است.

ارتباط با ماژول‌های دیگر:
    بالادست : market/quality.py (کندل پاک) و CandleRepository
    پایین‌دست: مدل‌های پیش‌بینی، موتور رژیم، آنسامبل
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.core.models import Candle
from app.logging import get_logger
from indicators.engine import IndicatorEngine
from market.quality import timeframe_seconds

logger = get_logger(__name__)

#: فیچرهایی که این ماژول خودش از اندیکاتورهای موجود می‌سازد.
BASE_FEATURES: tuple[str, ...] = (
    "price_returns",
    "volume_change",
    "rsi",
    "macd",
    "macd_signal",
    "macd_histogram",
    "atr",
    "atr_percent",
    "ema_distance",
    "bollinger_width",
    "adx",
)

#: نگاشت فیچر → (نام اندیکاتور در رجیستری، کلید خروجی سری).
#: چرا جدول نگاشت؟ تا افزودن فیچر جدید فقط یک خط باشد و منطق build
#: دست‌نخورده بماند.
_INDICATOR_FEATURES: dict[str, tuple[str, str]] = {
    "rsi": ("RSI", "rsi"),
    "macd": ("MACD", "macd"),
    "macd_signal": ("MACD", "signal"),
    "macd_histogram": ("MACD", "histogram"),
    "atr": ("ATR", "atr"),
    "atr_percent": ("ATR", "atr_percent"),
    "bollinger_width": ("BBANDS", "bandwidth"),
    "adx": ("ADX", "adx"),
}

#: اندیکاتورهایی که یک‌بار برای همهٔ فیچرها محاسبه می‌شوند.
_REQUIRED_INDICATORS: tuple[str, ...] = ("RSI", "MACD", "ATR", "BBANDS", "ADX", "EMA")


@dataclass(slots=True)
class FeatureVector:
    """
    فیچرهای یک لحظهٔ زمانی مشخص.

    close_time: زمان بسته‌شدن کندلِ مبنا (ثانیهٔ UTC) — این همان «زمان
    دانستنی‌بودن» فیچر است و هیچ فیچری حق ندارد قبل از آن مصرف شود.
    """

    close_time: int
    values: dict[str, float] = field(default_factory=dict)

    def get(self, name: str, default: float | None = None) -> float | None:
        """مقدار فیچر؛ اگر نبود default (بدون عددسازی)."""
        return self.values.get(name, default)


@dataclass(slots=True)
class FeatureSet:
    """
    مجموعهٔ فیچرهای یک نماد/تایم‌فریم.

    available: فیچرهایی که دست‌کم یک مقدار غیرتهی دارند — بر اساس همین
    فهرست مدل‌ها فعال/غیرفعال می‌شوند، نه حدس.
    """

    symbol: str
    timeframe: str
    vectors: list[FeatureVector] = field(default_factory=list)
    available: tuple[str, ...] = ()

    def __len__(self) -> int:
        """تعداد لحظه‌های دارای فیچر."""
        return len(self.vectors)

    def latest(self) -> FeatureVector | None:
        """آخرین بردار فیچر (تازه‌ترین اطلاعات)."""
        return self.vectors[-1] if self.vectors else None

    def matrix(self, names: list[str] | None = None) -> tuple[list[int], list[list[float]]]:
        """
        ماتریس کامل برای مدل‌ها.

        ردیف‌هایی که *هر* فیچر خواسته‌شده‌شان تهی است حذف می‌شوند —
        میانگین‌گیری/پرکردن سکوت‌آمیز ممنوع (قانون جعل داده).

        بازگشتی: (فهرست close_time ها هم‌طول با ردیف‌ها، ردیف‌های فیچر).
        """
        wanted = list(names) if names else list(self.available)
        times: list[int] = []
        rows: list[list[float]] = []
        for vector in self.vectors:
            row: list[float] | None = []
            for name in wanted:
                value = vector.get(name)
                if value is None or not math.isfinite(value):
                    row = None
                    break
                row.append(float(value))
            if row is not None:
                times.append(vector.close_time)
                rows.append(row)
        return times, rows

    def to_dict(self) -> dict[str, Any]:
        """خروجی سبک برای لاگ و Prompt عامل AI (سری کامل نمی‌رود)."""
        last = self.latest()
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "count": len(self.vectors),
            "available": list(self.available),
            "latest": {
                "close_time": last.close_time,
                "values": dict(last.values),
            }
            if last
            else None,
        }


class FeatureStore:
    """
    سازندهٔ استاندارد فیچرها از کندل‌های بسته‌شده.

    نمونه‌سازی:
        store = FeatureStore()
        features = store.build(candles, "1h", symbol="BTC/USDT", now=now)
    """

    def __init__(self, indicator_engine: IndicatorEngine | None = None) -> None:
        # موتور اندیکاتور تزریق می‌شود تا در آزمون‌ها fake قابل جایگزینی
        # باشد و در تولید از کش موجود استفاده شود — بازمحاسبه ممنوع.
        self._indicators = indicator_engine or IndicatorEngine()

    def build(
        self,
        candles: list[Candle],
        timeframe: str,
        *,
        symbol: str = "",
        now: int | None = None,
        extra: dict[str, list[float | None]] | None = None,
    ) -> FeatureSet:
        """
        ساخت فیچرها.

        پارامترها:
            candles   : کندل‌ها (معمولاً خروجی clean_candles).
            timeframe : کد تایم‌فریم پایه.
            symbol    : فقط برای فراداده.
            now       : زمان مرجع ثانیهٔ UTC. اگر داده شود، فقط کندل‌هایی
                        که تا این لحظه «بسته شده‌اند» (timestamp + گام ≤ now)
                        دیده می‌شوند. اگر None باشد، آخرین کندل «در حال
                        شکل‌گیری» فرض و حذف می‌شود — سیاست محافظه‌کارانه.
            extra     : فیچرهای اختیاری هم‌طول با کندل‌های بسته‌شده
                        (مثلاً oi_change وقتی منبع داده باشد).

        بازگشتی: FeatureSet؛ با دادهٔ ناکافی، فهرست خالی و available خالی —
        هرگز عدد ساختگی.
        """
        step = timeframe_seconds(timeframe)

        # ------------------------------------------------------------------
        # گام ۱: فقط کندل‌های بسته‌شده — سنگ‌بنای قانون ضد look-ahead.
        # ------------------------------------------------------------------
        if now is not None:
            closed = [c for c in candles if c.timestamp + step <= now]
        else:
            closed = candles[:-1] if len(candles) > 1 else []

        if len(closed) < 2:
            logger.debug(
                "FeatureStore: insufficient closed candles for %s %s (%d)",
                symbol, timeframe, len(closed),
            )
            return FeatureSet(symbol=symbol, timeframe=timeframe)

        # ------------------------------------------------------------------
        # گام ۲: فیچرهای قیمتی/حجمی که خودشان سری می‌سازند.
        # ------------------------------------------------------------------
        series: dict[str, list[float | None]] = {}
        returns: list[float | None] = [None]  # اولین کندل بازده ندارد
        volume_changes: list[float | None] = [None]
        for previous, current in zip(closed[:-1], closed[1:], strict=False):
            if previous.close > 0 and current.close > 0:
                returns.append(math.log(current.close / previous.close))
            else:
                returns.append(None)
            if previous.volume > 0:
                volume_changes.append((current.volume - previous.volume) / previous.volume)
            else:
                volume_changes.append(None)
        series["price_returns"] = returns
        series["volume_change"] = volume_changes

        # ------------------------------------------------------------------
        # گام ۳: فیچرهای اندیکاتوری از موتور موجود — نه بازنویسی.
        # خطای هر اندیکاتور فقط همان فیچر را غیرفعال می‌کند.
        # ------------------------------------------------------------------
        results = self._indicators.calculate_many(
            list(_REQUIRED_INDICATORS), closed, timeframe, symbol=symbol
        )
        for feature, (indicator_name, key) in _INDICATOR_FEATURES.items():
            result = results.get(indicator_name)
            if result is None:
                series[feature] = [None] * len(closed)
                continue
            values = result.values.get(key, [])
            series[feature] = [
                (float(v) if v is not None and math.isfinite(float(v)) else None)
                for v in values[: len(closed)]
            ] + [None] * max(0, len(closed) - len(values))

        # نرمال‌سازی فاصلهٔ EMA بر حسب ATR — مقایسه‌پذیری بین نمادها.
        ema_result = results.get("EMA")
        ema_series: list[float | None] = [None] * len(closed)
        if ema_result is not None:
            raw = ema_result.values.get("ema", [])
            ema_series = [
                (float(v) if v is not None and math.isfinite(float(v)) else None)
                for v in raw[: len(closed)]
            ] + [None] * max(0, len(closed) - len(raw))
        series["ema_distance"] = [
            (
                (c.close - e) / a
                if e is not None and a is not None and a > 0
                else None
            )
            for c, e, a in zip(closed, ema_series, series["atr"], strict=False)
        ]

        # ------------------------------------------------------------------
        # گام ۴: فیچرهای خارجی (OI/funding/CVD در فازهای بعد).
        # ------------------------------------------------------------------
        if extra:
            for name, values in extra.items():
                if len(values) >= len(closed):
                    series[name] = list(values[-len(closed):])
                else:
                    series[name] = list(values) + [None] * (len(closed) - len(values))

        # ------------------------------------------------------------------
        # گام ۵: ساخت بردارها با مهر «زمان بسته‌شدن».
        # برداری که هیچ فیچری ندارد (مثل کندل اول که بازده ندارد) ساخته
        # نمی‌شود — طول مجموعه یعنی «تعداد لحظه‌های دارای اطلاعات».
        # ------------------------------------------------------------------
        vectors: list[FeatureVector] = []
        for index, candle in enumerate(closed):
            values: dict[str, float] = {}
            for name, column in series.items():
                value = column[index] if index < len(column) else None
                if value is not None and math.isfinite(value):
                    values[name] = float(value)
            if values:
                vectors.append(FeatureVector(close_time=candle.timestamp + step, values=values))

        available = tuple(
            name
            for name, column in series.items()
            if any(v is not None and math.isfinite(v) for v in column)
        )

        return FeatureSet(
            symbol=symbol, timeframe=timeframe, vectors=vectors, available=available
        )
