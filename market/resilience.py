"""
نظارت‌چی اتصال (Connection Supervisor) — قلب قابلیت «همیشه آنلاین».

چرا این فایل وجود دارد؟
    هر جزء شبکهٔ برنامه به‌تنهایی مکانیزم بازاتصلی دارد: کلاینت‌های
    WebSocket با عقب‌نشینی نمایی و تشخیص رکود داده، حلقهٔ نظرسنجی REST
    با عقب‌نشینی تدریجی. اما هیچ‌کس مراقب **خودِ این مکانیزم‌ها** نیست:
    اگر وظیفهٔ نظرسنجی به هر دلیلی بمیرد (باگ، استثنای غیرمنتظره، لغو
    اشتباه)، پرچم `running` روی می‌ماند، برنامه «آنلاین» نشان داده می‌شود
    و قیمت‌ها برای همیشه یخ می‌زنند — دقیقاً همان مشکلی که کاربر آن را
    «قطع شدن» می‌نامد و حیاتی می‌داند.

    این ماژول یک نگهبان مستقل است که:
        • هر چند ثانیه «جانِ» حلقه‌ها را می‌سنجد (نه فقط پرچم‌ها را)؛
        • وظیفهٔ مُرده را با عقب‌نشینی نمایی + لرزش تصادفی (jitter)
          زنده می‌کند — jitter تا اتصال‌های هم‌زمان روی هم نیفتند؛
        • وضعیت را در یک ماشین حالت صریح می‌دهد: online / degraded /
          offline و لحظهٔ تغییر هر حالت را نگه می‌دارد؛
        • گذارهای حالت را روی event bus منتشر می‌کند تا رابط کاربری
          و هر جزء دیگری بدون نظرسنجی باخبر شوند.

    اصل مهم: این نگهبان هرگز داده نمی‌سازد و ادعا نمی‌کند؛ اگر همهٔ
    مسیرها مرده باشند، صادقانه «offline» می‌گوید.

ارتباط با ماژول‌های دیگر:
    بالادست : ui/controllers/main_controller.py (ساخت/راه‌اندازی)
    پایین‌دست: market/live_feed.py (بازرسی و احیا)، app/core/events.py
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable

from app.core.timeutil import now_utc
from app.logging import get_logger

logger = get_logger(__name__)

#: فاصلهٔ بازرسی دوره‌ای نگهبان (ثانیه).
DEFAULT_WATCH_INTERVAL = 5.0

#: تأخیر بازراه‌اندازی اولیه؛ با هر شکست پیوسته دو برابر می‌شود.
BASE_REVIVAL_DELAY = 1.0

#: سقف تأخیر بازراه‌اندازی — بیشتر از این یعنی بمباران بی‌فایدهٔ سرور.
MAX_REVIVAL_DELAY = 120.0

#: سهم لرزش تصادفی نسبت به تأخیر پایه (۰٫۲ = ±۲۰٪).
JITTER_FRACTION = 0.2


class ConnectivityState(str, Enum):
    """وضعیت اتصال از نگاه کاربر — ساده، صادقانه، سه‌حالته."""

    ONLINE = "online"        # داده تازه می‌آید
    DEGRADED = "degraded"    # حلقه‌ها زنده‌اند ولی داده تازه نیست (در حال بازاتصال)
    OFFLINE = "offline"      # داده تازه نیست و احیا هم جواب نداد


@dataclass(slots=True)
class RevivalAttempt:
    """ثبت یک تلاش احیا — برای آمار و اشکال‌زدایی."""

    at: datetime
    delay: float
    succeeded: bool
    detail: str = ""


@dataclass(slots=True)
class ConnectionSupervisor:
    r"""
    نگهبان زنده‌بودن فید قیمت.

    نمونه‌سازی:
        supervisor = ConnectionSupervisor(feed)
        await supervisor.start()

    وابستگی‌ها به‌عمد «مرکب» (duck-typed) نگه داشته شده‌اند تا در آزمون‌ها
    فیک ساده جای `LivePriceFeed` بنشیند: کافی است `running`، `poll_alive`
    و `is_fresh` داشته باشد و `stop()`/`start()` ناهمگام باشد.
    """

    feed: Any
    watch_interval: float = DEFAULT_WATCH_INTERVAL
    event_bus: Any | None = None
    # تزریق توابع زمان/تصادف برای آزمون‌پذیری قطعی — ساعت و تاس را
    # بیرونی می‌کنیم تا آزمون‌ها به زمان واقعی وابسته نباشند.
    sleep: Callable[[float], Any] = asyncio.sleep
    jitter: Callable[[float], float] = lambda delay: delay * random.uniform(
        1.0 - JITTER_FRACTION, 1.0 + JITTER_FRACTION
    )

    _task: asyncio.Task[None] | None = field(default=None, init=False)
    state: ConnectivityState = ConnectivityState.OFFLINE
    state_since: datetime = field(default_factory=now_utc, init=False)
    revivals: list[RevivalAttempt] = field(default_factory=list, init=False)
    _consecutive_revival_failures: int = field(default=0, init=False)
    _events_published: int = field(default=0, init=False)

    # ------------------------------------------------------------------
    # چرخهٔ عمر
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """شروع نگهبانی."""
        if self._task is not None and not self._task.done():
            return
        self._evaluate()  # وضعیت اولیه بدون انتظار برای اولین تیک
        self._task = asyncio.create_task(self._watch_loop(), name="connection-supervisor")
        logger.info("Connection supervisor started (every %.1fs)", self.watch_interval)

    async def stop(self) -> None:
        """توقف تمیز نگهبان."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - خاموشی نباید خطا بدهد
                pass
            self._task = None
        logger.info("Connection supervisor stopped")

    @property
    def running(self) -> bool:
        """آیا خود نگهبان زنده است."""
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------------
    # بازرسی و احیا
    # ------------------------------------------------------------------
    def _poll_alive(self) -> bool:
        """جانِ حلقهٔ نظرسنجی — پرچم running به‌تنهایی کافی نیست."""
        return bool(getattr(self.feed, "running", False)) and bool(
            getattr(self.feed, "poll_alive", True)
        )

    async def _revive(self) -> bool:
        """
        احیای فید مُرده: توقف تمیز + شروع دوباره.

        بازگشتی: موفقیت عملیات. شکستِ احیا مشکلی نیست؛ نگهبان با
        عقب‌نشینی بزرگ‌تر دوباره تلاش می‌کند.
        """
        delay = self._next_delay()
        try:
            await self.feed.stop()
            await self.feed.start()
        except Exception as exc:  # noqa: BLE001 - احیا نباید نگهبان را بکشد
            self._consecutive_revival_failures += 1
            self.revivals.append(
                RevivalAttempt(at=now_utc(), delay=delay, succeeded=False, detail=str(exc))
            )
            logger.warning("Feed revival failed (attempt delay %.1fs): %s", delay, exc)
            return False

        self.revivals.append(RevivalAttempt(at=now_utc(), delay=delay, succeeded=True))
        self._consecutive_revival_failures = 0
        logger.info("Feed revived after %.1fs", delay)
        return True

    def _next_delay(self) -> float:
        """تأخیر احیا: نمایی با سقف، به‌علاوهٔ لرزش تصادفی."""
        base = min(
            MAX_REVIVAL_DELAY,
            BASE_REVIVAL_DELAY * (2 ** self._consecutive_revival_failures),
        )
        return float(self.jitter(base))

    def _evaluate(self) -> None:
        """
        سنجش وضعیت فعلی و انتشار رویداد در صورت تغییر حالت.

        منطق سه‌حالته:
            • حلقه زنده + داده تازه        → ONLINE
            • حلقه زنده + داده کهنه        → DEGRADED (خودش دارد تلاش می‌کند)
            • حلقه مُرده (یا احیانش شکست)  → OFFLINE
        """
        alive = self._poll_alive()
        fresh = bool(getattr(self.feed, "is_fresh", False))

        if alive and fresh:
            new_state = ConnectivityState.ONLINE
        elif alive:
            new_state = ConnectivityState.DEGRADED
        else:
            new_state = ConnectivityState.OFFLINE

        if new_state is not self.state:
            logger.info(
                "Connectivity: %s → %s (alive=%s fresh=%s)",
                self.state.value, new_state.value, alive, fresh,
            )
            self.state = new_state
            self.state_since = now_utc()
            self._publish_state()

    def _publish_state(self) -> None:
        """انتشار رویداد گذار حالت روی باس رویداد (در صورت وجود)."""
        if self.event_bus is None:
            return
        try:
            from app.core.events import EventType  # noqa: PLC0415 - جلوگیری از import زودهنگام

            self.event_bus.publish(
                EventType.CONNECTIVITY_CHANGED,
                {
                    "state": self.state.value,
                    "since": self.state_since.isoformat(),
                },
            )
            self._events_published += 1
        except Exception:  # noqa: BLE001 - باس خراب نباید نگهبان را بکشد
            logger.debug("Event bus publish failed", exc_info=True)

    async def _watch_loop(self) -> None:
        """
        حلقهٔ اصلی نگهبانی.

        در هر تیک: ارزیابی وضعیت؛ اگر حلقهٔ فید مُرده باشد، احیا با
        عقب‌نشینی. خواب با `self.sleep` تزریق‌شده است تا آزمون‌ها بدون
        انتظار واقعی بتوانند زمان را جلو ببرند.
        """
        while True:
            try:
                if not self._poll_alive():
                    await self._revive()
                self._evaluate()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - یک تیک خراب نباید نگهبان را بکشد
                logger.exception("Supervisor tick failed; continuing")
            await self.sleep(self.watch_interval)

    # ------------------------------------------------------------------
    # گزارش
    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        """خلاصهٔ وضعیت برای نوار وضعیت UI و داشبورد سلامت."""
        since: datetime = self.state_since
        return {
            "state": self.state.value,
            "since": since.isoformat() if isinstance(since, datetime) else str(since),
            "seconds_in_state": _safe_age(since) if isinstance(since, datetime) else 0.0,
            "supervisor_alive": self.running,
            "revival_count": len(self.revivals),
            "failed_revivals": sum(1 for r in self.revivals if not r.succeeded),
            "events_published": self._events_published,
        }


def _safe_age(since: datetime) -> float:
    """سن حالت با تحمل ساعت naive (پایداری در برابر دادهٔ قدیمی)."""
    try:
        moment = since if since.tzinfo else since.replace(tzinfo=UTC)
        return max(0.0, (now_utc() - moment).total_seconds())
    except Exception:  # noqa: BLE001 - گزارش نباید هرگز exceptions بدهد
        return 0.0
