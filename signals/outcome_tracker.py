"""
ردیابی نتیجهٔ واقعی سیگنال‌ها (مورد ۱.۵ نقشهٔ راه).

مسئله:
    سیگنال تولید می‌شد و بعد فراموش. هیچ‌کس نمی‌دانست به هدف رسید یا حد
    ضرر خورد. ضریب اطمینان یک **ادعا**ست؛ بدون پیگیری نتیجه، هیچ راه
    صادقانه‌ای برای سنجش کیفیت موتور وجود ندارد.

این ماژول منطق خالص تصمیم‌گیری است: «با این قیمت تازه، وضعیت سیگنال چه
می‌شود؟» هیچ وابستگی به Qt یا شبکه ندارد، پس بدون رابط کاربری و بدون
اینترنت آزمودنی است. واکشی قیمت و ذخیره در پایگاه داده کار لایهٔ
بالاتر است.

تصمیم‌های مهم:

    **اهرم در محاسبه نمی‌آید.** درصد سود و زیان روی قیمت خام حساب
    می‌شود. اهرم انتخاب کاربر است نه ویژگی سیگنال؛ واردکردنش آمار را
    به عددی بی‌معنا تبدیل می‌کند که به تنظیمات لحظه‌ای کاربر بستگی دارد.

    **حد ضرر بر هدف مقدم است.** اگر در یک بازهٔ زمانی هم به هدف و هم به
    حد ضرر رسیده باشیم، بدبینانه حساب می‌کنیم. با داده‌ای که فقط یک
    قیمت در هر بازه دارد، نمی‌توان فهمید کدام زودتر لمس شده؛ فرض
    خوش‌بینانه آمار را به‌طور نظام‌مند بهتر از واقعیت نشان می‌دهد و
    این بدترین کاری است که یک ابزار سنجش می‌تواند بکند.

    **هدف‌های پله‌ای.** رسیدن به هدف اول سیگنال را نمی‌بندد؛ شمارش
    می‌شود و پیگیری تا آخرین هدف ادامه می‌یابد. معامله‌گر واقعی هم
    پله‌ای خارج می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: وضعیت‌های ممکن یک سیگنال تحت پیگیری
STATUS_PENDING = "PENDING"
STATUS_TARGET = "TARGET"
STATUS_STOP = "STOP"
STATUS_EXPIRED = "EXPIRED"
STATUS_CANCELLED = "CANCELLED"

#: وضعیت‌هایی که یعنی کار تمام است
CLOSED_STATUSES = frozenset({STATUS_TARGET, STATUS_STOP, STATUS_EXPIRED, STATUS_CANCELLED})

#: مهلت پیگیری بر حسب ساعت، به تفکیک تایم‌فریم اصلی سیگنال
#: سیگنال ۱۵ دقیقه‌ای که سه هفته باز بماند بی‌معناست؛ سیگنال روزانه هم
#: با مهلت دو ساعته به‌ناحق «منقضی» می‌شود.
EXPIRY_HOURS: dict[str, int] = {
    "1m": 4,
    "5m": 12,
    "15m": 24,
    "30m": 48,
    "1h": 72,
    "2h": 96,
    "4h": 168,
    "6h": 240,
    "12h": 336,
    "1d": 504,
    "3d": 720,
    "1w": 1440,
}

#: مهلت پیش‌فرض وقتی تایم‌فریم ناشناخته است (یک هفته)
DEFAULT_EXPIRY_HOURS = 168


def as_utc(moment: datetime) -> datetime:
    """
    یکسان‌سازی منطقهٔ زمانی برای مقایسه.

    پایگاه داده تاریخ‌ها را **بدون** منطقهٔ زمانی ذخیره می‌کند (به وقت
    UTC)، ولی منطق برنامه با زمان آگاه کار می‌کند. مقایسهٔ مستقیم این
    دو در پایتون `TypeError` می‌دهد. هر مقدار بی‌منطقه، UTC فرض می‌شود.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def expiry_for(timeframe: str, *, created_at: datetime | None = None) -> datetime:
    """
    زمان انقضای پیگیری بر پایهٔ تایم‌فریم سیگنال.

    مثال:
        expiry_for("4h")  →  ۱۶۸ ساعت بعد
    """
    hours = EXPIRY_HOURS.get(str(timeframe or "").strip().lower(), DEFAULT_EXPIRY_HOURS)
    base = as_utc(created_at) if created_at else datetime.now(timezone.utc)
    return base + timedelta(hours=hours)


