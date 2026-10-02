"""
فیچرهای جریان سفارش (Order Flow) — نسخهٔ ۲.۵.۵.

هدف: افزودن شواهد جریان سفارش به تصمیم هوشمند **بدون ساختن داده**.

سه لایه، از کم‌هزینه به پرهزینه:

1. نمایندهٔ کندلی (همیشه در دسترس):
   • volume_delta — تخمین «حجم خرید منهای فروش» هر کندل با CLV:
         CLV = ((close-low) - (high-close)) / (high-low)  ∈ [-1, 1]
         delta = CLV × volume
     این یک **تقریب** است (داده تیک واقعی نداریم) و با برچسب
     `proxy=True` گزارش می‌شود.
   • cvd — جمع تجمعی volume_delta.
   • cvd_slope — شیب نرمال‌شدهٔ CVD در N کندل اخیر (∈ [-1, 1]).

2. دفتر سفارش (اگر provider.get_orderbook پاسخ دهد):
   • orderbook_imbalance = (Σbid − Σask) / (Σbid + Σask) در عمق محدود.

3. بافت فیوچرز (فقط اگر منبع داده‌ای تزریق شود):
   open_interest، oi_change، funding_rate، funding_change، liquidations،
   long_short_ratio. هیچ صرافی فعلی پروژه این APIها را ندارد؛ پس به‌صورت
   پیش‌فرض همه «unavailable» علامت می‌خورند — هرگز عدد ساختگی.

خروجی `series_for_features` برای مکانیزم `FeatureStore.build(extra=...)`
آماده است (هم‌طول با کندل‌ها).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: نام فیچرهای فیوچرز؛ وقتی داده نیست در `unavailable` فهرست می‌شوند.
FUTURES_FEATURES: tuple[str, ...] = (
    "open_interest",
    "oi_change",
    "funding_rate",
    "funding_change",
    "liquidations",
    "long_short_ratio",
)

#: همهٔ فیچرهای جریان سفارش که این ماژول می‌شناسد.
ALL_FEATURES: tuple[str, ...] = (
    "volume_delta",
    "cvd",
    "cvd_slope",
    "orderbook_imbalance",
    *FUTURES_FEATURES,
)


def _clv(candle: Any) -> float:
    """Close Location Value؛ کندل بی‌دامنه → صفر (نه تقسیم بر صفر)."""
    high = float(candle.high)
    low = float(candle.low)
    rng = high - low
    if rng <= 0:
        return 0.0
    close = float(candle.close)
    return ((close - low) - (high - close)) / rng


def volume_delta_series(candles: list[Any]) -> list[float]:
    """تخمین دلتای حجم هر کندل (نمایندهٔ کندلی، نه دادهٔ تیک)."""
    return [_clv(c) * float(c.volume) for c in candles]


def cvd_series(candles: list[Any]) -> list[float]:
    """CVD تقریبی: جمع تجمعی volume_delta."""
    total = 0.0
    out: list[float] = []
    for delta in volume_delta_series(candles):
        total += delta
        out.append(total)
    return out


def cvd_slope(candles: list[Any], window: int = 20) -> float | None:
    """
    شیب نرمال‌شدهٔ CVD در `window` کندل اخیر.

    = Σdelta / Σvolume در پنجره ∈ [-1, 1]. مثبت یعنی فشار خرید غالب.
    با داده ناکافی یا حجم صفر → None (نامعلوم، نه صفر ساختگی).
    """
    if len(candles) < max(3, window // 2):
        return None
    tail = candles[-window:]
    volume = sum(float(c.volume) for c in tail)
    if volume <= 0:
        return None
    delta = sum(volume_delta_series(tail))
    return max(-1.0, min(1.0, delta / volume))


def orderbook_imbalance(orderbook: Any, depth: int = 20) -> float | None:
    """
    عدم‌تعادل دفتر سفارش در `depth` سطح اول ∈ [-1, 1].

    ورودی می‌تواند شیء با `bids`/`asks` یا دیکشنری باشد؛ هر سطح
    [price, qty] یا شیء با price/quantity. دادهٔ خراب → None.
    """
    if orderbook is None:
        return None
    bids = getattr(orderbook, "bids", None)
    asks = getattr(orderbook, "asks", None)
    if bids is None and isinstance(orderbook, dict):
        bids = orderbook.get("bids")
        asks = orderbook.get("asks")
    if not bids or not asks:
        return None

    def _qty(level: Any) -> float:
        try:
            if isinstance(level, (list, tuple)):
                return float(level[1])
            for attr in ("quantity", "amount", "size", "qty"):
                value = getattr(level, attr, None)
                if value is not None:
                    return float(value)
        except (TypeError, ValueError, IndexError):
            return 0.0
        return 0.0

    bid_total = sum(_qty(level) for level in list(bids)[:depth])
    ask_total = sum(_qty(level) for level in list(asks)[:depth])
    total = bid_total + ask_total
    if total <= 0:
        return None
    return (bid_total - ask_total) / total


@dataclass(slots=True)
class OrderFlowSnapshot:
    """عکس لحظه‌ای جریان سفارش برای تصمیم هوشمند و ثبت در یادگیری."""

    cvd_slope: float | None = None
    last_volume_delta: float | None = None
    orderbook_imbalance: float | None = None
    futures: dict[str, float] = field(default_factory=dict)
    unavailable: list[str] = field(default_factory=list)
    proxy: bool = True

    @property
    def available(self) -> bool:
        """آیا دست‌کم یک شاهد واقعی/تقریبی وجود دارد؟"""
        return self.cvd_slope is not None or self.orderbook_imbalance is not None

    def bias(self) -> float:
        """
        سوگیری ترکیبی ∈ [-1, 1] (مثبت = فشار خرید).

        دفتر سفارش (دادهٔ واقعی) وزن بیشتری از نمایندهٔ کندلی دارد.
        """
        parts: list[tuple[float, float]] = []
        if self.cvd_slope is not None:
            parts.append((self.cvd_slope, 1.0))
        if self.orderbook_imbalance is not None:
            parts.append((self.orderbook_imbalance, 1.5))
        funding = self.futures.get("funding_rate")
        if funding is not None:
            # فاندینگ شدیداً مثبت = ازدحام خرید → کمی خلاف‌جهت
            parts.append((max(-1.0, min(1.0, -float(funding) * 1000.0)), 0.5))
        if not parts:
            return 0.0
        weight = sum(w for _, w in parts)
        return max(-1.0, min(1.0, sum(v * w for v, w in parts) / weight))

    def reliability(self) -> float:
        """اعتبار شاهد: نمایندهٔ کندلی به‌تنهایی ۰٫۵، با دفتر سفارش ۱."""
        if self.orderbook_imbalance is not None:
            return 1.0
        if self.cvd_slope is not None:
            return 0.5
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        """نمایش قابل ذخیره (JSON)."""
        return {
            "cvd_slope": None if self.cvd_slope is None else round(self.cvd_slope, 4),
            "last_volume_delta": (
                None if self.last_volume_delta is None else round(self.last_volume_delta, 6)
            ),
            "orderbook_imbalance": (
                None if self.orderbook_imbalance is None else round(self.orderbook_imbalance, 4)
            ),
            "futures": {k: round(float(v), 8) for k, v in self.futures.items()},
            "unavailable": list(self.unavailable),
            "proxy": self.proxy,
            "bias": round(self.bias(), 4),
        }


def build_snapshot(
    candles: list[Any],
    *,
    orderbook: Any = None,
    futures: dict[str, float | None] | None = None,
    window: int = 20,
) -> OrderFlowSnapshot:
    """
    ساخت عکس لحظه‌ای جریان سفارش از هر داده‌ای که واقعاً موجود است.

    futures: دیکشنری اختیاری از منبع فیوچرز؛ مقادیر None یا غایب در
    `unavailable` ثبت می‌شوند.
    """
    slope = cvd_slope(candles, window) if candles else None
    last_delta = volume_delta_series(candles[-1:])[0] if candles else None
    imbalance = orderbook_imbalance(orderbook)
    clean_futures: dict[str, float] = {}
    for name in FUTURES_FEATURES:
        value = (futures or {}).get(name)
        if isinstance(value, (int, float)):
            clean_futures[name] = float(value)
    unavailable = [name for name in FUTURES_FEATURES if name not in clean_futures]
    if imbalance is None:
        unavailable.append("orderbook_imbalance")
    if slope is None:
        unavailable.extend(["cvd", "cvd_slope", "volume_delta"])
    return OrderFlowSnapshot(
        cvd_slope=slope,
        last_volume_delta=last_delta,
        orderbook_imbalance=imbalance,
        futures=clean_futures,
        unavailable=unavailable,
        proxy=imbalance is None,
    )


def series_for_features(
    candles: list[Any],
    *,
    futures_series: dict[str, list[float | None]] | None = None,
) -> dict[str, list[float | None]]:
    """
    سری‌های هم‌طول با کندل‌ها برای `FeatureStore.build(extra=...)`.

    فقط سری‌هایی برگردانده می‌شوند که دادهٔ واقعی (یا نمایندهٔ صریح
    کندلی) دارند؛ سری فیوچرز با طول نادرست کنار گذاشته می‌شود.
    """
    out: dict[str, list[float | None]] = {}
    if not candles:
        return out
    deltas = volume_delta_series(candles)
    out["volume_delta"] = list(deltas)
    total = 0.0
    cvd: list[float | None] = []
    for delta in deltas:
        total += delta
        cvd.append(total)
    out["cvd"] = cvd
    for name, series in (futures_series or {}).items():
        if name in FUTURES_FEATURES and len(series) == len(candles):
            out[name] = list(series)
    return out


__all__ = [
    "ALL_FEATURES",
    "FUTURES_FEATURES",
    "OrderFlowSnapshot",
    "build_snapshot",
    "cvd_series",
    "cvd_slope",
    "orderbook_imbalance",
    "series_for_features",
    "volume_delta_series",
]
