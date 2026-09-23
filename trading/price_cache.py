"""
کش قیمت تیک‌محور — قلب معماری رویدادمحور معامله‌گری.

زنجیرهٔ داده (خواستهٔ §۵ و §۶ تسک):

    WebSocket / Live Feed → Tick Event → Price Cache (Bid/Ask/Last)
        → Position Monitor همان لحظه

هر تیک سه مهر زمانی دارد و تأخیرها همان‌جا محاسبه می‌شوند:

    exchange timestamp   → لحظه‌ای که صرافی تیک را ساخت
    receive timestamp    → لحظه‌ای که به برنامه رسید
    processing timestamp → لحظه‌ای که پردازش و پخش شد

    receive_latency_ms        = received - exchange
    processing_latency_ms     = processed - received
    total_market_data_latency = processed - exchange

دادهٔ کهنه (stale) یعنی «اعتماد نکن»: ورود معاملهٔ تازه ممنوع است و
رابط کاربری باید صریح STALE نشان دهد — نه عدد یخ‌زده.

این ماژول Qt نمی‌شناسد و روی نخ asyncio زندگی می‌کند؛ شنوندگانش هم
همان‌جا صدا زده می‌شوند.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from app.logging import get_logger

logger = get_logger(__name__)

#: بیشینهٔ نقطهٔ تاریخچهٔ قیمت هر نماد (نمودار کوچک و پایش تیک)
MAX_HISTORY_POINTS = 600

#: مهر زمانی صرافی زیر این عدد (میلی‌ثانیه) نامعتبر تلقی می‌شود.
MIN_PLAUSIBLE_EXCHANGE_MS = 1_000_000_000_000.0


def _now_ms() -> float:
    """زمان جاری به میلی‌ثانیه (بر پایهٔ ساعت دیواری)."""
    return time.time() * 1000.0


def _parse_exchange_ms(timestamp: Any) -> float | None:
    """
    تبدیل مهر زمانی صرافی به میلی‌ثانیهٔ epoch.

    بعضی صرافی‌ها ثانیه می‌دهند و بعضی میلی‌ثانیه؛ هر دو پذیرفته
    می‌شود. مقدار نامعتبر یا صفر یعنی «نمی‌دانم» و تأخیر دریافت
    محاسبه نمی‌شود — عدد جعلی ساخته نمی‌شود.
    """
    try:
        value = float(timestamp)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value < 1e11:  # ثانیه
        value *= 1000.0
    if value < MIN_PLAUSIBLE_EXCHANGE_MS:
        return None
    return value


@dataclass
class TickQuote:
    """آخرین وضعیت قیمت یک نماد: Bid و Ask و Last جدا جدا."""

    symbol: str
    last: float
    bid: float = 0.0
    ask: float = 0.0
    source: str = "rest"
    exchange_ts_ms: float | None = None
    received_ts_ms: float = 0.0
    processed_ts_ms: float = 0.0
    #: عمق بهترین سطح دفتر سفارش (حجم) — صفر یعنی نامعلوم
    bid_depth: float = 0.0
    ask_depth: float = 0.0
    tick_direction: int = 0
    change_percent: float = 0.0

    @property
    def spread(self) -> float:
        """اسپرد واقعی Bid/Ask؛ صفر یعنی دفتر در دسترس نیست."""
        if self.bid > 0 and self.ask > 0 and self.ask >= self.bid:
            return self.ask - self.bid
        return 0.0

    @property
    def spread_percent(self) -> float:
        """اسپرد بر حسب درصد میان‌گین."""
        mid = (self.bid + self.ask) / 2.0 if self.bid > 0 and self.ask > 0 else self.last
        if mid <= 0 or self.spread <= 0:
            return 0.0
        return self.spread / mid * 100.0

    @property
    def mid(self) -> float:
        """میان‌گین Bid/Ask، یا Last اگر دفتر نیست."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last

    @property
    def receive_latency_ms(self) -> float | None:
        """تأخیر رسیدن: exchange → برنامه. نامعلوم یعنی None."""
        if self.exchange_ts_ms is None or self.received_ts_ms <= 0:
            return None
        return max(0.0, self.received_ts_ms - self.exchange_ts_ms)

    @property
    def processing_latency_ms(self) -> float | None:
        """تأخیر پردازش: رسیدن → پخش به پایشگر."""
        if self.received_ts_ms <= 0 or self.processed_ts_ms <= 0:
            return None
        return max(0.0, self.processed_ts_ms - self.received_ts_ms)

    @property
    def total_latency_ms(self) -> float | None:
        """تأخیر کل بازار: exchange → پردازش."""
        if self.exchange_ts_ms is None or self.processed_ts_ms <= 0:
            return None
        return max(0.0, self.processed_ts_ms - self.exchange_ts_ms)

    @property
    def age_ms(self) -> float:
        """سن داده از آخرین تیک — برای نمایش و دروازهٔ کهنگی."""
        if self.processed_ts_ms <= 0:
            return float("inf")
        return max(0.0, _now_ms() - self.processed_ts_ms)

    def exit_price(self, side: str) -> float:
        """
        قیمت واقعی خروج: LONG با Bid می‌فروشد، SHORT با Ask می‌خرد.

        بدون دفتر سفارش، Last برمی‌گردد — صادقانه‌ترین جایگزین موجود.
        """
        if side == "long" and self.bid > 0:
            return self.bid
        if side == "short" and self.ask > 0:
            return self.ask
        return self.last

    def entry_price(self, side: str) -> float:
        """
        قیمت واقعی ورود: LONG با Ask می‌خرد، SHORT با Bid می‌فروشد.

        ورود همیشه از سمت گران‌ترِ اسپرد است؛ نادیده‌گرفتن این یعنی
        سود کاغذی که در واقعیت وجود ندارد.
        """
        if side == "long" and self.ask > 0:
            return self.ask
        if side == "short" and self.bid > 0:
            return self.bid
        return self.last

    def to_dict(self) -> dict[str, Any]:
        """نمای دیکشنری برای UI و گزارش."""
        return {
            "symbol": self.symbol,
            "last": self.last,
            "bid": self.bid,
            "ask": self.ask,
            "spread": round(self.spread, 10),
            "spread_percent": round(self.spread_percent, 5),
            "source": self.source,
            "age_ms": round(self.age_ms, 1),
            "receive_latency_ms": (
                round(self.receive_latency_ms, 1) if self.receive_latency_ms is not None else None
            ),
            "processing_latency_ms": (
                round(self.processing_latency_ms, 2)
                if self.processing_latency_ms is not None
                else None
            ),
            "total_latency_ms": (
                round(self.total_latency_ms, 1) if self.total_latency_ms is not None else None
            ),
            "updated_at": datetime.now(UTC).isoformat(),
        }


