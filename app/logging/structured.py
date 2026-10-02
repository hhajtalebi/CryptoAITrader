"""
لاگ ساختاریافتهٔ سراسری — نسخهٔ ۲.۶.۰.

مسیر یک رکورد:

    logger.info(...) ──► SafeQueueHandler (فقط put_nowait؛ بدون I/O در مسیر داغ)
                              │
                       QueueListener (یک رشتهٔ پس‌زمینه)
                              │  _Fanout
          ┌───────────────────┼─────────────────────┬────────────────────┐
     LogBuffer (UI زنده)   CategoryRouterHandler   AuditStoreHandler (SQLite،
                           logs/<دسته>/<دسته>-روز.jsonl  فقط رویدادهای audit)
                           + errors/ برای ERROR+
                           + audit/ برای رویدادهای audit

- **غیرمسدودکننده:** مسیر ورود معامله فقط یک `put_nowait` می‌بیند. صف پر →
  رکورد دور ریخته و شمرده می‌شود؛ معامله هرگز منتظر دیسک نمی‌ماند.
- **خطای لاگر معامله را متوقف نمی‌کند:** همهٔ `handleError`ها بی‌صدا شمارش می‌کنند.
- **چرخش:** یک فایل برای هر روز و هر دسته؛ بیش از `max_bytes` → `.1`، `.2`، …؛
  فایل‌های قدیمی‌تر از `retention_days` و بیش از `max_files` حذف می‌شوند.
- **داده حساس:** هر خط JSON پیش از نوشتن از `SensitiveDataFilter.mask` می‌گذرد.

لاگ‌های قبلی (`app.log` و کنسول) دست‌نخورده‌اند؛ این لایه کنارشان اضافه می‌شود.
"""

from __future__ import annotations

import atexit
import json
import logging
import logging.handlers
import os
import queue
import re
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.logging.categories import LogCategory, category_for_logger, parse_category

#: کلیدهای `extra` که به فیلدهای سطح‌اول رویداد تبدیل می‌شوند
EVENT_FIELDS = ("event", "symbol", "trade_id", "reason_code", "scan_id", "correlation_id")

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_RETENTION_DAYS = 14
DEFAULT_MAX_FILES = 60
DEFAULT_BUFFER_CAPACITY = 5000
DEFAULT_QUEUE_SIZE = 50_000

_FILE_RE = re.compile(r"^(?P<stem>[a-z_]+)-(?P<day>\d{4}-\d{2}-\d{2})(?:\.(?P<part>\d+))?\.jsonl$")


# ---------------------------------------------------------------------------
# رکورد → رویداد
# ---------------------------------------------------------------------------


