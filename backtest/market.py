"""
بازار تاریخی بدون look-ahead — جایگزین MarketDataEngine در بک‌تست.

در زمان شبیه‌سازی t (ثانیه، لحظهٔ بسته‌شدن یک کندل پایه):
    • کندل‌های کامل تایم‌فریم X که `timestamp + step ≤ t` دارند دیده می‌شوند.
    • اگر سطل جاری X نیمه‌کاره است، مثل بازار زنده یک کندل «در حال شکل‌گیری»
      فقط از کندل‌های پایهٔ بسته‌شده (≤ t) ساخته و آخر فهرست گذاشته می‌شود.
هیچ داده‌ای پس از t هرگز برگردانده نمی‌شود (در آزمون‌ها بررسی شده).
"""

from __future__ import annotations

import bisect
from typing import Any

from app.core.models import Candle
from backtest.data import TIMEFRAME_SECONDS, resample


class HistoricalMarket:
    """بازار تاریخی چندنمادی با ساعت قابل تنظیم."""

    exchange_name = "backtest"
    #: موتور سیگنال با این پرچم می‌فهمد کندل آخر «در حال شکل‌گیری زنده» نیست
    live = False

    def __init__(self, base_tf: str = "5m") -> None:
        self.base_tf = base_tf
        self._base: dict[str, list[Candle]] = {}
        self._base_ts: dict[str, list[int]] = {}
        self._frames: dict[tuple[str, str], list[Candle]] = {}
        self._frame_ts: dict[tuple[str, str], list[int]] = {}
        self.now: int = 0

    def add_symbol(self, symbol: str, base_candles: list[Candle], timeframes: list[str]) -> None:
        """ثبت نماد با کندل‌های پایه و پیش‌ساخت تایم‌فریم‌های بزرگ‌تر."""
        self._base[symbol] = list(base_candles)
        self._base_ts[symbol] = [c.timestamp for c in base_candles]
        for timeframe in timeframes:
            frame = resample(base_candles, self.base_tf, timeframe)
            self._frames[(symbol, timeframe)] = frame
            self._frame_ts[(symbol, timeframe)] = [c.timestamp for c in frame]

    @property
    def symbols(self) -> list[str]:
        return list(self._base)

    def base_candles(self, symbol: str) -> list[Candle]:
        return self._base.get(symbol, [])

    def set_time(self, now: int) -> None:
        """تنظیم ساعت شبیه‌سازی (ثانیه UTC)."""
        self.now = int(now)

    def candles_at(self, symbol: str, timeframe: str, limit: int, now: int | None = None) -> list[Candle]:
        """کندل‌های قابل مشاهده در لحظهٔ now (بدون look-ahead)."""
        now = self.now if now is None else int(now)
        step = TIMEFRAME_SECONDS.get(timeframe)
        key = (symbol, timeframe)
        if step is None or key not in self._frames:
            return []
        frame = self._frames[key]
        stamps = self._frame_ts[key]
        # کندل‌های کامل: timestamp ≤ now - step
        idx = bisect.bisect_right(stamps, now - step)
        closed = frame[max(0, idx - limit):idx]
        base_step = TIMEFRAME_SECONDS[self.base_tf]
        if step > base_step:
            bucket_start = now - now % step
            if bucket_start < now:
                base = self._base[symbol]
                base_ts = self._base_ts[symbol]
                lo = bisect.bisect_left(base_ts, bucket_start)
                hi = bisect.bisect_right(base_ts, now - base_step)
                parts = base[lo:hi]
                if parts:
                    forming = Candle(
                        timestamp=bucket_start,
                        open=parts[0].open,
                        high=max(c.high for c in parts),
                        low=min(c.low for c in parts),
                        close=parts[-1].close,
                        volume=sum(c.volume for c in parts),
                    )
                    closed = (closed + [forming])[-limit:]
        return list(closed)

    async def get_candles(self, symbol: str, timeframe: str, limit: int = 250, **_: Any) -> list[Candle]:
        """همان امضای MarketDataEngine.get_candles."""
        return self.candles_at(symbol, timeframe, limit)

    def candle_source(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        """منبع کندل موتور پیش‌بینی (فقط کندل‌های کامل تا now)."""
        step = TIMEFRAME_SECONDS.get(timeframe)
        key = (symbol, timeframe)
        if step is None or key not in self._frames:
            return []
        stamps = self._frame_ts[key]
        idx = bisect.bisect_right(stamps, self.now - step)
        return list(self._frames[key][max(0, idx - limit):idx])


__all__ = ["HistoricalMarket"]
