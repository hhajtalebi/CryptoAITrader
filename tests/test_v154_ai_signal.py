"""
آزمون‌های نقص‌های مسیر سیگنالِ هوش مصنوعی (نسخهٔ ۱٫۵٫۴).

کاربر گفت: «قسمت سیگنال هم خیلی کنده... با هوش مصنوعی هم اصلا نمیده».
دو نقص واقعی پیدا شد که هر دو اینجا قفل می‌شوند تا برنگردند.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("qt_application")


# ---------------------------------------------------------------------------
# نگاشت خروجی مدل به اعتبارسنج
# ---------------------------------------------------------------------------
def test_reasoning_alias_is_accepted() -> None:
    """
    مدل‌ها «دلیل» را با نام‌های مختلف می‌نویسند.

    نقص واقعی: پرامپت کلید `reason` می‌خواست ولی مدل `reasoning` می‌داد و
    اعتبارسنج تصمیمِ کاملاً معتبر را با پیام
    «'reason' must explain the decision» رد می‌کرد. نتیجه برای کاربر:
    «با هوش مصنوعی سیگنال نمی‌دهد».
    """
    from ai.agent.autonomous_agent import AutonomousAgent

    payload = AutonomousAgent._to_validator_schema(
        {
            "direction": "LONG",
            "confidence": 62,
            "reasoning": "روند صعودی در چند تایم‌فریم هم‌راستا است.",
        }
    )
    assert payload["reason"] == "روند صعودی در چند تایم‌فریم هم‌راستا است."
    assert payload["signal"] == "LONG"


@pytest.mark.parametrize(
    "alias",
    ["reasoning", "explanation", "analysis", "rationale", "narrative", "summary"],
)
def test_every_reason_alias_maps(alias: str) -> None:
    """همهٔ نام‌های رایج «دلیل» باید پذیرفته شوند."""
    from ai.agent.autonomous_agent import AutonomousAgent

    payload = AutonomousAgent._to_validator_schema({"direction": "WAIT", alias: "چون داده کافی نیست."})
    assert payload["reason"] == "چون داده کافی نیست."


def test_explicit_reason_wins_over_alias() -> None:
    """اگر خود `reason` آمده باشد، نام‌های جایگزین نباید رونویسی‌اش کنند."""
    from ai.agent.autonomous_agent import AutonomousAgent

    payload = AutonomousAgent._to_validator_schema(
        {"direction": "LONG", "reason": "اصلی", "reasoning": "جایگزین"}
    )
    assert payload["reason"] == "اصلی"


def test_stop_loss_aliases_map() -> None:
    """حد ضرر هم با نام‌های گوناگون می‌آید."""
    from ai.agent.autonomous_agent import AutonomousAgent

    for alias in ("stopLoss", "stop", "sl"):
        payload = AutonomousAgent._to_validator_schema({"direction": "LONG", alias: 75500})
        assert payload["stop_loss"] == 75500


# ---------------------------------------------------------------------------
# تحلیل نوشتاری فارسی
# ---------------------------------------------------------------------------
def test_narrative_sends_real_message_objects() -> None:
    """
    نویسندهٔ تحلیل باید `AIMessage` بفرستد، نه dict خام.

    نقص واقعی: dict خام باعث `AttributeError: 'dict' object has no
    attribute 'to_dict'` می‌شد. این خطا در بالادست بلعیده می‌شد و تحلیل
    فارسی **همیشه** به قالب آماده برمی‌گشت، بی‌آنکه کسی خطایی ببیند.
    """
    import asyncio
    import inspect

    from ai.agent.narrative import NarrativeWriter
    from ai.providers.base import AIMessage

    source = inspect.getsource(NarrativeWriter._write_with_ai)
    assert "AIMessage(" in source, "پیام‌ها باید AIMessage باشند"

    captured: dict[str, object] = {}

    class FakeManager:
        """مدیر ساختگی که فقط پیام‌ها را ثبت می‌کند."""

        async def generate(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            captured["messages"] = messages
            captured["preferred"] = kwargs.get("preferred")

            class Response:
                content = "تحلیل فارسی آزمایشی."

            return Response()

    writer = NarrativeWriter(FakeManager(), preferred_provider="openrouter")
    signal = type(
        "Signal",
        (),
        {"symbol": "BTC/USDT", "direction": "WAIT", "confidence": 40, "timeframe": "4h"},
    )()

    text = asyncio.run(writer._write_with_ai(signal, {}))
    assert text == "تحلیل فارسی آزمایشی."
    assert all(isinstance(m, AIMessage) for m in captured["messages"])  # type: ignore[union-attr]
    # سرویس انتخابی کاربر باید اول زنجیره باشد
    assert captured["preferred"] == "openrouter"


# ---------------------------------------------------------------------------
# ترجیح سرویس انتخابی کاربر
# ---------------------------------------------------------------------------
def test_agents_accept_preferred_provider() -> None:
    """
    هر سه عامل باید سرویس انتخابی کاربر را بپذیرند.

    بدون این، هر تحلیل/سیگنال اول سراغ سرویس‌های محلیِ خاموش می‌رفت و
    کاربر معطل شکست آن‌ها می‌شد.
    """
    import inspect

    from ai.agent.analyst import AIAnalyst
    from ai.agent.autonomous_agent import AutonomousAgent
    from ai.agent.chat_agent import ChatAgent

    for cls in (AIAnalyst, AutonomousAgent, ChatAgent):
        params = inspect.signature(cls.__init__).parameters
        assert "preferred_provider" in params, f"{cls.__name__} باید سرویس ترجیحی بگیرد"


# ---------------------------------------------------------------------------
# انتخاب تایم‌فریم در صفحهٔ سیگنال‌ها
# ---------------------------------------------------------------------------
def test_signals_page_exposes_timeframe_selection(qt_application) -> None:  # type: ignore[no-untyped-def]
    """کاربر باید تایم‌فریم‌های تحلیل چنددوره‌ای را خودش انتخاب کند."""
    from localization import Translator
    from ui.pages.signals_page import DEFAULT_SIGNAL_TIMEFRAMES, SignalsPage

    tr = Translator("fa")
    tr.load()
    page = SignalsPage(tr)

    assert set(page.selected_timeframes()) == set(DEFAULT_SIGNAL_TIMEFRAMES)

    page.timeframe_chips.set_selection(["1h", "15m"])
    assert set(page.selected_timeframes()) == {"1h", "15m"}


def test_empty_timeframe_selection_falls_back(qt_application) -> None:  # type: ignore[no-untyped-def]
    """
    هیچ‌انتخابی نباید موتور را بی‌داده بگذارد.

    برگرداندن فهرست خالی یعنی سیگنالِ «داده ناکافی» — بدترین حالت ممکن.
    """
    from localization import Translator
    from ui.pages.signals_page import DEFAULT_SIGNAL_TIMEFRAMES, SignalsPage

    tr = Translator("fa")
    tr.load()
    page = SignalsPage(tr)
    page.timeframe_chips.set_selection([])
    assert set(page.selected_timeframes()) == set(DEFAULT_SIGNAL_TIMEFRAMES)


# ---------------------------------------------------------------------------
# حالت گفت‌وگو در صفحهٔ چت
# ---------------------------------------------------------------------------
def test_chat_mode_chips_default_and_switch(qt_application) -> None:  # type: ignore[no-untyped-def]
    """کاربر باید حالت گفت‌وگو را با یک کلیک عوض کند."""
    from localization import Translator
    from ui.pages.chat_page import CHAT_MODES, DEFAULT_CHAT_MODE, ChatPage

    tr = Translator("fa")
    tr.load()
    page = ChatPage(tr)

    assert page.current_mode() == DEFAULT_CHAT_MODE
    page.mode_chips.set_selection(["signal"])
    assert page.current_mode() == "signal"
    assert page.current_context()["mode"] == "signal"

    # هر حالت باید برچسب فارسی داشته باشد، نه کلید خام
    for key in CHAT_MODES:
        label = tr.tr(f"chat.mode_{key}")
        assert label and not label.startswith("chat."), f"ترجمهٔ {key} نیست"


def test_chat_mode_reaches_the_model() -> None:
    """
    حالت باید روی متن ارسالی اثر بگذارد.

    وگرنه تراشه‌ها فقط تزئین‌اند و کاربر گمان می‌کند چیزی عوض شده.
    """
    from ai.agent.chat_agent import ChatAgent

    prompt = ChatAgent._with_context("تحلیلش کن", {"symbol": "BTC/USDT", "mode": "learn"})
    assert "mode=learn" in prompt
    assert "Mode guidance" in prompt

    plain = ChatAgent._with_context("سلام", {"symbol": "BTC/USDT"})
    assert "Mode guidance" not in plain


def test_chat_modes_do_not_gate_tools() -> None:
    """
    هیچ حالتی نباید ابزارها را محدود کند.

    قانون کاربر: قابلیت هرگز پشت یک انتخاب ظاهری قفل نمی‌شود.
    """
    from ai.agent.chat_agent import ChatAgent
    from ui.pages.chat_page import CHAT_MODES

    for key in CHAT_MODES:
        assert key in ChatAgent.MODE_HINTS, f"راهنمای حالت {key} نیست"
    # راهنما فقط تمرکز می‌دهد و ابزاری را ممنوع نمی‌کند
    joined = " ".join(ChatAgent.MODE_HINTS.values()).lower()
    for forbidden in ("do not use", "no tools", "disable"):
        assert forbidden not in joined