def _json_safe(value: Any, depth: int = 0) -> Any:
    """تبدیل مقدار به چیزی که JSON بپذیرد (عمق محدود؛ هرگز استثنا نمی‌دهد)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if depth > 4:
        return str(value)[:200]
    if isinstance(value, dict):
        return {str(k): _json_safe(v, depth + 1) for k, v in list(value.items())[:200]}
    if isinstance(value, (list, tuple, set, frozenset, deque)):
        return [_json_safe(v, depth + 1) for v in list(value)[:200]]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int, float)):
        return value.value  # Enum
    return str(value)[:500]


def record_category(record: logging.LogRecord) -> LogCategory:
    """دسته: صریح (`extra.category`) وگرنه از نام لاگر."""
    explicit = parse_category(getattr(record, "category", None))
    return explicit or category_for_logger(record.name)


def record_to_event(record: logging.LogRecord) -> dict[str, Any]:
    """
    رویداد ساختاریافته از یک LogRecord (نتیجه روی رکورد کش می‌شود).

    کلیدها: ts, epoch, level, category, module, message, event, symbol, trade_id,
    reason_code, scan_id, correlation_id, context, exc, audit, persist.
    """
    cached = getattr(record, "_cai_event", None)
    if cached is not None:
        return cached
    try:
        message = record.getMessage()
    except Exception:  # noqa: BLE001 - قالب خراب نباید رکورد را بکشد
        message = str(record.msg)
    exc_text = getattr(record, "exc_text", None) or ""
    if not exc_text and record.exc_info:
        try:
            exc_text = "".join(traceback.format_exception(*record.exc_info))
        except Exception:  # noqa: BLE001
            exc_text = ""
    event: dict[str, Any] = {
        "ts": datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="milliseconds"),
        "epoch": float(record.created),
        "level": record.levelname,
        "category": record_category(record).value,
        "module": record.name,
        "message": message,
        "context": _json_safe(getattr(record, "context", None) or {}),
        "audit": bool(getattr(record, "audit", False)),
        "persist": bool(getattr(record, "persist", True)),
    }
    for name in EVENT_FIELDS:
        value = getattr(record, name, None)
        if value not in (None, ""):
            event[name] = _json_safe(value)
    if exc_text:
        event["exc"] = exc_text[-8000:]
    try:
        record._cai_event = event  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    return event


def _mask(text: str) -> str:
    from app.logging.logger import SensitiveDataFilter

    return SensitiveDataFilter.mask(text)


def event_to_line(event: dict[str, Any]) -> str:
    """یک خط JSON (بدون فیلدهای داخلی) با پوشاندن دادهٔ حساس."""
    public = {k: v for k, v in event.items() if k not in ("persist", "seq")}
    return _mask(json.dumps(public, ensure_ascii=False, default=str, separators=(",", ":")))


# ---------------------------------------------------------------------------
# بافر حافظه برای نمایش زنده
# ---------------------------------------------------------------------------


class LogBuffer:
    """حلقهٔ ثابت از آخرین رویدادها با شمارهٔ ترتیب یکنواخت (برای poll رابط)."""

    def __init__(self, capacity: int = DEFAULT_BUFFER_CAPACITY) -> None:
        self._items: deque[dict[str, Any]] = deque(maxlen=max(10, int(capacity)))
        self._lock = threading.Lock()
        self._seq = 0

    @property
    def last_seq(self) -> int:
        return self._seq

    def append(self, event: dict[str, Any]) -> int:
        with self._lock:
            self._seq += 1
            item = dict(event)
            item["seq"] = self._seq
            self._items.append(item)
            return self._seq

    def since(self, seq: int, limit: int | None = None) -> list[dict[str, Any]]:
        """رویدادهای جدیدتر از `seq` (به ترتیب زمان)."""
        with self._lock:
            # از انتها به عقب: هر poll فقط رکوردهای تازه را می‌پیماید
            items: list[dict[str, Any]] = []
            for event in reversed(self._items):
                if event["seq"] <= seq:
                    break
                items.append(event)
        items.reverse()
        return items[-limit:] if limit else items

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


class RingBufferHandler(logging.Handler):
    """نوشتن هر رکورد در `LogBuffer`."""

    def __init__(self, buffer: LogBuffer) -> None:
        super().__init__(logging.DEBUG)
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.buffer.append(record_to_event(record))
        except Exception:  # noqa: BLE001
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        _count_failure()


# ---------------------------------------------------------------------------
# فایل روزانه با سقف حجم
# ---------------------------------------------------------------------------


class DailySizeRotatingFile:
    """
    فایل JSONL روزانه: `<stem>-YYYY-MM-DD.jsonl`.

    بیش از `max_bytes` → فایل فعلی به `.N` تغییر نام می‌دهد و فایل تازه باز
    می‌شود. با هر روز تازه و هر چرخش، فایل‌های قدیمی‌تر از `retention_days`
    و اضافه بر `max_files` پاک می‌شوند.
    """

    def __init__(
        self,
        directory: Path,
        stem: str,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_files: int = DEFAULT_MAX_FILES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.stem = stem
        self.max_bytes = max(1024, int(max_bytes))
        self.retention_days = max(1, int(retention_days))
        self.max_files = max(2, int(max_files))
        self._clock = clock or datetime.now
        self._day: str = ""
        self._handle: Any = None
        self._size = 0

    def path_for(self, day: str) -> Path:
        return self.directory / f"{self.stem}-{day}.jsonl"

    def _open(self, day: str) -> None:
        self.close()
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(day)
        self._handle = open(path, "a", encoding="utf-8")  # noqa: SIM115
        self._size = path.stat().st_size if path.exists() else 0
        self._day = day

    def _rotate(self) -> None:
        path = self.path_for(self._day)
        self.close()
        part = 1
        while (self.directory / f"{self.stem}-{self._day}.{part}.jsonl").exists():
            part += 1
        try:
            os.replace(path, self.directory / f"{self.stem}-{self._day}.{part}.jsonl")
        except OSError:
            pass
        self._open(self._day)
        self.cleanup()

    def write(self, line: str) -> None:
        day = self._clock().strftime("%Y-%m-%d")
        if day != self._day or self._handle is None:
            self._open(day)
            self.cleanup()
        data = line + "\n"
        size = len(data.encode("utf-8"))
        if self._size and self._size + size > self.max_bytes:
            self._rotate()
        self._handle.write(data)
        self._handle.flush()
        self._size += size

    def files(self) -> list[Path]:
        """فایل‌های همین دسته، قدیمی‌ترین اول."""
        found = []
        if not self.directory.exists():
            return found
        for path in self.directory.iterdir():
            match = _FILE_RE.match(path.name)
            if match and match["stem"] == self.stem:
                found.append((match["day"], int(match["part"] or 10**6), path))
        return [p for _d, _part, p in sorted(found)]

    def cleanup(self) -> None:
        """حذف فایل‌های قدیمی‌تر از نگه‌داری و اضافه بر سقف تعداد."""
        cutoff = (self._clock() - timedelta(days=self.retention_days)).strftime("%Y-%m-%d")
        files = self.files()
        current = self.path_for(self._day) if self._day else None
        for path in files:
            match = _FILE_RE.match(path.name)
            if match and match["day"] < cutoff and path != current:
                _unlink(path)
        files = [p for p in self.files() if p != current]
        overflow = len(files) + (1 if current else 0) - self.max_files
        for path in files[: max(0, overflow)]:
            _unlink(path)

    def close(self) -> None:
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError:
                pass
        self._handle = None


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


class CategoryRouterHandler(logging.Handler):
    """
    هر رکورد → فایل دستهٔ خودش؛ ERROR+ → `errors/` هم؛ رویداد audit → `audit/` هم.

    رکوردهایی با `persist=False` (خلاصهٔ لحظه‌ای هر ثانیهٔ اولترا) فقط به
    بافر زنده می‌روند و فایل را پر نمی‌کنند.
    """

    def __init__(
        self,
        base_dir: Path,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_files: int = DEFAULT_MAX_FILES,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__(logging.DEBUG)
        self.base_dir = Path(base_dir)
        self._options = {"max_bytes": max_bytes, "retention_days": retention_days,
                         "max_files": max_files, "clock": clock}
        self._files: dict[str, DailySizeRotatingFile] = {}

    def file_for(self, category: str) -> DailySizeRotatingFile:
        handle = self._files.get(category)
        if handle is None:
            handle = DailySizeRotatingFile(self.base_dir / category, category, **self._options)
            self._files[category] = handle
        return handle

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = record_to_event(record)
            if not event.get("persist", True):
                return
            line = event_to_line(event)
            targets = [event["category"]]
            if record.levelno >= logging.ERROR and LogCategory.ERROR.value not in targets:
                targets.append(LogCategory.ERROR.value)
            if event.get("audit") and LogCategory.AUDIT.value not in targets:
                targets.append(LogCategory.AUDIT.value)
            with self.lock:
                for category in targets:
                    self.file_for(category).write(line)
        except Exception:  # noqa: BLE001
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        _count_failure()

    def close(self) -> None:
        with self.lock:
            for handle in self._files.values():
                handle.close()
        super().close()


# ---------------------------------------------------------------------------
# صف غیرمسدودکننده
# ---------------------------------------------------------------------------

_failures = 0
_dropped = 0


def _count_failure() -> None:
    global _failures
    _failures += 1


def stats() -> dict[str, int]:
    """شمار رکوردهای دورریخته (صف پر) و خطاهای داخلی لاگر."""
    return {"dropped": _dropped, "failures": _failures}


class SafeQueueHandler(logging.handlers.QueueHandler):
    """
    `put_nowait` بدون انتظار. پیام و traceback همین‌جا قالب‌بندی می‌شوند
    (آرگومان‌های قابل‌تغییر نباید بعداً در رشتهٔ دیگری خوانده شوند).
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            message = str(record.msg)
        exc_text = record.exc_text or ""
        if record.exc_info and not exc_text:
            try:
                exc_text = "".join(traceback.format_exception(*record.exc_info))
            except Exception:  # noqa: BLE001
                exc_text = ""
        clone = logging.makeLogRecord(record.__dict__)
        clone.msg = message
        clone.args = None
        clone.exc_info = None
        clone.exc_text = exc_text or None
        clone.stack_info = None
        return clone

    def enqueue(self, record: logging.LogRecord) -> None:
        global _dropped
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            _dropped += 1

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        _count_failure()


