"""
ابزارهای پاسخ‌گویی رابط — نسخهٔ ۲.۴.۲.

`UiStallWatchdog`
    یک QTimer سبک روی نخ رابط هر ۲۵۰ms «ضربان» ثبت می‌کند و یک نخ نگهبان
    (daemon) بررسی می‌کند. اگر نخ رابط بیش از `threshold` ثانیه پاسخ ندهد،
    پشتهٔ فراخوانی همان لحظهٔ نخ رابط در لاگ نوشته می‌شود (حداکثر هر ۳۰
    ثانیه یک بار). یعنی اگر کاربر باز هم «هنگ» دید، فایل لاگ دقیقاً نشان
    می‌دهد کدام کد مقصر بوده است — بدون حدس.

`ShowWatcher`
    فیلتر رویداد کوچکی که هنگام نمایش‌شدن یک ویجت تابعی را صدا می‌زند؛
    برای تازه‌سازی تنبل صفحه‌هایی که پنهان‌اند.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QObject, QTimer

from app.logging import get_logger

logger = get_logger(__name__)

#: فاصلهٔ ضربان نخ رابط (میلی‌ثانیه)
HEARTBEAT_MS = 250
#: بیش از این مکث نخ رابط «گیر» حساب می‌شود (ثانیه)
DEFAULT_STALL_THRESHOLD = 1.5
#: فاصلهٔ حداقل بین دو گزارش در لاگ (ثانیه)
REPORT_INTERVAL = 30.0


class UiStallWatchdog:
    """نگهبان گیرکردن نخ رابط؛ فقط گزارش می‌دهد، دخالتی نمی‌کند."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        threshold: float = DEFAULT_STALL_THRESHOLD,
        report_interval: float = REPORT_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.threshold = float(threshold)
        self.report_interval = float(report_interval)
        self._clock = clock
        self._beat = clock()
        self._ui_thread_id = threading.get_ident()
        self._last_report = -1e9
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.stalls = 0
        self.longest = 0.0
        self._timer = QTimer(parent)
        self._timer.setInterval(HEARTBEAT_MS)
        self._timer.timeout.connect(self.beat)

    def beat(self) -> None:
        self._beat = self._clock()

    def start(self) -> None:
        if self._thread is not None:
            return
        self.beat()
        self._ui_thread_id = threading.get_ident()
        self._timer.start()
        self._thread = threading.Thread(
            target=self._watch, name="ui-stall-watchdog", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._timer.stop()
        except RuntimeError:  # ویجت والد پیش‌تر پاک شده
            pass

    def _watch(self) -> None:
        while not self._stop.wait(0.5):
            try:
                self.check()
            except Exception:  # noqa: BLE001 - نگهبان هرگز نباید برنامه را بکشد
                pass

    def check(self) -> bool:
        """یک بار بررسی؛ True یعنی نخ رابط گیر است (برای آزمون هم قابل صدا)."""
        lag = self._clock() - self._beat
        if lag < self.threshold:
            return False
        self.stalls += 1
        self.longest = max(self.longest, lag)
        now = self._clock()
        if now - self._last_report >= self.report_interval:
            self._last_report = now
            logger.warning(
                "UI thread unresponsive for %.1fs; stack:\n%s", lag, self.ui_stack()
            )
        return True

    def ui_stack(self) -> str:
        frame = sys._current_frames().get(self._ui_thread_id)  # noqa: SLF001
        if frame is None:
            return "  (UI thread frame unavailable)"
        return "".join(traceback.format_stack(frame, limit=25))


class ShowWatcher(QObject):
    """صدا زدن `callback` هر بار که ویجت هدف نمایش داده شود."""

    def __init__(self, target: QObject, callback: Callable[[], Any]) -> None:
        super().__init__(target)
        self._callback = callback
        target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show:
            # پس از پایان رویداد نمایش، تا باز شدن صفحه کند نشود
            QTimer.singleShot(0, self._callback)
        return False
