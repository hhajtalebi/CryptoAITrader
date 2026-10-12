"""
آزمون‌های ۲٫۷٫۲ — «ترمینال مدام باز و بسته می‌شود» و فیوزِ فروپاشی مدل.

سه مکانیسم که می‌توانستند هنگام سیگنال‌گیری/معامله پنجرهٔ کنسول بسازند یا
درخواست‌های بی‌وقفهٔ سنگین بفرستند:

۱. کارگرهای استخر محاسبه (`signals.compute_pool`) که با CreateProcess و
   پرچم صفر ساخته می‌شوند و روی ویندوز برای والدِ بی‌کنسول، کنسولِ نمایان
   می‌سازند.
۲. `ollama serve` که پیش‌تر هر بارِ «سرویس در دسترس نیست» یک فرایند تازه
   می‌ساخت.
۳. فروپاشی‌های پیاپی اجراکنندهٔ مدل که هر بار بارگذاریِ دوباره (و روی
   ویندوز پنجرهٔ تازه) و معطلیِ چنددقیقه‌ای داشت.
"""

from __future__ import annotations

import asyncio
import sys
import time
import types

import pytest


# ---------------------------------------------------------------------------
# ۱) کارگرهای استخر نباید پنجرهٔ کنسول بسازند
# ---------------------------------------------------------------------------


class TestNoConsoleWindowFlash:
    """پرچم CREATE_NO_WINDOW باید به ساختِ فرایند ویندوزی اضافه شود."""

    @staticmethod
    def _fake_winapi(recorded: list):
        fake = types.ModuleType("_winapi")

        def create_process(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            recorded.append((args, kwargs))
            return (1, 2, 3, 4)

        fake.CreateProcess = create_process  # type: ignore[attr-defined]
        return fake

    def test_windows_process_creation_gets_the_hidden_console_flag(self, monkeypatch) -> None:
        """
        کارگر spawn باید CREATE_NO_WINDOW بگیرد.

        بدون این پرچم، روی ویندوز هر کارگر یک پنجرهٔ کنسول لحظه‌ای می‌سازد
        (والد بی‌کنسول) — دقیقاً همان «ترمینالی که مدام باز و بسته می‌شود».
        """
        import signals.compute_pool as cp

        recorded: list = []
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setitem(sys.modules, "_winapi", self._fake_winapi(recorded))
        monkeypatch.setattr(cp, "_console_suppression_installed", False)

        cp._suppress_worker_console_windows()
        assert cp._console_suppression_installed

        import _winapi  # noqa: PLC0415

        _winapi.CreateProcess("python.exe", "cmd", None, None, False, 0, None, None, None)

        assert recorded, "CreateProcess باید صدا زده می‌شد"
        args = recorded[0][0]
        assert args[5] == 0x08000000, f"پرچم CREATE_NO_WINDOW اضافه نشد: {args[5]:#x}"

    def test_other_creation_flags_are_preserved(self, monkeypatch) -> None:
        """فقط OR می‌شود؛ پرچم‌های موجود کنار نمی‌روند."""
        import signals.compute_pool as cp

        recorded: list = []
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setitem(sys.modules, "_winapi", self._fake_winapi(recorded))
        monkeypatch.setattr(cp, "_console_suppression_installed", False)
        cp._suppress_worker_console_windows()

        import _winapi  # noqa: PLC0415

        _winapi.CreateProcess("a", "b", None, None, False, 0x00000200, None, None, None)

        assert recorded[0][0][5] == 0x08000200

    def test_install_is_idempotent(self, monkeypatch) -> None:
        """دو بار نصب نباید بسته‌بندیِ تودرتو بسازد."""
        import signals.compute_pool as cp

        recorded: list = []
        fake = self._fake_winapi(recorded)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setitem(sys.modules, "_winapi", fake)
        monkeypatch.setattr(cp, "_console_suppression_installed", False)

        cp._suppress_worker_console_windows()
        wrapper = fake.CreateProcess  # type: ignore[attr-defined]
        cp._suppress_worker_console_windows()
        assert fake.CreateProcess is wrapper  # type: ignore[attr-defined]

    def test_nothing_happens_on_non_windows(self, monkeypatch) -> None:
        """روی لینوکس/مک هیچ دستکاری‌ای نباید رخ دهد."""
        import signals.compute_pool as cp

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(cp, "_console_suppression_installed", False)
        cp._suppress_worker_console_windows()
        assert cp._console_suppression_installed is False


# ---------------------------------------------------------------------------
# ۲) راه‌اندازی اولاما تک‌پروازه است
# ---------------------------------------------------------------------------


class TestOllamaLaunchCooldown:
    """`ollama serve` نباید در هر بررسیِ وضعیت دوباره ساخته شود."""

    def test_second_start_within_cooldown_does_not_spawn(self, monkeypatch) -> None:
        """
        بازتولید «ترمینال مدام باز و بسته می‌شود»: اگر سرویس پایین بود و رابط
        هر چند ثانیه وضعیت می‌پرسید، هر پرسش یک فرایند تازه می‌ساخت.
        """
        import ai.ollama_launcher as launcher

        spawned: list = []
        monkeypatch.setattr(
            launcher.subprocess,
            "Popen",
            lambda *a, **k: spawned.append(a) or types.SimpleNamespace(pid=1),
        )
        monkeypatch.setattr(launcher, "_last_launch_monotonic", 0.0)

        assert launcher.start_service("/usr/bin/fake-ollama") is True
        assert launcher.start_service("/usr/bin/fake-ollama") is False
        assert len(spawned) == 1, f"فقط یک فرایند باید ساخته می‌شد: {len(spawned)}"

    def test_after_cooldown_a_new_start_is_allowed(self, monkeypatch) -> None:
        """پس از سپری شدن فاصله، تلاش تازه مجاز است."""
        import ai.ollama_launcher as launcher

        spawned: list = []
        monkeypatch.setattr(
            launcher.subprocess,
            "Popen",
            lambda *a, **k: spawned.append(a) or types.SimpleNamespace(pid=1),
        )
        monkeypatch.setattr(
            launcher,
            "_last_launch_monotonic",
            time.monotonic() - launcher.LAUNCH_COOLDOWN_SECONDS - 1,
        )

        assert launcher.start_service("/usr/bin/fake-ollama") is True
        assert len(spawned) == 1

    def test_empty_executable_never_spawns(self, monkeypatch) -> None:
        """بدون مسیر، هیچ فرایندی ساخته نمی‌شود."""
        import ai.ollama_launcher as launcher

        spawned: list = []
        monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: spawned.append(a))
        monkeypatch.setattr(launcher, "_last_launch_monotonic", 0.0)

        assert launcher.start_service("") is False
        assert spawned == []


