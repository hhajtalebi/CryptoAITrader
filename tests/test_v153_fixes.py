"""
آزمون‌های ایرادهای گزارش‌شده روی نسخهٔ ۱٫۵٫۲.

کاربر گفت: سیستم کند است و با چند کار پشت سر هم هنگ می‌کند؛ روند در
بازارها مشخص نیست؛ قیمت‌ها باید با تتر مشخص شوند؛ اندیکاتورها قابل
انتخاب نیستند؛ چت جواب نمی‌دهد و باید گفتگوی طبیعی هم بکند؛ ظاهر چت
باید مثل ChatGPT باشد.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from PySide6.QtWidgets import QApplication

from localization import Translator

pytestmark = pytest.mark.usefixtures("qt_application")


@pytest.fixture()
def translator() -> Translator:
    """مترجم فارسی آمادهٔ آزمون."""
    tr = Translator("fa")
    tr.load()
    return tr


# ---------------------------------------------------------------------------
# کندی و هنگ: هم‌ادغامی کارهای هم‌کلید
# ---------------------------------------------------------------------------
def test_repeated_submits_do_not_pile_up() -> None:
    """
    چند کلیک پیاپی نباید ده کار موازی بسازد.

    این ریشهٔ «هنگ کردن» بود: هر کلیک یک درخواست شبکه تازه می‌فرستاد و
    هیچ‌کدام لغو نمی‌شد.
    """
    from ui.controllers.async_runner import AsyncRunner

    runner = AsyncRunner()
    runner.start()
    state = {"running": 0, "peak": 0}

    async def slow() -> None:
        state["running"] += 1
        state["peak"] = max(state["peak"], state["running"])
        await asyncio.sleep(0.4)
        state["running"] -= 1

    try:
        for _ in range(10):
            runner.submit("markets", slow())
        # تا وقتی همهٔ کارها تمام شوند صبر کن، نه یک مهلت ثابت. با مهلت
        # ثابت، این آزمون زیر بار سنگین (اجرای کل مجموعه) گاهی پیش از
        # پایان کارها داوری می‌کرد و تصادفی می‌شکست.
        deadline = time.time() + 15.0
        while time.time() < deadline:
            QApplication.processEvents()
            if state["running"] == 0 and state["peak"] > 0:
                break
            time.sleep(0.02)
        # با هم‌ادغامی، هم‌زمانی باید بسیار کم بماند (نه ۱۰ تا)
        assert state["peak"] > 0, "no task ran at all"
        assert state["peak"] <= 2
    finally:
        runner.stop()


def test_different_keys_still_run_in_parallel() -> None:
    """هم‌ادغامی نباید کارهای *متفاوت* را سریالی کند."""
    from ui.controllers.async_runner import AsyncRunner

    runner = AsyncRunner()
    runner.start()
    state = {"running": 0, "peak": 0}

    async def slow() -> None:
        state["running"] += 1
        state["peak"] = max(state["peak"], state["running"])
        await asyncio.sleep(0.3)
        state["running"] -= 1

    try:
        for key in ("markets", "signals", "wallet"):
            runner.submit(key, slow())
        deadline = time.time() + 2.5
        while time.time() < deadline:
            QApplication.processEvents()
            time.sleep(0.02)
        assert state["peak"] >= 2, "کارهای مستقل باید موازی بمانند"
    finally:
        runner.stop()


def test_opting_out_of_coalescing_keeps_both(qt_application) -> None:  # type: ignore[no-untyped-def]
    """کارهایی که نباید جایگزین شوند (مثل ارسال پیام) می‌توانند انصراف بدهند."""
    from ui.controllers.async_runner import AsyncRunner

    runner = AsyncRunner()
    runner.start()
    done: list[int] = []

    async def work(index: int) -> int:
        await asyncio.sleep(0.1)
        return index

    try:
        for i in range(3):
            runner.submit("chat", work(i), on_success=done.append, coalesce=False)
        deadline = time.time() + 2.5
        while time.time() < deadline and len(done) < 3:
            QApplication.processEvents()
            time.sleep(0.02)
        assert len(done) == 3
    finally:
        runner.stop()


# ---------------------------------------------------------------------------
# ستون روند در بازارها
# ---------------------------------------------------------------------------
def test_trend_cell_shows_persian_direction_and_colour(translator: Translator) -> None:
    """روند باید هم متن فارسی داشته باشد و هم رنگ."""
    from ui.widgets.trend_cell import TrendCell

    cell = TrendCell(translator)

    cell.set_trend(3.2, [1.0, 1.1, 1.3])
    assert "صعودی" in cell.label.text()
    assert "▲" in cell.label.text()

    cell.set_trend(-2.5, [1.3, 1.1, 1.0])
    assert "نزولی" in cell.label.text()
    assert "▼" in cell.label.text()

    cell.set_trend(0.0, [])
    assert "خنثی" in cell.label.text()


def test_trend_cell_without_history_still_labels(translator: Translator) -> None:
    """
    نبودن تاریخچه نباید ستون را خالی بگذارد.

    ایراد اصلی همین بود: نمودار داده نداشت و کاربر هیچ نشانی از روند
    نمی‌دید.
    """
    from ui.widgets.trend_cell import TrendCell

    cell = TrendCell(translator)
    cell.set_trend(1.5, None)
    assert "صعودی" in cell.label.text()


def test_markets_price_column_says_tether(translator: Translator) -> None:
    """کاربر گفت قیمت‌ها باید با تتر مشخص شوند، نه دلار."""
    from ui.pages.markets_page import MarketsPage

    page = MarketsPage(translator)
    header = page.table.horizontalHeaderItem(2).text()
    assert "تتر" in header


def test_every_market_row_gets_a_trend_widget(translator: Translator) -> None:
    """هر ردیف باید سلول روند داشته باشد، با تاریخچه یا بدون آن."""
    from ui.pages.markets_page import COL_TREND, MarketsPage

    page = MarketsPage(translator)
    page.set_rows(
        [
            {"symbol": "BTC/USDT", "price": 1.0, "change_percent": 2.0, "history": [1, 2, 3]},
            {"symbol": "ETH/USDT", "price": 1.0, "change_percent": -2.0},
        ]
    )
    assert page.table.cellWidget(0, COL_TREND) is not None
    assert page.table.cellWidget(1, COL_TREND) is not None


# ---------------------------------------------------------------------------
# انتخاب اندیکاتور
# ---------------------------------------------------------------------------
def test_indicator_select_all_and_clear(translator: Translator) -> None:
    """
    کاربر باید هم بتواند گزینشی انتخاب کند و هم «با همهٔ اندیکاتورها».
    """
    from ui.pages.analysis_page import AnalysisPage

    page = AnalysisPage(translator)
    page.set_indicator_catalog(
        [{"name": n, "label": n, "description": "d"} for n in ("RSI", "MACD", "EMA")],
        ["RSI"],
    )
    assert page.enabled_indicators() == ["RSI"]

    page.select_all_indicators()
    assert set(page.enabled_indicators()) == {"RSI", "MACD", "EMA"}

    page.clear_indicators()
    assert page.enabled_indicators() == []


def test_indicator_toggle_is_reachable(translator: Translator) -> None:
    """هر اندیکاتور باید کلید قابل کلیک داشته باشد."""
    from ui.pages.analysis_page import AnalysisPage

    page = AnalysisPage(translator)
    page.set_indicator_catalog([{"name": "RSI", "label": "RSI", "description": ""}], [])
    toggle = page._indicator_rows["RSI"]["toggle"]
    assert toggle.isEnabled()
    toggle.setChecked(True)
    assert page.enabled_indicators() == ["RSI"]


# ---------------------------------------------------------------------------
# چت
# ---------------------------------------------------------------------------
def test_chat_prompt_allows_general_conversation() -> None:
    """
    دستیار نباید فقط ربات بازار باشد.

    کاربر خواست گفتگوی طبیعی هم ممکن باشد و در عین حال کار با بازار
    از دست نرود.
    """
    from ai.agent.chat_agent import SYSTEM_PROMPT

    lowered = SYSTEM_PROMPT.lower()
    assert "general assistant" in lowered
    assert "any topic" in lowered
    # توانایی بازار نباید حذف شده باشد
    assert "live market access" in lowered
    assert "{tool_list}" in SYSTEM_PROMPT


def test_chat_prompt_prefers_plain_text() -> None:
    """
    اجبار به JSON خالص، مدل‌های کوچک را می‌شکست.

    حالا متن ساده حالت پیش‌فرض است و JSON فقط برای ابزار و اقدام.
    """
    from ai.agent.chat_agent import SYSTEM_PROMPT

    assert "plain, natural text" in SYSTEM_PROMPT


def test_chat_bubble_is_chatgpt_style(translator: Translator) -> None:
    """هر پیام یک ردیف با نشان گوینده و نام او است."""
    from ui.pages.chat_page import ChatPage

    page = ChatPage(translator)
    bubble = page.add_message("سلام", is_user=True)
    assert bubble.author.text() == translator.tr("chat.you")
    assert not bubble.avatar.pixmap().isNull()

    reply = page.add_message("درود", is_user=False)
    assert reply.author.text() == translator.tr("chat.assistant")
    assert not reply.avatar.pixmap().isNull()


def test_long_chat_message_is_not_clipped(translator: Translator) -> None:
    """
    متن بلند باید کامل دیده شود.

    در تصویر کاربر، پیام خوش‌آمد وسط جمله بریده می‌شد چون ارتفاع
    برچسبِ پیچیده‌شده به چیدمان اعلام نمی‌شد.
    """
    from PySide6.QtWidgets import QSizePolicy

    from ui.pages.chat_page import ChatPage

    page = ChatPage(translator)
    long_text = "سلام! " + ("این یک متن آزمایشی بلند است. " * 20)
    bubble = page.add_message(long_text, is_user=False)
    assert bubble.label.wordWrap()
    assert (
        bubble.label.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.MinimumExpanding
    )


# ---------------------------------------------------------------------------
# سرعت
# ---------------------------------------------------------------------------
def test_local_provider_uses_short_connect_timeout() -> None:
    """
    سرویس محلیِ خاموش نباید ۱۵ ثانیه کاربر را معطل کند.

    این یکی از دلایل «خیلی کند» بودن سیگنال و چت بود.
    """
    from ai.providers.openai_compatible import OpenAICompatibleProvider

    assert OpenAICompatibleProvider._is_local("http://127.0.0.1:11434/v1")
    assert OpenAICompatibleProvider._is_local("http://localhost:1234/v1")
    assert not OpenAICompatibleProvider._is_local("https://openrouter.ai/api/v1")


def test_ollama_probe_timeout_is_short() -> None:
    """کاوش Ollama محلی باید سریع شکست بخورد."""
    from ai.providers.ollama_provider import PROBE_TIMEOUT

    assert PROBE_TIMEOUT <= 3.0
