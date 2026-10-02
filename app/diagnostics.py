"""
تشخیص پایداری برنامه — نسخهٔ ۲.۵.۴.

گزارش کاربر: «نرم‌افزار بعد از چند ساعت باز بودن خودکار بسته می‌شود.»
در exe ویندوز (بدون کنسول) `sys.stdout`/`sys.stderr` برابر None است و
برنامه تا این نسخه **هیچ فایل لاگی** نمی‌نوشت؛ یعنی هر خطای کشنده بی‌رد
ناپدید می‌شد. این ماژول:

* `protect_std_streams` — جای خالی stdout/stderr را با devnull پر می‌کند تا
  کتابخانه‌ای که مستقیم روی آن‌ها می‌نویسد برنامه را نکشد.
* `install_crash_handlers` — faulthandler (فروپاشی بومی/Qt) در `crash.log`،
  و excepthook برای نخ اصلی و نخ‌های دیگر که خطا را **ثبت** می‌کنند.
* `SessionMonitor` — پرونده‌ای کوچک با ضربان هر دقیقه (زمان کارکرد، حافظه،
  تعداد نخ‌ها). اگر نشست قبلی بدون خاموشی تمیز تمام شده باشد، نشست بعدی
  دقیقاً می‌گوید کی، بعد از چند ساعت و با چه حافظه‌ای.
* `memory_mb` — حافظهٔ فعلی فرایند بدون وابستگی (psutil لازم نیست).
"""

from __future__ import annotations

import faulthandler
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from app.logging import get_logger

logger = get_logger(__name__)

SESSION_FILE = "session.json"
CRASH_FILE = "crash.log"

_crash_stream: IO[str] | None = None


