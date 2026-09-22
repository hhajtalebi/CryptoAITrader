"""
نردبان افق‌های پیش‌بینی (Horizon Ladder) — فاز ۲.

چرا این فایل وجود دارد؟
    خواستهٔ اول کاربر: پیش‌بینی مستقل برای ۱۳ افق زمانی از ۱ دقیقه تا
    ۷ روز. نکتهٔ حیاتی که در متن خواسته صریح آمده: «در صورت نبود دادهٔ
    کافی برای یک تایم‌فریم، آن تایم‌فریم را غیرفعال کن» — یعنی هیچ
    افقی بدون داشتن دادهٔ واقعی روشن نمی‌ماند و دلیلش هم گزارش می‌شود.

    این ماژول فقط «برنامه‌ریز» است: با دیدن اینترنت دادهٔ موجود (کدام
    تایم‌فریم چند کندل دارد) تصمیم می‌گیرد هر افق از کدام تایم‌فریم و با
    چند گام ساخته شود. محاسبهٔ خود پیش‌بینی کار `distribution.py` است.

سیاست انتخاب تایم‌فریم مبدأ برای هر افق:
    بزرگ‌ترین تایم‌فریمی که گامش از افق کوچک‌تر یا مساوی است انتخاب
    می‌شود — چون نمونه‌های مستقل بیشتری می‌دهد و نویز کمتری دارد.
"""

from __future__ import annotations

from dataclasses import dataclass

from market.quality import timeframe_seconds

#: نردبان کامل افق‌ها: (کد، دقیقه) — دقیقاً ۱۳ افق خواستهٔ کاربر.
HORIZON_LADDER: tuple[tuple[str, int], ...] = (
    ("1m", 1),
    ("3m", 3),
    ("5m", 5),
    ("15m", 15),
    ("30m", 30),
    ("1h", 60),
    ("2h", 120),
    ("4h", 240),
    ("6h", 360),
    ("12h", 720),
    ("24h", 1440),
    ("3d", 4320),
    ("7d", 10080),
)

#: نگاشت کد افق → دقیقه، برای استفادهٔ پایین‌دست.
HORIZON_MINUTES: dict[str, int] = dict(HORIZON_LADDER)

#: کمینهٔ کندل‌های اضافی لازم برای گرم‌کردن اندیکاتورها (ATR/بولینگر/…)
#: پیش از اولین پنجرهٔ قابل استفادهٔ افق.
WARMUP_CANDLES = 60

#: کمینهٔ کندل برای حالت تحلیلی (فقط ATR) وقتی نمونهٔ تجربی کافی نیست.
MIN_ANALYTIC_CANDLES = 80


@dataclass(slots=True)
class HorizonPlan:
    """برنامهٔ ساخت پیش‌بینی یک افق."""

    horizon: str
    minutes: int
    source_timeframe: str
    steps: int
    available_candles: int
    enabled: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        """نمایش دیکشنری برای گزارش و آزمون."""
        return {
            "horizon": self.horizon,
            "minutes": self.minutes,
            "source_timeframe": self.source_timeframe,
            "steps": self.steps,
            "available_candles": self.available_candles,
            "enabled": self.enabled,
            "reason": self.reason,
        }


def plan_horizons(available: dict[str, int]) -> list[HorizonPlan]:
    """
    برنامه‌ریزی نردبان افق‌ها بر اساس دادهٔ واقعاً موجود.

    پارامترها:
        available: نگاشت «کد تایم‌فریم → تعداد کندل بسته‌شدهٔ موجود».
                   صفر یا غیبت کلید یعنی آن تایم‌فریم داده ندارد.

    بازگشتی: فهرست ۱۳تایی `HorizonPlan` به ترتیب نردبان — همهٔ افق‌ها
    حاضرند ولی افقِ بی‌داده با `enabled=False` و دلیل صریح.
    """
    # فقط تایم‌فریم‌های با دادهٔ معتبر
    sources = {
        tf: count
        for tf, count in available.items()
        if count and count > 0 and _tf_minutes(tf) is not None
    }

    plans: list[HorizonPlan] = []
    for horizon, minutes in HORIZON_LADDER:
        candidates: list[tuple[int, str, int]] = []  # (گام دقیقه، tf، تعداد)
        for tf, count in sources.items():
            tf_minutes = _tf_minutes(tf)
            if tf_minutes is None or tf_minutes > minutes:
                continue
            steps = -(-minutes // tf_minutes)  # سقف تقسیم
            needed = steps + WARMUP_CANDLES
            if count >= needed:
                candidates.append((tf_minutes, tf, count))
            elif count >= max(MIN_ANALYTIC_CANDLES, steps * 2):
                # برای حالت تحلیلی کافی است ولی کمتر از بهینه
                candidates.append((tf_minutes, tf, count))

        if not candidates:
            # شاید تایم‌فریمی هست ولی خیلی کوتاه/کم‌داده است — دلیل دقیق بده
            reason = "no_source_timeframe"
            for tf, count in sorted(sources.items(), key=lambda kv: _tf_minutes(kv[0]) or 0):
                tf_minutes = _tf_minutes(tf)
                if tf_minutes is not None and tf_minutes <= minutes and count > 0:
                    reason = "insufficient_history"
                    break
            plans.append(
                HorizonPlan(
                    horizon=horizon,
                    minutes=minutes,
                    source_timeframe="",
                    steps=0,
                    available_candles=max(sources.values(), default=0),
                    enabled=False,
                    reason=reason,
                )
            )
            continue

        # بزرگ‌ترین گامِ ممکن = کمترین steps = مستقل‌ترین نمونه‌ها
        tf_minutes, tf, count = max(candidates)
        steps = -(-minutes // tf_minutes)
        # اگر فقط برای حالت تحلیلی کافی بود ولی نه تجربی، باز هم فعال است؛
        # روش نهایی را distribution.py بر اساس نمونه‌ها انتخاب می‌کند.
        plans.append(
            HorizonPlan(
                horizon=horizon,
                minutes=minutes,
                source_timeframe=tf,
                steps=steps,
                available_candles=count,
                enabled=True,
                reason="ok",
            )
        )
    return plans


def _tf_minutes(timeframe: str) -> int | None:
    """دقیقهٔ تایم‌فریم از رجیستری؛ نام ناشناخته None."""
    try:
        return timeframe_seconds(timeframe) // 60
    except Exception:  # noqa: BLE001 - نام نامعتبر نباید برنامه را بشکند
        return None
