"""
آزمون‌های نگهبان اتصال — قابلیت «همیشه آنلاین».

سناریوی اصلی: وظیفهٔ نظرسنجی فید می‌میرد ولی پرچم running روشن می‌ماند
(دقیقاً حالتی که برنامه را «آنلاینِ یخ‌زده» می‌کند). نگهبان باید:
    ۱. مرگ حلقه را تشخیص دهد (نه فقط پرچم را).
    ۲. فید را با عقب‌نشینی نمایی + لرزش احیا کند.
    ۳. وضعیت سه‌حالتهٔ صادقانه بدهد و گذارها را منتشر کند.

این آزمون‌ها PySide6 import نمی‌کنند؛ فید یک فیک است با همان قرارداد
running / poll_alive / is_fresh / start / stop.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from market.resilience import (
    BASE_REVIVAL_DELAY,
    MAX_REVIVAL_DELAY,
    ConnectivityState,
    ConnectionSupervisor,
)


class FakeFeed:
    """فیک فید قیمت با مرگ و احیای قابل کنترل."""

    def __init__(self, *, fresh: bool = True, alive: bool = True) -> None:
        self.running = True
        self.poll_alive = alive
        self.is_fresh = fresh
        self.start_calls = 0
        self.stop_calls = 0
        # اگر تنظیم شده باشد، start این استثنا را می‌دهد (شبیه شکست احیا)
        self.fail_start: Exception | None = None

    async def start(self) -> None:
        if self.fail_start is not None:
            raise self.fail_start
        self.start_calls += 1
        self.poll_alive = True  # احیا موفق: حلقه دوباره زنده است

    async def stop(self) -> None:
        self.stop_calls += 1


class FakeBus:
    """فیک باس رویداد."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append((kind, payload))


