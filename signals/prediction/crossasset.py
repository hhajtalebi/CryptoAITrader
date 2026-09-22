"""
هوش کراس-asset و تشخیص پیش‌تازی — خواسته‌های ۱۶ و ۱۷.

چرا این فایل وجود دارد؟
    بیت‌کوین جزیره نیست؛ حرکت ETH/SOL و کل بازار با آن هم‌بسته است و
    گاهی یکی از دیگری جلو می‌زند. کاربر خواسته این روابط «از دادهٔ
    تاریخی» استخراج شود و تصریح کرده همبستگی ساده کافی نیست —
    همبستگیِ با تأخیر (lagged) و غلتان (rolling) لازم است.

محدودهٔ صادقانه (تصمیم کاربر ۲۰۲۶-۰۹-۲۲): فقط دادهٔ کریپتوی درون
صرافی‌های متصل. DXY/طلا/نزدک منبع خارجی می‌خواهد و اضافه نمی‌شود؛
سلطهٔ BTC نیز بدون دادهٔ مارکت‌کپ قابل محاسبهٔ صادقانه نیست و ساخته
نمی‌شود.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.core.models import Candle


@dataclass(slots=True)
class LeadLagResult:
    """نتیجهٔ مقایسهٔ پیش‌تازی دو دارایی."""

    leader: str
    follower: str
    best_lag: int            # چند گام leader جلوتر است
    correlation: float       # همبستگی در بهترین تأخیر
    samples: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری."""
        return {
            "leader": self.leader,
            "follower": self.follower,
            "best_lag": self.best_lag,
            "correlation": round(self.correlation, 3),
            "samples": self.samples,
            "note": self.note,
        }


def _closes_by_time(candles: list[Candle]) -> dict[int, float]:
    """نگاشت timestamp → close برای هم‌ترازی دو سری."""
    return {c.timestamp: c.close for c in candles if c.close > 0}


def _aligned_returns(a: list[Candle], b: list[Candle]) -> tuple[list[float], list[float]]:
    """بازده‌های هم‌ترازشدهٔ دو سری روی مهرهای زمانی مشترک."""
    times = sorted(set(_closes_by_time(a)) & set(_closes_by_time(b)))
    if len(times) < 30:
        return [], []
    closes_a = _closes_by_time(a)
    closes_b = _closes_by_time(b)
    returns_a = [
        math.log(closes_a[t2] / closes_a[t1])
        for t1, t2 in zip(times[:-1], times[1:], strict=False)
        if closes_a[t1] > 0
    ]
    returns_b = [
        math.log(closes_b[t2] / closes_b[t1])
        for t1, t2 in zip(times[:-1], times[1:], strict=False)
        if closes_b[t1] > 0
    ]
    return returns_a, returns_b


def _pearson(x: list[float], y: list[float]) -> float:
    """ضریب همبستگی پیرسون؛ داده کم = ۰."""
    n = min(len(x), len(y))
    if n < 20:
        return 0.0
    x, y = x[-n:], y[-n:]
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=False))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0 or vy <= 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def rolling_correlation(
    a: list[float], b: list[float], window: int = 48
) -> list[float]:
    """سری همبستگی غلتان — همبستگی «همین امروز» بدون رجوع به آینده."""
    if len(a) != len(b) or len(a) <= window or window < 10:
        return []
    result: list[float] = []
    for end in range(window, len(a) + 1):
        result.append(_pearson(a[end - window:end], b[end - window:end]))
    return result


def lagged_cross_correlation(
    a: list[float], b: list[float], max_lag: int = 6
) -> tuple[int, float]:
    """
    همبستگی با تأخیر: بهترین جابه‌جایی و مقدارش.

    تعریف روشن: lag=k یعنی r_a[t] با r_b[t+k] هم‌بسته است — یعنی a
    جلوتر می‌زند و b دنبالش می‌رود.
    """
    best_lag, best_corr = 0, _pearson(a, b)
    for lag in range(1, min(max_lag, len(a) - 20) + 1):
        corr = _pearson(a[:-lag], b[lag:])
        if abs(corr) > abs(best_corr):
            best_lag, best_corr = lag, corr
    return best_lag, best_corr


def detect_lead_lag(
    name_a: str,
    candles_a: list[Candle],
    name_b: str,
    candles_b: list[Candle],
    *,
    max_lag: int = 6,
) -> LeadLagResult | None:
    """
    کدام دارایی معمولاً جلوتر حرکت می‌کند؟ — خواستهٔ ۱۷.

    بازگشتی: None اگر هم‌پوشانی زمانی کافی نباشد — بدون حدس.
    """
    returns_a, returns_b = _aligned_returns(candles_a, candles_b)
    if len(returns_a) < 60:
        return None

    # جهت A: آیا a جلوتر از b است؟
    lag_ab, corr_ab = lagged_cross_correlation(returns_a, returns_b, max_lag)
    # جهت B: آیا b جلوتر از a است؟
    lag_ba, corr_ba = lagged_cross_correlation(returns_b, returns_a, max_lag)

    if abs(corr_ab) >= abs(corr_ba):
        return LeadLagResult(
            leader=name_a,
            follower=name_b,
            best_lag=lag_ab,
            correlation=corr_ab,
            samples=len(returns_a),
            note="positive lag means leader's past returns align with follower's future returns",
        )
    return LeadLagResult(
        leader=name_b,
        follower=name_a,
        best_lag=lag_ba,
        correlation=corr_ba,
        samples=len(returns_a),
    )


def market_context(changes: dict[str, float]) -> dict[str, Any]:
    """
    وضعیت هم‌جهتی بازار از تغییرات درصدی چند دارایی — خواستهٔ ۱۶.

    خروجی: جهت هر دارایی + برچسب زمینهٔ بازار (risk_on/risk_off/mixed)
    برای مصرف در گزارش و فیوژن. هیچ سلطه/ماکرویی جعل نمی‌شود.
    """
    directions = {
        symbol: ("up" if change > 0.15 else "down" if change < -0.15 else "flat")
        for symbol, change in changes.items()
    }
    ups = sum(1 for d in directions.values() if d == "up")
    downs = sum(1 for d in directions.values() if d == "down")
    if ups and not downs:
        context = "risk_on"
    elif downs and not ups:
        context = "risk_off"
    elif ups and downs:
        context = "mixed"
    else:
        context = "flat"
    return {"changes_percent": {k: round(v, 2) for k, v in changes.items()},
            "directions": directions, "context": context}
