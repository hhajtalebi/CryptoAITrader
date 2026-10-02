"""
ذخیرهٔ رویدادهای ممیزی در SQLite موجود برنامه — نسخهٔ ۲.۶.۰.

`AuditStoreHandler.emit` فقط رویداد را در صف می‌گذارد (بدون I/O)؛ رشتهٔ
`AuditStoreWriter` هر نیم ثانیه (یا هر ۲۰۰ رویداد) دسته‌ای درج می‌کند.
خطای پایگاه داده شمرده و رد می‌شود؛ هرگز به موتور معامله نمی‌رسد.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

from app.logging.structured import current, record_to_event

BATCH_SIZE = 200
FLUSH_SECONDS = 0.5
PURGE_EVERY_SECONDS = 30 * 60
RETENTION_DAYS = 30
MAX_ROWS = 500_000


class AuditStoreWriter:
    """رشتهٔ نویسندهٔ دسته‌ای."""

    def __init__(self, repository: Any, *, queue_size: int = 20_000,
                 retention_days: int = RETENTION_DAYS, max_rows: int = MAX_ROWS) -> None:
        self.repository = repository
        self.queue: queue.Queue = queue.Queue(maxsize=max(100, int(queue_size)))
        self.retention_days = retention_days
        self.max_rows = max_rows
        self.written = 0
        self.dropped = 0
        self.failures = 0
        self._stop = threading.Event()
        self._idle = threading.Event()
        self._idle.set()
        self._thread = threading.Thread(target=self._run, name="audit-store", daemon=True)
        self._last_purge = 0.0

    def start(self) -> AuditStoreWriter:
        self._thread.start()
        return self

    def put(self, event: dict[str, Any]) -> None:
        try:
            self._idle.clear()
            self.queue.put_nowait(event)
        except queue.Full:
            self.dropped += 1

    def _drain(self, first: dict[str, Any] | None) -> list[dict[str, Any]]:
        batch = [first] if first is not None else []
        while len(batch) < BATCH_SIZE:
            try:
                batch.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _write(self, batch: list[dict[str, Any]]) -> None:
        if not batch:
            return
        try:
            self.written += int(self.repository.add_events(batch) or 0)
        except Exception:  # noqa: BLE001 - پایگاه داده قفل/خراب: رویداد از دست می‌رود، معامله نه
            self.failures += 1

    def _maybe_purge(self) -> None:
        now = time.monotonic()
        if now - self._last_purge < PURGE_EVERY_SECONDS:
            return
        self._last_purge = now
        try:
            self.repository.purge(older_than_days=self.retention_days, max_rows=self.max_rows)
        except Exception:  # noqa: BLE001
            self.failures += 1

    def _run(self) -> None:
        self._maybe_purge()
        while not self._stop.is_set():
            try:
                first = self.queue.get(timeout=FLUSH_SECONDS)
            except queue.Empty:
                self._idle.set()
                self._maybe_purge()
                continue
            self._write(self._drain(first))
            if self.queue.empty():
                self._idle.set()
        # تخلیهٔ پایانی
        while True:
            batch = self._drain(None)
            if not batch:
                break
            self._write(batch)
        self._idle.set()

    def flush(self, timeout: float = 5.0) -> bool:
        """صبر تا نوشته شدن همهٔ رویدادهای صف (برای آزمون/خروج)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.queue.empty() and self._idle.is_set():
                return True
            time.sleep(0.02)
        return False

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout)


class AuditStoreHandler(logging.Handler):
    """فقط رویدادهای ممیزیِ ماندگار را به نویسنده می‌دهد."""

    def __init__(self, writer: AuditStoreWriter) -> None:
        super().__init__(logging.DEBUG)
        self.writer = writer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not getattr(record, "audit", False) or not getattr(record, "persist", True):
                return
            self.writer.put(record_to_event(record))
        except Exception:  # noqa: BLE001
            self.writer.failures += 1

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        self.writer.failures += 1

    def close(self) -> None:
        try:
            self.writer.stop()
        finally:
            super().close()


_store: tuple[AuditStoreHandler, Any] | None = None


def attach_audit_store(repository: Any, **options: Any) -> AuditStoreHandler:
    """
    وصل کردن ذخیرهٔ SQLite. اگر لایهٔ ساختاریافته فعال است، سمت شنوندهٔ صف
    (پس‌زمینه) اضافه می‌شود؛ وگرنه مستقیم روی لاگر `audit` (emit فقط صف است).
    """
    detach_audit_store()
    global _store
    handler = AuditStoreHandler(AuditStoreWriter(repository, **options).start())
    structured = current()
    if structured is not None:
        structured.add_handler(handler)
        _store = (handler, structured)
    else:
        audit_logger = logging.getLogger("audit")
        audit_logger.addHandler(handler)
        if audit_logger.getEffectiveLevel() > logging.INFO:
            audit_logger.setLevel(logging.INFO)
        _store = (handler, None)
    return handler


def detach_audit_store() -> None:
    """جدا کردن و تخلیهٔ ذخیره (هنگام بستن برنامه)."""
    global _store
    if _store is None:
        return
    handler, structured = _store
    _store = None
    if structured is not None:
        structured.remove_handler(handler)
    else:
        logging.getLogger("audit").removeHandler(handler)
    try:
        handler.close()
    except Exception:  # noqa: BLE001
        pass


def audit_store() -> AuditStoreHandler | None:
    return _store[0] if _store is not None else None


__all__ = ["AuditStoreHandler", "AuditStoreWriter", "attach_audit_store", "audit_store", "detach_audit_store"]