@dataclass(frozen=True)
class PriceWindow:
    """
    بازهٔ قیمتی دیده‌شده از آخرین بررسی تا کنون.

    اگر فقط یک قیمت لحظه‌ای در دست باشد، هر سه مقدار همان است. اگر
    کندل یا تیک در دسترس باشد، `high` و `low` واقعیِ **همین بازه**
    می‌آیند و تشخیص لمس حد ضرر و هدف بسیار دقیق‌تر می‌شود.

    ⚠️ هشدار (۲٫۷٫۲ — باگی که نرخ برد را ۲٪ نشان می‌داد):

    `high`/`low` باید افراطِ **بازهٔ از آخرین بررسی تا حالا** باشند،
    نه ۲۴ ساعت اخیر. پیش‌تر سازندهٔ پنجره، `high_24h`/`low_24h` تیکر
    صرافی را می‌داد: بازه‌ای که **پیش از ورود به سیگنال** هم قیمت
    دیده بود. چون حد ضرر معمولاً زیر/بالای ساختارِ ۲۴ ساعت اخیر است،
    تقریباً هر سیگنالی در **نخستین بررسی** «حد ضرر خورده» اعلام
    می‌شد، بی‌آنکه بازار بعد از ورود اصلاً به آن سمت رفته باشد. هرگز
    از افراط‌های چرخشی (۲۴ ساعته/۷ روزه) برای این پنجره استفاده نکنید.
    """

    last: float
    high: float = 0.0
    low: float = 0.0

    @property
    def ceiling(self) -> float:
        """بالاترین قیمت بازه."""
        return max(self.last, self.high) if self.high else self.last

    @property
    def floor(self) -> float:
        """پایین‌ترین قیمت بازه."""
        candidates = [value for value in (self.last, self.low) if value > 0]
        return min(candidates) if candidates else self.last


def window_from_ticks(
    points: list[tuple[float, float]], last: float, *, since_ms: float = 0.0
) -> PriceWindow:
    """
    ساخت پنجرهٔ «از آخرین بررسی تا حالا» از تیک‌های ثبت‌شده.

    `points` فهرست `(millisecond timestamp, price)` است (همان چیزی که
    `TickEngine.history` می‌دهد). فقط تیک‌های بعد از `since_ms` شمرده
    می‌شوند تا قیمت‌های پیش از بازه — که ربطی به این سیگنال ندارند —
    وارد محاسبهٔ لمس حد ضرر/هدف نشوند.

    اگر تیکی در بازه نباشد، پنجره تک‌قیمتی (`last`) ساخته می‌شود؛
    کم‌دقت ولی **منصفانه**: هرگز با قیمت‌های قدیمی‌تر از بازه تصمیم
    نمی‌گیرد.
    """
    windowed = [price for stamp, price in points if stamp >= since_ms and price > 0]
    if not windowed:
        return PriceWindow(last=last)
    return PriceWindow(last=last, high=max(windowed), low=min(windowed))


