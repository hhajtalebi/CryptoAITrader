"""
موتور کیفیت داده (Data Quality Engine).

چرا این فایل وجود دارد؟
    قانون حیاتی شماره ۲ پروژه می‌گوید «هیچ داده‌ای جعل نشود». مکمل ضروری
    همین قانون این است که دادهٔ **خراب** هم به مدل‌ها راه پیدا نکند:
    یک کندل با سقف کمتر از کف، یا یک ردیف تکراری، می‌تواند فیچرها و در
    نتیجه همهٔ پیش‌بینی‌های پایین‌دستی را بی‌صدا مسموم کند.

    این ماژول «دروازهٔ ورود داده به مدل» است:
        • بازرسی کامل: ردیف تکراری، شکاف زمانی، بی‌ترتیبی، عدم تراز با
          شبکهٔ تایم‌فریم، مهر زمانی آینده، OHLC نامعتبر، قیمت/حجم منفی،
          جهش مشکوک.
        • پاک‌سازی محافظه‌کار: فقط ردیف‌های «به‌صراحت نامعتبر» حذف
          می‌شوند. ردیف‌های مشکوک نگه داشته می‌شوند ولی هشدار می‌گیرند.
        • شکاف هرگز با کندل ساختگی پر نمی‌شود — جعل داده ممنوع است.

ارتباط با ماژول‌های دیگر:
    بالادست : CandleRepository و providerها (دادهٔ خام)
    پایین‌دست: signals/prediction/features.py و موتورهای پیش‌بینی
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.models import Candle
from app.logging import get_logger

logger = get_logger(__name__)


class IssueKind(str, Enum):
    """نوع مشکل کیفیت داده."""

    EMPTY = "empty"                      # هیچ داده‌ای نرسیده
    DUPLICATE = "duplicate"              # مهر زمانی تکراری
    GAP = "gap"                          # کندل گم‌شده در توالی زمانی
    UNORDERED = "unordered"              # ترتیب زمانی نادرست
    MISALIGNED = "misaligned"            # عدم تراز با شبکهٔ تایم‌فریم
    FUTURE_TIMESTAMP = "future"          # کندلی که هنوز باز نشده
    INVALID_OHLC = "invalid_ohlc"        # سقف/کف با بدنهٔ کندل ناسازگار
    NON_POSITIVE_PRICE = "bad_price"     # قیمت صفر یا منفی
    NEGATIVE_VOLUME = "bad_volume"       # حجم منفی
    SUSPICIOUS_SPIKE = "spike"           # جهش غیرعادی ولی ممکن


class Severity(str, Enum):
    """شدت مشکل؛ فقط CRITICAL باعث حذف ردیف در پاک‌سازی می‌شود."""

    WARNING = "warning"
    CRITICAL = "critical"


#: آستانهٔ جهش مشکوک: بازدهٔ درون‌کندلی بزرگ‌تر از این کسر، هشدار می‌گیرد
#: ولی حذف نمی‌شود — چون در کریپتو سقوط‌های ۵۰٪+ واقعاً اتفاق افتاده‌اند
#: و حذف آن‌ها یعنی پنهان‌کردن واقعیت بازار از مدل.
SPIKE_RETURN_THRESHOLD = 0.50

#: نسبت ردیف‌های سالم به کل که پایین‌تر از آن، داده برای مدل قابل
#: اتکا تلقی نمی‌شود (در گزارش `usable` می‌آید).
MIN_VALID_RATIO = 0.80

#: تلورانس کجی ساعت بین سرور صرافی و سیستم کاربر. کندلی که حداکثر
#: این‌قدر «در آینده» باشد، خطای ساعت فرض می‌شود نه دادهٔ جعلی.
CLOCK_SKEW_TOLERANCE = 60


@dataclass(slots=True)
class QualityIssue:
    """یک مشکل کشف‌شده در داده."""

    kind: IssueKind
    severity: Severity
    detail: str
    timestamp: int | None = None
    index: int | None = None


@dataclass(slots=True)
class QualityReport:
    """
    گزارش کیفیت یک سری کندل.

    چرا dataclass و نه dict؟ تا قرارداد خروجی برای همهٔ فراخوان‌ها (UI،
    عامل AI، آزمون‌ها) یکسان و type-safe بماند.
    """

    symbol: str = ""
    timeframe: str = ""
    checked: int = 0
    issues: list[QualityIssue] = field(default_factory=list)
    duplicates: int = 0
    missing: int = 0
    invalid: int = 0
    future: int = 0
    suspicious: int = 0
    misaligned: int = 0
    unordered: bool = False
    gap_ranges: list[dict[str, int]] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """آیا این داده قابل ورود به مدل است؟"""
        if self.checked == 0:
            return False
        bad = self.invalid + self.future
        return bad / self.checked <= (1.0 - MIN_VALID_RATIO)

    def counts_by_severity(self) -> dict[str, int]:
        """تعداد مسئله به تفکیک شدت — برای نمایش خلاصه در UI."""
        result = {"warning": 0, "critical": 0}
        for issue in self.issues:
            result[issue.severity.value] = result.get(issue.severity.value, 0) + 1
        return result

    def to_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری برای لاگ، Prompt عامل AI و آزمون‌ها."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "checked": self.checked,
            "usable": self.usable,
            "duplicates": self.duplicates,
            "missing": self.missing,
            "invalid": self.invalid,
            "future": self.future,
            "suspicious": self.suspicious,
            "misaligned": self.misaligned,
            "unordered": self.unordered,
            "gap_ranges": list(self.gap_ranges),
            "issues": [
                {
                    "kind": i.kind.value,
                    "severity": i.severity.value,
                    "detail": i.detail,
                    "timestamp": i.timestamp,
                    "index": i.index,
                }
                for i in self.issues
            ],
        }


def timeframe_seconds(timeframe: str) -> int:
    """
    طول تایم‌فریم بر حسب ثانیه از رجیستری تایم‌فریم‌ها.

    چرا از اینجا می‌آید و نه محاسبهٔ محلی؟ تا فقط یک منبع حقیقت برای
    نگاشت «نام تایم‌فریم → ثانیه» وجود داشته باشد (DRY).
    """
    from market.timeframes import TIMEFRAME_MAP  # noqa: PLC0415 - جلوگیری از import چرخشی

    frame = TIMEFRAME_MAP.get(timeframe)
    if frame is None:
        from app.exceptions import TimeframeError  # noqa: PLC0415

        raise TimeframeError(
            f"Unknown timeframe for quality check: {timeframe!r}",
            details={"timeframe": timeframe},
        )
    return frame.seconds


def _row_is_invalid(candle: Candle) -> str | None:
    """
    بررسی اعتبار سختِ یک ردیف.

    بازگشتی: کد مشکل یا None. فقط موارد «ریاضیاتاً ناممکن» اینجا هستند؛
    هر چیز دیگری حدس‌زدنی است و حق تصمیم با مدل/کاربر است.
    """
    if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
        return "bad_price"
    if candle.volume < 0:
        return "bad_volume"
    body_top = max(candle.open, candle.close)
    body_bottom = min(candle.open, candle.close)
    if candle.high < body_top or candle.low > body_bottom or candle.high < candle.low:
        return "invalid_ohlc"
    return None


def inspect_candles(
    candles: list[Candle],
    timeframe: str,
    *,
    symbol: str = "",
    now: int | None = None,
) -> QualityReport:
    """
    بازرسی کامل کیفیت یک سری کندل — بدون تغییر داده.

    پارامترها:
        candles   : کندل‌ها به ترتیب ورودی (لازم نیست مرتب باشند).
        timeframe : کد تایم‌فریم مثل "15m" — برای شبکهٔ زمانی و شکاف‌ها.
        symbol    : فقط برای گزارش.
        now       : زمان مرجع (ثانیهٔ UTC). اگر داده باشد، کندل‌هایی که
                    هنوز باز نشده‌اند «آینده» علامت می‌خورند.

    بازگشتی: QualityReport. این تابع داده را اصلاح نمی‌کند؛ اصلاح کار
    `clean_candles` است تا تصمیم «چه چیزی حذف شود» شفاف و قابل آزمون بماند.
    """
    step = timeframe_seconds(timeframe)
    report = QualityReport(symbol=symbol, timeframe=timeframe, checked=len(candles))

    if not candles:
        report.issues.append(
            QualityIssue(IssueKind.EMPTY, Severity.CRITICAL, "no candles received")
        )
        return report

    seen: dict[int, int] = {}
    for index, candle in enumerate(candles):
        problem = _row_is_invalid(candle)
        if problem == "bad_price":
            report.invalid += 1
            report.issues.append(
                QualityIssue(
                    IssueKind.NON_POSITIVE_PRICE, Severity.CRITICAL,
                    "non-positive price", candle.timestamp, index,
                )
            )
        elif problem == "bad_volume":
            report.invalid += 1
            report.issues.append(
                QualityIssue(
                    IssueKind.NEGATIVE_VOLUME, Severity.CRITICAL,
                    "negative volume", candle.timestamp, index,
                )
            )
        elif problem == "invalid_ohlc":
            report.invalid += 1
            report.issues.append(
                QualityIssue(
                    IssueKind.INVALID_OHLC, Severity.CRITICAL,
                    "high/low inconsistent with body", candle.timestamp, index,
                )
            )

        if candle.timestamp in seen:
            report.duplicates += 1
            report.issues.append(
                QualityIssue(
                    IssueKind.DUPLICATE, Severity.WARNING,
                    "duplicate timestamp (last occurrence kept)",
                    candle.timestamp, index,
                )
            )
        seen[candle.timestamp] = index

        if candle.timestamp % step != 0:
            report.misaligned += 1
            report.issues.append(
                QualityIssue(
                    IssueKind.MISALIGNED, Severity.WARNING,
                    "timestamp not aligned to timeframe grid",
                    candle.timestamp, index,
                )
            )

        if now is not None and candle.timestamp > now + CLOCK_SKEW_TOLERANCE:
            report.future += 1
            report.issues.append(
                QualityIssue(
                    IssueKind.FUTURE_TIMESTAMP, Severity.CRITICAL,
                    "candle opens in the future", candle.timestamp, index,
                )
            )

        body_return = abs(candle.close / candle.open - 1.0) if candle.open > 0 else 0.0
        if problem is None and body_return > SPIKE_RETURN_THRESHOLD:
            report.suspicious += 1
            report.issues.append(
                QualityIssue(
                    IssueKind.SUSPICIOUS_SPIKE, Severity.WARNING,
                    f"intra-candle move {body_return:.0%} exceeds threshold (kept, not removed)",
                    candle.timestamp, index,
                )
            )

    # شکاف‌ها و ترتیب روی مهرهای زمانی یکتا بررسی می‌شوند.
    unique_times = sorted(seen)
    if unique_times != [c.timestamp for c in candles]:
        report.unordered = True
        report.issues.append(
            QualityIssue(
                IssueKind.UNORDERED, Severity.WARNING,
                "candles not in chronological order (will be sorted)",
            )
        )

    for previous, current in zip(unique_times[:-1], unique_times[1:], strict=False):
        slots = (current - previous) // step - 1
        if slots > 0:
            report.missing += int(slots)
            report.gap_ranges.append(
                {
                    "after": previous,
                    "before": current,
                    "missing": int(slots),
                }
            )
            report.issues.append(
                QualityIssue(
                    IssueKind.GAP, Severity.WARNING,
                    f"{slots} candle(s) missing between {previous} and {current}",
                    previous,
                )
            )

    return report


def clean_candles(
    candles: list[Candle],
    timeframe: str,
    *,
    symbol: str = "",
    now: int | None = None,
) -> tuple[list[Candle], QualityReport]:
    """
    حذف ردیف‌های به‌صراحت نامعتبر + مرتب‌سازی + حذف تکراری‌ها.

    سیاست:
        • حذف: OHLC نامعتبر، قیمت/حجم منفی، کندل آینده، تکراری (آخرین
          نسخه نگه داشته می‌شود چون جدیدترین نوشتن است).
        • حفظ: شکاف‌ها (فقط گزارش)، جهش‌های مشکوک، عدم تراز (هشدار).
        • شکاف هرگز با کندل ساختگی پر نمی‌شود — قانون «جعل داده ممنوع».

    بازگشتی: (کندل‌های پاک مرتب از قدیم به جدید، گزارش کیفیت ورودی).
    """
    report = inspect_candles(candles, timeframe, symbol=symbol, now=now)

    if not candles:
        return [], report

    horizon_limit = (now + CLOCK_SKEW_TOLERANCE) if now is not None else None
    cleaned_by_time: dict[int, Candle] = {}
    for candle in candles:
        if _row_is_invalid(candle) is not None:
            continue
        if horizon_limit is not None and candle.timestamp > horizon_limit:
            continue
        # تکراری: آخرین رخورد بازنویسی می‌کند (نگاشت dict به همان ترتیب).
        cleaned_by_time[candle.timestamp] = candle

    return [cleaned_by_time[t] for t in sorted(cleaned_by_time)], report
