"""
پویشگر بازار — گرفتن سیگنال از همهٔ نمادها، یکی‌یکی.

چرا این ماژول جدا از `SignalEngine` است؟
    موتور سیگنال کارش تحلیل **یک** نماد است و باید همان بماند. پویش کل
    بازار مسئلهٔ دیگری است: ترتیب و اولویت نمادها، محدودکردن هم‌زمانی تا
    صرافی محدودمان نکند، گزارش پیشرفت، لغو نیمه‌کاره، و مرتب‌سازی نتیجه.
    ریختن این‌ها داخل موتور، هم آن را سنگین می‌کرد و هم آزمونش را سخت.

چرا فقط موتور ریاضی؟
    کاربر صریح گفت: «از آنجایی که این کار توکن هوش مصنوعی زیاد می‌سوزاند،
    این کار با موتور ریاضی انجام بشود و بعداً بشود در جزئیات هر کدام را
    که خواستم جداگانه بدهم هوش مصنوعی تحلیل کند.»

    پس پویشگر **هرگز** هوش مصنوعی را صدا نمی‌زند. یک پویش روی ۳۰۰ نماد
    با هوش مصنوعی یعنی ۳۰۰ درخواست و هزینهٔ گزاف؛ با موتور ریاضی یعنی
    صفر توکن. تحلیل هوش مصنوعی بعداً و فقط روی نمادی که کاربر انتخاب
    می‌کند اجرا می‌شود.

نکتهٔ کارایی:
    نمادها با هم‌زمانی محدود (`concurrency`) پویش می‌شوند. کاملاً ترتیبی
    یعنی دقیقه‌ها انتظار؛ کاملاً موازی یعنی محدودشدن از سوی صرافی
    (429) و داده‌های ناقص. مقدار پیش‌فرض از تنظیمات
    `performance.parallel_requests` می‌آید.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from app.core.constants import SignalDirection
from app.core.models import TradingSignal
from app.logging import get_logger

logger = get_logger(__name__)

#: بیشینهٔ نمادی که یک پویش بررسی می‌کند، وقتی کاربر سقفی نداده باشد.
#: بازارهایی مثل LBank بیش از ۱۳۰۰ نماد دارند که بیشترشان بی‌نقدشوندگی
#: و بی‌فایده‌اند؛ پویش همهٔ آن‌ها فقط وقت و پهنای باند می‌سوزاند.
DEFAULT_SCAN_LIMIT = 120

#: نسخهٔ ۲.۴.۱ — سقف سهم CPU نخ شبکه در پویش دستی (۰ تا ۱).
#:
#: همهٔ کارهای ناهمگام برنامه (وب‌سوکت، داشبورد، معاملهٔ خودکار، پویش) روی
#: یک حلقهٔ asyncio در یک نخ اجرا می‌شوند و محاسبهٔ اندیکاتورها هم هم‌گام
#: است. پویش کل صرافی این نخ را صددرصد مشغول می‌کرد: رابط کاربری (که با GIL
#: رقابت می‌کند) هنگ می‌کرد و پینگ وب‌سوکت‌ها جا می‌ماند. با این سقف، پس از
#: هر نماد اگر مصرف CPU بیش از سهم مجاز بوده، پویش کمی مکث می‌کند.
DEFAULT_CPU_DUTY = 0.6
#: سقف سهم CPU برای پویش پس‌زمینهٔ خودکار (کاربر منتظرش نیست)
BACKGROUND_CPU_DUTY = 0.35
#: بلندترین مکث یک‌باره (ثانیه)؛ مانع «یخ‌زدن» ظاهری پویش می‌شود
MAX_PACE_SLEEP = 2.0
#: طول پنجرهٔ سنجش مصرف CPU (ثانیه)
PACE_WINDOW_SECONDS = 10.0


class CpuGovernor:
    """
    محدودکنندهٔ سهم CPU نخ جاری.

    `time.thread_time()` مصرف CPU همین نخ (حلقهٔ asyncio) را می‌دهد، شامل
    کارهای دیگری که روی همان حلقه اجرا می‌شوند؛ پس سقف روی **کل** بار نخ
    اعمال می‌شود و پویش سهم بقیه را نمی‌خورد.
    """

    def __init__(self, duty: float | None, *, clock: Callable[[], float] = time.monotonic,
                 cpu_clock: Callable[[], float] = time.thread_time) -> None:
        try:
            value = float(duty) if duty is not None else 1.0
        except (TypeError, ValueError):
            value = DEFAULT_CPU_DUTY
        self.duty = max(0.05, min(1.0, value))
        self._clock = clock
        self._cpu_clock = cpu_clock
        self._reset()
        self.slept = 0.0

    def _reset(self) -> None:
        self._wall0 = self._clock()
        self._cpu0 = self._cpu_clock()

    def delay(self) -> float:
        """مکث لازم (ثانیه) تا مصرف پنجرهٔ جاری به سقف برگردد."""
        if self.duty >= 1.0:
            return 0.0
        wall = self._clock() - self._wall0
        cpu = self._cpu_clock() - self._cpu0
        needed = cpu / self.duty - wall
        if wall >= PACE_WINDOW_SECONDS and needed <= 0:
            self._reset()
        return max(0.0, min(MAX_PACE_SLEEP, needed))

    async def pace(self) -> None:
        """نوبت‌دادن به بقیهٔ حلقه و در صورت نیاز مکث کوتاه."""
        wait = self.delay()
        self.slept += wait
        await asyncio.sleep(wait)


@dataclass(slots=True)
class ScanProgress:
    """گزارش لحظه‌ای پیشرفت پویش."""

    done: int
    total: int
    symbol: str = ""
    found: int = 0

    @property
    def percent(self) -> int:
        """درصد پیشرفت (۰ تا ۱۰۰)."""
        if self.total <= 0:
            return 0
        return int(self.done * 100 / self.total)


@dataclass(slots=True)
class ScanResult:
    """
    نتیجهٔ یک پویش کامل.

    `signals` بر پایهٔ ضریب اطمینان **نزولی** مرتب است، پس ردیف نخست
    همان «بالاترین ضریب اطمینان» است که کاربر خواست بالا بیاید.
    """

    signals: list[TradingSignal] = field(default_factory=list)
    scanned: int = 0
    failed: int = 0
    duration_seconds: float = 0.0
    cancelled: bool = False

    @property
    def actionable(self) -> list[TradingSignal]:
        """سیگنال‌هایی که جهت دارند (انتظار کنار گذاشته می‌شود)."""
        return [s for s in self.signals if s.direction is not SignalDirection.WAIT]

    def top(self, count: int = 10) -> list[TradingSignal]:
        """چند سیگنال برتر بر پایهٔ ضریب اطمینان."""
        return self.signals[: max(0, int(count))]


class MarketScanner:
    """
    پویش نمادهای بازار با موتور ریاضی.

    وابستگی‌ها تزریق می‌شوند (موتور بازار و موتور سیگنال) تا در آزمون
    بتوان جایگزینشان کرد و پویش بدون شبکه آزموده شود.
    """

    def __init__(
        self,
        market_engine: Any,
        signal_engine: Any,
        *,
        concurrency: int = 4,
        scan_limit: int = DEFAULT_SCAN_LIMIT,
    ) -> None:
        self._market = market_engine
        self._signals = signal_engine
        self._concurrency = max(1, int(concurrency))
        self._scan_limit = max(1, int(scan_limit))

    # ------------------------------------------------------------------
    # انتخاب نمادها
    # ------------------------------------------------------------------
    async def candidate_symbols(
        self,
        limit: int | None = None,
        *,
        universe: str = "top",
        filters: Any = None,
    ) -> list[str]:
        """
        فهرست نمادهایی که ارزش پویش دارند.

        مرتب‌سازی بر پایهٔ **گردش مالی ۲۴ ساعته** است نه حجم، چون حجم بر
        حسب واحد پایه است و بین ارزان و گران قابل مقایسه نیست: یک میلیون
        واحد از یک توکن بی‌ارزش، بازار پرگردشی نمی‌سازد.

        اگر گرفتن تیکرها شکست بخورد، به فهرست خام نمادها برمی‌گردیم تا
        پویش به‌کلی از کار نیفتد.
        """
        from signals.scan_universe import UNIVERSE_ALL, normalize_universe

        mode = normalize_universe(universe)
        if mode == UNIVERSE_ALL or filters is not None:
            # نسخهٔ ۲.۴.۰: کل بازار صرافی یا پالایش هوشمند (scan_universe).
            return await self._smart_candidates(mode, limit, filters)

        cap = max(1, int(limit or self._scan_limit))
        try:
            tickers = await self._market.get_all_tickers()
        except Exception:  # noqa: BLE001 - نبود تیکر نباید پویش را بکشد
            logger.warning("Could not rank symbols by turnover; falling back", exc_info=True)
            tickers = []

        if tickers:
            ranked = sorted(
                tickers,
                key=lambda t: float(getattr(t, "turnover_24h", 0.0) or 0.0),
                reverse=True,
            )
            return [str(t.symbol) for t in ranked[:cap]]

        symbols = await self._market.get_symbols()
        return [str(getattr(s, "symbol", s)) for s in symbols[:cap]]

    async def _smart_candidates(self, mode: str, limit: int | None, filters: Any) -> list[str]:
        """جهان پویش هوشمند: تیکرها برای اولویت، فهرست نمادها برای پوشش کامل."""
        from signals.scan_universe import UNIVERSE_ALL, build_universe

        try:
            tickers = await self._market.get_all_tickers()
        except Exception:  # noqa: BLE001 - بدون تیکر هم فهرست نمادها کافی است
            logger.warning("Could not load tickers for the scan universe", exc_info=True)
            tickers = []
        symbols: list[Any] = []
        if mode == UNIVERSE_ALL or not tickers:
            try:
                symbols = list(await self._market.get_symbols())
            except Exception:  # noqa: BLE001
                logger.warning("Could not load the exchange symbol list", exc_info=True)
                symbols = []
        cap = None if mode == UNIVERSE_ALL else max(1, int(limit or self._scan_limit))
        return build_universe(tickers, symbols, mode=mode, limit=cap, filters=filters)

    # ------------------------------------------------------------------
    # پویش
    # ------------------------------------------------------------------
    async def scan(
        self,
        symbols: Sequence[str] | None = None,
        timeframes: Iterable[str] | None = None,
        *,
        limit: int | None = None,
        min_confidence: int = 0,
        include_wait: bool = False,
        on_progress: Callable[[ScanProgress], None] | None = None,
        universe: str = "top",
        filters: Any = None,
        on_signal: Callable[[TradingSignal], None] | None = None,
        cpu_duty: float | None = DEFAULT_CPU_DUTY,
    ) -> ScanResult:
        """
        پویش نمادها و بازگرداندن سیگنال‌ها به ترتیب ضریب اطمینان.

        پارامترها:
            symbols        : فهرست دلخواه؛ خالی یعنی پرگردش‌ترین‌های بازار
            timeframes     : تایم‌فریم‌های موتور سیگنال
            min_confidence : سیگنال‌های ضعیف‌تر از این حد کنار گذاشته می‌شوند
            include_wait   : آیا «انتظار» هم در نتیجه بیاید
            on_progress    : پس‌فراخوانِ گزارش پیشرفت
            universe       : «top» پرگردش‌ترین‌ها تا limit؛ «all» همهٔ نمادهای صرافی
            filters        : UniverseFilter برای پالایش هوشمند (اختیاری)
            on_signal      : هر سیگنالِ پذیرفته‌شده همان لحظه گزارش می‌شود
                             (نمایش زنده؛ نتیجهٔ نیمه‌کاره با توقف گم نمی‌شود)

        **لغو:** این متد یک کوروتین معمولی است، پس `asyncio.CancelledError`
        را دست‌نخورده بالا می‌فرستد تا لایهٔ بالا بتواند پویش را قطع کند؛
        ولی نتیجهٔ جزئی از دست نمی‌رود چون پیشرفت هم‌زمان گزارش شده است.

        **تضمین:** شکست یک نماد، کل پویش را متوقف نمی‌کند. بازارهای بزرگ
        همیشه چند نماد تازه‌فهرست‌شده یا بی‌کندل دارند.
        """
        from market.engine import bulk_fetch

        with bulk_fetch():
            return await self._scan(
                symbols, timeframes, limit=limit, min_confidence=min_confidence,
                include_wait=include_wait, on_progress=on_progress, universe=universe,
                filters=filters, on_signal=on_signal, cpu_duty=cpu_duty,
            )

    async def _wait_for_cooldown(self) -> None:
        """
        در مکث محدودیت نرخ صرافی، پویش صبر می‌کند.

        بدون این، هر نمادِ باقی‌مانده فوراً با خطای «مکث» شکست می‌خورد (و
        به‌سراغ کندل ذخیره‌شده در پایگاه داده می‌رفت) — یعنی صدها نماد
        «پویش‌شده» بدون داده و فشار بی‌دلیل روی دیسک.
        """
        for _attempt in range(10):
            value = getattr(self._market, "rest_cooldown_remaining", 0.0)
            # فقط عدد واقعی؛ موتورهای ساختگی/Mock نباید پویش را معطل کنند
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return
            remaining = float(value)
            if remaining <= 0:
                return
            await asyncio.sleep(min(remaining, 30.0))

    async def _scan(
        self,
        symbols: Sequence[str] | None,
        timeframes: Iterable[str] | None,
        *,
        limit: int | None,
        min_confidence: int,
        include_wait: bool,
        on_progress: Callable[[ScanProgress], None] | None,
        universe: str,
        filters: Any,
        on_signal: Callable[[TradingSignal], None] | None,
        cpu_duty: float | None,
    ) -> ScanResult:
        started = time.monotonic()
        governor = CpuGovernor(cpu_duty)
        frames = list(timeframes or [])
        targets = [str(s).strip().upper() for s in (symbols or []) if str(s).strip()]
        if not targets:
            targets = await self.candidate_symbols(limit, universe=universe, filters=filters)
        elif limit:
            targets = targets[: int(limit)]

        result = ScanResult()
        total = len(targets)
        if total == 0:
            return result

        semaphore = asyncio.Semaphore(self._concurrency)
        done = 0
        lock = asyncio.Lock()

        async def worker(symbol: str) -> None:
            """پویش یک نماد؛ خطایش فقط شمرده می‌شود."""
            nonlocal done
            async with semaphore:
                signal: TradingSignal | None = None
                await governor.pace()
                await self._wait_for_cooldown()
                try:
                    signal = await self._signals.generate(symbol, frames or None)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001 - نماد خراب، پویش سالم
                    logger.debug("Scan failed for %s", symbol, exc_info=True)

                async with lock:
                    done += 1
                    if signal is None:
                        result.failed += 1
                    else:
                        result.scanned += 1
                        keep = include_wait or signal.direction is not SignalDirection.WAIT
                        if keep and int(signal.confidence or 0) >= int(min_confidence):
                            result.signals.append(signal)
                            if on_signal is not None:
                                try:
                                    on_signal(signal)
                                except Exception:  # noqa: BLE001 - نمایش نباید پویش را بکشد
                                    logger.debug("Scan signal callback failed", exc_info=True)
                    if on_progress is not None:
                        try:
                            on_progress(
                                ScanProgress(
                                    done=done,
                                    total=total,
                                    symbol=symbol,
                                    found=len(result.signals),
                                )
                            )
                        except Exception:  # noqa: BLE001 - گزارش نباید پویش را بکشد
                            logger.debug("Scan progress callback failed", exc_info=True)

        try:
            await asyncio.gather(*(worker(symbol) for symbol in targets))
        except asyncio.CancelledError:
            result.cancelled = True
            raise
        finally:
            # مرتب‌سازی حتی هنگام لغو انجام می‌شود تا نتیجهٔ جزئی هم
            # قابل استفاده باشد.
            result.signals.sort(key=_scan_sort_key, reverse=True)
            result.duration_seconds = time.monotonic() - started

        return result


def _scan_sort_key(signal: TradingSignal) -> tuple[int, float]:
    """
    کلید مرتب‌سازی: نخست ضریب اطمینان، سپس نسبت ریسک به ریوارد.

    چرا دو کلید؟ چون چند نماد ممکن است ضریب اطمینان برابر بگیرند؛ در آن
    صورت معامله‌ای که بازده بهتری نسبت به ریسکش دارد باید بالاتر بنشیند.
    """
    return (int(signal.confidence or 0), float(signal.risk_reward or 0.0))


__all__ = [
    "DEFAULT_SCAN_LIMIT",
    "MarketScanner",
    "ScanProgress",
    "ScanResult",
]
