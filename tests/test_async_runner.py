"""
آزمون اجراکننده کارهای پس‌زمینه.

این آزمون‌ها به رابط گرافیکی کامل نیاز ندارند، اما به یک حلقه رویداد Qt
نیاز دارند تا سیگنال‌های میان‌نخی تحویل داده شوند.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402

from app.exceptions import NetworkError  # noqa: E402
from ui.controllers.async_runner import AsyncRunner  # noqa: E402


@pytest.fixture()
def qt_app(qt_application) -> QCoreApplication:
    """
    برنامه Qt مشترک برای تحویل سیگنال‌ها.

    از نمونه سراسری جلسه استفاده می‌شود؛ ساخت نمونه دوم باعث فروپاشی
    مفسر می‌شد وقتی آزمون‌های ویجت هم در همان اجرا بودند.
    """
    return qt_application


@pytest.fixture()
def runner(qt_app: QCoreApplication):
    """اجراکننده فعال که پس از آزمون بسته می‌شود."""
    instance = AsyncRunner()
    instance.start()
    yield instance
    instance.stop()


def _wait(qt_app: QCoreApplication, handle, timeout_ms: int = 5000) -> None:
    """انتظار همگام تا پایان یک کار پس‌زمینه."""
    loop = QEventLoop()
    handle.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()


def test_runner_starts_and_stops(runner: AsyncRunner) -> None:
    """چرخه عمر باید تمیز باشد."""
    assert runner.running
    runner.stop()
    assert not runner.running


def test_successful_task_emits_result(qt_app, runner: AsyncRunner) -> None:
    """نتیجه کار موفق باید از راه سیگنال برسد."""
    received: list[object] = []

    async def work() -> int:
        await asyncio.sleep(0.01)
        return 42

    handle = runner.submit("work", work(), on_success=received.append)
    _wait(qt_app, handle)
    assert received == [42]


def test_failing_task_reports_error_instead_of_raising(qt_app, runner: AsyncRunner) -> None:
    """
    خطا هرگز نباید به بیرون پرتاب شود.

    یک خطای شبکه نباید کل برنامه را ببندد.
    """
    errors: list[str] = []

    async def work() -> None:
        raise NetworkError("connection refused")

    handle = runner.submit("boom", work(), on_error=lambda message, _exc: errors.append(message))
    _wait(qt_app, handle)
    assert errors and "connection refused" in errors[0]


def test_unexpected_exception_is_also_captured(qt_app, runner: AsyncRunner) -> None:
    """حتی خطای پیش‌بینی‌نشده هم باید مهار شود."""
    errors: list[str] = []

    async def work() -> None:
        raise ZeroDivisionError("division by zero")

    handle = runner.submit("boom", work(), on_error=lambda message, _exc: errors.append(message))
    _wait(qt_app, handle)
    assert errors


def test_cancelled_handle_does_not_deliver_result(qt_app, runner: AsyncRunner) -> None:
    """
    نتیجه کار لغوشده نباید تحویل شود.

    سناریو: کاربر پیش از پایان تحلیل، نماد دیگری انتخاب می‌کند.
    """
    received: list[object] = []

    async def work() -> str:
        await asyncio.sleep(0.05)
        return "late result"

    handle = runner.submit("slow", work(), on_success=received.append)
    handle.cancel()
    _wait(qt_app, handle)
    assert received == []


def test_finished_fires_for_both_outcomes(qt_app, runner: AsyncRunner) -> None:
    """سیگنال پایان باید در موفقیت و شکست هر دو ارسال شود."""
    calls: list[str] = []

    async def good() -> int:
        return 1

    async def bad() -> int:
        raise RuntimeError("nope")

    for name, coroutine in (("good", good()), ("bad", bad())):
        handle = runner.submit(name, coroutine, on_finished=lambda n=name: calls.append(n))
        _wait(qt_app, handle)
    assert set(calls) == {"good", "bad"}


def test_blocking_function_runs_off_the_main_thread(qt_app, runner: AsyncRunner) -> None:
    """
    کار همگام سنگین (مثل ساخت PDF) نباید روی نخ رابط گرافیکی اجرا شود.
    """
    import threading

    main_thread = threading.current_thread().ident
    seen: list[int | None] = []

    handle = runner.run_blocking(
        "blocking",
        lambda: threading.current_thread().ident,
        on_success=seen.append,
    )
    _wait(qt_app, handle)
    assert seen and seen[0] != main_thread


def test_submit_without_running_loop_fails_gracefully(qt_app) -> None:
    """ارسال کار به اجراکننده متوقف باید خطای تمیز بدهد، نه فروپاشی."""
    stopped = AsyncRunner()
    errors: list[str] = []

    async def work() -> int:
        return 1

    handle = stopped.submit("x", work(), on_error=lambda message, _exc: errors.append(message))
    assert errors and "not running" in errors[0]
    assert handle is not None