@dataclass
class OutcomeState:
    """
    وضعیت پیگیری یک سیگنال.

    همان چیزی است که در جدول `signal_outcomes` می‌نشیند، ولی به‌صورت
    یک شیء ساده تا منطق بدون پایگاه داده آزمودنی بماند.
    """

    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profits: tuple[float, ...] = ()
    status: str = STATUS_PENDING
    targets_hit: int = 0
    exit_price: float | None = None
    result_percent: float = 0.0
    realized_r: float = 0.0
    max_favorable_percent: float = 0.0
    max_adverse_percent: float = 0.0
    last_price: float = 0.0
    checked_at: datetime | None = None
    closed_at: datetime | None = None
    expires_at: datetime | None = None
    manual: bool = False

    @property
    def is_long(self) -> bool:
        """آیا سیگنال خرید است؟"""
        return str(self.direction).upper() != "SHORT"

    @property
    def closed(self) -> bool:
        """آیا پیگیری تمام شده است؟"""
        return self.status in CLOSED_STATUSES

    @property
    def risk_distance(self) -> float:
        """فاصلهٔ ورود تا حد ضرر — واحد سنجش «یک R»."""
        return abs(self.entry_price - self.stop_loss)


def percent_change(entry: float, price: float, *, is_long: bool) -> float:
    """
    درصد تغییر از دید سیگنال.

    برای پوزیشن فروش، افت قیمت **سود** است؛ علامت باید برگردد وگرنه کل
    آمار شورت‌ها وارونه می‌شود.
    """
    if entry <= 0:
        return 0.0
    raw = (price - entry) / entry * 100
    return raw if is_long else -raw


def update_outcome(
    state: OutcomeState, window: PriceWindow, *, now: datetime | None = None
) -> OutcomeState:
    """
    به‌روزرسانی وضعیت با قیمت تازه.

    شیء **جدید** برنمی‌گرداند؛ همان شیء را تغییر می‌دهد و برمی‌گرداند
    تا فراخوان بتواند مستقیماً ذخیره کند.

    ترتیب بررسی عمدی است: اول حد ضرر (بدبینانه)، بعد هدف‌ها، آخر انقضا.
    """
    moment = as_utc(now) if now else datetime.now(timezone.utc)

    if state.closed:
        # سیگنال بسته‌شده دیگر به‌روز نمی‌شود؛ وگرنه آمار گذشته با
        # قیمت‌های امروز بازنویسی می‌شود.
        return state

    if state.entry_price <= 0:
        logger.debug("Outcome skipped for %s: no entry price", state.symbol)
        return state

    is_long = state.is_long
    state.last_price = window.last
    state.checked_at = moment

    # ---- بیشترین سود و زیان شناور
    best_price = window.ceiling if is_long else window.floor
    worst_price = window.floor if is_long else window.ceiling
    favorable = percent_change(state.entry_price, best_price, is_long=is_long)
    adverse = percent_change(state.entry_price, worst_price, is_long=is_long)
    state.max_favorable_percent = max(state.max_favorable_percent, favorable)
    state.max_adverse_percent = min(state.max_adverse_percent, adverse)

    # ---- حد ضرر، پیش از هدف
    if state.stop_loss > 0 and _stop_touched(state, window):
        return _close(state, state.stop_loss, STATUS_STOP, moment)

    # ---- هدف‌ها، پله‌ای
    hit = _count_targets(state, window)
    if hit > state.targets_hit:
        state.targets_hit = hit
        if hit >= len(state.take_profits) and state.take_profits:
            # آخرین هدف لمس شد: کار تمام است
            return _close(state, state.take_profits[-1], STATUS_TARGET, moment)

    # ---- انقضا
    if state.expires_at is not None and moment >= as_utc(state.expires_at):
        return _close(state, window.last, STATUS_EXPIRED, moment)

    # ---- هنوز باز: سود و زیان شناور
    state.result_percent = round(
        percent_change(state.entry_price, window.last, is_long=is_long), 4
    )
    state.realized_r = _to_r(state, window.last)
    return state


def _stop_touched(state: OutcomeState, window: PriceWindow) -> bool:
    """آیا قیمت به حد ضرر رسیده است؟"""
    if state.is_long:
        return window.floor <= state.stop_loss
    return window.ceiling >= state.stop_loss


def _count_targets(state: OutcomeState, window: PriceWindow) -> int:
    """چند هدف تا این لحظه لمس شده است."""
    count = 0
    for target in state.take_profits:
        if target <= 0:
            continue
        reached = (
            window.ceiling >= target if state.is_long else window.floor <= target
        )
        if not reached:
            break
        count += 1
    return count