class _Fanout(logging.Handler):
    """پخش هر رکورد به فهرست قابل‌تغییر هندلرها (خطای یکی، بقیه را نمی‌کشد)."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self._targets: list[logging.Handler] = []
        self._targets_lock = threading.Lock()

    def add(self, handler: logging.Handler) -> None:
        with self._targets_lock:
            if handler not in self._targets:
                self._targets.append(handler)

    def remove(self, handler: logging.Handler) -> None:
        with self._targets_lock:
            if handler in self._targets:
                self._targets.remove(handler)

    def targets(self) -> list[logging.Handler]:
        with self._targets_lock:
            return list(self._targets)

    def handle(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        for target in self.targets():
            if record.levelno < target.level:
                continue
            try:
                target.handle(record)
            except Exception:  # noqa: BLE001
                _count_failure()
        return True

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - handle جایگزین است
        self.handle(record)


# ---------------------------------------------------------------------------
# راه‌اندازی
# ---------------------------------------------------------------------------


class StructuredLogging:
    """نگه‌دارندهٔ صف، شنونده و هندلرهای لایهٔ ساختاریافته."""

    def __init__(
        self,
        logs_dir: Path | None,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        max_files: int = DEFAULT_MAX_FILES,
        buffer_capacity: int = DEFAULT_BUFFER_CAPACITY,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.logs_dir = Path(logs_dir) if logs_dir is not None else None
        self.buffer = LogBuffer(buffer_capacity)
        self.queue: queue.Queue = queue.Queue(maxsize=max(100, int(queue_size)))
        self.queue_handler = SafeQueueHandler(self.queue)
        self.queue_handler.setLevel(logging.DEBUG)
        self.fanout = _Fanout()
        self.fanout.add(RingBufferHandler(self.buffer))
        self.router: CategoryRouterHandler | None = None
        if self.logs_dir is not None:
            self.router = CategoryRouterHandler(
                self.logs_dir, max_bytes=max_bytes, retention_days=retention_days,
                max_files=max_files, clock=clock,
            )
            self.fanout.add(self.router)
        self.listener = logging.handlers.QueueListener(self.queue, self.fanout, respect_handler_level=False)
        self._started = False

    def start(self, logger: logging.Logger | None = None) -> StructuredLogging:
        target = logger or logging.getLogger()
        if self.queue_handler not in target.handlers:
            target.addHandler(self.queue_handler)
        # رویدادهای ممیزی (هر رد اولترا) نباید کنسول و app.log را پر کنند:
        # فقط از همین صف به فایل‌های دسته‌ای، نمای زنده و SQLite می‌روند.
        audit_logger = logging.getLogger("audit")
        if self.queue_handler not in audit_logger.handlers:
            audit_logger.addHandler(self.queue_handler)
        audit_logger.propagate = False
        # ممیزی مستقل از سطح ریشه (ریشه ممکن است WARNING باشد)
        if audit_logger.level == logging.NOTSET or audit_logger.level > logging.INFO:
            audit_logger.setLevel(logging.INFO)
        if not self._started:
            self.listener.start()
            self._started = True
        self._logger = target
        return self

    def add_handler(self, handler: logging.Handler) -> None:
        """افزودن هندلر به سمت شنونده (مثلاً ذخیرهٔ SQLite پس از ساخت پایگاه داده)."""
        self.fanout.add(handler)

    def remove_handler(self, handler: logging.Handler) -> None:
        self.fanout.remove(handler)

    def flush(self, timeout: float = 5.0) -> bool:
        """صبر تا خالی شدن صف (برای آزمون و خروج)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return self.queue.unfinished_tasks == 0

    def stop(self) -> None:
        logger = getattr(self, "_logger", None)
        if logger is not None and self.queue_handler in logger.handlers:
            logger.removeHandler(self.queue_handler)
        audit_logger = logging.getLogger("audit")
        if self.queue_handler in audit_logger.handlers:
            audit_logger.removeHandler(self.queue_handler)
            audit_logger.propagate = True
        if self._started:
            try:
                self.listener.stop()
            except Exception:  # noqa: BLE001
                pass
            self._started = False
        for handler in self.fanout.targets():
            try:
                handler.close()
            except Exception:  # noqa: BLE001
                pass


