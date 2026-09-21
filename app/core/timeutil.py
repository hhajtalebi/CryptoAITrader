"""
کار با زمان و منطقه زمانی.

قاعده‌ای که در سراسر برنامه رعایت می‌شود:

    ذخیره‌سازی همیشه UTC  ←→  نمایش همیشه وقت محلی کاربر

دلیل: داده بازار از صرافی با مهر زمانی UTC می‌آید و اگر همان‌طور ذخیره
نشود، با تغییر ساعت تابستانی یا جابه‌جایی کاربر، سابقه سیگنال‌ها به‌هم
می‌ریزد. اما نمایش UTC به کاربر ایرانی یعنی ساعت‌ها اختلاف با ساعت
دیواری او — که دقیقاً همان اشکالی بود که گزارش شد.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.logging import get_logger

logger = get_logger(__name__)

#: قالب پیش‌فرض نمایش تاریخ و ساعت
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
TIME_FORMAT = "%H:%M:%S"

#: منطقه زمانی دستی‌شده توسط کاربر (اگر تنظیم شود بر منطقه سیستم مقدم است)
_override_timezone: tzinfo | None = None


def set_display_timezone(name: str | None) -> tzinfo:
    """
    تعیین منطقه زمانی نمایش.

    اگر `name` خالی یا نامعتبر باشد، به منطقه زمانی سیستم برمی‌گردیم؛
    منطقه زمانی نامعتبر نباید برنامه را بخواباند.
    """
    global _override_timezone
    if not name or name.lower() in ("system", "auto", "local"):
        _override_timezone = None
        return local_timezone()
    try:
        _override_timezone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unknown timezone '%s'; falling back to system timezone", name)
        _override_timezone = None
    return local_timezone()


def local_timezone() -> tzinfo:
    """منطقه زمانی جاری برای نمایش."""
    if _override_timezone is not None:
        return _override_timezone
    # astimezone() بدون آرگومان، منطقه زمانی پیکربندی‌شده سیستم را می‌دهد
    return datetime.now().astimezone().tzinfo or UTC


def now_utc() -> datetime:
    """اکنون به وقت UTC — برای ذخیره‌سازی."""
    return datetime.now(UTC)


def now_local() -> datetime:
    """اکنون به وقت محلی — برای نمایش."""
    return datetime.now(local_timezone())


def to_local(moment: datetime | None) -> datetime | None:
    """
    تبدیل یک زمان به وقت محلی.

    زمان‌های بدون منطقه (naive) که از پایگاه داده می‌آیند، UTC فرض
    می‌شوند؛ همه نوشتن‌های برنامه با UTC انجام شده است.
    """
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(local_timezone())


def format_datetime(moment: datetime | None, fmt: str = DATETIME_FORMAT) -> str:
    """قالب‌بندی زمان به وقت محلی."""
    localised = to_local(moment)
    return localised.strftime(fmt) if localised else "—"


def format_time(moment: datetime | None = None) -> str:
    """قالب‌بندی ساعت به وقت محلی."""
    return format_datetime(moment or now_utc(), TIME_FORMAT)


def format_timestamp(timestamp: int | float | None, fmt: str = DATETIME_FORMAT) -> str:
    """قالب‌بندی مهر زمانی یونیکس (ثانیه) به وقت محلی."""
    if timestamp is None:
        return "—"
    try:
        return datetime.fromtimestamp(float(timestamp), UTC).astimezone(local_timezone()).strftime(fmt)
    except (ValueError, OSError, OverflowError):
        return "—"


def utc_offset_label() -> str:
    """
    برچسب اختلاف با UTC، مثل `UTC+03:30`.

    برای نمایش در نوار وضعیت تا کاربر بداند ساعت‌ها بر چه پایه‌ای است.
    """
    offset = now_local().utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def timezone_name() -> str:
    """نام منطقه زمانی جاری."""
    if _override_timezone is not None:
        return str(_override_timezone)
    return now_local().tzname() or "local"


def relative_label(moment: datetime | None) -> str:
    """
    فاصله زمانی خوانا نسبت به اکنون، مثل «۲ دقیقه پیش».

    برای نشان دادن تازگی داده در جدول‌ها استفاده می‌شود.
    """
    if moment is None:
        return "—"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    seconds = (now_utc() - moment).total_seconds()
    if seconds < 0:
        return "now"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"