def _close(
    state: OutcomeState, price: float, status: str, moment: datetime
) -> OutcomeState:
    """بستن پیگیری با قیمت و وضعیت مشخص."""
    state.status = status
    state.exit_price = price
    state.closed_at = moment
    state.result_percent = round(
        percent_change(state.entry_price, price, is_long=state.is_long), 4
    )
    state.realized_r = _to_r(state, price)
    logger.info(
        "Signal outcome for %s: %s (%.2f%%)", state.symbol, status, state.result_percent
    )
    return state


def _to_r(state: OutcomeState, price: float) -> float:
    """
    تبدیل نتیجه به واحد R (چند برابر ریسک اولیه).

    درصد خام میان نمادها قابل مقایسه نیست — ۲٪ روی بیت‌کوین ریسک
    متفاوتی از ۲٪ روی یک آلت‌کوین پرنوسان دارد. R واحد مشترک است.
    """
    risk = state.risk_distance
    if risk <= 0:
        return 0.0
    move = (price - state.entry_price) if state.is_long else (state.entry_price - price)
    return round(move / risk, 3)


# ----------------------------------------------------------------- آمار


def _field(item: Any, name: str, default: Any = 0) -> Any:
    """خواندن یک فیلد از شیء یا دیکشنری."""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def ladder_exit(item: Any) -> tuple[float, float]:
    """
    نتیجهٔ «خروج پله‌ای» — آنچه یک معامله‌گر واقعی بانک می‌کرد (۲٫۷٫۲).

    سیگنال سه هدف دارد و پیگیری هم پله‌ای است (`targets_hit`)، اما
    حسابداریِ قدیمی فقط قیمتِ نهایی (حد ضرر یا آخرین هدف) را می‌شمرد:
    سیگنالی که به هدف اول و دوم رسیده بود و بعد حد ضرر خورده بود،
    «باختِ -۱R» ثبت می‌شد — در حالی که معامله‌گر دو سوم را با سود
    بسته بود. همین تعریف، نرخ برد را نظام‌مند پایین‌تر از واقعیت
    نشان می‌داد و «میانگین R» را بی‌معنا می‌کرد.

    سیاست خروج: سهم‌های مساوی (یک‌سوم) روی هر هدف؛ باقی‌مانده در
    قیمتِ نهایی (حد ضرر/انقضا). اهرم و سلیقهٔ کاربر در کار نیست،
    دقیقاً مثل بقیهٔ این ماژول.

    بازگشتی: (درصد، R) — برای سیگنالِ باز یا بدون هدف، همان مقادیرِ
    مسیر قیمت (`result_percent`/`realized_r`) برگردانده می‌شود.
    """
    entry = float(_field(item, "entry_price", 0.0) or 0.0)
    raw_targets = _field(item, "take_profits", ()) or ()
    if isinstance(raw_targets, str):
        # رکوردهای قدیمی/سریال‌شده ممکن است رشتهٔ «103,106,109» باشند
        raw_targets = [part for part in raw_targets.split(",") if part.strip()]
    try:
        targets = tuple(float(t) for t in raw_targets if float(t) > 0)
    except (TypeError, ValueError):
        return float(_field(item, "result_percent", 0.0) or 0.0), float(
            _field(item, "realized_r", 0.0) or 0.0
        )
    exit_price = _field(item, "exit_price", None)
    status = str(_field(item, "status", STATUS_PENDING) or STATUS_PENDING)
    path_percent = float(_field(item, "result_percent", 0.0) or 0.0)
    path_r = float(_field(item, "realized_r", 0.0) or 0.0)

    if (
        entry <= 0
        or not targets
        or exit_price is None
        or float(exit_price or 0) <= 0
        or status not in CLOSED_STATUSES
    ):
        return path_percent, path_r

    is_long = str(_field(item, "direction", "LONG") or "LONG").upper() != "SHORT"
    stop = float(_field(item, "stop_loss", 0.0) or 0.0)
    risk = abs(entry - stop) if stop > 0 else 0.0
    hit = max(0, min(int(_field(item, "targets_hit", 0) or 0), len(targets)))

    percents: list[float] = []
    rs: list[float] = []
    for index in range(len(targets)):
        if index < hit:
            price = targets[index]
        else:
            price = float(exit_price)
        percents.append(percent_change(entry, price, is_long=is_long))
        if risk > 0:
            move = (price - entry) if is_long else (entry - price)
            rs.append(move / risk)
        else:
            rs.append(0.0)

    return round(sum(percents) / len(percents), 4), round(sum(rs) / len(rs), 3)