class NoSleep:
    """خواب صفر — بدون انتظار واقعی ولی با بازپس‌دادن کنترل به حلقه."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, seconds: float) -> None:
        self.calls += 1
        # نکتهٔ حیاتی: await روی کوروتینِ فوری کنترل را پس نمی‌دهد و
        # حلقهٔ نگهبان را به چرخهٔ بی‌نهایتِ همگام تبدیل می‌کند.
        await asyncio.sleep(0)


def make_supervisor(
    feed: FakeFeed,
    *,
    bus: FakeBus | None = None,
    jitter=lambda d: d,  # پیش‌فرض: بدون لرزش تا اعداد قطعی باشند
) -> ConnectionSupervisor:
    return ConnectionSupervisor(
        feed,
        watch_interval=0.01,
        event_bus=bus,
        sleep=NoSleep(),
        jitter=jitter,
    )


class TestStateDetection:
    """تشخیص صادقانهٔ سه حالت."""

    async def test_alive_and_fresh_is_online(self) -> None:
        feed = FakeFeed(fresh=True, alive=True)
        supervisor = make_supervisor(feed)
        await supervisor.start()
        try:
            assert supervisor.state is ConnectivityState.ONLINE
        finally:
            await supervisor.stop()

    async def test_alive_but_stale_is_degraded(self) -> None:
        feed = FakeFeed(fresh=False, alive=True)
        supervisor = make_supervisor(feed)
        await supervisor.start()
        try:
            assert supervisor.state is ConnectivityState.DEGRADED
        finally:
            await supervisor.stop()

    async def test_dead_loop_is_offline_then_revived(self) -> None:
        feed = FakeFeed(fresh=True, alive=False)
        supervisor = make_supervisor(feed)
        await supervisor.start()
        try:
            await asyncio.sleep(0)  # فرصت برای اولین تیک نگهبان
            # احیا در همان اولین تیک انجام می‌شود
            assert feed.stop_calls >= 1
            assert feed.start_calls >= 1
            assert feed.poll_alive is True
            assert supervisor.state is ConnectivityState.ONLINE
            assert len(supervisor.revivals) >= 1
            assert supervisor.revivals[0].succeeded
        finally:
            await supervisor.stop()

    async def test_running_flag_alone_does_not_fool_supervisor(self) -> None:
        """حالت «آنلاینِ یخ‌زده»: running=True ولی حلقه مُرده."""
        feed = FakeFeed(fresh=False, alive=False)
        supervisor = make_supervisor(feed, bus=FakeBus())
        await supervisor.start()
        try:
            await asyncio.sleep(0)  # تیک اول: احیا
            # احیا انجام شده و چون فیک بعد از start زنده می‌شود، تازه نیست
            # ولی حلقه زنده است → degraded نه online
            assert supervisor.state is ConnectivityState.DEGRADED
        finally:
            await supervisor.stop()


class TestRevivalBackoff:
    """عقب‌نشینی نمایی + سقف + لرزش."""

    async def test_exponential_growth_and_reset(self) -> None:
        feed = FakeFeed(alive=False)
        feed.fail_start = RuntimeError("boom")  # احیا اول شکست می‌خورد

        supervisor = make_supervisor(feed)
        await supervisor.start()
        try:
            # چند تیک با شکست پیوسته — تأخیر هر تلاش در همان رکورد ثبت شده
            for _ in range(3):
                await asyncio.sleep(0)
            assert len(supervisor.revivals) >= 3
            delays = [r.delay for r in supervisor.revivals if not r.succeeded]
            assert delays[0] == pytest.approx(BASE_REVIVAL_DELAY)
            assert delays[1] == pytest.approx(BASE_REVIVAL_DELAY * 2)
            assert delays[2] == pytest.approx(BASE_REVIVAL_DELAY * 4)

            # احیا موفق → شمارندهٔ شکست صفر می‌شود
            feed.fail_start = None
            feed.poll_alive = False
            await asyncio.sleep(0)
            assert supervisor.revivals[-1].succeeded
            assert supervisor._next_delay() == pytest.approx(BASE_REVIVAL_DELAY)
        finally:
            await supervisor.stop()

    async def test_delay_capped(self) -> None:
        feed = FakeFeed(fresh=True, alive=True)
        supervisor = make_supervisor(feed)
        supervisor._consecutive_revival_failures = 30
        assert supervisor._next_delay() <= MAX_REVIVAL_DELAY * 1.2  # با لرزش
        await supervisor.stop()

    def test_jitter_applied(self) -> None:
        feed = FakeFeed()
        seen: list[float] = []
        supervisor = ConnectionSupervisor(
            feed, watch_interval=0.01, sleep=NoSleep(),
            jitter=lambda d: seen.append(d) or d,
        )
        supervisor._consecutive_revival_failures = 1
        supervisor._next_delay()
        assert seen == [BASE_REVIVAL_DELAY * 2]  # jitter روی تأخیر پایه اجرا شد


class TestEventsAndStatus:
    """انتشار رویداد گذار و گزارش وضعیت."""

    async def test_transition_publishes_event(self) -> None:
        feed = FakeFeed(fresh=True, alive=True)
        bus = FakeBus()
        supervisor = make_supervisor(feed, bus=bus)
        await supervisor.start()
        try:
            feed.is_fresh = False  # گذار آنلاین → تحلیل‌رفته
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            states = [payload["state"] for kind, payload in bus.events]
            assert "degraded" in states
            assert supervisor._events_published >= 1
        finally:
            await supervisor.stop()

    async def test_failed_revival_counted(self) -> None:
        feed = FakeFeed(alive=False)
        feed.fail_start = RuntimeError("no route to host")
        supervisor = make_supervisor(feed)
        await supervisor.start()
        try:
            await asyncio.sleep(0)
            assert supervisor.status()["failed_revivals"] >= 1
            assert supervisor.state is ConnectivityState.OFFLINE
        finally:
            await supervisor.stop()

    async def test_status_shape(self) -> None:
        feed = FakeFeed(fresh=True, alive=True)
        supervisor = make_supervisor(feed)
        await supervisor.start()
        try:
            status = supervisor.status()
            assert status["state"] == "online"
            assert status["supervisor_alive"] is True
            assert status["seconds_in_state"] >= 0.0
            assert status["revival_count"] == 0
        finally:
            await supervisor.stop()

    async def test_supervisor_survives_feed_exceptions(self) -> None:
        """خطای یک تیک نباید نگهبان را بکشد (خودِ نگهبان هم باید همیشه‌آنلاین باشد)."""

        class PoisonFlag:
            """فلگی که هر بولین‌گیری از آن استثنا می‌دهد."""

            def __bool__(self) -> bool:
                raise RuntimeError("bad flag")

        feed = FakeFeed(fresh=True, alive=True)
        supervisor = make_supervisor(feed)
        await supervisor.start()
        try:
            feed.is_fresh = PoisonFlag()  # type: ignore[assignment]
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert supervisor.running  # هنوز زنده است
            feed.is_fresh = True
            await asyncio.sleep(0)
            assert supervisor.state is ConnectivityState.ONLINE
        finally:
            await supervisor.stop()


class TestLiveFeedPollAlive:
    """قرارداد جدید LivePriceFeed — پرچم جدا از جانِ حلقه."""

    def test_poll_alive_reflects_task_state(self) -> None:
        from market.live_feed import LivePriceFeed

        feed = LivePriceFeed.__new__(LivePriceFeed)  # بدون MarketDataEngine
        feed._running = True
        feed._poll_task = None
        assert feed.poll_alive is False  # بدون وظیفه، زنده نیست

        class DoneTask:
            def done(self) -> bool:
                return True

        feed._poll_task = DoneTask()  # type: ignore[assignment]
        assert feed.poll_alive is False  # وظیفهٔ تمام‌شده = مرده

        class LiveTask:
            def done(self) -> bool:
                return False

        feed._poll_task = LiveTask()  # type: ignore[assignment]
        assert feed.poll_alive is True
