"""
پنجرهٔ اعتبار سیگنال و تشخیص «سیگنال سوخته».

چرا وجود دارد؟
    کاربر گزارش کرد بعضی سیگنال‌ها سودی نداده‌اند. یکی از دلایل ریشه‌ای
    این است که سیگنال **تاریخ مصرف** دارد ولی برنامه آن را نشان
    نمی‌داد. سیگنالی که دو ساعت پیش روی تایم‌فریم ۱۵ دقیقه‌ای ساخته
    شده، دیگر همان سیگنال نیست: هشت کندل گذشته و شرایطی که آن را
    ساخته بود احتمالاً از بین رفته است. کاربر آن را می‌دید، وارد
    می‌شد، و وارد معامله‌ای می‌شد که دیگر وجود نداشت.

    ایراد دوم و ظریف‌تر: حتی سیگنال تازه هم ممکن است «سوخته» باشد.
    اگر قیمت پیش از ورود شما بخش بزرگی از راه تا هدف را رفته باشد،
    نسبت ریسک به ریوارد دیگر آن چیزی نیست که موقع ساخت سیگنال بود —
    حد ضرر همان‌جاست ولی سود باقی‌مانده کمتر شده. ورود در این نقطه
    یعنی پذیرفتن همان ریسک برای پاداش کمتر. این ماژول هر دو را
    می‌سنجد: گذر **زمان** و گذر **قیمت**.

فلسفهٔ طراحی:
    این ماژول عمداً هیچ وابستگی سنگینی ندارد (نه pandas، نه پایگاه
    داده) تا هم سریع باشد و هم در هر لایه‌ای قابل استفاده. تصمیم‌ها
    محاسباتی و قطعی‌اند؛ هوش مصنوعی اینجا نقشی ندارد چون «چند دقیقه
    از ساخت سیگنال گذشته» پرسشی نیست که مدل زبانی باید جواب بدهد.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

#: طول هر تایم‌فریم به دقیقه.
TIMEFRAME_MINUTES: dict[str, int] = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080,
}

#: پنجرهٔ ورود، برحسب **تعداد کندل** تایم‌فریم اصلی.
#:
#: چرا بر پایهٔ کندل و نه ساعت ثابت؟
#:     چون سیگنال از ساختار کندل‌ها زاده می‌شود. سه کندل روی تایم‌فریم
#:     ۱ دقیقه‌ای یعنی سه دقیقه، و روی تایم‌فریم روزانه یعنی سه روز؛ در
#:     هر دو حالت «حدوداً همان‌قدر بازار جلو رفته است». عدد ثابت ساعتی
#:     برای یکی خیلی کوتاه و برای دیگری بی‌معنا می‌شد.
ENTRY_WINDOW_CANDLES = 3

#: پس از این تعداد کندل، سیگنال کاملاً منقضی است.
EXPIRY_CANDLES = 12

#: کف و سقف پنجرهٔ ورود بر حسب دقیقه.
#: تایم‌فریم یک‌دقیقه‌ای بدون کف، پنجره‌ای سه‌دقیقه‌ای می‌داد که تا کاربر
#: سیگنال را ببیند تمام شده بود.
MIN_ENTRY_MINUTES = 10
MAX_ENTRY_MINUTES = 7 * 24 * 60

#: چند درصد از مسیر تا اولین هدف را می‌توان از دست داد و هنوز وارد شد.
#:
#: چرا ۳۵٪؟
#:     ورود پس از طی‌شدن یک‌سوم راه یعنی نسبت ریسک به ریوارد تقریباً
#:     یک‌سوم بدتر شده، چون حد ضرر سر جایش است ولی سود باقی‌مانده کمتر.
#:     سیگنالی با نسبت ۳ به ۱ به حدود ۲ به ۱ می‌رسد که هنوز قابل قبول
#:     است. فراتر از آن، معامله دیگر ارزش ریسکش را ندارد.
MAX_MOVE_CONSUMED = 0.35

#: اگر قیمت بیش از این نسبت از فاصلهٔ حد ضرر **خلاف** جهت رفته باشد،
#: سیگنال از پیش در حال شکست است.
MAX_ADVERSE_MOVE = 0.5


class Freshness(str, Enum):
    """
    وضعیت تازگی یک سیگنال.

    مقادیر رشته‌ای‌اند تا مستقیم در پایگاه داده و JSON بنشینند.
    """

    #: تازه؛ در پنجرهٔ ورود و قیمت هنوز در محدودهٔ مناسب است
    FRESH = "FRESH"
    #: هنوز قابل استفاده ولی بخشی از پنجره یا حرکت مصرف شده
    AGING = "AGING"
    #: سوخته؛ فرصت ورود از دست رفته، اما سیگنال هنوز منقضی نشده
    STALE = "STALE"
    #: منقضی؛ زمان اعتبار تمام شده است
    EXPIRED = "EXPIRED"
    #: باطل؛ قیمت حد ضرر را رد کرده یا خلاف جهت رفته است
    INVALIDATED = "INVALIDATED"


#: وضعیت‌هایی که ورود تازه در آن‌ها توصیه نمی‌شود.
NOT_ENTERABLE = frozenset({Freshness.STALE, Freshness.EXPIRED, Freshness.INVALIDATED})


@dataclass(slots=True)
class ValidityWindow:
    """
    پنجرهٔ اعتبار یک سیگنال با همهٔ اعدادی که کاربر باید ببیند.

    این ساختار عمداً همه‌چیز را از پیش حساب می‌کند (نه تنبل) تا رابط
    کاربری بتواند بدون منطق اضافی فقط نمایش بدهد.
    """

    #: لحظهٔ ساخت سیگنال
    created_at: datetime
    #: تا این لحظه ورود منطقی است
    enter_before: datetime
    #: پس از این لحظه سیگنال کاملاً بی‌اعتبار است
    expires_at: datetime
    #: تایم‌فریمی که پنجره از آن حساب شده
    timeframe: str
    #: وضعیت تازگی
    freshness: Freshness = Freshness.FRESH
    #: چند دقیقه تا پایان پنجرهٔ ورود مانده (منفی یعنی گذشته)
    minutes_to_enter: float = 0.0
    #: چند دقیقه تا انقضا مانده
    minutes_to_expiry: float = 0.0
    #: چند درصد از مسیر تا اولین هدف پیش از ورود طی شده است
    move_consumed_percent: float = 0.0
    #: نسبت ریسک به ریوارد در قیمت **فعلی** (نه قیمت زمان ساخت)
    effective_risk_reward: float | None = None
    #: کلید ترجمهٔ توضیح وضعیت
    reason_key: str = ""
    #: مقادیری که در متن ترجمه جایگزین می‌شوند
    reason_args: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """جلوگیری از اشتراک دیکشنری پیش‌فرض بین نمونه‌ها."""
        if self.reason_args is None:
            self.reason_args = {}

    @property
    def is_enterable(self) -> bool:
        """آیا ورود تازه به این سیگنال هنوز منطقی است؟"""
        return self.freshness not in NOT_ENTERABLE

    @property
    def is_burned(self) -> bool:
        """آیا سیگنال «سوخته» است؟ (اصطلاح خود کاربر)"""
        return self.freshness in NOT_ENTERABLE

    def to_dict(self) -> dict[str, Any]:
        """تبدیل برای ذخیره و انتقال."""
        return {
            "created_at": self.created_at.isoformat(),
            "enter_before": self.enter_before.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "timeframe": self.timeframe,
            "freshness": self.freshness.value,
            "minutes_to_enter": round(self.minutes_to_enter, 1),
            "minutes_to_expiry": round(self.minutes_to_expiry, 1),
            "move_consumed_percent": round(self.move_consumed_percent, 1),
            "effective_risk_reward": self.effective_risk_reward,
            "reason_key": self.reason_key,
            "reason_args": dict(self.reason_args),
        }


def as_utc(moment: datetime) -> datetime:
    """
    یکسان‌سازی منطقهٔ زمانی.

    پایگاه داده زمان را بدون منطقه ذخیره می‌کند (به وقت UTC) ولی منطق
    برنامه با زمان آگاه کار می‌کند؛ مقایسهٔ مستقیم این دو در پایتون
    استثنا می‌دهد.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def timeframe_minutes(timeframe: str) -> int:
    """طول یک تایم‌فریم به دقیقه، با بازگشت امن برای مقدار ناشناخته."""
    return TIMEFRAME_MINUTES.get((timeframe or "").strip().lower(), 60)


