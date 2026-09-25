"""
اسکالپ فوق‌سریع (Ultra) — نسخهٔ ۲.۵.۴.

خواستهٔ کاربر: «یک معامله باز بشه و با اهرم بالا به محض اینکه به سود خالص
مثلاً ۲ دلار (پس از کسر کارمزد) رسید سریع بسته بشه… با ۱۰۰۰ دلار موجودی
سیستم بتواند ۱۰۰ معاملهٔ اسکالپ خیلی سریع را همزمان انجام دهد، با اهرم ۳۰
یا ۵۰ یا ۶۰ که کاربر تعیین می‌کند.»

چرا منبع جدا؟
    منبع «اطمینان» برای هر دور، موتور کامل سیگنال را روی ده‌ها نماد و چند
    تایم‌فریم اجرا می‌کند (ده‌ها ثانیه و صدها درخواست) و حد ضرر نوسانی
    می‌دهد. برای ده‌ها معاملهٔ هم‌زمان چند دقیقه‌ای، این هم کند است و هم
    نامناسب.

این منبع **هیچ درخواست شبکهٔ اضافه‌ای نمی‌زند**:
    * قیمت و تاریخچهٔ کوتاه هر نماد از `TickEngine` (که فید زنده هر ۳ ثانیه
      کل بازار را در آن می‌ریزد و وب‌سوکت نمادهای باز را لحظه‌ای)؛
    * گردش ۲۴ ساعته از `get_all_tickers` که ۱۰ ثانیه کش می‌شود.

امتیاز = اندازهٔ حرکت پنجرهٔ کوتاه × یکنواختی آن × ضریب نقدینگی. جهت =
ادامهٔ همان حرکت (مومنتوم). هدف و حد ضرر را خود موتور از عددهای دلاری
کاربر می‌سازد: بستن در لحظهٔ رسیدن به سود **خالص** پس از هر دو کارمزد.

هشدار صادقانه: مومنتوم کوتاه‌مدت پیش‌بینی مطمئن نیست؛ با اهرم بالا، زیان هر
معامله دقیقاً همان سقف دلاری است که کاربر گذاشته و کارمزد بخش بزرگی از هر
حرکت را می‌خورد. هیچ سودی تضمین نمی‌شود.
"""

from __future__ import annotations

import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: پنجرهٔ پیش‌فرض سنجش حرکت (ثانیه)
DEFAULT_WINDOW_SECONDS = 30.0
#: کمترین حرکت پنجره (درصد) که نویز حساب نشود
DEFAULT_MIN_MOVE_PERCENT = 0.04
#: کمترین یکنواختی حرکت (۰ تا ۱)
DEFAULT_MIN_CONSISTENCY = 0.35
#: کمترین شمار نقطهٔ قیمت در پنجره
MIN_POINTS = 3


@dataclass
class UltraCandidate:
    """نامزد اسکالپ فوق‌سریع — همان فیلدهایی که `AutoTrader` می‌خواند."""

    symbol: str
    price: float
    direction: str  # LONG | SHORT
    #: امتیاز ۵۰ تا ۹۹ (برای نمایش و حالت تخصیص «اطمینان»)
    score: float
    move_percent: float = 0.0
    consistency: float = 0.0
    turnover_24h: float | None = None
    reasons: list[str] = field(default_factory=list)
    observed_at: float = field(default_factory=time.time)
    #: هدف/حد ضرر ندارد؛ موتور از بودجهٔ دلاری کاربر می‌سازد
    take_profit: float = 0.0
    stop_loss: float = 0.0


def momentum(points: list[tuple[float, float]], *, now_ms: float, window_ms: float) -> tuple[float, float, int]:
    """
    (حرکت درصدی، یکنواختی، شمار نقطه) در پنجرهٔ اخیر.

    یکنواختی = |جمع گام‌ها| ÷ جمع |گام‌ها|؛ ۱ یعنی حرکت یک‌طرفه، ۰ یعنی رفت‌وبرگشت.
    """
    recent = [(ts, price) for ts, price in points if now_ms - ts <= window_ms and price > 0]
    if len(recent) < MIN_POINTS:
        return 0.0, 0.0, len(recent)
    first, last = recent[0][1], recent[-1][1]
    steps = [b[1] - a[1] for a, b in zip(recent, recent[1:])]
    travel = sum(abs(step) for step in steps)
    consistency = abs(sum(steps)) / travel if travel > 0 else 0.0
    move = (last - first) / first * 100.0 if first > 0 else 0.0
    return move, consistency, len(recent)


