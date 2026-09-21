"""
سیگنال‌گیری خودکار و دوره‌ای.

کاربر خواست برنامه خودش هر چند دقیقه یک‌بار سیگنال بگیرد، و دو رفتار
متفاوت را نام برد:

    ۱. **تمرکز** — نمادهایی که در پویش‌های پیشین بالاترین ضریب اطمینان
       را داشته‌اند، مکرر و با فاصلهٔ زمانیِ کوتاه دوباره بررسی شوند؛
       چون فرصت معاملاتی روی همان‌ها در جریان است.
    ۲. **چرخش کامل** — برنامه روی **همهٔ** نمادهای موجود بچرخد و خودش
       بهترین سیگنال را پیدا کند.

هر دو با هم کار می‌کنند: چرخهٔ کامل کندتر اجرا می‌شود و نتیجه‌اش فهرست
تمرکز را تغذیه می‌کند؛ چرخهٔ تمرکز سریع‌تر روی همان فهرست می‌دود. این
دقیقاً همان چیزی است که یک معامله‌گر دستی انجام می‌دهد.

چرا زمان‌بند جدا و نه `QTimer` در کنترلر؟
    منطق زمان‌بندی هیچ ربطی به Qt ندارد و باید بدون رابط کاربری آزمودنی
    باشد. این ماژول فقط می‌گوید «حالا نوبت چه کاری است»؛ اجرای واقعی با
    لایهٔ بالاتر است.

نکتهٔ مصرف منابع:
    پویش کامل چند دقیقه طول می‌کشد. اگر چرخهٔ بعدی پیش از پایان قبلی
    برسد، **رد می‌شود** نه اینکه صف شود؛ وگرنه برنامه زیر بار پویش‌های
    روی‌هم‌انباشته خفه می‌شود.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: کمینهٔ فاصلهٔ مجاز میان دو پویش خودکار (ثانیه)
#: کمتر از این، هم صرافی محدودیت می‌گذارد هم داده‌ها هنوز عوض نشده‌اند.
MIN_INTERVAL_SECONDS = 30

#: بیشترین فاصله — یک شبانه‌روز
MAX_INTERVAL_SECONDS = 24 * 60 * 60

#: پیش‌فرض چرخهٔ تمرکز: هر ۵ دقیقه
DEFAULT_FOCUS_INTERVAL = 300

#: پیش‌فرض چرخهٔ کامل: هر ۳۰ دقیقه
DEFAULT_FULL_INTERVAL = 1800

#: چند نماد برتر در فهرست تمرکز بماند
DEFAULT_FOCUS_SIZE = 10

#: کمینهٔ ضریب اطمینان برای ورود به فهرست تمرکز
DEFAULT_FOCUS_MIN_CONFIDENCE = 55


def clamp_interval(seconds: Any) -> int:
    """
    محدودکردن فاصلهٔ زمانی به بازهٔ معقول.

    ورودی نامعتبر یا صفر به پیش‌فرض برمی‌گردد، نه اینکه حلقهٔ بی‌وقفه
    بسازد.
    """
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return DEFAULT_FOCUS_INTERVAL
    if value <= 0:
        return DEFAULT_FOCUS_INTERVAL
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))


@dataclass
class AutoScanConfig:
    """تنظیمات سیگنال‌گیری خودکار، همان‌طور که کاربر در تنظیمات می‌چیند."""

    #: آیا سیگنال‌گیری خودکار روشن است
    enabled: bool = False
    #: فاصلهٔ پویش نمادهای پراطمینان (ثانیه)
    focus_interval: int = DEFAULT_FOCUS_INTERVAL
    #: آیا چرخش روی همهٔ نمادها انجام شود
    full_sweep_enabled: bool = True
    #: فاصلهٔ چرخش کامل (ثانیه)
    full_interval: int = DEFAULT_FULL_INTERVAL
    #: چند نماد در فهرست تمرکز
    focus_size: int = DEFAULT_FOCUS_SIZE
    #: کمینهٔ اطمینان برای ورود به فهرست تمرکز
    focus_min_confidence: int = DEFAULT_FOCUS_MIN_CONFIDENCE
    #: سقف نمادها در هر چرخش کامل (جلوگیری از پویش بی‌پایان)
    sweep_limit: int = 120
    #: فقط وقتی پنجرهٔ برنامه دیده می‌شود پویش کن
    only_when_visible: bool = False

    def normalized(self) -> AutoScanConfig:
        """نسخهٔ اصلاح‌شده با مقادیر درون بازهٔ مجاز."""
        return AutoScanConfig(
            enabled=bool(self.enabled),
            focus_interval=clamp_interval(self.focus_interval),
            full_sweep_enabled=bool(self.full_sweep_enabled),
            full_interval=clamp_interval(self.full_interval),
            focus_size=max(1, min(50, int(self.focus_size or DEFAULT_FOCUS_SIZE))),
            focus_min_confidence=max(0, min(100, int(self.focus_min_confidence or 0))),
            sweep_limit=max(10, min(1000, int(self.sweep_limit or 120))),
            only_when_visible=bool(self.only_when_visible),
        )

    @classmethod
    def from_settings(cls, settings: Any) -> AutoScanConfig:
        """ساخت پیکربندی از تنظیمات برنامه."""
        get = settings.get
        return cls(
            enabled=bool(get("signals.auto_scan_enabled", False)),
            focus_interval=int(get("signals.auto_scan_interval", DEFAULT_FOCUS_INTERVAL) or 0),
            full_sweep_enabled=bool(get("signals.auto_scan_full_sweep", True)),
            full_interval=int(get("signals.auto_scan_full_interval", DEFAULT_FULL_INTERVAL) or 0),
            focus_size=int(get("signals.auto_scan_focus_size", DEFAULT_FOCUS_SIZE) or 0),
            focus_min_confidence=int(
                get("signals.auto_scan_min_confidence", DEFAULT_FOCUS_MIN_CONFIDENCE) or 0
            ),
            sweep_limit=int(get("signals.auto_scan_sweep_limit", 120) or 0),
            only_when_visible=bool(get("signals.auto_scan_only_visible", False)),
        ).normalized()


@dataclass
class ScanJob:
    """یک نوبت پویش که زمان‌بند پیشنهاد می‌دهد."""

    #: "focus" یا "full"
    kind: str
    #: نمادهایی که باید بررسی شوند؛ خالی یعنی «همه»
    symbols: tuple[str, ...] = ()
    #: دلیل انتخاب، برای گزارش و نمایش به کاربر
    reason: str = ""


@dataclass
class AutoScanScheduler:
    """
    تصمیم‌گیرندهٔ زمان و موضوع پویش بعدی.

    نمونه‌سازی:
        scheduler = AutoScanScheduler(config)
        job = scheduler.due()
        if job is not None:
            ...  # اجرای پویش
            scheduler.complete(job, signals)

    این کلاس هیچ کاری را خودش اجرا نمی‌کند و به شبکه دست نمی‌زند؛ فقط
    حساب می‌کند. به همین دلیل بدون رابط کاربری و بدون اینترنت آزمودنی
    است.
    """

    config: AutoScanConfig = field(default_factory=AutoScanConfig)
    #: نمادهای پراطمینان، به ترتیب اهمیت
    focus_symbols: list[str] = field(default_factory=list)
    #: زمان آخرین پویش تمرکز
    last_focus_at: datetime | None = None
    #: زمان آخرین چرخش کامل
    last_full_at: datetime | None = None
    #: آیا پویشی همین حالا در جریان است
    running: bool = False
    #: شمار چرخه‌های ردشده به‌خاطر همپوشانی
    skipped: int = 0

    # ------------------------------------------------------------------
    # زمان‌بندی
    # ------------------------------------------------------------------
    def due(self, now: datetime | None = None) -> ScanJob | None:
        """
        آیا اکنون نوبت پویشی هست؟

        اولویت با چرخش کامل است: فهرست تمرکز از دل آن ساخته می‌شود، پس
        اگر عقب بیفتد، چرخهٔ تمرکز روی داده‌های کهنه می‌دود.
        """
        if not self.config.enabled:
            return None
        if self.running:
            # پویش قبلی هنوز تمام نشده؛ این نوبت رد می‌شود تا درخواست‌ها
            # روی هم انباشته نشوند.
            self.skipped += 1
            return None

        moment = now or datetime.now(timezone.utc)

        if self.config.full_sweep_enabled and self._elapsed(self.last_full_at, moment) >= (
            self.config.full_interval
        ):
            return ScanJob(kind="full", symbols=(), reason="auto.reason_full_sweep")

        if self.focus_symbols and self._elapsed(self.last_focus_at, moment) >= (
            self.config.focus_interval
        ):
            return ScanJob(
                kind="focus",
                symbols=tuple(self.focus_symbols[: self.config.focus_size]),
                reason="auto.reason_focus",
            )

        # هنوز فهرست تمرکزی نداریم و چرخش کامل خاموش است: یک چرخش کامل
        # لازم است وگرنه سیستم هرگز شروع نمی‌شود.
        if not self.focus_symbols and self.last_full_at is None:
            return ScanJob(kind="full", symbols=(), reason="auto.reason_bootstrap")

        return None

    def seconds_until_next(self, now: datetime | None = None) -> int:
        """
        چند ثانیه تا نوبت بعدی مانده است.

        برای نمایش شمارش معکوس در رابط کاربری؛ عدد منفی برنمی‌گرداند.
        """
        if not self.config.enabled:
            return 0
        moment = now or datetime.now(timezone.utc)

        waits: list[float] = []
        if self.config.full_sweep_enabled:
            waits.append(self.config.full_interval - self._elapsed(self.last_full_at, moment))
        if self.focus_symbols:
            waits.append(self.config.focus_interval - self._elapsed(self.last_focus_at, moment))
        if not waits:
            return 0

        remaining = min(waits)

        # «هرگز اجرا نشده» یعنی زمان سپری‌شده بی‌نهایت است، پس باقی‌مانده
        # منفیِ بی‌نهایت می‌شود و `int()` روی آن OverflowError می‌دهد.
        #
        # این دقیقاً در بدترین لحظه رخ می‌داد: همان تیک اولِ پس از روشن
        # کردن سیگنال‌گیری خودکار، وقتی هنوز هیچ چرخشی اجرا نشده بود. و
        # چون از داخل تایمر صدا زده می‌شد، هر تیک دوباره می‌ترکید.
        #
        # معنای درستِ «هرگز اجرا نشده» این است که همین حالا موعدش است.
        if remaining == float("-inf"):
            return 0
        if remaining == float("inf"):
            # نوبتی در کار نیست؛ شمارش معکوس معنا ندارد
            return 0
        return max(0, int(remaining))

    def _elapsed(self, since: datetime | None, now: datetime) -> float:
        """ثانیه‌های گذشته از یک زمان؛ `None` یعنی «هرگز» و بی‌نهایت است."""
        if since is None:
            return float("inf")
        return (now - since).total_seconds()

    # ------------------------------------------------------------------
    # گزارش نتیجه
    # ------------------------------------------------------------------
    def start(self, job: ScanJob) -> None:
        """اعلام شروع اجرای یک نوبت."""
        self.running = True
        logger.debug("Auto-scan started: %s", job.kind)

    def complete(
        self, job: ScanJob, signals: list[Any], now: datetime | None = None
    ) -> list[str]:
        """
        ثبت پایان یک نوبت و به‌روزرسانی فهرست تمرکز.

        بازگشتی: فهرست تمرکز تازه. فقط چرخش کامل فهرست را از نو می‌سازد؛
        چرخهٔ تمرکز آن را **پالایش** می‌کند تا نمادی که دیگر سیگنال
        نمی‌دهد بیرون برود ولی فهرست یک‌باره خالی نشود.
        """
        moment = now or datetime.now(timezone.utc)
        self.running = False

        if job.kind == "full":
            self.last_full_at = moment
            # چرخش کامل، چرخهٔ تمرکز را هم تازه می‌کند
            self.last_focus_at = moment
            self.focus_symbols = self._rank(signals)
        else:
            self.last_focus_at = moment
            self._refresh_focus(signals)

        logger.debug(
            "Auto-scan finished: %s → focus=%s", job.kind, ", ".join(self.focus_symbols) or "—"
        )
        return list(self.focus_symbols)

    def fail(self, job: ScanJob, now: datetime | None = None) -> None:
        """
        ثبت شکست یک نوبت.

        زمان ثبت می‌شود تا در صورت قطعی شبکه، برنامه هر ثانیه دوباره
        تلاش نکند.
        """
        moment = now or datetime.now(timezone.utc)
        self.running = False
        if job.kind == "full":
            self.last_full_at = moment
        else:
            self.last_focus_at = moment

    def _rank(self, signals: list[Any]) -> list[str]:
        """برگزیدن نمادهای پراطمینان از نتیجهٔ پویش."""
        ranked: list[tuple[float, str]] = []
        seen: set[str] = set()
        for signal in signals:
            symbol = str(getattr(signal, "symbol", "") or "")
            if not symbol or symbol in seen:
                continue
            confidence = float(getattr(signal, "confidence", 0) or 0)
            if confidence < self.config.focus_min_confidence:
                continue
            direction = getattr(signal, "direction", None)
            if str(getattr(direction, "name", direction or "")).upper() == "WAIT":
                # «انتظار» فرصت نیست؛ جای نماد دیگری را در فهرست نگیرد
                continue
            seen.add(symbol)
            ranked.append((confidence, symbol))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [symbol for _confidence, symbol in ranked[: self.config.focus_size]]

    def _refresh_focus(self, signals: list[Any]) -> None:
        """
        به‌روزرسانی ترتیب فهرست تمرکز پس از یک چرخهٔ تمرکز.

        نمادی که ضریبش افت کرده به ته فهرست می‌رود ولی بلافاصله حذف
        نمی‌شود؛ نوسان لحظه‌ای نباید فهرست را بی‌ثبات کند.
        """
        fresh = self._rank(signals)
        if not fresh:
            return
        remaining = [s for s in self.focus_symbols if s not in fresh]
        self.focus_symbols = (fresh + remaining)[: self.config.focus_size]

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def apply_config(self, config: AutoScanConfig) -> None:
        """
        اعمال تنظیمات تازه بدون از دست دادن وضعیت.

        اگر کاربر فاصله را کم کند، نباید منتظر پایان فاصلهٔ قبلی بماند؛
        و اگر اندازهٔ فهرست را کم کند، فهرست همان لحظه کوتاه می‌شود.
        """
        self.config = config.normalized()
        self.focus_symbols = self.focus_symbols[: self.config.focus_size]

    def reset(self) -> None:
        """پاک‌کردن وضعیت — مثلاً پس از تعویض صرافی."""
        self.focus_symbols.clear()
        self.last_focus_at = None
        self.last_full_at = None
        self.running = False
        self.skipped = 0

    def next_run_at(self, now: datetime | None = None) -> datetime | None:
        """زمان تقریبی اجرای بعدی، برای نمایش در رابط کاربری."""
        if not self.config.enabled:
            return None
        moment = now or datetime.now(timezone.utc)
        return moment + timedelta(seconds=self.seconds_until_next(moment))


__all__ = [
    "DEFAULT_FOCUS_INTERVAL",
    "DEFAULT_FOCUS_MIN_CONFIDENCE",
    "DEFAULT_FOCUS_SIZE",
    "DEFAULT_FULL_INTERVAL",
    "MAX_INTERVAL_SECONDS",
    "MIN_INTERVAL_SECONDS",
    "AutoScanConfig",
    "AutoScanScheduler",
    "ScanJob",
    "clamp_interval",
]
