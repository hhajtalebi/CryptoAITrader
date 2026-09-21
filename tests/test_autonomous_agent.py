"""
آزمون‌های عامل خودمختار.

تمرکز آزمون‌ها روی رفتار عامل است، نه روی هوش مدل: مدل ساختگی
(`ScriptedProvider`) پاسخ‌های از پیش تعیین‌شده می‌دهد تا بتوانیم بررسی
کنیم عامل در برابر پاسخ خراب، ابزار ناموجود و پیشنهاد خطرناک چه می‌کند.
"""

from __future__ import annotations

import json

import pytest

from ai.agent.autonomous_agent import AgentStep, AutonomousAgent
from ai.providers import manager as manager_module
from ai.providers.base import AIProvider, AIProviderConfig, AIResponse
from ai.providers.manager import AIProviderManager
from app.core.models import RiskParameters

VALID_LONG = {
    "thought": "clean setup",
    "final": {
        "direction": "LONG",
        "confidence": 72,
        "entry_min": 78000,
        "entry_max": 78200,
        "stop_loss": 76500,
        "take_profits": [80000, 82000, 84000],
        "leverage": 5,
        "trend": "BULLISH",
        "market_structure": "UPTREND",
        "reason": "Higher lows with volume expansion.",
        "invalidation": "4h close below 76500",
        "narrative": "Buyers remain in control.",
    },
}

INVALID_LONG = {
    "thought": "reckless",
    "final": {
        "direction": "LONG",
        "confidence": 95,
        "entry_min": 78000,
        "entry_max": 78100,
        "stop_loss": 79000,          # حد ضرر بالای ورود در خرید: نامعتبر
        "take_profits": [77000],     # هدف زیر ورود در خرید: نامعتبر
        "leverage": 75,
        "trend": "BULLISH",
        "market_structure": "UPTREND",
        "reason": "vibes",
        "narrative": "n",
    },
}