_current: StructuredLogging | None = None
_fallback_buffer = LogBuffer(DEFAULT_BUFFER_CAPACITY)
_atexit_registered = False


def setup_structured_logging(logs_dir: Path | None, **options: Any) -> StructuredLogging:
    """راه‌اندازی (یا راه‌اندازی دوباره) لایهٔ ساختاریافته روی لاگر ریشه."""
    global _current, _atexit_registered
    shutdown_structured_logging()
    _current = StructuredLogging(logs_dir, **options).start()
    if not _atexit_registered:
        atexit.register(shutdown_structured_logging)
        _atexit_registered = True
    return _current


def shutdown_structured_logging() -> None:
    """توقف شنونده و بستن فایل‌ها (صف پیش از توقف خالی می‌شود)."""
    global _current
    if _current is not None:
        _current.stop()
    _current = None


def current() -> StructuredLogging | None:
    return _current


def log_buffer() -> LogBuffer:
    """بافر زنده؛ اگر لایه راه‌اندازی نشده، بافر خالی جایگزین."""
    return _current.buffer if _current is not None else _fallback_buffer


def logs_dir() -> Path | None:
    return _current.logs_dir if _current is not None else None


# ---------------------------------------------------------------------------
# خواندن فایل‌ها برای تاریخچه
# ---------------------------------------------------------------------------


