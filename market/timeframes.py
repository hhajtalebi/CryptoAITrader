"""
موتور تایم‌فریم (Timeframe Engine).

چرا وجود دارد؟
    صرافی‌ها همه تایم‌فریم‌ها را ارائه نمی‌دهند. برای مثال LBank تایم‌فریم‌های
    ۳ دقیقه، ۲ ساعت، ۶ ساعت، ۸ ساعت و ۱۲ ساعت را پشتیبانی نمی‌کند (این
    موضوع با آزمایش مستقیم API تأیید شده است). این ماژول تایم‌فریم‌های
    گم‌شده را از روی داده پایه «تجمیع» (Aggregate) می‌کند.

ارتباط با ماژول‌های دیگر:
    providers از این ماژول برای نگاشت نام تایم‌فریم استفاده می‌کنند و
    MarketDataEngine برای ساخت تایم‌فریم‌های مصنوعی.
"""

from __future__ import annotations

from datetime import UTC, datetime

from dataclasses import dataclass

from app.core.models import Candle
from app.exceptions import TimeframeError
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Timeframe:
    """
    توصیف یک تایم‌فریم استاندارد.

    code    : شناسه داخلی یکتا، مثل "4h"
    seconds : طول بازه بر حسب ثانیه
    label   : برچسب نمایشی
    """

    code: str
    seconds: int
    label: str

    @property
    def minutes(self) -> int:
        """طول تایم‌فریم بر حسب دقیقه."""
        return self.seconds // 60


# فهرست کامل تایم‌فریم‌های پشتیبانی‌شده توسط نرم‌افزار
SUPPORTED_TIMEFRAMES: tuple[Timeframe, ...] = (
    Timeframe("1m", 60, "1 Minute"),
    Timeframe("3m", 180, "3 Minutes"),
    Timeframe("5m", 300, "5 Minutes"),
    Timeframe("15m", 900, "15 Minutes"),
    Timeframe("30m", 1800, "30 Minutes"),
    Timeframe("1h", 3600, "1 Hour"),
    Timeframe("2h", 7200, "2 Hours"),
    Timeframe("4h", 14400, "4 Hours"),
    Timeframe("6h", 21600, "6 Hours"),
    Timeframe("8h", 28800, "8 Hours"),
    Timeframe("12h", 43200, "12 Hours"),
    Timeframe("1d", 86400, "1 Day"),
    Timeframe("1w", 604800, "1 Week"),
    # ماهانه: طول ثابت ۳۰ روزه فقط برای مرتب‌سازی و تخمین است؛ هم‌ترازی
    # واقعی ماه در align_timestamp با تقویم انجام می‌شود چون ماه‌ها
    # ۲۸ تا ۳۱ روزند.
    Timeframe("1M", 2592000, "1 Month"),
)

TIMEFRAME_MAP: dict[str, Timeframe] = {tf.code: tf for tf in SUPPORTED_TIMEFRAMES}


def get_timeframe(code: str) -> Timeframe:
    """
    دریافت شیء تایم‌فریم از روی کد آن.

    در صورت نامعتبر بودن کد، خطای TimeframeError پرتاب می‌شود تا داده
    نادرست وارد زنجیره تحلیل نشود.
    """
    # حساس به حروف بزرگ و کوچک: «1M» ماهانه است ولی «1m» یک‌دقیقه‌ای.
    # پس اول تطبیق دقیق را امتحان می‌کنیم و تنها در صورت نبود، به حالت
    # بی‌تفاوت به حروف برمی‌گردیم تا ورودی‌هایی مثل «1H» هم پذیرفته شود.
    stripped = code.strip()
    timeframe = TIMEFRAME_MAP.get(stripped)
    if timeframe is None:
        timeframe = TIMEFRAME_MAP.get(stripped.lower())
    if timeframe is None:
        raise TimeframeError(
            f"Unsupported timeframe: {code}",
            details={"supported": list(TIMEFRAME_MAP)},
        )
    return timeframe


def normalize_timeframe(code: str) -> str:
    """
    یکدست‌سازی کد تایم‌فریم به شکل رسمی آن.

    این تابع نگهبان یک اشتباه ظریف است: «1M» (ماهانه) و «1m» (یک‌دقیقه‌ای)
    تنها در بزرگی حرف فرق دارند. هرجای برنامه که قبلاً `code.lower()`
    می‌نوشت، ماهانه را بی‌صدا به یک‌دقیقه‌ای تبدیل می‌کرد — یعنی کاربر
    نمودار ماهانه می‌خواست و کندل یک‌دقیقه‌ای می‌گرفت.

    مثال:
        normalize_timeframe(" 1M ") == "1M"
        normalize_timeframe("1H")   == "1h"
    """
    return get_timeframe(code).code


def timeframe_seconds(code: str) -> int:
    """طول یک تایم‌فریم بر حسب ثانیه."""
    return get_timeframe(code).seconds