class UltraScalpSource:
    """
    پویش لحظه‌ای کل بازار از روی کش تیک.

    `tick_engine` باید `history(symbol, limit)`، `get(symbol)` و `is_stale(symbol)`
    داشته باشد. `tickers_source` (اختیاری) فهرست تیکرها با `turnover_24h`.
    """

    def __init__(
        self,
        tick_engine_source: Callable[[], Any],
        *,
        tickers_source: Callable[[], Awaitable[list[Any]]] | None = None,
        settings: Callable[[str, Any], Any] | None = None,
        clock_ms: Callable[[], float] | None = None,
    ) -> None:
        self._tick_engine_source = tick_engine_source
        self._tickers_source = tickers_source
        self._settings = settings or (lambda _key, default: default)
        self._clock_ms = clock_ms or (lambda: time.time() * 1000.0)
        self.last_stats: dict[str, Any] = {}

    def _float(self, key: str, default: float) -> float:
        try:
            value = float(self._settings(key, default))
        except (TypeError, ValueError):
            return default
        return value if math.isfinite(value) else default

    async def _turnovers(self) -> dict[str, float]:
        if self._tickers_source is None:
            return {}
        try:
            tickers = await self._tickers_source()
        except Exception:  # noqa: BLE001 - نبود گردش نباید پویش را بکشد
            logger.debug("Ultra scalp: tickers unavailable", exc_info=True)
            return {}
        result: dict[str, float] = {}
        for ticker in tickers or []:
            symbol = str(getattr(ticker, "symbol", "") or "").upper()
            if symbol:
                result[symbol] = float(getattr(ticker, "turnover_24h", 0.0) or 0.0)
        return result

    async def scan(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 50,
        exclude: set[str] | None = None,
    ) -> list[UltraCandidate]:
        """بهترین نامزدهای همین لحظه، به ترتیب امتیاز نزولی."""
        engine = self._tick_engine_source()
        if engine is None:
            self.last_stats = {"symbols": 0, "candidates": 0, "reason": "no_tick_engine"}
            return []
        window_ms = max(5.0, self._float("scalp.ultra_window_seconds", DEFAULT_WINDOW_SECONDS)) * 1000.0
        min_move = max(0.0, self._float("scalp.ultra_min_move_percent", DEFAULT_MIN_MOVE_PERCENT))
        min_consistency = max(0.0, min(1.0, self._float("scalp.ultra_min_consistency", DEFAULT_MIN_CONSISTENCY)))
        min_turnover = max(0.0, self._float("scalp.min_liquidity", 2_000_000.0))
        turnovers = await self._turnovers()
        universe = [s.upper() for s in symbols] if symbols is not None else self._symbols(engine)
        excluded = {s.upper() for s in (exclude or set())}
        now_ms = self._clock_ms()
        candidates: list[UltraCandidate] = []
        stale = quiet = illiquid = 0
        for symbol in universe:
            if symbol in excluded:
                continue
            try:
                if engine.is_stale(symbol):
                    stale += 1
                    continue
                points = engine.history(symbol, 0)
            except Exception:  # noqa: BLE001
                continue
            turnover = turnovers.get(symbol)
            if turnover is not None and min_turnover > 0 and turnover < min_turnover:
                illiquid += 1
                continue
            move, consistency, count = momentum(points, now_ms=now_ms, window_ms=window_ms)
            if count < MIN_POINTS or abs(move) < min_move or consistency < min_consistency:
                quiet += 1
                continue
            liquidity = 1.0
            if turnover:
                liquidity = max(0.5, min(1.5, math.log10(max(turnover, 10.0)) / 7.0))
            raw = abs(move) * (0.5 + consistency) * liquidity
            score = max(50.0, min(99.0, 50.0 + raw * 100.0))
            price = float(points[-1][1])
            direction = "LONG" if move > 0 else "SHORT"
            candidates.append(UltraCandidate(
                symbol=symbol, price=price, direction=direction, score=round(score, 1),
                move_percent=round(move, 4), consistency=round(consistency, 3),
                turnover_24h=turnover,
                reasons=[f"حرکت {move:+.3f}٪ در {window_ms / 1000:.0f} ثانیه، یکنواختی {consistency:.2f}"],
            ))
        candidates.sort(key=lambda item: item.score, reverse=True)
        self.last_stats = {
            "symbols": len(universe), "candidates": len(candidates),
            "stale": stale, "quiet": quiet, "illiquid": illiquid,
        }
        return candidates[: max(1, int(limit))]

    @staticmethod
    def _symbols(engine: Any) -> list[str]:
        listing = getattr(engine, "symbols", None)
        return list(listing()) if callable(listing) else []


__all__ = ["UltraCandidate", "UltraScalpSource", "momentum"]