def entry_window_minutes(timeframe: str) -> int:
    """
    طول پنجرهٔ ورود به دقیقه.

    بین کف و سقف محدود می‌شود تا نه آن‌قدر کوتاه باشد که کاربر فرصت
    دیدنش را نداشته باشد، نه آن‌قدر بلند که بی‌معنا شود.
    """
    raw = timeframe_minutes(timeframe) * ENTRY_WINDOW_CANDLES
    return int(max(MIN_ENTRY_MINUTES, min(MAX_ENTRY_MINUTES, raw)))


def expiry_minutes(timeframe: str) -> int:
    """طول کل اعتبار سیگنال به دقیقه."""
    raw = timeframe_minutes(timeframe) * EXPIRY_CANDLES
    return int(max(MIN_ENTRY_MINUTES * 2, min(MAX_ENTRY_MINUTES * 4, raw)))


def primary_timeframe(timeframes: list[str] | None) -> str:
    """
    تایم‌فریم تعیین‌کنندهٔ سرعت سیگنال.

    وقتی تحلیل چند تایم‌فریمی است، **کوچک‌ترین** تایم‌فریم سرعت را
    تعیین می‌کند: سیگنالی که به کندل ۱۵ دقیقه‌ای نگاه می‌کند با همان
    سرعت هم کهنه می‌شود، حتی اگر تصویر کلان روزانه باشد. انتخاب
    تایم‌فریم بزرگ‌تر یعنی به کاربر بگوییم سیگنال هنوز معتبر است در
    حالی که نیست.
    """
    known = [tf for tf in (timeframes or []) if (tf or "").lower() in TIMEFRAME_MINUTES]
    if not known:
        return "1h"
    return min(known, key=lambda tf: TIMEFRAME_MINUTES[tf.lower()])