class _StubToolset:
    """مجموعه ابزار ساختگی که بدون شبکه پاسخ می‌دهد."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._fail = fail

    def set_risk_parameters(self, parameters):  # noqa: ANN001, ANN201
        self.parameters = parameters

    @staticmethod
    def get_definitions():  # noqa: ANN205
        from ai.tools.market_tools import MarketToolset

        return MarketToolset.get_definitions()

    async def execute(self, name, arguments=None):  # noqa: ANN001, ANN201
        from ai.tools.market_tools import ToolResult

        self.calls.append((name, dict(arguments or {})))
        if self._fail or name == "nonexistent_tool":
            return ToolResult(tool=name, ok=False, error=f"Unknown tool: {name}")
        return ToolResult(tool=name, ok=True, data={"symbol": "BTC/USDT", "value": 42})


def _manager_with(responses: list, type_name: str) -> AIProviderManager:
    """ساخت مدیر ارائه‌دهنده با مدلی که پاسخ‌های داده‌شده را به ترتیب برمی‌گرداند."""

    class _Scripted(AIProvider):
        _queue = list(responses)

        async def is_available(self):  # noqa: ANN201
            return True, "ok"

        async def list_models(self):  # noqa: ANN201
            return ["stub-model"]

        async def generate(self, messages, **kwargs):  # noqa: ANN001, ANN201
            item = self._queue.pop(0) if self._queue else responses[-1]
            content = item if isinstance(item, str) else json.dumps(item)
            return AIResponse(content=content, provider="stub", model="stub-model")

    manager_module.PROVIDER_TYPES[type_name] = _Scripted
    manager = AIProviderManager()
    manager.register(
        AIProviderConfig(
            name=type_name,
            base_url="",
            model="stub-model",
            extra={"provider_type": type_name},
        )
    )
    return manager


@pytest.fixture()
def risk() -> RiskParameters:
    return RiskParameters()


@pytest.mark.asyncio()
async def test_agent_returns_validated_long(risk: RiskParameters) -> None:
    """پیشنهاد معتبر خرید باید پذیرفته و کامل برگردانده شود."""
    tools = _StubToolset()
    agent = AutonomousAgent(_manager_with([VALID_LONG], "t_long"), tools, risk)

    outcome = await agent.run("BTC/USDT", timeframe="4h")

    assert outcome.succeeded
    assert outcome.direction == "LONG"
    assert outcome.confidence == 72
    assert outcome.decision["entry_min"] == pytest.approx(78000)
    assert outcome.decision["take_profits"] == [80000, 82000, 84000]
    assert outcome.decision["risk_reward"] is not None


@pytest.mark.asyncio()
async def test_agent_refuses_invalid_trade(risk: RiskParameters) -> None:
    """پیشنهاد با حد ضرر در سمت اشتباه باید به WAIT امن تبدیل شود."""
    tools = _StubToolset()
    agent = AutonomousAgent(_manager_with([INVALID_LONG], "t_bad"), tools, risk)

    outcome = await agent.run("BTC/USDT")

    assert outcome.direction == "WAIT"
    assert outcome.confidence == 0
    assert not outcome.succeeded
    assert outcome.errors, "باید دلیل رد شدن گزارش شود"


@pytest.mark.asyncio()
async def test_agent_clamps_leverage_to_user_limit() -> None:
    """اهرم پیشنهادی مدل هرگز نباید از سقف کاربر بیشتر شود."""
    payload = json.loads(json.dumps(VALID_LONG))
    payload["final"]["leverage"] = 100
    parameters = RiskParameters(max_leverage=5)
    agent = AutonomousAgent(
        _manager_with([payload], "t_lev"), _StubToolset(), parameters
    )

    outcome = await agent.run("BTC/USDT")

    assert outcome.decision["leverage"] <= 5
    assert any("Leverage" in w for w in outcome.warnings)


@pytest.mark.asyncio()
async def test_agent_uses_tools_before_deciding(risk: RiskParameters) -> None:
    """عامل باید بتواند ابزار صدا بزند و سپس تصمیم بگیرد."""
    tools = _StubToolset()
    responses = [
        {"thought": "need context", "tool": "get_ticker", "arguments": {"symbol": "BTC/USDT"}},
        {"thought": "need momentum", "tool": "calculate_indicator",
         "arguments": {"symbol": "BTC/USDT", "indicator": "RSI"}},
        VALID_LONG,
    ]
    agent = AutonomousAgent(_manager_with(responses, "t_tools"), tools, risk)

    outcome = await agent.run("BTC/USDT")

    # از نسخهٔ ۱.۹.۱۸ عامل پیش از شروع حلقه، سه ابزار پایه را موازی
    # می‌گیرد تا مدلِ کند مجبور نباشد برای هر داده یک رفت‌وبرگشت کند.
    # پس فهرست فراخوانی‌ها دیگر دقیقاً دو مورد نیست؛ چیزی که اهمیت
    # دارد این است که ابزارهای درخواستیِ مدل هم واقعاً اجرا شده باشند.
    called = [name for name, _ in tools.calls]
    assert "get_ticker" in called
    assert "calculate_indicator" in called
    assert called.index("get_ticker") < called.index("calculate_indicator")
    assert "get_ticker" in outcome.tools_used
    assert "calculate_indicator" in outcome.tools_used
    assert outcome.succeeded


@pytest.mark.asyncio()
async def test_agent_survives_failing_tool(risk: RiskParameters) -> None:
    """شکست یک ابزار نباید کل تحلیل را از کار بیندازد."""
    responses = [
        {"thought": "try", "tool": "nonexistent_tool", "arguments": {}},
        VALID_LONG,
    ]
    agent = AutonomousAgent(_manager_with(responses, "t_toolfail"), _StubToolset(), risk)

    outcome = await agent.run("BTC/USDT")

    assert outcome.succeeded
    assert any(step.ok is False for step in outcome.steps)


@pytest.mark.asyncio()
async def test_agent_recovers_from_unparseable_response(risk: RiskParameters) -> None:
    """یک پاسخ بی‌قالب باید با تذکر جبران شود، نه با شکست کامل."""
    responses = ["this is not json at all", VALID_LONG]
    agent = AutonomousAgent(_manager_with(responses, "t_json"), _StubToolset(), risk)

    outcome = await agent.run("BTC/USDT")

    assert outcome.succeeded
    assert outcome.direction == "LONG"


@pytest.mark.asyncio()
async def test_agent_gives_up_after_repeated_garbage(risk: RiskParameters) -> None:
    """دو پاسخ بی‌قالب پشت سر هم یعنی مدل ناتوان است؛ باید متوقف شود."""
    agent = AutonomousAgent(
        _manager_with(["garbage", "still garbage"], "t_json2"), _StubToolset(), risk
    )

    outcome = await agent.run("BTC/USDT")

    assert not outcome.succeeded
    assert outcome.direction == "WAIT"
    assert outcome.errors


@pytest.mark.asyncio()
async def test_agent_reports_missing_provider(risk: RiskParameters) -> None:
    """بدون ارائه‌دهنده، عامل باید صادقانه شکست را اعلام کند."""
    agent = AutonomousAgent(AIProviderManager(), _StubToolset(), risk)

    outcome = await agent.run("BTC/USDT")

    assert not outcome.succeeded
    assert outcome.direction == "WAIT"
    assert "provider" in outcome.errors[0].lower()


@pytest.mark.asyncio()
async def test_agent_stops_at_iteration_limit(risk: RiskParameters) -> None:
    """عامل حریص نباید بی‌نهایت ابزار صدا بزند."""
    loop_forever = {"thought": "again", "tool": "get_ticker", "arguments": {"symbol": "BTC/USDT"}}
    tools = _StubToolset()
    agent = AutonomousAgent(
        _manager_with([loop_forever] * 10, "t_limit"), tools, risk, max_iterations=4
    )

    outcome = await agent.run("BTC/USDT")

    assert len(tools.calls) <= 4
    assert outcome.direction == "WAIT"


@pytest.mark.asyncio()
async def test_progress_callback_receives_steps(risk: RiskParameters) -> None:
    """رابط کاربری باید بتواند مسیر تحلیل را زنده دنبال کند."""
    seen: list[AgentStep] = []
    responses = [
        {"thought": "look", "tool": "get_ticker", "arguments": {"symbol": "BTC/USDT"}},
        VALID_LONG,
    ]
    agent = AutonomousAgent(_manager_with(responses, "t_progress"), _StubToolset(), risk)
    agent.set_progress_callback(seen.append)

    await agent.run("BTC/USDT")

    assert len(seen) >= 2
    assert seen[0].tool == "get_ticker"
    assert "get_ticker" in seen[0].summary()


@pytest.mark.asyncio()
async def test_broken_progress_callback_does_not_break_analysis(risk: RiskParameters) -> None:
    """خطا در نمایش نباید تحلیل را از بین ببرد."""

    def explode(_step):  # noqa: ANN001, ANN202
        raise RuntimeError("UI blew up")

    agent = AutonomousAgent(_manager_with([VALID_LONG], "t_cb"), _StubToolset(), risk)
    agent.set_progress_callback(explode)

    outcome = await agent.run("BTC/USDT")

    assert outcome.succeeded


def test_parse_handles_fenced_json() -> None:
    """مدل‌ها اغلب JSON را داخل بلوک کد می‌گذارند."""
    fenced = '```json\n{"thought": "hi", "tool": "get_ticker"}\n```'
    parsed = AutonomousAgent._parse(fenced)

    assert parsed is not None
    assert parsed["tool"] == "get_ticker"


def test_parse_handles_prose_around_json() -> None:
    """توضیح اضافه قبل و بعد از JSON نباید مشکل‌ساز باشد."""
    messy = 'Sure! Here is my answer:\n{"thought": "ok", "tool": "get_ticker"}\nHope that helps.'
    parsed = AutonomousAgent._parse(messy)

    assert parsed is not None
    assert parsed["thought"] == "ok"


def test_parse_rejects_garbage() -> None:
    """متن بدون JSON باید صریحاً رد شود."""
    assert AutonomousAgent._parse("no json here") is None
    assert AutonomousAgent._parse("") is None


def test_schema_mapping_round_trip() -> None:
    """نگاشت میان قرارداد مدل و قرارداد اعتبارسنج باید بی‌اتلاف باشد."""
    mapped = AutonomousAgent._to_validator_schema(VALID_LONG["final"])

    assert mapped["signal"] == "LONG"
    assert mapped["entry"] == {"min": 78000, "max": 78200}
    assert mapped["take_profit"] == [80000, 82000, 84000]

    back = AutonomousAgent._from_validator_schema(mapped)
    assert back["direction"] == "LONG"
    assert back["entry_min"] == 78000
    assert back["take_profits"] == [80000, 82000, 84000]
