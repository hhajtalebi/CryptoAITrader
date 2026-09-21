"""
آزمون‌های نمایش گام‌به‌گام ابزارها در گفتگو (نسخه ۱٫۷٫۱).

چرا این آزمون‌ها نوشته شدند
    تا پیش از این، کنترلر خلاصهٔ ابزارها را در یک فهرست محلی جمع می‌کرد و
    هرگز جایی نشان نمی‌داد؛ `ChatPage.update_progress` هم کد مرده بود.
    یعنی کاربر در تمام مدتی که دستیار قیمت می‌گرفت و روند را تحلیل
    می‌کرد فقط یک «در حال فکر کردن…» بی‌حرکت می‌دید. این آزمون‌ها آن
    مسیر را از عامل تا ویجت قفل می‌کنند.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from ai.agent.chat_agent import ChatAgent, ChatToolCall
from ui.widgets.tool_trail import MAX_OBSERVATION_CHARS, ToolStep, ToolTrail


@pytest.fixture
def chat_page(qt_application: Any) -> Any:
    """
    صفحهٔ چت سبک، بدون ساخت کل برنامه.

    ساختن `Application` کامل برای هر آزمون رابط کاربری، مهاجرت‌های
    پایگاه‌داده را اجرا می‌کند و مجموعه را در این سندباکس قفل می‌کند.
    """
    from localization.translator import Translator
    from ui.pages.chat_page import ChatPage

    page = ChatPage(Translator("fa"))
    # ویجت نمایش‌داده‌نشده هندسهٔ کهنه نگه می‌دارد و `isVisible` همیشه
    # False برمی‌گرداند؛ بدون این، آزمون‌های نمایانی بی‌معنا می‌شوند.
    page.show()
    return page


# ---------------------------------------------------------------- ویجت گام


def test_a_new_step_starts_in_the_running_state(qt_application: Any) -> None:
    """گامی که تازه ساخته می‌شود باید «در حال اجرا» باشد."""
    step = ToolStep("get_current_price", {"symbol": "BTC/USDT"})
    assert step.state == "running"
    assert step.mark_label.text() == ToolStep.STATE_MARKS["running"][0]


def test_a_successful_result_switches_the_mark(qt_application: Any) -> None:
    """نتیجهٔ موفق، نشانه را به تیک تغییر می‌دهد."""
    step = ToolStep("detect_trend")
    step.set_result(ok=True, observation="روند صعودی")
    assert step.state == "ok"
    assert step.mark_label.text() == "✓"


def test_a_failed_result_is_visually_distinct(qt_application: Any) -> None:
    """شکست ابزار باید نشانه و رنگ متفاوتی بگیرد."""
    step = ToolStep("get_orderbook")
    step.set_result(ok=False, observation="اتصال برقرار نشد")
    assert step.state == "failed"
    assert step.mark_label.text() == "✗"
    assert step.mark_label.styleSheet() != ""


def test_arguments_appear_next_to_the_tool_name(qt_application: Any) -> None:
    """کاربر باید ببیند ابزار با چه ورودی‌ای صدا زده شده است."""
    step = ToolStep("get_ohlcv", {"symbol": "ETH/USDT", "timeframe": "4h"})
    title = step.title_label.text()
    assert "ETH/USDT" in title
    assert "4h" in title


def test_the_result_is_hidden_until_the_step_is_clicked(qt_application: Any) -> None:
    """جزئیات پیش‌فرض بسته است تا گفتگو شلوغ نشود."""
    step = ToolStep("detect_trend")
    step.set_result(ok=True, observation="جزئیات کامل روند")
    assert step.detail_label.isVisible() is False

    step.toggle()
    assert step.expanded is True
    assert "جزئیات کامل روند" in step.detail_label.text()


def test_a_step_without_a_result_cannot_be_expanded(qt_application: Any) -> None:
    """وقتی نتیجه‌ای نیست، کلیک نباید کارت خالی باز کند."""
    step = ToolStep("get_volume")
    step.toggle()
    assert step.expanded is False
    assert step.chevron_label.isVisible() is False


def test_a_huge_observation_is_truncated(qt_application: Any) -> None:
    """
    خروجی خام ابزار گاهی چند کیلوبایت است.

    ریختن همه‌اش در حباب، گفتگو را غیرقابل استفاده می‌کند، پس باید
    بریده شود — ولی نه آن‌قدر که بی‌فایده شود.
    """
    step = ToolStep("get_ohlcv")
    step.set_result(ok=True, observation="د" * (MAX_OBSERVATION_CHARS * 3))
    step.toggle()
    shown = step.detail_label.text()
    assert len(shown) < MAX_OBSERVATION_CHARS * 3
    assert shown.endswith("…")


def test_the_display_name_replaces_the_technical_name(qt_application: Any) -> None:
    """کاربر فارسی‌زبان نباید `get_current_price` ببیند."""
    step = ToolStep("get_current_price", {"symbol": "BTC/USDT"})
    step.set_display_name("قیمت لحظه‌ای")
    assert "قیمت لحظه‌ای" in step.title_label.text()
    assert "get_current_price" not in step.title_label.text()


# ---------------------------------------------------------------- مجموعه گام


def test_the_trail_is_invisible_until_a_tool_runs(qt_application: Any) -> None:
    """پاسخ بدون ابزار نباید فضای خالی بگیرد."""
    trail = ToolTrail()
    assert trail.isVisible() is False
    assert trail.steps() == []


def test_finishing_a_step_updates_the_row_that_started_it(qt_application: Any) -> None:
    """«شروع» و «پایان» دو رویدادند و باید به یک ردیف برسند."""
    trail = ToolTrail()
    trail.begin_step("detect_trend", {"symbol": "BTC/USDT"})
    trail.finish_step("detect_trend", ok=True, observation="صعودی")

    assert len(trail.steps()) == 1
    assert trail.steps()[0].state == "ok"


def test_the_same_tool_called_twice_keeps_two_rows(qt_application: Any) -> None:
    """
    مدل ممکن است یک ابزار را با دو نماد مختلف صدا بزند.

    ادغام آن‌ها در یک ردیف، یکی از دو فراخوانی را پنهان می‌کرد.
    """
    trail = ToolTrail()
    trail.begin_step("get_current_price", {"symbol": "BTC/USDT"})
    trail.finish_step("get_current_price", ok=True, observation="۶۷۰۰۰")
    trail.begin_step("get_current_price", {"symbol": "ETH/USDT"})
    trail.finish_step("get_current_price", ok=True, observation="۳۲۰۰")

    assert len(trail.steps()) == 2


def test_a_result_without_a_start_still_shows_up(qt_application: Any) -> None:
    """نتیجهٔ یتیم نباید بی‌صدا گم شود."""
    trail = ToolTrail()
    trail.finish_step("calculate_risk", ok=True, observation="نسبت ۲٫۱")
    assert len(trail.steps()) == 1
    assert trail.steps()[0].state == "ok"


def test_clearing_removes_every_row(qt_application: Any) -> None:
    """شروع گفتگوی تازه باید گام‌های قبلی را پاک کند."""
    trail = ToolTrail()
    trail.begin_step("get_ticker")
    trail.clear()
    assert trail.steps() == []
    assert trail.isVisible() is False


def test_display_names_reach_steps_added_later(qt_application: Any) -> None:
    """نگاشت نام باید روی گام‌های بعدی هم اثر کند، نه فقط موجودها."""
    trail = ToolTrail()
    trail.set_display_names({"get_volume": "بررسی حجم"})
    trail.begin_step("get_volume")
    assert "بررسی حجم" in trail.steps()[0].title_label.text()


def test_theme_colours_follow_the_active_theme(qt_application: Any) -> None:
    """نشانهٔ گام از توکن پوسته رنگ می‌گیرد، نه مقدار ثابت."""
    from ui.themes.catalog import THEME_CATALOG

    trail = ToolTrail()
    step = trail.begin_step("detect_trend")
    step.set_result(ok=True)

    theme = THEME_CATALOG["glass_dark"]
    trail.apply_theme(theme)
    assert theme.colors.success.lower() in step.mark_label.styleSheet().lower()


# ---------------------------------------------------------------- عامل


@dataclass
class _FakeResult:
    """نتیجهٔ ساختگی اجرای ابزار."""

    ok: bool = True
    data: dict[str, Any] | None = None
    error: str = ""


class _RecordingProgress:
    """پس‌فراخوان پیشرفت که رویدادها را ثبت می‌کند."""

    def __init__(self) -> None:
        self.events: list[tuple[str, bool]] = []

    def __call__(self, call: ChatToolCall, *, running: bool = False) -> None:
        self.events.append((call.name, running))


def test_the_agent_announces_a_tool_before_running_it() -> None:
    """
    مهم‌ترین آزمون این فایل.

    اعلام فقط پس از اجرا یعنی کاربر دقیقاً در فاصله‌ای که منتظر شبکه
    است هیچ بازخوردی نمی‌گیرد. باید دو رویداد بیاید: اول شروع، بعد پایان.
    """
    progress = _RecordingProgress()
    agent = ChatAgent.__new__(ChatAgent)
    agent._progress = progress  # type: ignore[attr-defined]

    call = ChatToolCall(name="detect_trend", arguments={"symbol": "BTC/USDT"})
    agent._emit(call, running=True)
    call.ok = True
    agent._emit(call)

    assert progress.events == [("detect_trend", True), ("detect_trend", False)]


def test_a_legacy_single_argument_callback_still_works() -> None:
    """پس‌فراخوان‌های قدیمی نباید با افزودن `running` بشکنند."""
    seen: list[str] = []
    agent = ChatAgent.__new__(ChatAgent)
    agent._progress = lambda call: seen.append(call.name)  # type: ignore[attr-defined]

    call = ChatToolCall(name="get_ticker")
    agent._emit(call, running=True)  # قدیمی «شروع» را نمی‌فهمد → نادیده
    agent._emit(call)

    assert seen == ["get_ticker"]


def test_a_broken_progress_callback_never_breaks_the_chat() -> None:
    """خطای رابط کاربری نباید گفتگو را از کار بیندازد."""
    def explode(call: ChatToolCall, *, running: bool = False) -> None:
        raise RuntimeError("boom")

    agent = ChatAgent.__new__(ChatAgent)
    agent._progress = explode  # type: ignore[attr-defined]
    agent._emit(ChatToolCall(name="get_volume"), running=True)  # نباید پرتاب کند


# ---------------------------------------------------------------- صفحه چت


def test_the_chat_page_shows_a_running_tool_on_the_pending_bubble(
    chat_page: Any,
) -> None:
    """شروع ابزار باید روی حباب انتظار دیده شود."""
    chat_page.begin_reply()
    chat_page.tool_started("get_current_price", {"symbol": "BTC/USDT"})

    trail = chat_page._pending_bubble.tool_trail
    assert len(trail.steps()) == 1
    assert trail.steps()[0].state == "running"


def test_the_chat_page_records_the_tool_result(chat_page: Any) -> None:
    """پایان ابزار باید همان ردیف را ببندد."""
    chat_page.begin_reply()
    chat_page.tool_started("detect_trend", {"symbol": "BTC/USDT"})
    chat_page.tool_finished("detect_trend", ok=True, observation="روند صعودی است")

    step = chat_page._pending_bubble.tool_trail.steps()[0]
    assert step.state == "ok"
    step.toggle()
    assert "صعودی" in step.detail_label.text()


def test_tool_events_without_a_pending_bubble_are_ignored(chat_page: Any) -> None:
    """
    رسیدن دیرهنگام یک رویداد نباید برنامه را بشکند.

    اگر کاربر گفتگو را پاک کند در حالی که ابزاری هنوز در حال اجراست،
    رویداد پایان بدون حباب می‌رسد.
    """
    chat_page.tool_started("get_ticker", {})
    chat_page.tool_finished("get_ticker", ok=True, observation="x")
    # صرف اینکه پرتاب نکرد کافی است


def test_the_summary_line_is_dropped_when_live_steps_exist(chat_page: Any) -> None:
    """
    نباید یک اطلاعات دو بار زیر پاسخ تکرار شود.

    وقتی فهرست گام‌های زنده پر است، خط متنی قدیمی باید ساکت بماند.
    """
    chat_page.begin_reply()
    bubble = chat_page._pending_bubble
    chat_page.tool_started("detect_trend", {"symbol": "BTC/USDT"})
    chat_page.tool_finished("detect_trend", ok=True, observation="صعودی")
    chat_page.finish_reply("پاسخ نهایی", ["✓ detect_trend(symbol=BTC/USDT)"])

    # `isVisibleTo` وضعیت خودِ show/hide را می‌سنجد؛ `isVisible` به
    # نمایان‌بودن همهٔ والدین (اینجا ناحیهٔ پیمایش) هم وابسته است.
    assert bubble.tools_label.isVisibleTo(bubble) is False
    assert len(bubble.tool_trail.steps()) == 1


def test_history_replies_still_use_the_summary_line(chat_page: Any) -> None:
    """
    پاسخ‌های بازیابی‌شده از پایگاه‌داده گام زنده ندارند.

    برای آن‌ها خط خلاصه تنها چیزی است که باقی مانده و نباید حذف شود.
    """
    chat_page.begin_reply()
    bubble = chat_page._pending_bubble
    chat_page.finish_reply("پاسخ", ["✓ get_ticker(symbol=BTC/USDT)"])

    assert bubble.tools_label.isVisibleTo(bubble) is True
    assert "get_ticker" in bubble.tools_label.text()


def test_persian_tool_names_are_used_on_the_page(chat_page: Any) -> None:
    """نام ابزار روی صفحه باید ترجمه‌شده باشد."""
    chat_page.begin_reply()
    chat_page.tool_started("get_current_price", {"symbol": "BTC/USDT"})

    title = chat_page._pending_bubble.tool_trail.steps()[0].title_label.text()
    assert "get_current_price" not in title
    assert "BTC/USDT" in title


def test_every_known_tool_has_a_persian_name() -> None:
    """
    هر ابزاری که عامل می‌شناسد باید نام فارسی داشته باشد.

    ابزار تازه‌ای که ترجمه ندارد، نام فنی انگلیسی را وسط گفتگوی فارسی
    نشان می‌دهد.
    """
    import json

    from ui.pages.chat_page import TOOL_NAME_KEYS

    with open("localization/fa/chat.json", encoding="utf-8") as handle:
        names = json.load(handle)["tools"]

    missing = [key for key in TOOL_NAME_KEYS if key not in names]
    assert missing == []


def test_the_tool_name_list_matches_the_real_toolset() -> None:
    """
    فهرست نام‌ها نباید از ابزارهای واقعی عقب بماند.

    اگر ابزاری به توست اضافه شود و اینجا ثبت نشود، بی‌سروصدا بدون
    ترجمه نمایش داده می‌شود.
    """
    from ai.tools.market_tools import MarketToolset
    from ui.pages.chat_page import TOOL_NAME_KEYS

    definitions = MarketToolset.__dict__.get("get_definitions")
    assert definitions is not None

    toolset = MarketToolset.__new__(MarketToolset)
    real = {d.name for d in toolset.get_definitions()}
    assert real - set(TOOL_NAME_KEYS) == set()


# ---------------------------------------------------------------- کنترلر


def test_the_controller_emits_both_tool_signals() -> None:
    """
    پل بین نخ شبکه و رابط کاربری باید هر دو رویداد را بفرستد.

    پیش‌تر کنترلر خلاصه‌ها را در فهرستی محلی جمع می‌کرد و دور می‌ریخت.
    """
    from ui.controllers.main_controller import MainController

    source = MainController.send_chat_message.__doc__ or ""
    import inspect

    body = inspect.getsource(MainController.send_chat_message)
    assert "chat_tool_started.emit" in body
    assert "chat_tool_finished.emit" in body
    # فهرست مردهٔ قبلی نباید برگردد
    assert "used.append" not in body
