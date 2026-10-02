"""
نسخهٔ ۲.۵.۹ — اولامای واقعاً کارا.

کاربر: «اولاما در تنظیمات "وصل" نشان داده می‌شد ولی در تحلیل سیگنال، چت و
بقیهٔ بخش‌ها هیچ پاسخی نمی‌آمد.» ریشه‌ها:
- مدل‌های استدلالی خروجی را در `message.thinking` می‌گذارند و `content` خالی می‌ماند؛
- آزمایش اتصال فقط `/api/tags` را می‌خواند، نه تولید واقعی؛
- اولامای نصب‌شده ولی خاموش راه‌اندازی نمی‌شد.
"""

from __future__ import annotations

import pytest

from ai.providers.base import AIMessage, AIProviderConfig
from ai.providers.ollama_provider import OllamaProvider, think_setting


async def _async(value):  # noqa: ANN001, ANN202
    return value


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self) -> dict:
        return self._payload


def _provider(model: str = "qwen3:8b", base_url: str = "http://127.0.0.1:11434") -> OllamaProvider:
    return OllamaProvider(
        AIProviderConfig(name="ollama", base_url=base_url, model=model, max_tokens=800,
                         extra={"provider_type": "ollama"})
    )


def _answer(text: str, thinking: str = "") -> dict:
    message = {"role": "assistant", "content": text}
    if thinking:
        message["thinking"] = thinking
    return {"model": "m", "message": message, "done": True}


class TestThinkSetting:
    @pytest.mark.parametrize("model", ["qwen3:8b", "deepseek-r1:8b", "QwQ:32b"])
    def test_reasoning_models_get_think_off(self, model: str) -> None:
        assert think_setting(model) is False

    def test_gpt_oss_gets_low(self) -> None:
        assert think_setting("gpt-oss:20b") == "low"

    @pytest.mark.parametrize("model", ["llama3.1:8b", "qwen2.5:7b", "mistral", ""])
    def test_plain_models_send_nothing(self, model: str) -> None:
        assert think_setting(model) is None


