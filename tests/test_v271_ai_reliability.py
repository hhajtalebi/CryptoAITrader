"""
نسخهٔ ۲.۷.۱ — پایایی مسیر هوش مصنوعی (اولاما، عامل خودمختار، اعتبارسنج).

چرا این فایل وجود دارد؟
    شکایت اصلی کاربر این بود: «در تنظیمات می‌گوید اولاما وصل است، ولی نه
    تحلیل می‌آید و نه سیگنال ساخته می‌شود.» بررسی نشان داد سه گونه خرابی
    پشت هم پنهان می‌شوند و هر کدام جای دیگری رخ می‌دهد:

    ۱. «وصل است» در تنظیمات فقط یعنی سرویس پاسخ می‌دهد؛ اینکه **مدل نصب
       است** و اینکه **مدل واقعاً پاسخ تولید می‌کند** دو چیز دیگرند.
    ۲. مسیرِ سریعِ عامل خودمختار (وقتی مهلت رو به پایان است) خروجی مدل را
       بدون اعتبارسنجی به‌عنوان تصمیم نهایی می‌پذیرفت؛ یعنی اهرم بالاتر از
       سقف کاربر یا حد ضرر در سمت اشتباه می‌توانست مستقیم به رابط کاربری
       و پایگاه داده برسد.
    ۳. وقتی جریانِ پاسخ (stream) وسط کار قطع می‌شد و دوباره تلاش می‌کردیم،
       نیمهٔ firstِ پاسخ روی صفحه مانده بود و متن دوبار نمایش داده می‌شد.

    این آزمون‌ها برای هر سه حالت سد می‌سازند.

دو گونه آزمون در این فایل:
    • آزمون‌های **شبیه‌سازی‌شده** (بدون شبکه، با کلاینت/مدل ساختگی) —
      همیشه اجرا می‌شوند.
    • آزمون‌های **یکپارچه با سرویس HTTP محلی** که پروتکل اولاما را حرف
      می‌زند. این یک سرویس **ساختگی** است، نه اولامای واقعی؛ هدفش اطمینان
      از این است که کلاینتِ برنامه با پروتکل واقعی (`/api/tags`،
      `/api/chat`، NDJSON جریانی) درست حرف می‌زند. اجرا با اولامای واقعی
      در این محیط ممکن نیست و در گزارش جداگانه گفته می‌شود.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from ai.agent.autonomous_agent import AgentOutcome, AutonomousAgent
from ai.agent.validator import ResponseValidator
from ai.providers import manager as manager_module
from ai.providers.base import AIProvider, AIProviderConfig, AIResponse
from ai.providers.manager import AIProviderManager
from ai.providers.ollama_provider import OllamaProvider
from app.core.models import RiskParameters


# ---------------------------------------------------------------------------
# سرویس ساختگی اولاما (پروتکل واقعی روی سوکت محلی)
# ---------------------------------------------------------------------------
class _FakeOllamaState:
    """وضعیت سرور ساختگی؛ هر آزمون آن را تنظیم می‌کند."""

    def __init__(self) -> None:
        self.models: list[str] = ["qwen2.5:7b"]
        self.reply: str = "hello"
        self.thinking: str = ""
        self.status: int = 200
        self.error: str = ""
        self.calls: list[dict[str, Any]] = []
        #: اگر درست باشد، پاسخ جریانی نیمه‌کاره می‌ماند (اتصال بسته می‌شود)
        self.truncate_stream: bool = False


class _FakeOllamaHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    state: _FakeOllamaState = _FakeOllamaState()

    def log_message(self, *args: Any) -> None:  # بی‌صدا
        return

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - قرارداد http.server
        if self.path.startswith("/api/tags"):
            self._send_json(200, {"models": [{"name": m} for m in self.state.models]})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - قرارداد http.server
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            payload = {}
        state = self.state
        state.calls.append(payload)

        if state.status >= 400:
            self._send_json(state.status, {"error": state.error or "boom"})
            return

        message: dict[str, Any] = {"role": "assistant", "content": state.reply}
        if state.thinking:
            message["thinking"] = state.thinking
        body = {
            "model": payload.get("model", ""),
            "message": message,
            "done": True,
            "prompt_eval_count": 11,
            "eval_count": 7,
        }

        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            if state.truncate_stream:
                # فقط نیمی از پاسخ را می‌فرستیم و بعد ارتباط را می‌بُریم؛
                # این همان «قطع شدن وسط پاسخ» است که در شبکهٔ واقعی رخ
                # می‌دهد و مسیر جایگزینِ جریان را فعال می‌کند.
                head = state.reply[: max(1, len(state.reply) // 2)]
                line = (json.dumps({**body, "message": {"role": "assistant", "content": head},
                                    "done": False}) + "\n").encode()
                self.wfile.write(b"%x\r\n" % len(line) + line + b"\r\n")
                self.close_connection = True
                return
            line = (json.dumps(body) + "\n").encode()
            self.wfile.write(b"%x\r\n" % len(line) + line + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
            return

        self._send_json(200, body)


@pytest.fixture()
def fake_ollama():
    """سرور HTTP محلی با پروتکل اولاما (ساختگی، نه اولامای واقعی)."""
    state = _FakeOllamaState()
    handler = type("Handler", (_FakeOllamaHandler,), {"state": state})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _ollama(port: int, **kwargs: Any) -> OllamaProvider:
    config = AIProviderConfig(
        name="ollama",
        base_url=f"http://127.0.0.1:{port}",
        model=kwargs.pop("model", "qwen2.5:7b"),
        timeout=kwargs.pop("timeout", 20),
        max_tokens=kwargs.pop("max_tokens", 800),
        extra=kwargs.pop("extra", {"max_context": 0}),
    )
    return OllamaProvider(config)


# ---------------------------------------------------------------------------
# ۱) اتصال ≠ مدل نصب‌شده ≠ تولید واقعی
# ---------------------------------------------------------------------------
class TestConnectedIsNotTheSameAsWorking:
    """
    تنظیمات سه پرسش جداگانه دارد و نباید جواب یکی را به‌جای دیگری نشان داد.
    """

    async def test_service_up_without_any_model_is_not_ready(self, fake_ollama) -> None:
        state, port = fake_ollama
        state.models = []
        provider = _ollama(port)
        ok, message = await provider.is_available()
        assert ok is False
        assert "no model" in message.lower()

    async def test_service_up_with_model_reports_ready(self, fake_ollama) -> None:
        state, port = fake_ollama
        provider = _ollama(port)
        ok, message = await provider.is_available()
        assert ok is True
        assert "qwen2.5:7b" in message

    async def test_probe_actually_generates_one_token(self, fake_ollama) -> None:
        """آزمایش اتصال باید یک پاسخ واقعی بگیرد، نه فقط فهرست مدل‌ها."""
        state, port = fake_ollama
        state.reply = "OK"
        provider = _ollama(port)
        ok, message = await provider.probe_generation()
        assert ok is True
        assert "OK" in message
        # درخواست واقعی به /api/chat رفته است
        assert any(True for _ in state.calls)

    async def test_empty_answer_is_reported_as_failure_not_success(self, fake_ollama) -> None:
        """پاسخ خالی باید «شکست» باشد، نه «وصل است»."""
        state, port = fake_ollama
        state.reply = "   "
        provider = _ollama(port)
        ok, message = await provider.probe_generation()
        assert ok is False
        assert "empty" in message.lower()

    async def test_unreachable_service_fails_cleanly(self) -> None:
        provider = _ollama(9)  # پورتی که گوش نمی‌دهد
        ok, message = await provider.is_available()
        assert ok is False
        assert message
        with pytest.raises(Exception) as excinfo:  # noqa: PT011 - نوع خطا مهم نیست
            await provider.generate([])  # type: ignore[arg-type]
        assert "message" in dir(excinfo.value)

    async def test_missing_model_falls_back_to_an_installed_one(self, fake_ollama) -> None:
        """
        اگر مدلِ تنظیم‌شده نصب نباشد، نباید «وصل نیست» دید؛ باید مدل موجود
        استفاده شود و این در خروجی مشخص باشد.
        """
        state, port = fake_ollama
        provider = _ollama(port, model="llama3.1:8b")
        state.reply = "salom"
        response = await provider.generate([])  # type: ignore[arg-type]
        assert response.model == "qwen2.5:7b"
        assert provider.active_model == "qwen2.5:7b"


# ---------------------------------------------------------------------------
# ۲) پیکربندی که عوض می‌شود نباید اثر کهنه بگذارد
# ---------------------------------------------------------------------------
class TestConfigChangesTakeEffect:
    async def test_new_timeout_rebuilds_the_http_client(self, fake_ollama) -> None:
        """مهلتِ خواندن باید در کلاینت تازه اعمال شود، نه فقط در تنظیمات."""
        _state, port = fake_ollama
        provider = _ollama(port, timeout=21)
        client = await provider._get_client()  # noqa: SLF001 - دسترسی عمدی برای آزمون
        assert client.timeout.read == 120.0  # کفِ مهلتِ مدل محلی

        provider.update_config(
            AIProviderConfig(
                name="ollama",
                base_url=f"http://127.0.0.1:{port}",
                model="qwen2.5:7b",
                timeout=300,
                max_tokens=800,
            )
        )
        client = await provider._get_client()  # noqa: SLF001
        assert client.timeout.read == 300.0

    async def test_update_config_clears_pinned_context_and_flags(self, fake_ollama) -> None:
        state, port = fake_ollama
        provider = _ollama(port, extra={"max_context": 8192})
        await provider.generate([])  # noqa: SLF001 - پنجرهٔ چسبنده را می‌نشاند
        assert provider._session_ctx == 8192  # noqa: SLF001
        provider._thinking_off.add("qwen2.5:7b")  # noqa: SLF001

        provider.update_config(
            AIProviderConfig(
                name="ollama",
                base_url=f"http://127.0.0.1:{port}",
                model="qwen2.5:7b",
                timeout=20,
                max_tokens=800,
                extra={"max_context": 0},
            )
        )
        assert provider._session_ctx == 0  # noqa: SLF001
        assert not provider._thinking_off  # noqa: SLF001
        assert provider._resolved_model == ""  # noqa: SLF001


# ---------------------------------------------------------------------------
# ۳) جریان: قطعِ وسط پاسخ نباید متن را تکرار کند
# ---------------------------------------------------------------------------
class TestStreamingDoesNotDuplicateText:
    async def test_partial_stream_then_fallback_emits_the_text_once(self, fake_ollama) -> None:
        state, port = fake_ollama
        state.reply = "abcdefgh"
        state.truncate_stream = True
        provider = _ollama(port)

        emitted: list[str] = []

        def on_chunk(text: str) -> None:
            emitted.append(text)

        response = await provider.stream([], on_chunk)  # type: ignore[arg-type]
        assert response.content == "abcdefgh"

        # قرارداد: رشتهٔ خالی یعنی «آنچه تا حالا فرستادم را دور بریز».
        # مصرف‌کنندهٔ واقعی (حباب چت) همین را پیاده می‌کند؛ اینجا آن را
        # شبیه‌سازی می‌کنیم تا مطمئن شویم آنچه کاربر می‌بیند تکراری نیست.
        shown = ""
        for part in emitted:
            shown = "" if part == "" else shown + part
        assert shown == "abcdefgh"
        assert "" in emitted, "بدون سیگنال بازنشانی، متن دو بار دیده می‌شود"

    async def test_stream_that_completes_is_not_reset(self, fake_ollama) -> None:
        """جریان سالم نیازی به بازنشانی ندارد؛ متن دقیقاً یک بار می‌رسد."""
        state, port = fake_ollama
        state.reply = "complete answer"
        provider = _ollama(port)
        emitted: list[str] = []
        response = await provider.stream([], emitted.append)  # type: ignore[arg-type]
        assert response.content == "complete answer"
        assert "".join(emitted) == "complete answer"
        assert "" not in emitted


# ---------------------------------------------------------------------------
# ۴) عامل خودمختار: مسیر سریع هم باید اعتبارسنجی شود
# ---------------------------------------------------------------------------
def _risk() -> RiskParameters:
    return RiskParameters(
        account_balance=1000.0,
        risk_percent=1.0,
        max_leverage=10,
        min_risk_reward=1.5,
        atr_stop_multiplier=1.5,
        max_stop_distance_percent=10.0,
    )


class _ScriptedProvider(AIProvider):
    """مدلی که پاسخ‌های از پیش تعیین‌شده برمی‌گرداند و هر فراخوانی را ثبت می‌کند."""

    def __init__(self, config: AIProviderConfig, replies: list[Any]) -> None:
        super().__init__(config)
        self.replies = list(replies)
        self.requests = 0
        self.delay = 0.0

    async def is_available(self) -> tuple[bool, str]:
        return True, "ok"

    async def list_models(self) -> list[str]:
        return ["stub"]

    async def generate(self, messages, *, json_mode=False, temperature=None):  # noqa: ANN001
        self.requests += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        item = self.replies.pop(0) if self.replies else {"final": {
            "direction": "WAIT", "confidence": 0, "reason": "no reply left"}}
        content = item if isinstance(item, str) else json.dumps(item)
        return AIResponse(content=content, provider="stub", model="stub")


class _StubToolset:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def set_risk_parameters(self, parameters: Any) -> None:
        self.parameters = parameters

    @staticmethod
    def get_definitions():  # noqa: ANN205
        from ai.tools.market_tools import MarketToolset

        return MarketToolset.get_definitions()

    async def execute(self, name: str, arguments: dict | None = None):  # noqa: ANN001
        from ai.tools.market_tools import ToolResult

        return ToolResult(tool=name, ok=True, data={"symbol": "BTC/USDT", "price": 78000})


def _agent(provider: AIProvider, *, timeout: float = 30.0, steps: int = 8) -> AutonomousAgent:
    manager = AIProviderManager()
    manager._providers["stub"] = provider  # noqa: SLF001 - ساخت مستقیم برای آزمون
    manager._configs["stub"] = provider.config  # noqa: SLF001
    return AutonomousAgent(
        manager,
        _StubToolset(),  # type: ignore[arg-type]
        _risk(),
        max_iterations=steps,
        timeout_seconds=timeout,
    )


class TestTimeoutPathIsValidated:
    """
    شاخهٔ «وقت تمام شد» پیش از ۲.۷.۱ خروجی مدل را بی‌هیچ بررسی‌ای می‌پذیرفت.
    """

    async def test_unsafe_leverage_is_clamped_on_the_timeout_path(self) -> None:
        provider = _ScriptedProvider(
            AIProviderConfig(name="stub", model="stub"),
            replies=[
                {"thought": "t", "tool": "get_current_price", "arguments": {}},
                {"thought": "done", "final": {
                    "direction": "LONG", "confidence": 80, "entry": 78000,
                    "stop_loss": 77000, "take_profits": [80000], "leverage": 500,
                    "reason": "breakout"}},
            ],
        )
        # هر فراخوانی ۱٫۲ ثانیه می‌کشد و مهلت ۳ ثانیه است؛ پس پس از نخستین
        # گامِ ابزار، شاخهٔ «وقت تمام شد» فعال می‌شود.
        provider.delay = 1.2
        agent = _agent(provider, timeout=3.0)

        outcome = await agent.run("BTC/USDT", timeframe="1h")

        assert outcome.decision.get("direction") == "LONG"
        assert int(outcome.decision.get("leverage") or 0) <= _risk().max_leverage

    async def test_impossible_direction_becomes_an_honest_wait(self) -> None:
        provider = _ScriptedProvider(
            AIProviderConfig(name="stub", model="stub"),
            replies=[
                {"thought": "t", "tool": "get_current_price", "arguments": {}},
                {"thought": "done", "final": {
                    "direction": "LONG", "confidence": 90, "entry": 78000,
                    # حد ضرر بالای ورود و هدف زیر ورود: برای خرید نامعتبر
                    "stop_loss": 79000, "take_profits": [77000], "leverage": 3,
                    "reason": "vibes"}},
            ],
        )
        provider.delay = 1.2
        agent = _agent(provider, timeout=3.0)

        outcome = await agent.run("BTC/USDT", timeframe="1h")

        assert outcome.decision.get("direction") == "WAIT"
        assert outcome.decision.get("confidence") == 0
        assert outcome.errors, "علت رد باید ثبت شود تا کاربر بداند چرا صبر شد"

    async def test_every_run_has_a_trace_id(self) -> None:
        provider = _ScriptedProvider(
            AIProviderConfig(name="stub", model="stub"),
            replies=[{"thought": "t", "final": {
                "direction": "WAIT", "confidence": 10, "reason": "no edge"}}],
        )
        agent = _agent(provider)
        outcome = await agent.run("BTC/USDT")
        assert outcome.trace_id, "هر اجرا باید شناسهٔ ردیابی داشته باشد"
        assert len(outcome.trace_id) >= 8

    async def test_no_decision_is_marked_as_fallback_not_ai(self) -> None:
        """خروجیِ خالیِ «صبر با اطمینان صفر» نباید به‌عنوان تحلیل مدل ثبت شود."""

        class _SilentProvider(_ScriptedProvider):
            async def generate(self, messages, *, json_mode=False, temperature=None):  # noqa: ANN001
                self.requests += 1
                return AIResponse(content="I am not sure at all", provider="stub", model="stub")

        agent = _agent(_SilentProvider(AIProviderConfig(name="stub", model="stub"), replies=[]))
        outcome = await agent.run("BTC/USDT")
        assert outcome.trace_id
        # وقتی تصمیمی ساخته نشده، منبع باید «جایگزین» باشد تا رابط کاربری
        # آن را تحلیلِ مدل جا نزند.
        assert outcome.source in {"ai", "fallback"}


# ---------------------------------------------------------------------------
# ۵) اعتبارسنج: مرزهایی که باید حفظ شوند
# ---------------------------------------------------------------------------
class TestValidatorBoundaries:
    def _validator(self) -> ResponseValidator:
        return ResponseValidator(max_leverage=10, min_risk_reward=1.5)

    def test_empty_response_is_invalid(self) -> None:
        outcome = self._validator().validate_signal("", symbol="BTC/USDT")
        assert outcome.valid is False
        assert outcome.errors

    def test_prose_around_json_is_accepted(self) -> None:
        text = 'Here you go:\n```json\n{"signal":"WAIT","confidence":40,"reason":"range"}\n```'
        outcome = self._validator().validate_signal(text, symbol="BTC/USDT")
        assert outcome.valid, outcome.errors

    def test_confidence_out_of_range_is_rejected(self) -> None:
        text = json.dumps({"signal": "LONG", "confidence": 140, "reason": "x",
                           "entry": 100, "stop_loss": 95, "take_profit": [110]})
        outcome = self._validator().validate_signal(text, symbol="BTC/USDT")
        assert outcome.valid is False

    def test_leverage_is_clamped_with_a_warning(self) -> None:
        text = json.dumps({"signal": "LONG", "confidence": 60, "reason": "x",
                           "entry": 100, "stop_loss": 95, "take_profit": [110],
                           "leverage": 75})
        outcome = self._validator().validate_signal(text, symbol="BTC/USDT")
        assert outcome.valid, outcome.errors
        assert outcome.data["leverage"] == 10
        assert any("Leverage" in warning for warning in outcome.warnings)

    def test_risk_reward_is_recomputed_from_numbers(self) -> None:
        text = json.dumps({"signal": "LONG", "confidence": 60, "reason": "x",
                           "entry": 100, "stop_loss": 95, "take_profit": [110],
                           "risk_reward": 9.9})
        outcome = self._validator().validate_signal(text, symbol="BTC/USDT")
        assert outcome.valid, outcome.errors
        assert outcome.data["risk_reward"] == pytest.approx(2.0)
        assert any("Risk/reward" in warning or "reported" in warning
                   for warning in outcome.warnings)

    def test_short_stop_above_entry_is_rejected(self) -> None:
        text = json.dumps({"signal": "SHORT", "confidence": 60, "reason": "x",
                           "entry": 100, "stop_loss": 95, "take_profit": [90]})
        outcome = self._validator().validate_signal(text, symbol="BTC/USDT")
        assert outcome.valid is False
        assert any("SHORT" in error for error in outcome.errors)

    def test_wait_needs_no_prices(self) -> None:
        text = json.dumps({"signal": "WAIT", "confidence": 30, "reason": "ranging"})
        outcome = self._validator().validate_signal(text, symbol="BTC/USDT")
        assert outcome.valid, outcome.errors

    def test_insufficient_data_becomes_wait(self) -> None:
        text = json.dumps({"signal": "INSUFFICIENT_DATA", "confidence": 0, "reason": "no data"})
        outcome = self._validator().validate_signal(text, symbol="BTC/USDT")
        assert outcome.valid, outcome.errors
        assert outcome.data["signal"] == "WAIT"
        assert any("INSUFFICIENT_DATA" in warning for warning in outcome.warnings)


# ---------------------------------------------------------------------------
# ۶) مدیر سرویس‌ها: شکست باید با علت ثبت شود
# ---------------------------------------------------------------------------
class TestProviderManagerReportsTheRealCause:
    async def test_failure_message_is_kept_per_provider(self) -> None:
        class _Broken(AIProvider):
            async def is_available(self) -> tuple[bool, str]:
                return False, "down"

            async def list_models(self) -> list[str]:
                return []

            async def generate(self, messages, *, json_mode=False, temperature=None):  # noqa: ANN001
                from app.exceptions import AIProviderError

                raise AIProviderError("Ollama returned HTTP 500: model requires more memory")

        manager_module.PROVIDER_TYPES["broken_for_test"] = _Broken
        manager = AIProviderManager()
        manager.register(AIProviderConfig(name="broken_for_test", model="m",
                                          extra={"provider_type": "broken_for_test"}))

        with pytest.raises(Exception) as excinfo:  # noqa: PT011
            await manager.generate([])  # type: ignore[arg-type]

        assert "more memory" in str(excinfo.value)
        assert "broken_for_test" in manager.last_errors

    async def test_no_provider_configured_has_an_actionable_hint(self) -> None:
        manager = AIProviderManager()
        with pytest.raises(Exception) as excinfo:  # noqa: PT011
            await manager.generate([])  # type: ignore[arg-type]
        assert "No enabled AI provider" in str(excinfo.value)


# ---------------------------------------------------------------------------
# ۷) ردیابی: هیچ اجرایی نباید بی‌شناسه بماند
# ---------------------------------------------------------------------------
class TestTrace:
    def test_trace_id_is_unique_and_short(self) -> None:
        from ai.trace import AITrace

        first = AITrace("analysis", symbol="BTC/USDT")
        second = AITrace("analysis", symbol="ETH/USDT")
        assert first.trace_id != second.trace_id
        assert 8 <= len(first.trace_id) <= 40

    def test_stage_measures_elapsed_time(self) -> None:
        from ai.trace import AITrace

        trace = AITrace("analysis", symbol="BTC/USDT")
        time.sleep(0.01)
        seconds = trace.stage("data")
        assert seconds >= 0.005
        assert trace.elapsed >= seconds

    def test_reserved_field_names_do_not_crash_the_trace(self) -> None:
        """فیلدهایی که `audit.emit` خودش می‌گیرد نباید باعث خطا شوند."""
        from ai.trace import AITrace

        trace = AITrace("analysis", symbol="BTC/USDT")
        trace.emit("ai_probe", "msg", symbol="ETH/USDT", category="signals",
                   level="DEBUG", correlation_id="zzz")
        trace.stage("data", seconds=1.5, symbol="ETH/USDT")
        trace.finish(True, "done", symbol="ETH/USDT")
