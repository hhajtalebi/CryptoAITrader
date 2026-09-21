"""
آزمون‌های پاسخ جریانی چت (تایپ تدریجی).

سه لایه سنجیده می‌شود:
۱. تجزیهٔ SSE در `OpenAICompatibleProvider`
۲. استخراج تدریجی `answer` از JSON ناقص
۳. اتصال عامل گفتگو و صفحهٔ چت

همه آفلاین‌اند؛ هیچ آزمونی به شبکه وابسته نیست.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from ai.agent.stream_extractor import StreamingAnswerExtractor
from ai.providers.base import AIMessage, AIProvider, AIProviderConfig, AIResponse
from ai.providers.openai_compatible import _STREAM_DONE, OpenAICompatibleProvider

# ---------------------------------------------------------------------------
# ۱) تجزیهٔ خطوط SSE
# ---------------------------------------------------------------------------
_parse = OpenAICompatibleProvider._parse_sse_line


def test_blank_and_comment_lines_are_ignored() -> None:
    """خطوط خالی و کامنت keep-alive نباید چیزی تولید کنند."""
    assert _parse("") is None
    assert _parse("   ") is None
    assert _parse(": ping") is None


def test_done_marker_is_recognised() -> None:
    """پایان جریان باید تشخیص داده شود."""
    assert _parse("data: [DONE]") is _STREAM_DONE
    assert _parse("[DONE]") is _STREAM_DONE


def test_broken_json_is_skipped_not_raised() -> None:
    """
    JSON خراب نباید استثنا بدهد.

    بعضی درگاه‌ها میان جریان خط ناقص می‌فرستند؛ یک خط بد نباید کل پاسخ
    را از بین ببرد.
    """
    assert _parse("data: {not json") is None
    assert _parse("data: [1,2,3]") is None


def test_content_delta_is_extracted() -> None:
    """متن باید از delta.content بیرون بیاید."""
    line = 'data: {"model":"m1","choices":[{"delta":{"content":"سلام"}}]}'
    text, model, finish, usage = _parse(line)
    assert text == "سلام"
    assert model == "m1"
    assert finish == ""
    assert usage == {}


def test_reasoning_field_is_used_when_content_is_empty() -> None:
    """مدل‌های استدلالی گاهی متن را در reasoning می‌گذارند."""
    line = 'data: {"choices":[{"delta":{"reasoning_content":"فکر"}}]}'
    text, *_ = _parse(line)
    assert text == "فکر"


def test_finish_reason_and_usage_are_captured() -> None:
    """آمار مصرف توکن باید از فریم پایانی خوانده شود."""
    line = (
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
        '"usage":{"prompt_tokens":5,"completion_tokens":7}}'
    )
    text, _model, finish, usage = _parse(line)
    assert text == ""
    assert finish == "stop"
    assert usage["prompt_tokens"] == 5
    assert usage["completion_tokens"] == 7


def test_openai_compatible_advertises_streaming() -> None:
    """سرویس‌های سازگار با OpenAI باید جریان را اعلام کنند."""
    provider = OpenAICompatibleProvider(
        AIProviderConfig(name="x", base_url="http://localhost:1/v1", model="m")
    )
    assert provider.supports_streaming is True


# ---------------------------------------------------------------------------
# ۲) استخراج تدریجی پاسخ
# ---------------------------------------------------------------------------
def _drain(chunks: list[str]) -> tuple[str, StreamingAnswerExtractor]:
    """پخش تکه‌ها و برگرداندن متنی که کاربر دیده است."""
    extractor = StreamingAnswerExtractor()
    shown = ""
    for chunk in chunks:
        shown += extractor.feed(chunk)
    return shown, extractor


def test_json_answer_is_revealed_progressively() -> None:
    """
    کاربر باید متن پاسخ را ببیند، نه ساختار JSON را.

    این اصل ماجراست: بدون استخراج، روی صفحه `{"answer": "سلا` می‌افتاد.
    """
    shown, extractor = _drain(['{"ans', 'wer": "سلا', "م دنیا", '"}'])
    assert shown == "سلام دنیا"
    assert extractor.finish() == "سلام دنیا"
    assert "{" not in shown


def test_structure_before_answer_is_not_shown() -> None:
    """تا رسیدن به مقدار answer نباید چیزی نمایش داده شود."""
    shown, _ = _drain(['{"too', 'l": "get_price", ', '"args": {}'])
    assert shown == ""


def test_answer_after_another_key_is_found() -> None:
    """ترتیب کلیدها نباید مهم باشد."""
    shown, _ = _drain(['{"action": {"x": 1}, "answer": "بعدی"}'])
    assert shown == "بعدی"


def test_text_key_is_accepted_as_answer() -> None:
    """کلید جایگزین `text` هم پذیرفته می‌شود."""
    shown, _ = _drain(['{"text": "متن جایگزین"}'])
    assert shown == "متن جایگزین"


def test_plain_text_streams_through_untouched() -> None:
    """اگر مدل JSON ندهد، متن خام همان‌طور پخش می‌شود."""
    shown, _ = _drain(["سلام ", "بدون ", "جیسون"])
    assert shown == "سلام بدون جیسون"


def test_escaped_newline_becomes_a_real_newline() -> None:
    """کاربر نباید `\\n` را به‌صورت دو نویسه ببیند."""
    shown, _ = _drain(['{"answer": "خط اول\\nخط دوم"}'])
    assert shown == "خط اول\nخط دوم"


def test_unicode_escape_split_across_chunks() -> None:
    """
    گریز یونیکدِ نصفه‌شده بین دو تکه نباید خراب شود.

    اگر `\\u06c` در یک تکه و `c` در تکهٔ بعدی بیاید، نباید نویسهٔ بی‌معنی
    نمایش داده شود.
    """
    shown, _ = _drain(['{"answer": "\\u06c', 'c\\u06a9"}'])
    assert shown == "یک"


def test_inner_quotes_are_unescaped() -> None:
    """نقل‌قول داخلی باید درست باز شود."""
    shown, _ = _drain(['{"answer": "او گفت \\"سلام\\" و رفت"}'])
    assert shown == 'او گفت "سلام" و رفت'


def test_code_fence_is_skipped() -> None:
    """حصار ```json نباید روی صفحه بیفتد."""
    shown, _ = _drain(["```json\n", '{"answer": "با حصار"}', "\n```"])
    assert shown == "با حصار"


def test_feed_returns_only_the_delta() -> None:
    """
    هر بار فقط متن تازه برگردد.

    مصرف‌کننده متن را به انتهای حباب می‌چسباند؛ اگر کل رشته برگردد،
    پاسخ چند برابر می‌شود.
    """
    extractor = StreamingAnswerExtractor()
    first = extractor.feed('{"answer": "ابتدا')
    second = extractor.feed(' و ادامه"}')
    assert first == "ابتدا"
    assert second == " و ادامه"


def test_reset_clears_everything() -> None:
    """بازنشانی باید حافظه را کاملاً پاک کند."""
    extractor = StreamingAnswerExtractor()
    extractor.feed('{"answer": "قدیمی"}')
    extractor.reset()
    assert extractor.finish() == ""
    assert extractor.feed('{"answer": "تازه"}') == "تازه"


def test_empty_chunk_is_harmless() -> None:
    """تکهٔ خالی نباید چیزی تغییر دهد."""
    extractor = StreamingAnswerExtractor()
    assert extractor.feed("") == ""


# ---------------------------------------------------------------------------
# ۳) لایهٔ سرویس: جریان و بازگشت به حالت عادی
# ---------------------------------------------------------------------------
class _FakeStreamProvider(AIProvider):
    """سرویس ساختگی که تکه‌های از پیش تعیین‌شده می‌دهد."""

    def __init__(self, chunks: list[str], *, name: str = "fake", fail: bool = False) -> None:
        super().__init__(AIProviderConfig(name=name, base_url="http://x/v1", model="m"))
        self._chunks = chunks
        self._fail = fail
        self.generate_calls = 0

    @property
    def supports_streaming(self) -> bool:
        return True

    async def is_available(self):
        return True, "ok"

    async def list_models(self):
        return ["m"]

    async def generate(self, messages, *, json_mode=False, temperature=None):
        self.generate_calls += 1
        return AIResponse(
            content="پاسخ کامل", provider=self.name, model="m", finish_reason="stop"
        )

    async def stream(self, messages, on_chunk, *, temperature=None):
        if self._fail:
            raise RuntimeError("stream exploded")
        for chunk in self._chunks:
            on_chunk(chunk)
        return AIResponse(
            content="".join(self._chunks),
            provider=self.name,
            model="m",
            finish_reason="stop",
        )


def test_base_provider_falls_back_to_generate() -> None:
    """
    سرویسی که جریان ندارد باید از راه `generate` کار کند.

    یعنی لایهٔ بالاتر لازم نیست هیچ شرطی بگذارد.
    """

    class _NoStream(AIProvider):
        async def is_available(self):
            return True, "ok"

        async def list_models(self):
            return []

        async def generate(self, messages, *, json_mode=False, temperature=None):
            return AIResponse(content="یکجا", provider="n", model="m", finish_reason="stop")

    provider = _NoStream(AIProviderConfig(name="n", base_url="http://x", model="m"))
    assert provider.supports_streaming is False

    received: list[str] = []
    response = asyncio.run(provider.stream([AIMessage(role="user", content="hi")], received.append))
    assert received == ["یکجا"]
    assert response.content == "یکجا"


def test_manager_streams_from_the_first_provider() -> None:
    """مدیر باید تکه‌ها را از سرویس فعال عبور دهد."""
    manager = _manager_with(_FakeStreamProvider(["الف", "ب", "ج"]))

    received: list[str] = []
    response = asyncio.run(
        manager.stream([AIMessage(role="user", content="hi")], received.append)
    )
    assert received == ["الف", "ب", "ج"]
    assert response.content == "الفبج"


def test_manager_resets_the_view_before_switching_provider() -> None:
    """
    اگر سرویس اول وسط جریان بشکند، متن نیمه‌کاره باید پاک شود.

    بدون این، پاسخ سرویس دوم به دنبالهٔ متن ناقص سرویس اول می‌چسبد و
    چیزی بی‌معنی نمایش داده می‌شود.
    """
    class _HalfThenFail(_FakeStreamProvider):
        async def stream(self, messages, on_chunk, *, temperature=None):
            on_chunk("نیمه")
            raise RuntimeError("died mid-stream")

    manager = _manager_with(
        _HalfThenFail([], name="first"), _FakeStreamProvider(["کامل"], name="second")
    )
    manager.set_fallback_enabled(True)

    received: list[str] = []
    response = asyncio.run(
        manager.stream([AIMessage(role="user", content="hi")], received.append)
    )
    # رشتهٔ خالی یعنی «پاک کن»
    assert "" in received
    assert received[-1] == "کامل"
    assert response.content == "کامل"


# ---------------------------------------------------------------------------
# ۴) عامل گفتگو
# ---------------------------------------------------------------------------
class _EmptyToolset:
    """ابزارخانهٔ خالی تا عامل مستقیم پاسخ متنی بدهد."""

    tool_names: list[str] = []

    def get_definitions(self):
        return []

    async def execute(self, name, args):  # pragma: no cover - صدا زده نمی‌شود
        raise AssertionError("no tools should run")


def _manager_with(*providers):
    """
    مدیر سرویس با نمونه‌های آماده.

    `register()` از روی config نمونه می‌سازد، ولی اینجا نمونهٔ ساختگیِ
    خودمان لازم است؛ پس مستقیم در جدول داخلی می‌نشانیم.
    """
    from ai.providers.manager import AIProviderManager

    manager = AIProviderManager()
    for provider in providers:
        manager._providers[provider.name] = provider  # noqa: SLF001
        manager._configs[provider.name] = provider._config  # noqa: SLF001
    return manager


def _agent_with(provider):
    """ساخت عامل گفتگو روی یک سرویس مشخص."""
    from ai.agent.chat_agent import ChatAgent

    risk = SimpleNamespace(max_leverage=5, min_risk_reward=1.5)
    return ChatAgent(_manager_with(provider), _EmptyToolset(), risk)


def test_agent_streams_when_no_tools_are_registered() -> None:
    """
    بدون ابزار، پاسخ حتماً متنی است پس جریان بی‌خطر است.

    کاربر باید متن را در حال شکل‌گیری ببیند.
    """
    provider = _FakeStreamProvider(['{"answer": "سلا', 'م"}'])
    agent = _agent_with(provider)

    seen: list[tuple[str, bool]] = []
    agent.set_stream_callback(lambda delta, replace: seen.append((delta, replace)))

    reply = asyncio.run(agent.send("سلام"))
    assert reply.text == "سلام"
    assert "".join(d for d, _ in seen) == "سلام"


class _ToolsetWithDefinitions(_EmptyToolset):
    """
    ابزارخانه‌ای که واقعاً ابزار دارد — مثل برنامهٔ واقعی.

    در برنامه، ابزارها همیشه ثبت‌اند. نسخهٔ اول این قابلیت، جریان را در
    دور اول خاموش می‌کرد و چون رایج‌ترین حالت (پرسش ساده) در همان دور
    اول پاسخ می‌گیرد، عملاً هیچ‌وقت جریان نداشتیم.
    """

    tool_names = ["get_price"]

    def get_definitions(self):
        # تعریف ابزار شیء است نه دیکشنری (عامل به `.name` دسترسی می‌گیرد)
        return [
            SimpleNamespace(
                name="get_price",
                description="قیمت لحظه‌ای یک نماد",
                parameters={"symbol": "str"},
            )
        ]


def test_agent_streams_even_when_tools_are_registered() -> None:
    """
    وجود ابزار نباید جریان را خاموش کند.

    این دقیقاً رگرسیونی است که فقط در آزمون زندهٔ رابط کاربری دیده شد:
    همه‌چیز در آزمون واحد سبز بود ولی کاربر هیچ تایپ تدریجی نمی‌دید.
    """
    from ai.agent.chat_agent import ChatAgent

    provider = _FakeStreamProvider(['{"answer": "پاسخ ', 'ساده"}'])
    risk = SimpleNamespace(max_leverage=5, min_risk_reward=1.5)
    agent = ChatAgent(_manager_with(provider), _ToolsetWithDefinitions(), risk)

    seen: list[str] = []
    agent.set_stream_callback(lambda delta, replace: seen.append(delta))

    reply = asyncio.run(agent.send("سلام"))
    assert reply.text == "پاسخ ساده"
    assert "".join(seen) == "پاسخ ساده"
    assert provider.generate_calls == 0  # از مسیر جریان آمد، نه generate


def test_tool_request_is_not_shown_to_the_user() -> None:
    """
    درخواست ابزار نباید روی صفحه بیفتد.

    مدل در دور اول `{"tool": ...}` می‌دهد؛ استخراج‌گر فقط `answer` را
    می‌خواند، پس کاربر ساختار داخلی را نمی‌بیند — فقط پاسخ نهایی را.
    """
    from ai.agent.chat_agent import ChatAgent

    class _TwoRound(_FakeStreamProvider):
        """دور اول ابزار می‌خواهد، دور دوم پاسخ می‌دهد."""

        def __init__(self) -> None:
            super().__init__([])
            self.round = 0

        async def stream(self, messages, on_chunk, *, temperature=None):
            self.round += 1
            if self.round == 1:
                text = '{"tool": "get_price", "arguments": {"symbol": "BTC/USDT"}}'
            else:
                text = '{"answer": "قیمت ۷۷ هزار دلار است"}'
            for piece in (text[:15], text[15:]):
                on_chunk(piece)
            return AIResponse(
                content=text, provider=self.name, model="m", finish_reason="stop"
            )

    class _RunnableTools(_ToolsetWithDefinitions):
        async def execute(self, name, args):
            return SimpleNamespace(ok=True, data={"price": 77000}, error="")

    provider = _TwoRound()
    risk = SimpleNamespace(max_leverage=5, min_risk_reward=1.5)
    agent = ChatAgent(_manager_with(provider), _RunnableTools(), risk)

    shown = ""
    def on_stream(delta: str, replace: bool) -> None:
        nonlocal shown
        shown = delta if replace else shown + delta

    agent.set_stream_callback(on_stream)
    reply = asyncio.run(agent.send("قیمت بیت‌کوین؟"))

    assert reply.text == "قیمت ۷۷ هزار دلار است"
    # نه نام ابزار و نه ساختار JSON نباید دیده شده باشد
    assert "get_price" not in shown
    assert "{" not in shown
    assert shown == "قیمت ۷۷ هزار دلار است"


def test_agent_without_callback_uses_plain_generate() -> None:
    """بدون ثبت مصرف‌کننده، مسیر عادی باید طی شود."""
    provider = _FakeStreamProvider(['{"answer": "بدون جریان"}'])
    agent = _agent_with(provider)
    reply = asyncio.run(agent.send("سلام"))
    assert reply.text == "پاسخ کامل"  # از generate آمده
    assert provider.generate_calls == 1


def test_streaming_enabled_reflects_the_callback() -> None:
    """پرچم باید وضعیت واقعی را نشان دهد."""
    agent = _agent_with(_FakeStreamProvider([]))
    assert agent.streaming_enabled is False
    agent.set_stream_callback(lambda d, r: None)
    assert agent.streaming_enabled is True
    agent.set_stream_callback(None)
    assert agent.streaming_enabled is False


def test_stream_callback_error_does_not_break_the_reply() -> None:
    """خطای رابط کاربری نباید پاسخ را از بین ببرد."""
    provider = _FakeStreamProvider(['{"answer": "پابرجا"}'])
    agent = _agent_with(provider)

    def boom(_delta, _replace):
        raise RuntimeError("ui exploded")

    agent.set_stream_callback(boom)
    reply = asyncio.run(agent.send("سلام"))
    assert reply.text == "پابرجا"


# ---------------------------------------------------------------------------
# ۵) صفحهٔ چت
# ---------------------------------------------------------------------------
@pytest.fixture
def chat_page(qt_application):
    """صفحهٔ چت سبک، بدون ساخت کل برنامه."""
    from localization.translator import Translator
    from ui.pages.chat_page import ChatPage

    return ChatPage(Translator("fa"))


def test_stream_delta_appends_to_the_pending_bubble(chat_page) -> None:
    """تکه‌ها باید پشت سر هم در حباب انتظار بنشینند."""
    chat_page.begin_reply()
    chat_page.stream_delta("سلام")
    chat_page.stream_delta(" دنیا")
    assert chat_page.streamed_text == "سلام دنیا"


def test_stream_delta_with_replace_clears_previous_text(chat_page) -> None:
    """بازنشانی باید متن قبلی را دور بریزد، نه به آن اضافه کند."""
    chat_page.begin_reply()
    chat_page.stream_delta("نیمه‌کاره")
    chat_page.stream_delta("", True)
    assert chat_page.streamed_text == ""
    chat_page.stream_delta("تازه")
    assert chat_page.streamed_text == "تازه"


def test_stream_delta_without_a_pending_bubble_is_safe(chat_page) -> None:
    """
    تکهٔ دیررسیده پس از پایان پاسخ نباید برنامه را بشکند.

    این واقعاً رخ می‌دهد: پاسخ تمام می‌شود ولی یک سیگنال در صف مانده.
    """
    chat_page.stream_delta("یتیم")  # نباید استثنا بدهد


def test_begin_reply_clears_the_previous_stream(chat_page) -> None:
    """بافر نوبت قبل نباید به نوبت تازه نشت کند."""
    chat_page.begin_reply()
    chat_page.stream_delta("نوبت اول")
    chat_page.finish_reply("نوبت اول")
    chat_page.begin_reply()
    assert chat_page.streamed_text == ""


def test_finish_reply_overrides_streamed_text(chat_page) -> None:
    """
    متن نهایی باید جایگزین متن جریانی شود.

    اگر جریان ناقص مانده باشد، پاسخ معتبر آن را اصلاح می‌کند.
    """
    chat_page.begin_reply()
    chat_page.stream_delta("ناقـ")
    chat_page.finish_reply("ناقص نیست، کامل است")
    assert chat_page.streamed_text == ""
    assert chat_page._bubbles[-1].text() == "ناقص نیست، کامل است"


def test_streaming_setting_defaults_to_on() -> None:
    """جریان باید پیش‌فرض روشن باشد؛ بی‌خطر است چون خودکار برمی‌گردد."""
    from app.config.defaults import DEFAULT_SETTINGS, SettingKey

    assert DEFAULT_SETTINGS[SettingKey.AI_CHAT_STREAMING.value] is True


def test_streaming_setting_is_a_user_preference() -> None:
    """کلید باید در فهرست ترجیحات کاربر باشد تا در تنظیمات ذخیره شود."""
    from app.config.defaults import SettingKey
    from app.core.auth_service import PREFERENCE_KEYS

    assert SettingKey.AI_CHAT_STREAMING.value in PREFERENCE_KEYS
