"""
دفترچهٔ نتیجهٔ پیش‌بینی‌ها.

چرا این فایل وجود دارد: `score_forecast()` از نسخهٔ ۱.۹.۱۷ ساخته شد ولی
هیچ‌چیز آن را صدا نمی‌زد، یعنی عملاً کدِ مرده بود. بدون اجرای خودکار،
ادعای «بازهٔ ۸۰ درصدی» هرگز اثبات نمی‌شود.

این ماژول پیش‌بینی‌های ذخیره‌شده را با **قیمت واقعیِ همان لحظه** مقایسه
می‌کند و می‌گوید بازه‌ها درست تنظیم شده‌اند یا نه:

    • نرخ اصابت خیلی کمتر از ۸۰٪ ⇒ بازه‌ها تنگ‌اند.
    • نرخ اصابت خیلی بیشتر از ۸۰٪ ⇒ بازه‌ها پهن و بی‌فایده‌اند.

نکتهٔ مهم دربارهٔ صداقت آمار: افقی که زمانش **هنوز نرسیده** شمرده
نمی‌شود. اگر افق‌های نرسیده را «خطا» حساب کنیم آمار بدبینانه می‌شود و
اگر «درست» حساب کنیم خوش‌بینانه — هر دو دروغ است.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from signals.forecast import score_forecast

logger = logging.getLogger(__name__)

#: طول هر افق بر حسب ثانیه، برای تشخیص اینکه زمانش رسیده یا نه
HORIZON_SECONDS: dict[str, int] = {
    "5m": 300,
    "15m": 900,
    "1h": 3_600,
    "4h": 14_400,
    "1d": 86_400,
    "1w": 604_800,
    "1M": 2_592_000,
}

#: نرخ اصابت هدف (بازه‌ها با همین اطمینان ساخته می‌شوند)
TARGET_HIT_RATE = 80.0

#: تا این اندازه انحراف از هدف طبیعی است و نیازی به تغییر نیست
ACCEPTABLE_DRIFT = 12.0

#: کمتر از این تعداد نمونه، نتیجه‌گیری آماری بی‌معناست
MIN_SAMPLES_FOR_VERDICT = 20


@dataclass(slots=True)
class ScorecardRow:
    """نتیجهٔ یک افق زمانی (مثلاً همهٔ پیش‌بینی‌های «۱ ساعته»)."""

    horizon: str
    checked: int = 0
    hits: int = 0
    total_miss: float = 0.0

    @property
    def hit_rate(self) -> float:
        """درصد مواقعی که قیمت واقعی داخل بازه افتاد."""
        return round(self.hits / self.checked * 100, 2) if self.checked else 0.0

    @property
    def average_miss(self) -> float:
        """میانگین فاصله از بازه، فقط برای مواردی که بیرون افتادند."""
        missed = self.checked - self.hits
        return round(self.total_miss / missed, 6) if missed else 0.0

    def as_dict(self) -> dict[str, Any]:
        """شکل آمادهٔ نمایش در جدول."""
        return {
            "horizon": self.horizon,
            "checked": self.checked,
            "hits": self.hits,
            "hit_rate": self.hit_rate,
            "average_miss": self.average_miss,
        }


@dataclass(slots=True)
class ScorecardReport:
    """گزارش کامل، شامل حکم نهایی دربارهٔ تنظیم بازه‌ها."""

    rows: list[ScorecardRow] = field(default_factory=list)
    signals_examined: int = 0
    pending: int = 0

    @property
    def checked(self) -> int:
        """کل افق‌های ارزیابی‌شده."""
        return sum(row.checked for row in self.rows)

    @property
    def hits(self) -> int:
        """کل افق‌هایی که داخل بازه افتادند."""
        return sum(row.hits for row in self.rows)

    @property
    def hit_rate(self) -> float:
        """نرخ اصابت کلی."""
        return round(self.hits / self.checked * 100, 2) if self.checked else 0.0

    @property
    def verdict(self) -> str:
        """
        حکم: `too_narrow`، `too_wide`، `calibrated` یا `insufficient_data`.

        با نمونهٔ کم هیچ حکمی صادر نمی‌شود؛ سه پیش‌بینی چیزی را ثابت
        نمی‌کند و تغییردادن ضریب بر پایهٔ آن، وضع را بدتر می‌کند.
        """
        if self.checked < MIN_SAMPLES_FOR_VERDICT:
            return "insufficient_data"
        drift = self.hit_rate - TARGET_HIT_RATE
        if drift < -ACCEPTABLE_DRIFT:
            return "too_narrow"
        if drift > ACCEPTABLE_DRIFT:
            return "too_wide"
        return "calibrated"

    @property
    def suggested_sigma_shift(self) -> float:
        """
        پیشنهاد تغییر `SIGMA_MULTIPLIER`.

        عمداً محافظه‌کارانه است: حداکثر ±۰٫۲ در هر دور. پرش بزرگ باعث
        نوسانِ بیش‌ازحدِ تنظیم می‌شود.
        """
        if self.verdict == "too_narrow":
            return round(min(0.2, (TARGET_HIT_RATE - self.hit_rate) / 100), 3)
        if self.verdict == "too_wide":
            return round(-min(0.2, (self.hit_rate - TARGET_HIT_RATE) / 100), 3)
        return 0.0

    def as_dict(self) -> dict[str, Any]:
        """شکل آمادهٔ نمایش و ذخیره."""
        return {
            "rows": [row.as_dict() for row in self.rows],
            "signals_examined": self.signals_examined,
            "pending": self.pending,
            "checked": self.checked,
            "hits": self.hits,
            "hit_rate": self.hit_rate,
            "target_rate": TARGET_HIT_RATE,
            "verdict": self.verdict,
            "suggested_sigma_shift": self.suggested_sigma_shift,
        }


def horizon_is_due(created_at: datetime, horizon: str, *, now: datetime | None = None) -> bool:
    """
    آیا زمان یک افق رسیده است؟

    پیش‌بینیِ «۴ ساعته» که ۱۰ دقیقه پیش ساخته شده هنوز قابل قضاوت نیست.
    """
    seconds = HORIZON_SECONDS.get(horizon)
    if not seconds:
        return False
    moment = now or datetime.now(UTC)
    reference = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    return moment >= reference + timedelta(seconds=seconds)


def build_report(
    signals: list[dict[str, Any]],
    price_lookup: dict[tuple[str, str], float],
    *,
    now: datetime | None = None,
) -> ScorecardReport:
    """
    ساخت گزارش از سیگنال‌های ذخیره‌شده.

    پارامترها:
        signals: هر آیتم شامل `symbol`، `created_at` و `forecast`
            (خروجی `HorizonForecast.as_dict()`).
        price_lookup: نگاشت `(نماد، افق)` به قیمت واقعیِ آن لحظه.
        now: زمان مرجع، برای آزمون‌پذیری.

    بازگشتی: `ScorecardReport`.
    """
    moment = now or datetime.now(UTC)
    buckets: dict[str, ScorecardRow] = {}
    report = ScorecardReport()

    for signal in signals:
        horizons = signal.get("forecast") or []
        if not isinstance(horizons, list) or not horizons:
            continue

        symbol = str(signal.get("symbol") or "")
        created = signal.get("created_at")
        if not symbol or not isinstance(created, datetime):
            continue

        report.signals_examined += 1

        # فقط افق‌هایی که هم زمانشان رسیده و هم قیمت واقعی داریم
        actual: dict[str, float] = {}
        for item in horizons:
            if not isinstance(item, dict):
                continue
            horizon = str(item.get("horizon", ""))
            if not horizon:
                continue
            if not horizon_is_due(created, horizon, now=moment):
                report.pending += 1
                continue
            price = price_lookup.get((symbol, horizon))
            if price is None or float(price) <= 0:
                report.pending += 1
                continue
            actual[horizon] = float(price)

        if not actual:
            continue

        scored = score_forecast(horizons, actual)
        for detail in scored.get("details", []):  # type: ignore[union-attr]
            horizon = str(detail.get("horizon", ""))
            row = buckets.setdefault(horizon, ScorecardRow(horizon=horizon))
            row.checked += 1
            if detail.get("inside"):
                row.hits += 1
            else:
                row.total_miss += float(detail.get("miss", 0.0) or 0.0)

    # ترتیب ثابت و قابل پیش‌بینی برای جدول
    order = list(HORIZON_SECONDS)
    report.rows = sorted(
        buckets.values(),
        key=lambda row: order.index(row.horizon) if row.horizon in order else 99,
    )
    logger.info(
        "Forecast scorecard: %d checked, %.1f%% hit rate, verdict=%s",
        report.checked, report.hit_rate, report.verdict,
    )
    return report
