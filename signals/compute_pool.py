"""
استخر فرایند محاسبهٔ سیگنال — نسخهٔ ۲.۴.۲.

چرا؟
    در ۲.۴.۱ پویش کل بازار روی نخ پس‌زمینه با «دروازهٔ محاسبه» و سقف سهم
    CPU سبک شد؛ ولی پایتون قفل سراسری (GIL) دارد: هر میلی‌ثانیه محاسبهٔ
    pandas در نخ پس‌زمینه، نخ رابط گرافیکی را پس از هر فراخوانی Qt معطل
    می‌کند («کاروان GIL») و برنامه با وجود مصرف CPU متوسط «هنگ» به نظر
    می‌رسد. پروفایل نشان داد ~۹۵٪ زمان هر نماد صرف محاسبهٔ اندیکاتور،
    ساختار و سطوح است — دقیقاً بخشی که این ماژول به فرایند جدا می‌برد.

طراحی
    * فقط در پویش انبوه (`market.engine.is_bulk_fetch()`) استفاده می‌شود؛
      تحلیل تک‌نماد، نمودار و معاملهٔ خودکار دست‌نخورده می‌مانند.
    * کندل در فرایند اصلی می‌ماند؛ فقط فهرست کندل‌ها فرستاده و نتیجهٔ
      قابل pickle (خلاصهٔ اندیکاتورها، ساختار، سطوح، روند، ATR) برگردانده
      می‌شود. منطق همان `signals.engine.compute_timeframe_analysis` است.
    * حداکثر ۲ کارگر با اولویت پایین سیستم‌عامل؛ سیستم کاربر درگیر نمی‌شود.
    * هر خطا (خرابی استخر، pickle، ...) → `None` و موتور همان محاسبهٔ محلی
      قبلی را انجام می‌دهد؛ پس از چند خطای پیاپی استخر برای این نشست خاموش
      می‌شود. پس از مدتی بیکاری کارگرها بسته می‌شوند تا حافظه آزاد شود.

این ماژول نباید PySide وارد کند (در فرایند کارگر هم بارگذاری می‌شود).
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import sys
import threading
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: سقف کارگرها؛ بیشتر از این، سیستم کاربر را درگیر می‌کند
MAX_WORKERS = 2
#: بستن کارگرها پس از این مدت بیکاری (ثانیه)
IDLE_SHUTDOWN_SECONDS = 180.0
#: پس از این تعداد خطای پیاپی، استخر برای این نشست خاموش می‌شود
MAX_CONSECUTIVE_FAILURES = 3
#: کلاس اولویت «زیر عادی» ویندوز
_BELOW_NORMAL_PRIORITY_CLASS = 0x00004000

# ---------------------------------------------------------------- سمت کارگر
_worker_engine: Any = None


def default_worker_count(cpu_count: int | None = None) -> int:
    """تعداد کارگر: دو هستهٔ آزاد برای رابط و سیستم، حداکثر ۲."""
    cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    return max(1, min(MAX_WORKERS, cpus - 2))


def lower_process_priority() -> bool:
    """پایین‌آوردن اولویت فرایند جاری؛ شکست بی‌خطر است."""
    try:
        if sys.platform == "win32":
            import ctypes  # noqa: PLC0415

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            return bool(
                kernel32.SetPriorityClass(
                    kernel32.GetCurrentProcess(), _BELOW_NORMAL_PRIORITY_CLASS
                )
            )
        os.nice(10)
        return True
    except Exception:  # noqa: BLE001 - اولویت فقط بهینه‌سازی است
        return False


def _init_worker() -> None:
    """آماده‌سازی کارگر: اولویت پایین + ثبت اندیکاتورها."""
    lower_process_priority()
    _ensure_worker_engine()


def _ensure_worker_engine() -> Any:
    global _worker_engine  # noqa: PLW0603
    if _worker_engine is None:
        from indicators.engine import IndicatorEngine  # noqa: PLC0415
        from indicators.registry import (  # noqa: PLC0415
            indicator_registry,
            register_builtin_indicators,
        )

        if not indicator_registry.available():
            register_builtin_indicators()
        _worker_engine = IndicatorEngine()
    return _worker_engine


def compute_timeframe_job(
    symbol: str,
    timeframe: str,
    candles: list[Any],
    default_parameters: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, Any]:
    """
    کار کارگر: تحلیل یک تایم‌فریم.

    بازگشتی: ("ok", payload بدون کندل) یا ("error", متن خطا). استثنا عمداً
    به فرایند اصلی پرتاب نمی‌شود چون استثناهای برنامه همیشه قابل unpickle
    نیستند؛ فرایند اصلی در خطا همان محاسبهٔ محلی را انجام می‌دهد.
    """
    try:
        from signals.engine import compute_timeframe_analysis  # noqa: PLC0415

        engine = _ensure_worker_engine()
        engine._default_parameters = {  # noqa: SLF001 - رونوشت تنظیم کاربر
            str(name).upper(): dict(values)
            for name, values in (default_parameters or {}).items()
        }
        payload = compute_timeframe_analysis(engine, symbol, timeframe, candles)
        payload.pop("candles", None)
        return "ok", payload
    except Exception as exc:  # noqa: BLE001
        return "error", f"{exc.__class__.__name__}: {exc}"


# ---------------------------------------------------------------- سمت اصلی
class ComputePool:
    """مدیر تنبل استخر فرایند؛ همهٔ متدها امن در برابر خطا هستند."""

    def __init__(
        self,
        workers: int | None = None,
        *,
        idle_shutdown: float = IDLE_SHUTDOWN_SECONDS,
    ) -> None:
        self._workers = max(1, int(workers or default_worker_count()))
        self._idle_shutdown = float(idle_shutdown)
        self._executor: ProcessPoolExecutor | None = None
        self._lock = threading.Lock()
        self._disabled = False
        self._failures = 0
        self._inflight = 0
        self._idle_handle: asyncio.TimerHandle | None = None
        self.jobs_done = 0
        self.fallbacks = 0

    # ---------------------------------------------------------- وضعیت
    @property
    def workers(self) -> int:
        return self._workers

    @property
    def enabled(self) -> bool:
        return not self._disabled

    @property
    def running(self) -> bool:
        return self._executor is not None

    def disable(self) -> None:
        self._disabled = True
        self.shutdown()

    # ---------------------------------------------------------- اجرا
    def _ensure_executor(self) -> ProcessPoolExecutor | None:
        if self._disabled:
            return None
        with self._lock:
            if self._executor is None:
                try:
                    # spawn در همهٔ سیستم‌عامل‌ها: fork پس از ساخت نخ‌های Qt و
                    # شبکه ناامن است و رفتار ویندوز را هم یکسان می‌کند.
                    context = multiprocessing.get_context("spawn")
                    self._executor = ProcessPoolExecutor(
                        max_workers=self._workers,
                        mp_context=context,
                        initializer=_init_worker,
                    )
                    logger.info("Compute pool started with %d worker(s)", self._workers)
                except Exception:  # noqa: BLE001
                    logger.warning("Compute pool unavailable; using local compute",
                                   exc_info=True)
                    self._disabled = True
                    return None
            return self._executor

    async def compute_timeframe(
        self,
        symbol: str,
        timeframe: str,
        candles: list[Any],
        default_parameters: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """تحلیل یک تایم‌فریم در کارگر؛ None یعنی «محلی حساب کن»."""
        executor = self._ensure_executor()
        if executor is None:
            return None
        loop = asyncio.get_running_loop()
        self._cancel_idle()
        self._inflight += 1
        try:
            status, payload = await loop.run_in_executor(
                executor, compute_timeframe_job, symbol, timeframe, list(candles),
                default_parameters or {},
            )
        except BrokenProcessPool:
            logger.warning("Compute pool broke; falling back to local compute")
            self._record_failure(broken=True)
            return None
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - pickle یا خطای ناشناخته
            logger.debug("Compute pool job failed for %s %s", symbol, timeframe,
                         exc_info=True)
            self._record_failure()
            return None
        finally:
            self._inflight -= 1
            self._schedule_idle(loop)

        if status != "ok":
            # خطای محاسبه (مثلاً دادهٔ خراب): محلی تکرار شود تا پیام دقیق
            # همان مسیر قبلی را بدهد. شمارش خرابی استخر نیست.
            self.fallbacks += 1
            return None
        self._failures = 0
        self.jobs_done += 1
        return payload

    def _record_failure(self, *, broken: bool = False) -> None:
        self.fallbacks += 1
        self._failures += 1
        if broken:
            self.shutdown()
        if self._failures >= MAX_CONSECUTIVE_FAILURES:
            logger.warning("Compute pool disabled after %d failures", self._failures)
            self.disable()

    # ---------------------------------------------------------- بیکاری/توقف
    def _cancel_idle(self) -> None:
        if self._idle_handle is not None:
            self._idle_handle.cancel()
            self._idle_handle = None

    def _schedule_idle(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._inflight or self._idle_shutdown <= 0 or loop.is_closed():
            return
        self._cancel_idle()
        try:
            self._idle_handle = loop.call_later(self._idle_shutdown, self._on_idle)
        except RuntimeError:
            self._idle_handle = None

    def _on_idle(self) -> None:
        self._idle_handle = None
        if not self._inflight:
            logger.debug("Compute pool idle; releasing workers")
            self.shutdown()

    def shutdown(self) -> None:
        """بستن کارگرها بدون انتظار؛ فراخوانی مکرر بی‌خطر است."""
        self._cancel_idle()
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:  # noqa: BLE001
                logger.debug("Compute pool shutdown error", exc_info=True)