def _consumed_fraction(
    *,
    direction: str,
    reference_entry: float,
    first_target: float | None,
    current_price: float,
) -> float:
    """
    چه کسری از مسیر تا اولین هدف پیش از ورود ما طی شده است.

    صفر یعنی قیمت هنوز سر جای ورود است؛ یک یعنی هدف اول قبلاً خورده و
    ورود تازه بی‌معنی است. مقدار منفی (قیمت خلاف جهت رفته) به صفر
    محدود می‌شود چون از دید «فرصت از دست رفته» ضرری نکرده‌ایم.
    """
    if not first_target or reference_entry <= 0:
        return 0.0
    span = abs(first_target - reference_entry)
    if span <= 0:
        return 0.0
    if direction == "LONG":
        moved = current_price - reference_entry
    else:
        moved = reference_entry - current_price
    return max(0.0, moved / span)


def _adverse_fraction(
    *,
    direction: str,
    reference_entry: float,
    stop_loss: float | None,
    current_price: float,
) -> float:
    """چه کسری از فاصله تا حد ضرر، خلاف جهت طی شده است."""
    if not stop_loss or reference_entry <= 0:
        return 0.0
    span = abs(reference_entry - stop_loss)
    if span <= 0:
        return 0.0
    if direction == "LONG":
        moved = reference_entry - current_price
    else:
        moved = current_price - reference_entry
    return max(0.0, moved / span)


def _effective_risk_reward(
    *,
    direction: str,
    current_price: float,
    stop_loss: float | None,
    first_target: float | None,
) -> float | None:
    """
    نسبت ریسک به ریوارد اگر **همین حالا** با قیمت فعلی وارد شویم.

    این عدد با نسبتی که موقع ساخت سیگنال حساب شده فرق دارد و تفاوتشان
    دقیقاً همان چیزی است که کاربر باید ببیند: سیگنال ۳ به ۱ که دیر
    دیده شده، ممکن است حالا ۱٫۲ به ۱ باشد.
    """
    if not stop_loss or not first_target or current_price <= 0:
        return None
    if direction == "LONG":
        risk = current_price - stop_loss
        reward = first_target - current_price
    else:
        risk = stop_loss - current_price
        reward = current_price - first_target
    if risk <= 0 or reward <= 0:
        return 0.0
    return round(reward / risk, 2)