def read_log_files(
    base_dir: Path,
    *,
    categories: Iterable[str] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 20_000,
) -> list[dict[str, Any]]:
    """
    رویدادهای ذخیره‌شده در فایل‌ها، قدیمی‌ترین اول (حداکثر `limit` تای آخر).

    فقط فایل‌هایی که روزشان در بازه است خوانده می‌شوند؛ خط خراب نادیده گرفته می‌شود.
    """
    base = Path(base_dir)
    wanted = [c for c in (categories or [c.value for c in LogCategory])]
    first_day = start.strftime("%Y-%m-%d") if start else ""
    last_day = end.strftime("%Y-%m-%d") if end else "9999-99-99"
    start_epoch = start.timestamp() if start else None
    end_epoch = end.timestamp() if end else None
    events: deque[dict[str, Any]] = deque(maxlen=max(1, int(limit)))
    for category in wanted:
        folder = base / category
        if not folder.is_dir():
            continue
        paths = []
        for path in folder.iterdir():
            match = _FILE_RE.match(path.name)
            if match and first_day <= match["day"] <= last_day:
                paths.append((match["day"], int(match["part"] or 10**6), path))
        for _day, _part, path in sorted(paths):
            try:
                with open(path, encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        epoch = float(event.get("epoch") or 0)
                        if start_epoch is not None and epoch < start_epoch:
                            continue
                        if end_epoch is not None and epoch > end_epoch:
                            continue
                        events.append(event)
            except OSError:
                continue
    ordered = sorted(events, key=lambda e: float(e.get("epoch") or 0))
    if len(wanted) > 1:
        # رویداد ERROR در errors/ و دستهٔ خودش هست؛ تکراری حذف شود
        seen: set[tuple] = set()
        unique = []
        for event in ordered:
            key = (event.get("epoch"), event.get("module"), event.get("message"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(event)
        ordered = unique
    return ordered[-limit:]


__all__ = [
    "CategoryRouterHandler",
    "DailySizeRotatingFile",
    "LogBuffer",
    "RingBufferHandler",
    "SafeQueueHandler",
    "StructuredLogging",
    "current",
    "event_to_line",
    "log_buffer",
    "logs_dir",
    "read_log_files",
    "record_to_event",
    "setup_structured_logging",
    "shutdown_structured_logging",
    "stats",
]
