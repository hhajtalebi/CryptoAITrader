"""
اجرای کارهای ناهمگام بدون قفل شدن رابط گرافیکی.

مسئله:
    موتور بازار و موتور سیگنال ناهمگام (async) هستند و ممکن است چند ثانیه
    طول بکشند. اگر روی نخ رابط گرافیکی اجرا شوند، پنجره یخ می‌زند.

راه‌حل:
    یک حلقه رویداد asyncio روی یک نخ جداگانه اجرا می‌شود و نتیجه از راه
    سیگنال‌های Qt به نخ رابط گرافیکی برمی‌گردد. اتصال سیگنال بین دو نخ
    به‌صورت خودکار صف‌بندی می‌شود، پس هیچ ویجتی از نخ پس‌زمینه دست‌کاری
    نمی‌شود — این تنها روش امن در Qt است.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.exceptions import AppError
from app.logging import get_logger

logger = get_logger(__name__)


class TaskHandle(QObject):
    """
    دسته یک کار پس‌زمینه.

    این شیء در نخ رابط گرافیکی ساخته می‌شود، پس سیگنال‌هایش هنگام emit
    شدن از نخ پس‌زمینه به‌صورت صف‌بندی‌شده تحویل داده می‌شوند.
    """

    succeeded = Signal(object)
    failed = Signal(str, object)
    finished = Signal()

    def __init__(self, name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self._cancelled = False

    def cancel(self) -> None:
        """
        لغو تحویل نتیجه.

        کار پس‌زمینه ممکن است ادامه یابد، اما نتیجه‌اش نادیده گرفته می‌شود؛
        مثلاً وقتی کاربر پیش از پایان تحلیل، نماد دیگری انتخاب می‌کند.
        """
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        """آیا نتیجه باید نادیده گرفته شود."""
        return self._cancelled


class AsyncRunner(QObject):
    """
    حلقه رویداد asyncio روی نخ پس‌زمینه.

    مثال:
        runner = AsyncRunner()
        runner.start()
        handle = runner.submit("price", market.get_current_price("BTC/USDT"))
        handle.succeeded.connect(show_price)
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._handles: set[TaskHandle] = set()
        #: کار در حال اجرا به ازای هر کلید، برای جلوگیری از انباشت
        self._active: dict[str, tuple[TaskHandle, Any, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    def start(self) -> None:
        """راه‌اندازی نخ و حلقه رویداد."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run_loop, name="AsyncRunner", daemon=True)
        self._thread.start()
        # بدون این انتظار، اولین submit ممکن است پیش از آماده شدن حلقه برسد
        self._ready.wait(timeout=5)
        logger.debug("Async runner started")

    def _run_loop(self) -> None:
        """بدنه نخ پس‌زمینه."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            finally:
                loop.close()

    def stop(self, timeout: float = 5.0) -> None:
        """توقف تمیز حلقه و نخ."""
        if self._loop is None or self._thread is None:
            return
        for handle in list(self._handles):
            handle.cancel()
        with self._lock:
            self._active.clear()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=timeout)
        self._thread = None
        self._loop = None
        self._ready.clear()
        logger.debug("Async runner stopped")

    @property
    def running(self) -> bool:
        """آیا حلقه فعال است."""
        return self._loop is not None and self._loop.is_running()

    # ------------------------------------------------------------------
    # اجرای کار
    # ------------------------------------------------------------------
    def submit(
        self,
        name: str,
        coroutine: Coroutine[Any, Any, Any],
        *,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str, Exception], None] | None = None,
        on_finished: Callable[[], None] | None = None,
        coalesce: bool = True,
    ) -> TaskHandle:
        """
        اجرای یک کوروتین در نخ پس‌زمینه و بازگرداندن دسته آن.

        خطاها هرگز به بیرون پرتاب نمی‌شوند؛ همیشه از راه سیگنال `failed`
        گزارش می‌شوند تا یک خطای شبکه کل برنامه را نبندد.
        """
        # هم‌ادغامی بر پایهٔ کلید: اگر کاربر پشت سر هم روی یک دکمه بزند،
        # نباید ده درخواست موازی روی شبکه برود. نمونهٔ قبلیِ همان کلید
        # لغو می‌شود و فقط تازه‌ترین درخواست معتبر می‌ماند. بدون این،
        # چند کلیک پیاپی برنامه را کند و در نهایت بی‌پاسخ می‌کرد.
        if coalesce:
            with self._lock:
                previous = self._active.get(name)
            if previous is not None:
                old_handle, old_future, old_coro = previous
                old_handle.cancel()
                if old_future is not None:
                    # لغو کار قبلی. اگر هنوز شروع نشده باشد، پوششِ _wrap
                    # هرگز اجرا نمی‌شود و کوروتین اصلی باید بسته شود تا
                    # هشدار «never awaited» و نشت منبع ندهد.
                    if old_future.cancel():
                        try:
                            old_coro.close()
                        except (RuntimeError, AttributeError):
                            logger.debug("Superseded coroutine already closed")

        handle = TaskHandle(name, parent=self)
        if on_success is not None:
            handle.succeeded.connect(on_success)
        if on_error is not None:
            handle.failed.connect(on_error)
        if on_finished is not None:
            handle.finished.connect(on_finished)
        handle.finished.connect(lambda: self._handles.discard(handle))
        handle.finished.connect(lambda: self._release(name, handle))
        self._handles.add(handle)

        if self._loop is None:
            coroutine.close()
            handle.failed.emit("Background runner is not running", RuntimeError("runner stopped"))
            handle.finished.emit()
            return handle

        future = asyncio.run_coroutine_threadsafe(self._wrap(handle, coroutine), self._loop)
        if coalesce:
            with self._lock:
                self._active[name] = (handle, future, coroutine)
        return handle

    def _release(self, name: str, handle: TaskHandle) -> None:
        """آزادکردن کلید پس از پایان کار، اگر همان کار هنوز ثبت‌شده باشد."""
        with self._lock:
            current = self._active.get(name)
            if current is not None and current[0] is handle:
                self._active.pop(name, None)

    def cancel(self, name: str) -> bool:
        """
        لغو کار در حال اجرا با این کلید.

        وقتی پنجره‌ای بسته می‌شود، پاسخِ در راه دیگر گیرنده‌ای ندارد و اگر
        اعمال شود به شیء نابودشده دست می‌زند و برنامه بسته می‌شود.
        """
        with self._lock:
            current = self._active.pop(name, None)
        if current is None:
            return False
        handle, future, coroutine = current
        handle.cancel()
        if future.cancel():
            # فقط وقتی لغو موفق بود می‌توان کوروتین را بست؛ وگرنه
            # هشدار «coroutine was never awaited» می‌گیریم.
            close = getattr(coroutine, "close", None)
            if callable(close):
                close()
        return True

    def active_keys(self) -> list[str]:
        """کلید کارهای در حال اجرا (برای آزمون و عیب‌یابی)."""
        with self._lock:
            return sorted(self._active)

    def run_blocking(self, name: str, function: Callable[[], Any], **kwargs: Any) -> TaskHandle:
        """
        اجرای یک تابع همگام سنگین (مثل ساخت گزارش PDF) در نخ پس‌زمینه.
        """

        async def _call() -> Any:
            return await asyncio.to_thread(function)

        return self.submit(name, _call(), **kwargs)

    async def _wrap(self, handle: TaskHandle, coroutine: Coroutine[Any, Any, Any]) -> None:
        """اجرای کوروتین و تبدیل نتیجه یا خطا به سیگنال."""
        try:
            result = await coroutine
        except asyncio.CancelledError:
            logger.debug("Task cancelled: %s", handle.name)
            if not handle.cancelled:
                handle.failed.emit("Cancelled", asyncio.CancelledError())
        except AppError as exc:
            logger.warning("Task failed: %s — %s", handle.name, exc)
            if not handle.cancelled:
                handle.failed.emit(str(exc), exc)
        except Exception as exc:  # noqa: BLE001 - آخرین سد دفاعی برنامه
            logger.exception("Unexpected failure in task %s", handle.name)
            if not handle.cancelled:
                handle.failed.emit(str(exc) or exc.__class__.__name__, exc)
        else:
            if not handle.cancelled:
                handle.succeeded.emit(result)
        finally:
            handle.finished.emit()