def evaluate(
    *,
    created_at: datetime,
    timeframes: list[str] | None,
    direction: str,
    entry_min: float | None = None,
    entry_max: float | None = None,
    stop_loss: float | None = None,
    take_profits: list[float] | None = None,
    current_price: float | None = None,
    now: datetime | None = None,
) -> ValidityWindow:
    """
    سنجش کامل اعتبار و تازگی یک سیگنال.

    آرگومان‌ها:
        created_at: لحظهٔ ساخت سیگنال.
        timeframes: تایم‌فریم‌های تحلیل؛ کوچک‌ترین ملاک سرعت است.
        direction: `LONG`، `SHORT` یا `WAIT`.
        entry_min/entry_max: محدودهٔ ورود پیشنهادی.
        stop_loss: حد ضرر.
        take_profits: اهداف سود، مرتب در جهت معامله.
        current_price: قیمت لحظه‌ای؛ اگر ندهید فقط زمان سنجیده می‌شود.
        now: برای آزمون‌پذیری.

    بازگشت:
        `ValidityWindow` با وضعیت و کلید ترجمهٔ توضیح.

    ترتیب بررسی عمدی است: **ابطال پیش از انقضا، و انقضا پیش از
    سنجش قیمت.** سیگنالی که حد ضررش خورده، دیگر مهم نیست چقدر تازه
    است.
    """
    moment = as_utc(now or datetime.now(timezone.utc))
    created = as_utc(created_at)
    frame = primary_timeframe(timeframes)

    enter_before = created + timedelta(minutes=entry_window_minutes(frame))
    expires_at = created + timedelta(minutes=expiry_minutes(frame))

    window = ValidityWindow(
        created_at=created,
        enter_before=enter_before,
        expires_at=expires_at,
        timeframe=frame,
        minutes_to_enter=(enter_before - moment).total_seconds() / 60.0,
        minutes_to_expiry=(expires_at - moment).total_seconds() / 60.0,
    )

    normalized = (direction or "").strip().upper()

    # سیگنال انتظار تاریخ مصرف ورود ندارد؛ فقط کهنه می‌شود.
    if normalized not in {"LONG", "SHORT"}:
        if moment >= expires_at:
            window.freshness = Freshness.EXPIRED
            window.reason_key = "validity.expired_wait"
        else:
            window.freshness = Freshness.FRESH
            window.reason_key = "validity.wait_active"
        return window

    targets = [float(t) for t in (take_profits or []) if t]
    first_target = targets[0] if targets else None
    reference = _reference_entry(entry_min, entry_max, current_price)

    # ۱) ابطال با قیمت — مهم‌تر از هر چیز دیگری
    if current_price and stop_loss:
        hit_stop = (
            current_price <= stop_loss if normalized == "LONG" else current_price >= stop_loss
        )
        if hit_stop:
            window.freshness = Freshness.INVALIDATED
            window.reason_key = "validity.stop_hit"
            window.reason_args = {"price": current_price, "stop": stop_loss}
            return window

    # ۲) انقضای زمانی
    if moment >= expires_at:
        window.freshness = Freshness.EXPIRED
        window.reason_key = "validity.expired"
        window.reason_args = {
            "timeframe": frame,
            "hours": round(expiry_minutes(frame) / 60, 1),
        }
        return window

    # ۳) سنجش حرکت قیمت
    if current_price and reference:
        consumed = _consumed_fraction(
            direction=normalized,
            reference_entry=reference,
            first_target=first_target,
            current_price=current_price,
        )
        window.move_consumed_percent = round(consumed * 100, 1)
        window.effective_risk_reward = _effective_risk_reward(
            direction=normalized,
            current_price=current_price,
            stop_loss=stop_loss,
            first_target=first_target,
        )

        adverse = _adverse_fraction(
            direction=normalized,
            reference_entry=reference,
            stop_loss=stop_loss,
            current_price=current_price,
        )

        if consumed >= 1.0:
            window.freshness = Freshness.STALE
            window.reason_key = "validity.target_reached"
            return window

        if consumed > MAX_MOVE_CONSUMED:
            window.freshness = Freshness.STALE
            window.reason_key = "validity.move_consumed"
            window.reason_args = {
                "percent": window.move_consumed_percent,
                "risk_reward": window.effective_risk_reward or 0.0,
            }
            return window

        if adverse > MAX_ADVERSE_MOVE:
            window.freshness = Freshness.AGING
            window.reason_key = "validity.adverse_move"
            window.reason_args = {"percent": round(adverse * 100, 1)}
            return window

    # ۴) سنجش زمانی پنجرهٔ ورود
    if moment >= enter_before:
        window.freshness = Freshness.STALE
        window.reason_key = "validity.entry_window_passed"
        window.reason_args = {
            "minutes": int(abs(window.minutes_to_enter)),
            "timeframe": frame,
        }
        return window

    # نیمهٔ دوم پنجره: هنوز معتبر، ولی باید عجله کرد
    half = entry_window_minutes(frame) / 2
    if window.minutes_to_enter <= half:
        window.freshness = Freshness.AGING
        window.reason_key = "validity.entry_window_closing"
        window.reason_args = {"minutes": int(max(0, window.minutes_to_enter))}
        return window

    window.freshness = Freshness.FRESH
    window.reason_key = "validity.fresh"
    window.reason_args = {"minutes": int(max(0, window.minutes_to_enter))}
    return window


def _reference_entry(
    entry_min: float | None, entry_max: float | None, current_price: float | None
) -> float:
    """
    قیمت مرجع ورود.

    میانهٔ محدودهٔ ورود منطقی‌ترین نماینده است. اگر محدوده‌ای نبود، به
    قیمت فعلی برمی‌گردیم که یعنی «هیچ حرکتی مصرف نشده» — محافظه‌کارانه
    و بی‌خطر.
    """
    values = [float(v) for v in (entry_min, entry_max) if v]
    if values:
        return sum(values) / len(values)
    return float(current_price or 0.0)
