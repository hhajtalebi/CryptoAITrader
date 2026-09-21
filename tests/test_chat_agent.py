"""
آزمون‌های دستیار گفتگو.

تمرکز این آزمون‌ها روی سه چیز است:
    ۱) گفتگو با مدل‌هایی که خروجی تمیز نمی‌دهند هم باید کار کند
    ۲) ابزارها فقط با نام‌های شناخته‌شده اجرا شوند (مرز امنیتی)
    ۳) اقدام‌ها فقط پیشنهاد باشند و انواع ناشناخته دور ریخته شوند

از یک مدیر ارائه‌دهنده ساختگی استفاده می‌شود چون در محیط آزمون نه سرویس
هوش مصنوعی هست و نه باید هزینه‌ای ایجاد شود.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai.agent.chat_agent import MAX_HISTORY_MESSAGES, ChatAgent, ChatToolCall
from ai.providers.base import AIResponse


class FakeToolResult:
    """نتیجه ابزار ساختگی."""

    def __init__(self, ok: bool = True, data: object | None = None) -> None:
        self.ok = ok
        self.data = data if data is not None else {"last": 78100.0}

    def to_dict(self) -> dict[str, object]:
        """قالب مورد انتظار دستیار."""
        return {"tool": "get_ticker", "ok": self.ok, "data": self.data}


class FakeToolset:
    """مجموعه ابزار ساختگی که فراخوانی‌ها را ثبت می‌کند."""

    tool_names = ["get_ticker", "get_current_price", "calculate_indicator"]

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.calls: list[tuple[str, dict]] = []

    def get_definitions(self) -> list[SimpleNamespace]:
        """تعریف ابزارها برای ساخت Prompt."""
        return [
            SimpleNamespace(name="get_ticker", description="24h stats", parameters={"symbol": {}}),
            SimpleNamespace(name="get_current_price", description="price", parameters={"symbol": {}}),
            SimpleNamespace(
                name="calculate_indicator", description="indicator", parameters={"symbol": {}, "indicator": {}}
            ),
        ]

    def set_risk_parameters(self, parameters: object) -> None:
        """هم‌گام‌سازی ریسک (در آزمون بی‌اثر)."""

    async def execute(self, name: str, arguments: dict) -> FakeToolResult:
        """ثبت و اجرای ساختگی ابزار."""
        self.calls.append((name, dict(arguments)))
        return FakeToolResult(self.ok)


class ScriptedManager:
    """مدیر ارائه‌دهنده که پاسخ‌های از پیش نوشته‌شده می‌دهد."""

    def __init__(self, script: list[str], has_providers: bool = True) -> None:
        self.script = list(script)
        self.has_providers = has_providers
        self.calls = 0

    async def generate(self, messages: list, **kwargs: object) -> AIResponse:
        """برگرداندن پاسخ بعدی از فیلم‌نامه."""
        self.calls += 1
        content = self.script.pop(0) if self.script else '{"answer": "done"}'
        return AIResponse(content=content, provider="stub", model="stub-1")

    async def check_all(self) -> dict[str, tuple[bool, str]]:
        """وضعیت ساختگی سرویس."""
        return {"stub": (True, "ready")}


RISK = SimpleNamespace(max_leverage=5, min_risk_reward=1.5)


def make_agent(script: list[str], toolset: FakeToolset | None = None) -> tuple[ChatAgent, FakeToolset]:
    """ساخت دستیار آماده آزمون."""
    tools = toolset or FakeToolset()
    return ChatAgent(ScriptedManager(script), tools, RISK), tools


# ----------------------------------------------------------------------
# پاسخ‌دهی پایه
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_plain_json_answer() -> None:
    """پاسخ ساده JSON باید مستقیم نمایش داده شود."""
    agent, _ = make_agent([json.dumps({"answer": "سلام"})])
    reply = await agent.send("سلام")
    assert reply.succeeded
    assert reply.text == "سلام"
    assert reply.error == ""


@pytest.mark.asyncio
async def test_non_json_reply_is_accepted() -> None:
    """
    مدل‌های کوچک اغلب JSON نمی‌دهند.

    برای یک چت، متن خام کاملاً قابل استفاده است و نباید خطا شود.
    """
    agent, _ = make_agent(["فقط یک جمله ساده بدون JSON"])
    reply = await agent.send("سلام")
    assert reply.succeeded
    assert "بدون JSON" in reply.text


@pytest.mark.asyncio
async def test_fenced_json_is_parsed() -> None:
    """JSON داخل ``` هم باید خوانده شود."""
    agent, _ = make_agent(['```json\n{"answer": "fenced"}\n```'])
    reply = await agent.send("hi")
    assert reply.text == "fenced"


@pytest.mark.asyncio
async def test_empty_message_is_rejected() -> None:
    """پیام خالی نباید به سرویس فرستاده شود."""
    agent, _ = make_agent([])
    reply = await agent.send("   ")
    assert not reply.succeeded
    assert reply.error == "Empty message"


@pytest.mark.asyncio
async def test_no_provider_reports_clearly() -> None:
    """بدون سرویس پیکربندی‌شده باید پیام روشن بدهد، نه خطای مبهم."""
    agent = ChatAgent(ScriptedManager([], has_providers=False), FakeToolset(), RISK)
    reply = await agent.send("hi")
    assert not reply.succeeded
    assert "provider" in reply.error.lower()


# ----------------------------------------------------------------------
# ابزارها
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tool_call_then_answer() -> None:
    """دستیار باید ابزار را اجرا کند و بعد با داده‌اش جواب بدهد."""
    script = [
        json.dumps({"thought": "need price", "tools": [{"name": "get_ticker", "arguments": {"symbol": "BTC/USDT"}}]}),
        json.dumps({"answer": "قیمت ۷۸۱۰۰ است"}),
    ]
    agent, tools = make_agent(script)
    reply = await agent.send("قیمت چنده؟")

    assert reply.succeeded
    assert tools.calls == [("get_ticker", {"symbol": "BTC/USDT"})]
    assert reply.tools_used == ["get_ticker"]


@pytest.mark.asyncio
async def test_single_tool_format_is_supported() -> None:
    """قالب ساده `tool` (نه `tools`) هم باید پذیرفته شود."""
    script = [
        json.dumps({"tool": "get_current_price", "arguments": {"symbol": "ETH/USDT"}}),
        json.dumps({"answer": "ok"}),
    ]
    agent, tools = make_agent(script)
    await agent.send("price?")
    assert tools.calls[0][0] == "get_current_price"


@pytest.mark.asyncio
async def test_unknown_tool_is_never_executed() -> None:
    """
    مرز امنیتی: فقط ابزارهای ثبت‌شده اجرا می‌شوند.

    اگر مدل (یا متنی که از بازار خوانده) نام ابزار جعلی بدهد، باید بی‌اثر
    بماند.
    """
    script = [
        json.dumps({"tools": [{"name": "delete_database", "arguments": {}}]}),
        json.dumps({"answer": "no"}),
    ]
    agent, tools = make_agent(script)
    reply = await agent.send("do it")
    assert tools.calls == []
    assert reply.succeeded


@pytest.mark.asyncio
async def test_context_symbol_is_injected() -> None:
    """اگر مدل نماد را ننویسد، نماد انتخاب‌شده در رابط کاربری جایگزین شود."""
    script = [
        json.dumps({"tools": [{"name": "get_ticker", "arguments": {}}]}),
        json.dumps({"answer": "ok"}),
    ]
    agent, tools = make_agent(script)
    await agent.send("تحلیلش کن", context={"symbol": "SOL/USDT", "timeframe": "1h"})
    assert tools.calls[0][1]["symbol"] == "SOL/USDT"


@pytest.mark.asyncio
async def test_tool_call_limit_is_enforced() -> None:
    """درخواست ابزار بیش از سقف باید بریده شود."""
    many = [{"name": "get_ticker", "arguments": {"symbol": f"X{i}/USDT"}} for i in range(10)]
    script = [json.dumps({"tools": many}), json.dumps({"answer": "ok"})]
    tools = FakeToolset()
    agent = ChatAgent(ScriptedManager(script), tools, RISK, max_tool_calls=2)
    await agent.send("go")
    assert len(tools.calls) == 2


@pytest.mark.asyncio
async def test_failed_tool_does_not_break_chat() -> None:
    """ابزار ناموفق باید گزارش شود ولی گفتگو ادامه یابد."""
    script = [
        json.dumps({"tools": [{"name": "get_ticker", "arguments": {"symbol": "BTC/USDT"}}]}),
        json.dumps({"answer": "داده در دسترس نبود"}),
    ]
    agent, _ = make_agent(script, FakeToolset(ok=False))
    reply = await agent.send("قیمت؟")
    assert reply.succeeded
    assert reply.tools_used == []
    assert reply.tool_calls[0].ok is False


@pytest.mark.asyncio
async def test_progress_callback_receives_calls() -> None:
    """رابط کاربری باید بتواند پیشرفت را نشان دهد."""
    script = [
        json.dumps({"tools": [{"name": "get_ticker", "arguments": {"symbol": "BTC/USDT"}}]}),
        json.dumps({"answer": "ok"}),
    ]
    agent, _ = make_agent(script)
    seen: list[ChatToolCall] = []
    agent.set_progress_callback(seen.append)
    await agent.send("hi")
    assert len(seen) == 1
    assert seen[0].name == "get_ticker"


# ----------------------------------------------------------------------
# اقدام‌ها
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_valid_action_is_returned() -> None:
    """اقدام معتبر باید به رابط کاربری برسد تا دکمه‌اش نمایش داده شود."""
    payload = {
        "answer": "می‌توانم سیگنال بگیرم",
        "action": {"type": "generate_signal", "symbol": "BTC/USDT", "timeframe": "4h", "label": "بگیر"},
    }
    agent, _ = make_agent([json.dumps(payload)])
    reply = await agent.send("سیگنال بده")
    assert reply.action is not None
    assert reply.action.type == "generate_signal"
    assert reply.action.symbol == "BTC/USDT"


@pytest.mark.asyncio
async def test_unknown_action_type_is_dropped() -> None:
    """
    مرز امنیتی: فقط اقدام‌های تعریف‌شده پذیرفته می‌شوند.

    مدل نباید بتواند رفتار جدیدی اختراع کند.
    """
    payload = {"answer": "x", "action": {"type": "transfer_funds", "label": "send"}}
    agent, _ = make_agent([json.dumps(payload)])
    reply = await agent.send("hi")
    assert reply.action is None


@pytest.mark.asyncio
async def test_action_falls_back_to_context_symbol() -> None:
    """اگر اقدام نماد نداشته باشد، از زمینه گفتگو پر شود."""
    payload = {"answer": "ok", "action": {"type": "run_analysis"}}
    agent, _ = make_agent([json.dumps(payload)])
    reply = await agent.send("تحلیل کن", context={"symbol": "ADA/USDT", "timeframe": "1d"})
    assert reply.action is not None
    assert reply.action.symbol == "ADA/USDT"


# ----------------------------------------------------------------------
# حافظه گفتگو
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_history_is_kept_between_turns() -> None:
    """دستیار باید نوبت قبلی را به یاد داشته باشد."""
    agent, _ = make_agent([json.dumps({"answer": "یک"}), json.dumps({"answer": "دو"})])
    await agent.send("اول")
    await agent.send("دوم")
    assert agent.message_count == 4  # دو پرسش و دو پاسخ


@pytest.mark.asyncio
async def test_reset_clears_history() -> None:
    """گفتگوی جدید باید حافظه را خالی کند."""
    agent, _ = make_agent([json.dumps({"answer": "یک"})])
    await agent.send("سلام")
    assert agent.message_count > 0
    agent.reset()
    assert agent.message_count == 0


@pytest.mark.asyncio
async def test_history_is_trimmed() -> None:
    """گفتگوی طولانی نباید بی‌نهایت رشد کند."""
    script = [json.dumps({"answer": f"پاسخ {i}"}) for i in range(30)]
    agent, _ = make_agent(script)
    for i in range(30):
        await agent.send(f"پیام {i}")
    assert agent.message_count <= MAX_HISTORY_MESSAGES


@pytest.mark.asyncio
async def test_health_check_reports_ready() -> None:
    """بررسی سلامت باید سرویس آماده را گزارش کند."""
    agent, _ = make_agent([])
    ok, detail = await agent.health_check()
    assert ok
    assert "stub" in detail