def summarize(outcomes: list[Any]) -> dict[str, Any]:
    """
    خلاصهٔ عملکرد از روی فهرست نتیجه‌ها.

    «برد» یعنی معامله‌ای که با سیاستِ خروجِ پله‌ای (یک‌سوم روی هر هدف،
    بدون فرضِ سربه‌سر کردنِ حد ضرر) سودده بسته شده باشد — نه لزوماً
    رسیدن به آخرین هدف. تعریف قدیمی (فقط رسیدن به هدفِ سوم) صادقانه
    بود ولی گمراه‌کننده: سیگنالی که دو هدف را زده بود و بعد حد ضرر
    خورده بود «باختِ -۱R» حساب می‌شد، در حالی که معامله‌گر با خروج
    پله‌ای ‎+1R‎ بانک کرده بود.

    وضعیت‌های خام هم کنارش می‌آیند (`targets_full`، `stops_hit`) تا
    کسی از دید هیچ‌چیز پنهان نماند. سیگنال‌های منقضی در نرخ برد نمی‌آیند
    (نه بردند نه باخت) ولی در Rهای جمع‌شده شمرده می‌شوند.
    """
    total = len(outcomes)
    pending = [item for item in outcomes if _status(item) == STATUS_PENDING]
    targets_full = [item for item in outcomes if _status(item) == STATUS_TARGET]
    stops_hit = [item for item in outcomes if _status(item) == STATUS_STOP]
    expired = [item for item in outcomes if _status(item) == STATUS_EXPIRED]

    closed = [item for item in outcomes if _status(item) in CLOSED_STATUSES]
    ladder = [ladder_exit(item) for item in closed]
    decided_pairs = [
        pair
        for item, pair in zip(closed, ladder, strict=True)
        if _status(item) in (STATUS_TARGET, STATUS_STOP)
    ]
    wins = [pair for pair in decided_pairs if pair[1] > 0]
    losses = [pair for pair in decided_pairs if pair[1] <= 0]
    profitable = [pair for pair in ladder if pair[1] > 0]

    decided = len(decided_pairs)
    win_rate = (len(wins) / decided * 100) if decided else 0.0

    r_values = [float(getattr(item, "realized_r", 0) or 0) for item in outcomes
                if _status(item) in CLOSED_STATUSES]
    ladder_percents = [pair[0] for pair in ladder]
    ladder_rs = [pair[1] for pair in ladder]

    win_amounts = [value for value in ladder_percents if value > 0]
    loss_amounts = [abs(value) for value in ladder_percents if value < 0]

    gross_win = sum(win_amounts)
    gross_loss = sum(loss_amounts)
    # ضریب سود: مجموع سودها تقسیم بر مجموع زیان‌ها. بالای ۱ یعنی سودده.
    profit_factor = (gross_win / gross_loss) if gross_loss else (gross_win and float("inf"))

    tp1_reached = sum(1 for item in closed if int(_field(item, "targets_hit", 0) or 0) >= 1)

    return {
        "total": total,
        "pending": len(pending),
        "wins": len(wins),
        "losses": len(losses),
        "expired": len(expired),
        "decided": decided,
        "win_rate": round(win_rate, 1),
        # شفافیتِ تعریف (۲٫۷٫۲): وضعیت‌های خام و متریک‌های پله‌ای
        "targets_full": len(targets_full),
        "stops_hit": len(stops_hit),
        "full_target_rate": round(len(targets_full) / decided * 100, 1) if decided else 0.0,
        "tp1_reached": tp1_reached,
        "tp1_rate": round(tp1_reached / decided * 100, 1) if decided else 0.0,
        "profitable": len(profitable),
        "profitable_rate": round(len(profitable) / len(ladder) * 100, 1) if ladder else 0.0,
        "total_percent": round(sum(ladder_percents), 2) if ladder_percents else 0.0,
        "average_percent": round(sum(ladder_percents) / len(ladder_percents), 2) if ladder_percents else 0.0,
        "total_r": round(sum(ladder_rs), 2) if ladder_rs else 0.0,
        "average_r": round(sum(ladder_rs) / len(ladder_rs), 2) if ladder_rs else 0.0,
        # مقادیر «مسیر قیمت» (بدون خروج پله‌ای) برای مقایسه و اشکال‌زدایی
        "path_total_r": round(sum(r_values), 2),
        "path_average_r": round(sum(r_values) / len(r_values), 2) if r_values else 0.0,
        "best_percent": round(max(ladder_percents), 2) if ladder_percents else 0.0,
        "worst_percent": round(min(ladder_percents), 2) if ladder_percents else 0.0,
        "average_win": round(sum(win_amounts) / len(win_amounts), 2) if win_amounts else 0.0,
        "average_loss": round(sum(loss_amounts) / len(loss_amounts), 2) if loss_amounts else 0.0,
        "profit_factor": round(profit_factor, 2) if profit_factor not in (0, float("inf")) else profit_factor,
    }