def align_timestamp(timestamp: int, code: str) -> int:
    """
    هم‌ترازسازی یک زمان با ابتدای بازه تایم‌فریم.

    مثال: زمان 10:07 در تایم‌فریم ۱۵ دقیقه به 10:00 نگاشت می‌شود.

    برای تایم‌فریم هفتگی، شروع هفته «دوشنبه ۰۰:۰۰ UTC» در نظر گرفته می‌شود
    (قرارداد ISO-8601). چون مبدأ زمان یونیکس پنجشنبه بوده، ۳ روز افست لازم
    است. توجه: کندل هفتگی خودِ LBank با قرارداد دیگری شروع می‌شود؛ به همین
    دلیل هروقت صرافی تایم‌فریم هفتگی را مستقیماً بدهد، از داده خودش استفاده
    می‌کنیم و این تابع فقط برای تجمیع داخلی به کار می‌رود.
    """
    seconds = timeframe_seconds(code)
    if code == "1M":
        # ماه طول ثابت ندارد؛ تقسیم عددی جواب نمی‌دهد و باید با تقویم
        # به ابتدای ماه میلادی برویم.
        moment = datetime.fromtimestamp(timestamp, UTC)
        start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return int(start.timestamp())
    if code == "1w":
        offset = 3 * 86400  # جبران اختلاف پنجشنبه (مبدأ یونیکس) تا دوشنبه
        return ((timestamp + offset) // seconds) * seconds - offset
    return (timestamp // seconds) * seconds


def aggregate_candles(candles: list[Candle], source_code: str, target_code: str) -> list[Candle]:
    """
    ساخت کندل‌های تایم‌فریم بزرگ‌تر از روی کندل‌های تایم‌فریم کوچک‌تر.

    قواعد تجمیع:
        open   : قیمت باز شدن اولین کندل بازه
        high   : بیشترین سقف بازه
        low    : کمترین کف بازه
        close  : قیمت بسته شدن آخرین کندل بازه
        volume : مجموع حجم‌ها

    محدودیت‌ها:
        • تایم‌فریم مقصد باید مضرب صحیحی از تایم‌فریم مبدأ باشد.
        • آخرین بازه ممکن است ناقص باشد؛ همچنان تولید می‌شود ولی مصرف‌کننده
          باید بداند که «کندل در حال شکل‌گیری» است.
    """
    if not candles:
        return []

    source_seconds = timeframe_seconds(source_code)
    target_seconds = timeframe_seconds(target_code)

    if target_seconds < source_seconds:
        raise TimeframeError(
            f"Cannot aggregate from {source_code} to a smaller timeframe {target_code}",
            details={"source": source_code, "target": target_code},
        )
    if target_seconds == source_seconds:
        return list(candles)
    if target_seconds % source_seconds != 0:
        raise TimeframeError(
            f"Timeframe {target_code} is not an exact multiple of {source_code}",
            details={"source_seconds": source_seconds, "target_seconds": target_seconds},
        )

    ordered = sorted(candles, key=lambda c: c.timestamp)
    buckets: dict[int, list[Candle]] = {}
    for candle in ordered:
        bucket_start = align_timestamp(candle.timestamp, target_code)
        buckets.setdefault(bucket_start, []).append(candle)

    aggregated: list[Candle] = []
    for bucket_start in sorted(buckets):
        group = buckets[bucket_start]
        aggregated.append(
            Candle(
                timestamp=bucket_start,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            )
        )
    logger.debug(
        "Aggregated %d %s candles into %d %s candles", len(ordered), source_code, len(aggregated), target_code
    )
    return aggregated


def find_aggregation_source(target_code: str, available_codes: set[str]) -> str | None:
    """
    یافتن بهترین تایم‌فریم مبدأ برای ساخت یک تایم‌فریم پشتیبانی‌نشده.

    راهبرد: بزرگ‌ترین تایم‌فریم موجود که مقسوم‌علیه دقیق تایم‌فریم مقصد
    باشد انتخاب می‌شود؛ چون هرچه مبدأ بزرگ‌تر باشد، تعداد کندل کمتری لازم
    است و فشار روی API کمتر می‌شود.
    """
    if target_code == "1M":
        # ماه مضرب دقیق هیچ تایم‌فریم کوچک‌تری نیست (۲۸ تا ۳۱ روز)، پس
        # تجمیع عددی معنا ندارد و باید از داده بومی صرافی استفاده شود.
        return None

    target_seconds = timeframe_seconds(target_code)
    candidates = [
        code
        for code in available_codes
        if code in TIMEFRAME_MAP
        and TIMEFRAME_MAP[code].seconds < target_seconds
        and target_seconds % TIMEFRAME_MAP[code].seconds == 0
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda code: TIMEFRAME_MAP[code].seconds)


def candles_needed(target_code: str, source_code: str, target_count: int) -> int:
    """
    تعداد کندل مبدأ لازم برای ساخت تعداد مشخصی کندل مقصد.

    مقداری حاشیه اطمینان (یک بازه اضافه) در نظر گرفته می‌شود تا کندل ناقص
    ابتدای بازه، نتیجه را ناقص نکند.
    """
    ratio = timeframe_seconds(target_code) // timeframe_seconds(source_code)
    return (target_count + 1) * ratio