def protect_std_streams() -> None:
    """در exe بدون کنسول، stdout/stderr وجود ندارند؛ devnull جایشان می‌نشیند."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115


def memory_mb() -> float:
    """حافظهٔ مقیم فرایند به مگابایت (۰ یعنی نامعلوم)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            process = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(
                process, ctypes.byref(counters), counters.cb
            ):
                return counters.WorkingSetSize / (1024 * 1024)
            return 0.0
        with open("/proc/self/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except Exception:  # noqa: BLE001 - تشخیص نباید برنامه را بکشد
        return 0.0
    return 0.0


def install_crash_handlers(logs_dir: Path) -> Path:
    """
    ثبت هر نوع خروج غیرعادی.

    * فروپاشی بومی (segfault در Qt/درایور): faulthandler پشتهٔ همهٔ نخ‌ها را
      در `crash.log` می‌نویسد.
    * استثنای بی‌صاحب نخ اصلی: ثبت در لاگ؛ برنامهٔ گرافیکی ادامه می‌دهد.
    * استثنای بی‌صاحب نخ‌های دیگر: ثبت در لاگ.
    """
    global _crash_stream
    logs_dir.mkdir(parents=True, exist_ok=True)
    crash_path = logs_dir / CRASH_FILE
    try:
        if _crash_stream is None:
            _crash_stream = open(crash_path, "a", encoding="utf-8")  # noqa: SIM115
            _crash_stream.write(f"\n=== session start {datetime.now(UTC).isoformat()} pid={os.getpid()} ===\n")
            _crash_stream.flush()
        faulthandler.enable(file=_crash_stream, all_threads=True)
    except (OSError, RuntimeError, ValueError):
        logger.warning("faulthandler could not be enabled", exc_info=True)

    def excepthook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logger.critical("Unhandled exception (main thread)", exc_info=(exc_type, exc, tb))

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit:
            return
        logger.critical(
            "Unhandled exception in thread %s",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_hook
    return crash_path


def install_qt_message_handler() -> None:
    """پیام‌های هشدار/خطای Qt به لاگ برنامه (در exe جای دیگری ندارند)."""
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except ImportError:
        return
    qt_logger = get_logger("qt")

    def handler(mode: Any, _context: Any, message: str) -> None:
        if mode == QtMsgType.QtFatalMsg:
            qt_logger.critical("Qt fatal: %s", message)
            flush_logs()
        elif mode == QtMsgType.QtCriticalMsg:
            qt_logger.error("Qt: %s", message)
        elif mode == QtMsgType.QtWarningMsg:
            qt_logger.warning("Qt: %s", message)

    qInstallMessageHandler(handler)


def flush_logs() -> None:
    """خالی کردن بافر همهٔ Handlerها — پیش از خروج احتمالی."""
    import logging

    for handler in logging.getLogger().handlers:
        try:
            handler.flush()
        except Exception:  # noqa: BLE001
            pass


@dataclass
class PreviousSession:
    """خلاصهٔ نشست قبلی که بدون خاموشی تمیز تمام شد."""

    started_at: str
    last_heartbeat: str
    uptime_hours: float
    memory_mb: float
    peak_memory_mb: float
    threads: int
    extra: dict[str, Any]


class SessionMonitor:
    """
    ضربان نشست در `session.json`.

    شروع: اگر پرونده‌ای با `clean=false` بماند یعنی نشست قبلی ناگهان بسته شده
    (فروپاشی، کمبود حافظه، کشته‌شدن فرایند). `previous_unclean` خلاصهٔ آن را
    نگه می‌دارد. هر `heartbeat` حال فعلی را می‌نویسد؛ `mark_clean_exit`
    پایان عادی را ثبت می‌کند.
    """

    def __init__(self, logs_dir: Path, *, clock: Any = time.time) -> None:
        self.path = Path(logs_dir) / SESSION_FILE
        self._clock = clock
        self.started = clock()
        self.peak_memory = 0.0
        self.previous_unclean: PreviousSession | None = None
        self._extra_provider: Any = None

    def start(self) -> PreviousSession | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and not data.get("clean", True):
                self.previous_unclean = PreviousSession(
                    started_at=str(data.get("started_at", "")),
                    last_heartbeat=str(data.get("heartbeat_at", "")),
                    uptime_hours=float(data.get("uptime_hours", 0.0) or 0.0),
                    memory_mb=float(data.get("memory_mb", 0.0) or 0.0),
                    peak_memory_mb=float(data.get("peak_memory_mb", 0.0) or 0.0),
                    threads=int(data.get("threads", 0) or 0),
                    extra=dict(data.get("extra") or {}),
                )
                logger.warning(
                    "Previous session ended unexpectedly: started %s, last heartbeat %s, "
                    "uptime %.2f h, memory %.0f MB (peak %.0f MB), threads %d, extra %s",
                    self.previous_unclean.started_at, self.previous_unclean.last_heartbeat,
                    self.previous_unclean.uptime_hours, self.previous_unclean.memory_mb,
                    self.previous_unclean.peak_memory_mb, self.previous_unclean.threads,
                    self.previous_unclean.extra,
                )
        except (OSError, ValueError, TypeError):
            pass
        self.heartbeat()
        return self.previous_unclean

    def set_extra_provider(self, provider: Any) -> None:
        """تابعی که عددهای اضافی (مثلاً شمار دسته‌های runner) برمی‌گرداند."""
        self._extra_provider = provider

    def snapshot(self, *, clean: bool = False) -> dict[str, Any]:
        memory = memory_mb()
        self.peak_memory = max(self.peak_memory, memory)
        extra: dict[str, Any] = {}
        if self._extra_provider is not None:
            try:
                extra = dict(self._extra_provider() or {})
            except Exception:  # noqa: BLE001
                extra = {"error": "extra provider failed"}
        now = self._clock()
        return {
            "pid": os.getpid(),
            "started_at": datetime.fromtimestamp(self.started, UTC).isoformat(),
            "heartbeat_at": datetime.fromtimestamp(now, UTC).isoformat(),
            "uptime_hours": round((now - self.started) / 3600.0, 3),
            "memory_mb": round(memory, 1),
            "peak_memory_mb": round(self.peak_memory, 1),
            "threads": threading.active_count(),
            "extra": extra,
            "clean": clean,
        }

    def heartbeat(self) -> dict[str, Any]:
        data = self.snapshot()
        self._write(data)
        return data

    def mark_clean_exit(self) -> None:
        self._write(self.snapshot(clean=True))

    def _write(self, data: dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self.path)
        except OSError:
            logger.debug("Session heartbeat could not be written", exc_info=True)


__all__ = [
    "PreviousSession",
    "SessionMonitor",
    "flush_logs",
    "install_crash_handlers",
    "install_qt_message_handler",
    "memory_mb",
    "protect_std_streams",
]