def group_by(outcomes: list[Any], attribute: str) -> dict[str, dict[str, Any]]:
    """
    آمار به تفکیک یک ویژگی: نماد، تایم‌فریم یا بازهٔ اطمینان.

    این همان چیزی است که به سؤال «موتور روی چه چیزی خوب کار می‌کند؟»
    پاسخ می‌دهد.
    """
    buckets: dict[str, list[Any]] = {}
    for item in outcomes:
        key = str(getattr(item, attribute, "") or "—")
        buckets.setdefault(key, []).append(item)
    return {key: summarize(items) for key, items in sorted(buckets.items())}


def confidence_buckets(outcomes: list[Any], *, width: int = 10) -> dict[str, dict[str, Any]]:
    """
    آمار به تفکیک بازهٔ ضریب اطمینان.

    مهم‌ترین نمودار کل سیستم: اگر نرخ برد با بالارفتن ضریب اطمینان
    **زیاد نشود**، یعنی ضریب اطمینان بی‌معناست و موتور باید بازنگری
    شود. این تنها راه اثبات یا ردّ ادعای موتور است.
    """
    buckets: dict[str, list[Any]] = {}
    for item in outcomes:
        confidence = int(getattr(item, "confidence", 0) or 0)
        low = max(0, min(100, confidence)) // width * width
        buckets.setdefault(f"{low}-{low + width - 1}", []).append(item)
    return {key: summarize(items) for key, items in sorted(buckets.items())}


def _status(item: Any) -> str:
    """خواندن وضعیت از شیء یا دیکشنری."""
    if isinstance(item, dict):
        return str(item.get("status") or STATUS_PENDING)
    return str(getattr(item, "status", STATUS_PENDING) or STATUS_PENDING)


__all__ = [
    "CLOSED_STATUSES",
    "DEFAULT_EXPIRY_HOURS",
    "EXPIRY_HOURS",
    "STATUS_CANCELLED",
    "STATUS_EXPIRED",
    "STATUS_PENDING",
    "STATUS_STOP",
    "STATUS_TARGET",
    "OutcomeState",
    "as_utc",
    "PriceWindow",
    "confidence_buckets",
    "expiry_for",
    "group_by",
    "ladder_exit",
    "percent_change",
    "summarize",
    "update_outcome",
    "window_from_ticks",
]