class TestGenerate:
    async def test_think_false_is_sent_for_reasoning_models(self, monkeypatch) -> None:
        calls: list[dict] = []

        class Client:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                calls.append(json)
                return FakeResponse(200, _answer("سلام"))

        provider = _provider("qwen3:8b")
        monkeypatch.setattr(provider, "_get_client", lambda: _async(Client()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("qwen3:8b"))
        response = await provider.generate([AIMessage("user", "hi")])
        assert response.content == "سلام"
        assert calls[0]["think"] is False

    async def test_plain_model_payload_has_no_think(self, monkeypatch) -> None:
        calls: list[dict] = []

        class Client:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                calls.append(json)
                return FakeResponse(200, _answer("ok"))

        provider = _provider("llama3.1:8b")
        monkeypatch.setattr(provider, "_get_client", lambda: _async(Client()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("llama3.1:8b"))
        await provider.generate([AIMessage("user", "hi")])
        assert "think" not in calls[0]

    async def test_thinking_only_reply_is_retried_with_thinking_off(self, monkeypatch) -> None:
        """مدل ناشناخته‌ای که فقط فکر برگرداند → یک بار دوباره با think:false."""
        calls: list[dict] = []

        class Client:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                calls.append(dict(json))
                if len(calls) == 1:
                    return FakeResponse(200, _answer("", thinking="let me think..."))
                return FakeResponse(200, _answer("LONG"))

        provider = _provider("my-custom:7b")
        monkeypatch.setattr(provider, "_get_client", lambda: _async(Client()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("my-custom:7b"))
        response = await provider.generate([AIMessage("user", "hi")])
        assert response.content == "LONG"
        assert len(calls) == 2
        assert "think" not in calls[0] and calls[1]["think"] is False
        # برای همین مدل به خاطر سپرده می‌شود
        assert provider._think_for("my-custom:7b") is False  # noqa: SLF001

    async def test_old_ollama_rejecting_think_is_retried_without_it(self, monkeypatch) -> None:
        calls: list[dict] = []

        class Client:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                calls.append(dict(json))
                if "think" in json:
                    return FakeResponse(400, {"error": "invalid option: think"})
                return FakeResponse(200, _answer("ok"))

        provider = _provider("deepseek-r1:8b")
        monkeypatch.setattr(provider, "_get_client", lambda: _async(Client()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("deepseek-r1:8b"))
        response = await provider.generate([AIMessage("user", "hi")])
        assert response.content == "ok"
        assert "think" in calls[0] and "think" not in calls[-1]

    async def test_probe_generation_requires_a_real_answer(self, monkeypatch) -> None:
        provider = _provider("llama3.1:8b")

        class Client:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                return FakeResponse(200, _answer("OK"))

        monkeypatch.setattr(provider, "_get_client", lambda: _async(Client()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("llama3.1:8b"))
        ok, message = await provider.probe_generation()
        assert ok and "llama3.1:8b" in message

    async def test_probe_reports_model_failure(self, monkeypatch) -> None:
        provider = _provider("llama3.1:8b")

        class Client:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                return FakeResponse(404, {"error": "model 'llama3.1:8b' not found"})

        monkeypatch.setattr(provider, "_get_client", lambda: _async(Client()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("llama3.1:8b"))
        ok, _message = await provider.probe_generation()
        assert not ok


class TestLauncher:
    def test_is_local_url(self) -> None:
        from ai.ollama_launcher import is_local_url

        assert is_local_url("http://127.0.0.1:11434")
        assert is_local_url("http://localhost:11434/")
        assert not is_local_url("http://192.168.1.20:11434")

    async def test_running_service_is_not_restarted(self, monkeypatch) -> None:
        import ai.ollama_launcher as launcher

        started: list[str] = []
        monkeypatch.setattr(launcher, "service_reachable", lambda url, timeout=2.0: _async(True))
        monkeypatch.setattr(launcher, "start_service", lambda exe: started.append(exe) or True)
        ok, note = await launcher.ensure_running("http://127.0.0.1:11434")
        assert ok and note == "running" and not started

    async def test_installed_but_stopped_is_started(self, monkeypatch) -> None:
        import ai.ollama_launcher as launcher

        state = {"up": False}
        monkeypatch.setattr(launcher, "service_reachable", lambda url, timeout=2.0: _async(state["up"]))
        monkeypatch.setattr(launcher, "find_ollama_executable", lambda: "/usr/bin/ollama")

        def start(exe: str) -> bool:
            state["up"] = True
            return True

        monkeypatch.setattr(launcher, "start_service", start)
        monkeypatch.setattr(launcher, "POLL_INTERVAL", 0.01)
        ok, note = await launcher.ensure_running("http://127.0.0.1:11434", wait_seconds=1)
        assert ok and "started" in note

    async def test_not_installed_is_reported(self, monkeypatch) -> None:
        import ai.ollama_launcher as launcher

        monkeypatch.setattr(launcher, "service_reachable", lambda url, timeout=2.0: _async(False))
        monkeypatch.setattr(launcher, "find_ollama_executable", lambda: "")
        ok, note = await launcher.ensure_running("http://127.0.0.1:11434")
        assert not ok and "not installed" in note

    async def test_remote_url_is_never_started(self, monkeypatch) -> None:
        import ai.ollama_launcher as launcher

        monkeypatch.setattr(launcher, "service_reachable", lambda url, timeout=2.0: _async(False))
        monkeypatch.setattr(launcher, "find_ollama_executable", lambda: pytest.fail("must not look"))
        ok, _note = await launcher.ensure_running("http://10.0.0.5:11434")
        assert not ok


class TestAgentHealthCheck:
    async def test_connected_but_silent_model_is_not_reported_healthy(self) -> None:
        """«وصل است» کافی نیست: آزمون تولید واقعی باید موفق باشد."""
        from types import SimpleNamespace

        from ai.agent.autonomous_agent import AutonomousAgent

        silent = SimpleNamespace(name="ollama",
                                 probe_generation=lambda: _async((False, "model failed")))
        providers = SimpleNamespace(
            has_providers=True,
            check_all=lambda: _async({"ollama": (True, "connected")}),
            ordered_providers=lambda preferred=None: [silent],
        )
        agent = AutonomousAgent.__new__(AutonomousAgent)
        agent._providers = providers  # noqa: SLF001
        agent._preferred = None  # noqa: SLF001
        ok, message = await agent.health_check()
        assert not ok and "model failed" in message


class TestLocalTimeouts:
    def test_ollama_gets_longer_timeout_floors(self) -> None:
        from ai.speed_profile import LOCAL_MODEL_FLOORS, effective_limits, limits_for

        local = {"ai.provider": "ollama", "ai.speed_profile": "fast"}
        limits = effective_limits(local)
        for name, floor in LOCAL_MODEL_FLOORS.items():
            assert getattr(limits, name) >= floor
        # سرویس ابری دست‌نخورده می‌ماند
        cloud = {"ai.provider": "openai", "ai.speed_profile": "fast"}
        assert effective_limits(cloud) == limits_for(cloud)
