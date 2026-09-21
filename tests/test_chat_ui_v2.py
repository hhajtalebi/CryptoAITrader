"""
آزمون‌های بازطراحی چت (نسخهٔ ۱.۴) و مدال تحلیل نوشتاری.

کاربر گفت: «ظاهر چت را مانند GPT کن و اینطور باشه که نوشته‌های کاربر و
هوش مصنوعی کامل قابل خواندن باشه چون الان محدودیت است … و چت‌ها همه ذخیره
بشه و قابلیت حذف داشته باشه».
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from localization import Translator
from ui.dialogs.analysis_dialog import AnalysisDialog
from ui.pages.chat_page import INPUT_MAX_HEIGHT, INPUT_MIN_HEIGHT, ChatInput, ChatPage

pytestmark = pytest.mark.usefixtures("qt_application")


@pytest.fixture()
def page() -> ChatPage:
    """صفحهٔ چت فارسی."""
    translator = Translator()
    translator.set_language("fa")
    return ChatPage(translator)


# ---------------------------------------------------------------------------
# جعبهٔ ورودی چندخطی
# ---------------------------------------------------------------------------
def test_input_is_multiline(page: ChatPage) -> None:
    """
    ورودی باید چندخطی باشد.

    پیش‌تر QLineEdit بود؛ متن بلند از دید کاربر خارج می‌شد و همین شکایت
    اصلی کاربر بود.
    """
    assert isinstance(page.input, ChatInput)


def test_long_text_is_fully_retrievable(page: ChatPage) -> None:
    """متن بسیار بلند باید کامل خوانده شود، بدون بریدگی."""
    long_text = "این یک پیام بسیار بلند است. " * 60  # حدود ۱۷۰۰ نویسه
    page.input.setText(long_text)
    assert page.input.text() == long_text
    assert len(page.input.text()) > 1500


def test_input_grows_with_content(page: ChatPage) -> None:
    """جعبه با متن بلند بلندتر می‌شود ولی از سقف نمی‌گذرد."""
    start = page.input.height()
    page.input.setText("خط\n" * 30)
    grown = page.input.height()
    assert grown >= start
    assert grown <= INPUT_MAX_HEIGHT


def test_input_starts_at_minimum_height(page: ChatPage) -> None:
    """ارتفاع اولیه همان کمینه است."""
    assert page.input.height() == INPUT_MIN_HEIGHT


def test_enter_sends_message(page: ChatPage) -> None:
    """Enter پیام را می‌فرستد."""
    sent: list[str] = []
    page.message_sent.connect(sent.append)
    page.input.setText("سلام")
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    page.input.keyPressEvent(event)
    assert sent == ["سلام"]


def test_shift_enter_does_not_send(page: ChatPage) -> None:
    """Shift+Enter فقط خط تازه می‌سازد و پیام نمی‌فرستد."""
    sent: list[str] = []
    page.message_sent.connect(sent.append)
    page.input.setText("سلام")
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier
    )
    page.input.keyPressEvent(event)
    assert sent == []


# ---------------------------------------------------------------------------
# حباب‌ها
# ---------------------------------------------------------------------------
def test_bubble_shows_full_long_text(page: ChatPage) -> None:
    """حباب باید متن بلند را کامل نگه دارد."""
    long_text = "متن طولانی. " * 100
    bubble = page.add_message(long_text, is_user=False)
    assert bubble.text() == long_text


def test_bubble_wraps_text(page: ChatPage) -> None:
    """شکستن خط روشن است تا متن بریده نشود."""
    bubble = page.add_message("متن", is_user=True)
    assert bubble.label.wordWrap() is True


def test_bubble_text_is_selectable(page: ChatPage) -> None:
    """کاربر باید بتواند متن را انتخاب و کپی کند."""
    bubble = page.add_message("متن", is_user=False)
    flags = bubble.label.textInteractionFlags()
    assert bool(flags & Qt.TextInteractionFlag.TextSelectableByMouse)


def test_bubble_width_follows_window(page: ChatPage) -> None:
    """
    عرض ستون متن نسبتی از عرض پنجره است، نه عدد ثابت.

    در سبک ChatGPT خودِ ردیف تمام‌عرض است و محدودیت روی برچسب متن
    اعمال می‌شود، نه روی کل ردیف.
    """
    bubble = page.add_message("متن", is_user=True)
    page.resize(1400, 800)
    bubble.apply_max_width(1000)
    assert bubble.label.maximumWidth() == 1000


# ---------------------------------------------------------------------------
# تاریخچهٔ گفت‌وگو
# ---------------------------------------------------------------------------
def test_history_panel_exists(page: ChatPage) -> None:
    """ستون تاریخچه باید وجود داشته باشد."""
    assert page.history_list is not None
    assert page.new_chat_button is not None


def test_set_conversations_fills_list(page: ChatPage) -> None:
    """فهرست گفت‌وگوها پر می‌شود."""
    page.set_conversations([
        {"id": 1, "title": "گفت‌وگوی اول", "message_count": 2},
        {"id": 2, "title": "گفت‌وگوی دوم", "message_count": 4},
    ])
    assert page.history_list.count() == 2
    assert page.history_list.item(0).data(Qt.ItemDataRole.UserRole) == 1


def test_untitled_conversation_gets_placeholder(page: ChatPage) -> None:
    """گفت‌وگوی بی‌نام برچسب جایگزین می‌گیرد."""
    page.set_conversations([{"id": 5, "title": "", "message_count": 0}])
    assert page.history_list.item(0).text().strip() != ""


def test_pinned_conversation_is_marked(page: ChatPage) -> None:
    """گفت‌وگوی سنجاق‌شده نشانه دارد."""
    page.set_conversations([{"id": 1, "title": "مهم", "pinned": True}])
    assert "📌" in page.history_list.item(0).text()


def test_clicking_history_emits_id(page: ChatPage) -> None:
    """کلیک روی گفت‌وگو شناسه را منتشر می‌کند."""
    page.set_conversations([{"id": 7, "title": "الف"}])
    received: list[int] = []
    page.conversation_selected.connect(received.append)
    page._on_history_clicked(page.history_list.item(0))
    assert received == [7]


def test_new_chat_button_emits(page: ChatPage) -> None:
    """دکمهٔ گفت‌وگوی تازه سیگنال می‌دهد."""
    received: list[bool] = []
    page.new_conversation_requested.connect(lambda: received.append(True))
    page.new_chat_button.click()
    assert received == [True]


def test_history_search_filters(page: ChatPage) -> None:
    """جست‌وجو ردیف‌های نامرتبط را پنهان می‌کند."""
    page.set_conversations([
        {"id": 1, "title": "تحلیل بیت‌کوین"},
        {"id": 2, "title": "تحلیل اتریوم"},
    ])
    page.history_search.setText("اتریوم")
    assert page.history_list.item(0).isHidden() is True
    assert page.history_list.item(1).isHidden() is False


def test_history_search_clears(page: ChatPage) -> None:
    """پاک کردن جست‌وجو همه را برمی‌گرداند."""
    page.set_conversations([{"id": 1, "title": "الف"}, {"id": 2, "title": "ب"}])
    page.history_search.setText("الف")
    page.history_search.setText("")
    assert all(not page.history_list.item(i).isHidden() for i in range(2))


def test_select_conversation_highlights(page: ChatPage) -> None:
    """گفت‌وگوی فعال در فهرست برجسته می‌شود."""
    page.set_conversations([{"id": 1, "title": "الف"}, {"id": 2, "title": "ب"}])
    page.select_conversation(2)
    assert page.history_list.currentItem().data(Qt.ItemDataRole.UserRole) == 2


def test_load_messages_replaces_conversation(page: ChatPage) -> None:
    """بارگذاری گفت‌وگوی ذخیره‌شده، پیام‌های قبلی را جایگزین می‌کند."""
    page.add_message("قدیمی", is_user=True)
    page.load_messages([
        {"role": "user", "content": "پرسش", "tools": []},
        {"role": "assistant", "content": "پاسخ", "tools": ["get_ticker"]},
    ])
    assert page.message_count == 2
    assert page._bubbles[0].text() == "پرسش"
    assert page._bubbles[1].text() == "پاسخ"


def test_load_messages_skips_system(page: ChatPage) -> None:
    """پیام سیستمی نباید به کاربر نشان داده شود."""
    page.load_messages([
        {"role": "system", "content": "دستور داخلی"},
        {"role": "user", "content": "سلام"},
    ])
    assert page.message_count == 1


def test_load_empty_messages_shows_welcome(page: ChatPage) -> None:
    """گفت‌وگوی خالی پیام خوش‌آمد نشان می‌دهد."""
    page.load_messages([])
    assert page.message_count == 1


def test_load_messages_restores_tools(page: ChatPage) -> None:
    """ابزارهای استفاده‌شده پس از بارگذاری دوباره دیده می‌شوند."""
    page.load_messages([{"role": "assistant", "content": "پاسخ", "tools": ["get_ohlcv"]}])
    assert page._bubbles[0].tools_label.isVisible() or page._bubbles[0].tools_label.text()


def test_set_context_updates_combos(page: ChatPage) -> None:
    """تعیین زمینه از بیرون (مثلاً از مدال ارز) کار می‌کند."""
    page.set_symbols(["BTC/USDT", "ETH/USDT"])
    page.set_context("ETH/USDT", "1d")
    context = page.current_context()
    assert context["symbol"] == "ETH/USDT"
    assert context["timeframe"] == "1d"


def test_retranslate_updates_history_widgets(page: ChatPage) -> None:
    """پس از تغییر زبان، متن ستون تاریخچه هم عوض می‌شود."""
    before = page.new_chat_button.text()
    page.tr_.set_language("en")
    page.retranslate()
    assert page.new_chat_button.text() != before


# ---------------------------------------------------------------------------
# مدال تحلیل نوشتاری
# ---------------------------------------------------------------------------
@pytest.fixture()
def translator() -> Translator:
    """مترجم فارسی."""
    instance = Translator()
    instance.set_language("fa")
    return instance


def test_analysis_dialog_renders_headings(translator: Translator) -> None:
    """عنوان‌های ## به تیتر HTML تبدیل می‌شوند."""
    dialog = AnalysisDialog(
        {"symbol": "BTC/USDT", "direction": "LONG", "analysis_text": "## خلاصه\n\nمتن تحلیل."},
        translator,
    )
    assert "<h3" in dialog.viewer.toHtml()


