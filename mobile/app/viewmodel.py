"""
منطق نمایش (بدون Kivy) — قالب‌بندی عددها، مرتب‌سازی، فیلتر.

هر چیزی که «تصمیم» است اینجاست تا آزمون‌پذیر باشد؛ فایل‌های رابط فقط
رسم می‌کنند.
"""

from __future__ import annotations

SORTS = ("volume", "gainers", "losers")

# حجم دلاری ۲۴ ساعته کمتر از این ← نماد مرده؛ تحلیل تکنیکالش معنا ندارد.
MIN_SCAN_TURNOVER = 100_000


def format_price(value: float) -> str:
    """تعداد اعشار متناسب با بزرگی قیمت (۶۵٬۴۳۲٫۱ و ۰٫۰۰۰۰۱۲۳۴ هر دو خوانا)."""
    if value is None or value != value or value <= 0:  # noqa: PLR0124 — NaN
        return "—"
    if value >= 1000:
        return f"{value:,.1f}"
    if value >= 1:
        return f"{value:,.3f}".rstrip("0").rstrip(".") if value < 100 else f"{value:,.2f}"
    digits = 4
    probe = value
    while probe < 0.1 and digits < 10:
        probe *= 10
        digits += 1
    return f"{value:.{digits}f}"


def format_change(change: float) -> str:
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.2f}%"


def format_volume(turnover: float) -> str:
    """حجم دلاری کوتاه: 1.2B ، 34.5M ، 870K."""
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if turnover >= size:
            return f"{turnover / size:.1f}{unit}"
    return f"{turnover:.0f}"


def trend_of(change: float) -> str:
    """up | down | flat — رنگ ردیف از همین می‌آید."""
    if change > 0.05:
        return "up"
    if change < -0.05:
        return "down"
    return "flat"


def filter_and_sort(rows: list[dict], query: str = "", sort: str = "volume", limit: int = 100) -> list[dict]:
    """
    جست‌وجو + مرتب‌سازی فهرست بازار.

    برای «بیشترین رشد/ریزش» جفت‌های کم‌حجم کنار گذاشته می‌شوند: یک توکن
    مرده با ۲۰۰٪ رشد روی ۵۰ دلار حجم، اطلاعات نیست، نویز است.
    """
    q = query.strip().upper().replace("/", "")
    items = [r for r in rows if not q or q in r["base"] or q in r["symbol"].replace("/", "")]
    if sort == "gainers":
        items = [r for r in items if r["turnover"] >= 100_000]
        items.sort(key=lambda r: r["change"], reverse=True)
    elif sort == "losers":
        items = [r for r in items if r["turnover"] >= 100_000]
        items.sort(key=lambda r: r["change"])
    else:
        items.sort(key=lambda r: r["turnover"], reverse=True)
    return items[:limit]


def market_breadth(rows: list[dict]) -> dict:
    """خلاصهٔ بالای صفحهٔ بازار: چند نماد مثبت/منفی و میانگین تغییر (وزن حجم)."""
    liquid = [r for r in rows if r["turnover"] >= 100_000]
    if not liquid:
        return {"up": 0, "down": 0, "avg": 0.0, "count": 0}
    total = sum(r["turnover"] for r in liquid)
    avg = sum(r["change"] * r["turnover"] for r in liquid) / total if total else 0.0
    return {
        "up": sum(1 for r in liquid if r["change"] > 0),
        "down": sum(1 for r in liquid if r["change"] < 0),
        "avg": avg,
        "count": len(liquid),
    }


def scan_universe(rows: list[dict], size: int) -> list[str]:
    """نمادهای پویش: پرحجم‌ترین‌ها (نقدشوندگی = سیگنال قابل‌اتکاتر)."""
    liquid = [r for r in rows if r["turnover"] >= MIN_SCAN_TURNOVER]
    return [r["symbol"] for r in filter_and_sort(liquid, sort="volume", limit=size)]


def sort_signals(signals: list, tradeable_only: bool = False) -> list:
    items = [s for s in signals if s.is_tradeable] if tradeable_only else list(signals)
    items.sort(key=lambda s: (s.is_tradeable, s.confidence), reverse=True)
    return items


def direction_label(direction: str) -> str:
    return {"LONG": "خرید", "SHORT": "فروش", "WAIT": "منتظر"}.get(direction, direction)


def confidence_level(confidence: float) -> str:
    if confidence >= 70:
        return "قوی"
    if confidence >= 45:
        return "متوسط"
    return "ضعیف"


def percent_from(entry: float, level: float) -> str:
    """فاصلهٔ درصدی یک سطح از ورود — روی گوشی از عدد خام خواناتر است."""
    if not entry:
        return ""
    return format_change((level - entry) / entry * 100.0)


def sparkline_points(values: list[float], width: float, height: float, pad: float = 0.0) -> list[float]:
    """مختصات خط نمودار (x0,y0,x1,y1,…) داخل کادر."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2 or width <= 0 or height <= 0:
        return []
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    step = (width - 2 * pad) / (len(vals) - 1)
    pts: list[float] = []
    for i, v in enumerate(vals):
        pts += [pad + i * step, pad + (v - lo) / span * (height - 2 * pad)]
    return pts


def indicator_snapshot(highs: list[float], lows: list[float], closes: list[float]) -> dict:
    """
    کاشی‌های صفحهٔ تحلیل: RSI، مکدی، نوسان (ATR٪)، روند — هر کدام با برچسب
    و لحن (up/down/flat) تا رنگ کاشی معنا داشته باشد.
    """
    from . import indicators_lite as ind  # noqa: PLC0415

    out: dict = {"ema20": ind.ema(closes, 20) if closes else []}
    price = closes[-1] if closes else 0.0

    r = ind.rsi(closes, 14)[-1] if len(closes) > 15 else None
    if r is None:
        out["rsi"] = ("—", "flat", "")
    else:
        note = "اشباع فروش" if r < 30 else "اشباع خرید" if r > 70 else "خنثی"
        out["rsi"] = (f"{r:.0f}", "up" if r < 30 else "down" if r > 70 else "flat", note)

    h = ind.macd(closes)["histogram"][-1] if len(closes) > 35 else None
    if h is None:
        out["macd"] = ("—", "flat", "")
    else:
        out["macd"] = ("مثبت" if h > 0 else "منفی", "up" if h > 0 else "down", f"{h:.4g}")

    a = ind.atr(highs, lows, closes, 14)[-1] if len(closes) > 15 else None
    if a is None or not price:
        out["atr"] = ("—", "flat", "")
    else:
        pct = a / price * 100
        out["atr"] = (f"{pct:.2f}%", "flat", "زیاد" if pct > 3 else "کم" if pct < 0.7 else "معمولی")

    f, s = (ind.ema(closes, 20)[-1], ind.ema(closes, 50)[-1]) if len(closes) >= 50 else (None, None)
    if f is None or s is None:
        out["trend"] = ("—", "flat", "")
    else:
        gap = (f - s) / s * 100 if s else 0.0
        out["trend"] = ("صعودی" if f > s else "نزولی", "up" if f > s else "down", f"{gap:+.2f}%")
    return out