class TickEngine:
    """
    انبار تیک زنده + پخش فوری به شنوندگان.

    AutoTrader خودش را شنونده ثبت می‌کند تا همان لحظه‌ای که تیک می‌رسد
    TP/SL/سر‌به‌سر/تریلینگ را بسنجد — بدون انتظار برای هیچ تایمری.
    """

    def __init__(self, *, stale_after_seconds: float = 10.0) -> None:
        self.stale_after_ms = max(1.0, float(stale_after_seconds)) * 1000.0
        self._quotes: dict[str, TickQuote] = {}
        self._history: dict[str, deque[tuple[float, float]]] = {}
        self._listeners: list[Callable[[TickQuote], None]] = []
        self._tick_count = 0
        self._ws_tick_count = 0
        self._last_tick_at_ms = 0.0
        self._latency_samples: deque[float] = deque(maxlen=200)

    # ------------------------------------------------------------------
    # ثبت داده
    # ------------------------------------------------------------------
    def record(
        self,
        symbol: str,
        price: float,
        *,
        source: str = "rest",
        exchange_ts: Any = None,
        bid: float = 0.0,
        ask: float = 0.0,
        tick_direction: int = 0,
        change_percent: float = 0.0,
        received_at_ms: float | None = None,
    ) -> TickQuote | None:
        """
        ثبت یک تیک و پخش فوری آن.

        قیمت نامعتبر (صفر/منفی) رد می‌شود. اگر قیمت و اسپرد هیچ تغییری
        نکرده باشند، تیک به‌روزرسانیِ مهر زمانی می‌گیرد ولی دوباره پخش
        نمی‌شود — شنونده‌ها قرار نیست با تکرار بیدار شوند.
        """
        price = float(price or 0.0)
        symbol = str(symbol or "").strip().upper()
        if price <= 0 or not symbol:
            return None

        received = received_at_ms if received_at_ms is not None else _now_ms()
        processed = _now_ms()
        exchange_ms = _parse_exchange_ms(exchange_ts)

        previous = self._quotes.get(symbol)
        unchanged = (
            previous is not None
            and abs(previous.last - price) < 1e-12
            and abs(previous.bid - float(bid or 0.0)) < 1e-12
            and abs(previous.ask - float(ask or 0.0)) < 1e-12
        )

        quote = TickQuote(
            symbol=symbol,
            last=price,
            bid=float(bid or 0.0),
            ask=float(ask or 0.0),
            source=str(source or "rest"),
            exchange_ts_ms=exchange_ms,
            received_ts_ms=received,
            processed_ts_ms=processed,
            tick_direction=int(tick_direction or 0),
            change_percent=float(change_percent or 0.0),
        )
        if previous is not None:
            quote.bid_depth = previous.bid_depth
            quote.ask_depth = previous.ask_depth
            if quote.tick_direction == 0 and price != previous.last:
                quote.tick_direction = 1 if price > previous.last else -1

        self._quotes[symbol] = quote
        self._tick_count += 1
        if source == "websocket":
            self._ws_tick_count += 1
        self._last_tick_at_ms = processed
        total = quote.total_latency_ms
        if total is not None:
            self._latency_samples.append(total)

        history = self._history.setdefault(
            symbol, deque(maxlen=MAX_HISTORY_POINTS)
        )
        history.append((processed, price))

        if not unchanged:
            self._notify(quote)
        return quote

    def record_book(self, symbol: str, book: Any) -> TickQuote | None:
        """
        ثبت بهترین Bid/Ask و عمق آن از دفتر سفارش.

        آخرین قیمت دست‌نخورده می‌ماند؛ این فراخوانی فقط لایهٔ دفتر را
        تازه می‌کند و تغییر اسپرد را پخش می‌کند.
        """
        symbol = str(symbol or "").strip().upper()
        if symbol == "" or book is None:
            return None
        bid = float(getattr(book, "best_bid", 0.0) or 0.0)
        ask = float(getattr(book, "best_ask", 0.0) or 0.0)
        bids = list(getattr(book, "bids", []) or [])
        asks = list(getattr(book, "asks", []) or [])
        bid_depth = float(getattr(bids[0], "amount", 0.0) or 0.0) if bids else 0.0
        ask_depth = float(getattr(asks[0], "amount", 0.0) or 0.0) if asks else 0.0

        quote = self._quotes.get(symbol)
        if quote is None:
            # دفتر بدون تیک قبلی: قیمت میانی را به‌عنوان Last ثبت نکن —
            # عدد جعلی نیست. فقط ذخیرهٔ لایه‌ای بی‌معناست؛ رد می‌شود.
            return None
        quote.bid = bid
        quote.ask = ask
        quote.bid_depth = bid_depth
        quote.ask_depth = ask_depth
        self._notify(quote)
        return quote

    # ------------------------------------------------------------------
    # خواندن
    # ------------------------------------------------------------------
    def get(self, symbol: str) -> TickQuote | None:
        """آخرین تیک نماد."""
        return self._quotes.get(str(symbol or "").strip().upper())

    def price(self, symbol: str) -> float:
        """آخرین قیمت؛ صفر یعنی داده‌ای نیست."""
        quote = self.get(symbol)
        return quote.last if quote else 0.0

    def history(self, symbol: str, limit: int = 120) -> list[tuple[float, float]]:
        """(timestamp_ms, price)های اخیر — برای نمودار کوچک."""
        points = self._history.get(str(symbol or "").strip().upper())
        if not points:
            return []
        if limit <= 0 or limit >= len(points):
            return list(points)
        return list(points)[-limit:]

    def is_stale(self, symbol: str, *, now_ms: float | None = None) -> bool:
        """
        آیا دادهٔ نماد کهنه است؟

        نبودِ تیک هم کهنه است — بهتر است صادقانه بگوییم «داده نداریم»
        تا اینکه با آخرین عدد قدیمی معامله بگیریم.
        """
        quote = self.get(symbol)
        if quote is None:
            return True
        # سن داده نسبت به مهر پردازش همان تیک سنجیده می‌شود
        return quote.age_ms > self.stale_after_ms

    def stale_symbols(self, symbols: list[str]) -> list[str]:
        """نمادهای کهنه از میان فهرست داده‌شده."""
        return [s for s in symbols if self.is_stale(s)]

    # ------------------------------------------------------------------
    # شنوندگان
    # ------------------------------------------------------------------
    def add_listener(self, callback: Callable[[TickQuote], None]) -> None:
        """ثبت شنوندهٔ تیک — AutoTrader برای پایش میلی‌ثانیه‌ای."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[TickQuote], None]) -> None:
        """حذف شنونده."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, quote: TickQuote) -> None:
        """پخش فوری — خطای یک شنونده بقیه را نمی‌کشد."""
        for callback in list(self._listeners):
            try:
                callback(quote)
            except Exception:  # noqa: BLE001
                logger.exception("Tick listener failed for %s", quote.symbol)

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        """خلاصهٔ وضعیت برای داشبورد — همهٔ عددها واقعی و اندازه‌گیری‌شده."""
        samples = list(self._latency_samples)
        avg_latency = sum(samples) / len(samples) if samples else None
        worst = max(samples) if samples else None
        last = self._quotes and max(
            self._quotes.values(), key=lambda q: q.processed_ts_ms
        )
        return {
            "symbols": len(self._quotes),
            "ticks": self._tick_count,
            "websocket_ticks": self._ws_tick_count,
            "avg_total_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
            "worst_total_latency_ms": round(worst, 1) if worst is not None else None,
            "last_tick_age_ms": (
                round(max(0.0, _now_ms() - self._last_tick_at_ms), 0)
                if self._last_tick_at_ms
                else None
            ),
            "last_tick_symbol": last.symbol if last else None,
            "stale_after_seconds": self.stale_after_ms / 1000.0,
        }


__all__ = ["MAX_HISTORY_POINTS", "TickEngine", "TickQuote"]