def test_analysis_dialog_empty_text(translator: Translator) -> None:
    """نبود تحلیل پیام روشن می‌دهد، نه پنجرهٔ خالی."""
    dialog = AnalysisDialog({"symbol": "BTC/USDT"}, translator)
    assert dialog.viewer.toPlainText().strip() != ""


def test_analysis_dialog_pdf_button_emits(translator: Translator) -> None:
    """دکمهٔ PDF دادهٔ سیگنال را منتشر می‌کند."""
    payload = {"symbol": "BTC/USDT", "direction": "LONG", "analysis_text": "متن"}
    dialog = AnalysisDialog(payload, translator)
    received: list[dict] = []
    dialog.pdf_requested.connect(received.append)
    dialog.pdf_button.click()
    assert received and received[0]["symbol"] == "BTC/USDT"


def test_analysis_dialog_escapes_html(translator: Translator) -> None:
    """
    متن مدل نباید بتواند HTML تزریق کند.

    مدل متن آزاد برمی‌گرداند؛ اگر escape نشود می‌تواند ظاهر پنجره را
    خراب کند.
    """
    dialog = AnalysisDialog(
        {"symbol": "X", "analysis_text": "<script>bad()</script> متن"},
        translator,
    )
    assert "<script>" not in dialog.viewer.toHtml()


def test_analysis_dialog_shows_source(translator: Translator) -> None:
    """منبع تحلیل (هوش مصنوعی یا قالبی) نمایش داده می‌شود."""
    dialog = AnalysisDialog(
        {"symbol": "X", "analysis_text": "متن", "analysis_source": "ai"},
        translator,
    )
    assert dialog.analysis_text == "متن"