# ---------------------------------------------------------------------------
# ۳) فیوزِ فروپاشی‌های پیاپی اجراکنندهٔ مدل
# ---------------------------------------------------------------------------


class TestCrashFuse:
    """وقتی مدل پشت‌سرهم می‌میرد، درخواست‌ها باید سریع و صادقانه رد شوند."""

    @staticmethod
    def _provider():
        from ai.providers.base import AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            AIProviderConfig(
                name="ollama",
                base_url="http://127.0.0.1:11434",
                model="llama3.1:8b",
                max_tokens=1500,
                extra={"provider_type": "ollama"},
            )
        )

    @staticmethod
    def _reset():
        from ai.providers.ollama_provider import reset_crash_breaker

        reset_crash_breaker()

    def test_three_crashes_open_the_fuse(self) -> None:
        from ai.providers.ollama_provider import (
            CRASH_BREAKER_THRESHOLD,
            _crash_breaker_note,
            _record_crash_failure,
        )

        self._reset()
        try:
            for _ in range(CRASH_BREAKER_THRESHOLD - 1):
                _record_crash_failure()
            assert _crash_breaker_note() is None, "پیش از آستانه نباید فیوز باز شود"
            _record_crash_failure()
            note = _crash_breaker_note()
            assert note is not None
            assert "smaller" in note or "quantised" in note, "پیام باید راه‌حل بدهد"
        finally:
            self._reset()

    @pytest.mark.asyncio
    async def test_generate_fails_fast_while_fused(self) -> None:
        """
        در حالت فیوز نباید اصلاً به مدل فشار بیاید؛ پیام باید علتِ واقعی
        (سخت‌افزار/اندازهٔ مدل) را بگوید، نه «شبکه».
        """
        from app.exceptions import AIProviderError
        from ai.providers.base import AIMessage
        from ai.providers.ollama_provider import _record_crash_failure

        self._reset()
        try:
            for _ in range(3):
                _record_crash_failure()
            provider = self._provider()
            with pytest.raises(AIProviderError) as excinfo:
                await provider.generate([AIMessage("user", "سلام")])
            assert excinfo.value.details.get("fused") is True
            assert "hardware" in str(excinfo.value) or "crashing" in str(excinfo.value)
        finally:
            self._reset()

    @pytest.mark.asyncio
    async def test_a_successful_reply_closes_the_fuse(self) -> None:
        """یک پاسخ موفق باید فیوز را ببندد."""
        from ai.providers.base import AIMessage
        from ai.providers.ollama_provider import (
            _clear_crash_failures,
            _crash_breaker_note,
            _record_crash_failure,
        )

        self._reset()
        try:
            for _ in range(3):
                _record_crash_failure()
            assert _crash_breaker_note() is not None
            _clear_crash_failures()
            assert _crash_breaker_note() is None
        finally:
            self._reset()

    @pytest.mark.asyncio
    async def test_normal_generation_is_unaffected(self) -> None:
        """فیوزِ بسته نباید مسیر عادی را دست بزند."""
        from ai.providers.base import AIMessage

        self._reset()
        try:
            calls: list = []

            class FakeResponse:
                status_code = 200

                @staticmethod
                def json():
                    return {
                        "model": "llama3.1:8b",
                        "message": {"content": "پاسخ"},
                        "done": True,
                    }

            class FakeClient:
                async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                    calls.append(json)
                    return FakeResponse()

            provider = self._provider()
            provider._get_client = lambda: _async(FakeClient())  # noqa: SLF001
            provider.resolve_model = lambda: _async("llama3.1:8b")  # noqa: SLF001

            response = await provider.generate([AIMessage("user", "سلام")])
            assert response.content == "پاسخ"
        finally:
            self._reset()


def _async(value):
    """ساختن آینده‌ای آماده — الگوی مشترک آزمون‌های اولاما."""

    async def _wrap():
        return value

    return _wrap()


def test_event_loop_helper_is_consistent() -> None:
    """سلامتِ کمکیِ آینده‌ها در آزمون‌های بالا."""
    assert asyncio.run(_async(42)) == 42
