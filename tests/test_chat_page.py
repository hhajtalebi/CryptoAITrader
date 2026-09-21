"""
آزمون‌های صفحه چت.

هدف: مطمئن شویم آنچه کاربر روی صفحه می‌بیند درست کار می‌کند — حباب‌ها،
دکمه اقدام، پاک کردن گفتگو، و تغییر زبان.

همه از یک نمونه Qt مشترک استفاده می‌کنند؛ ساختن دو QApplication در یک
فرایند، مفسر را می‌کشد.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from localization import Translator  # noqa: E402
from market.timeframes import SUPPORTED_TIMEFRAMES  # noqa: E402
from ui.pages.chat_page import ChatPage  # noqa: E402


@pytest.fixture()
def qt_app(qt_application: QApplication) -> QApplication:
    """نمونه Qt مشترک جلسه (از conftest)."""
    return qt_application


@pytest.fixture()
def page(qt_app: QApplication) -> ChatPage:
    """صفحه چت فارسی آماده آزمون."""
    return ChatPage(Translator("fa"))


# ----------------------------------------------------------------------
# ساختار پایه
# ----------------------------------------------------------------------
def test_page_starts_with_welcome_message(page: ChatPage) -> None:
    """کاربر نباید با صفحه خالی روبه‌رو شود."""
    assert page.message_count == 1
    assert page._bubbles[0].label.text().strip()


def test_all_timeframes_are_available(page: ChatPage) -> None:
    """همه تایم‌فریم‌ها، از یک دقیقه تا ماهانه."""
    assert page.timeframe_combo.count() == len(SUPPORTED_TIMEFRAMES)
    codes = {page.timeframe_combo.itemData(i) for i in range(page.timeframe_combo.count())}
    assert {"1m", "4h", "1d", "1w", "1M"} <= codes


def test_default_timeframe_is_4h(page: ChatPage) -> None:
    """تایم‌فریم پیش‌فرض باید همان پیش‌فرض بقیه صفحات باشد."""
    assert page.timeframe_combo.currentData() == "4h"


def test_symbol_list_is_searchable(page: ChatPage) -> None:
    """فهرست هزار نمادی بدون جست‌وجو غیرقابل استفاده است."""
    assert page.symbol_combo.isEditable()
    completer = page.symbol_combo.completer()
    assert completer is not None
    assert completer.filterMode() == Qt.MatchFlag.MatchContains


def test_set_symbols_fills_combo(page: ChatPage) -> None:
    """پر شدن فهرست نمادها از موتور بازار."""
    page.set_symbols(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    assert page.symbol_combo.count() == 3


def test_current_context_reports_selection(page: ChatPage) -> None:
    """زمینه گفتگو باید انتخاب کاربر را منعکس کند."""
    page.set_symbols(["BTC/USDT"])
    page.symbol_combo.setCurrentText("BTC/USDT")
    context = page.current_context()
    assert context["symbol"] == "BTC/USDT"
    assert context["timeframe"] == "4h"


# ----------------------------------------------------------------------
# جریان پیام
# ----------------------------------------------------------------------
def test_sending_emits_signal_and_adds_bubble(page: ChatPage) -> None:
    """پیام کاربر باید هم روی صفحه بیاید و هم به کنترلر برسد."""
    seen: list[str] = []
    page.message_sent.connect(seen.append)

    page.input.setText("سلام")
    page.send_current()

    assert seen == ["سلام"]
    assert page.message_count == 2
    assert page.input.text() == ""


def test_empty_message_is_ignored(page: ChatPage) -> None:
    """فضای خالی نباید پیام حساب شود."""
    seen: list[str] = []
    page.message_sent.connect(seen.append)
    page.input.setText("   ")
    page.send_current()
    assert seen == []
    assert page.message_count == 1


def test_reply_lifecycle_replaces_placeholder(page: ChatPage) -> None:
    """
    حباب «در حال فکر کردن» باید با پاسخ نهایی جایگزین شود.

    اگر جایگزین نشود، کاربر دو حباب می‌بیند و گیج می‌شود.
    """
    page.input.setText("سؤال")
    page.send_current()
    count_before = page.message_count

    page.begin_reply()
    assert page.message_count == count_before + 1

    page.finish_reply("پاسخ نهایی", ["✓ get_ticker(symbol=BTC/USDT)"])
    assert page.message_count == count_before + 1
    assert page._bubbles[-1].label.text() == "پاسخ نهایی"


def test_tools_are_shown_under_answer(page: ChatPage) -> None:
    """شفافیت: کاربر باید بداند عدد از کجا آمده."""
    page.begin_reply()
    page.finish_reply("پاسخ", ["✓ get_ticker(symbol=BTC/USDT)"])
    bubble = page._bubbles[-1]
    assert "get_ticker" in bubble.tools_label.text()


def test_answer_without_tools_hides_tool_row(page: ChatPage) -> None:
    """وقتی ابزاری استفاده نشده، ردیف ابزار نباید جا بگیرد."""
    page.begin_reply()
    page.finish_reply("سلام", [])
    assert page._bubbles[-1].tools_label.isHidden()


def test_busy_state_locks_input(page: ChatPage) -> None:
    """هنگام انتظار پاسخ، ورودی باید قفل شود تا صف پیام درست بماند."""
    page.begin_reply()
    assert not page.input.isEnabled()
    assert not page.send_button.isEnabled()
    page.finish_reply("تمام")
    assert page.input.isEnabled()
    assert page.send_button.isEnabled()


def test_failed_reply_is_displayed(page: ChatPage) -> None:
    """خطا هم باید در گفتگو دیده شود، نه اینکه بی‌صدا گم شود."""
    page.begin_reply()
    page.fail_reply("سرویس در دسترس نیست")
    assert "دسترس" in page._bubbles[-1].label.text()
    assert page.input.isEnabled()


# ----------------------------------------------------------------------
# دکمه اقدام
# ----------------------------------------------------------------------
def test_action_button_hidden_by_default(page: ChatPage) -> None:
    """بدون پیشنهاد، دکمه اقدام نباید دیده شود."""
    assert page.action_button.isHidden()


def test_show_action_reveals_button(page: ChatPage) -> None:
    """پیشنهاد دستیار باید دکمه‌ای با برچسب خودش بسازد."""
    page.show()
    page.show_action({"type": "generate_signal", "symbol": "BTC/USDT", "label": "تولید سیگنال"})
    assert not page.action_button.isHidden()
    assert "تولید سیگنال" in page.action_button.text()


def test_action_requires_explicit_click(page: ChatPage) -> None:
    """
    مرز امنیتی: اقدام فقط با کلیک کاربر اجرا می‌شود.

    نمایش دکمه به‌تنهایی نباید هیچ رویدادی بفرستد.
    """
    fired: list[dict] = []
    page.action_requested.connect(fired.append)

    page.show_action({"type": "run_analysis", "symbol": "ETH/USDT", "label": "تحلیل"})
    assert fired == []

    page.action_button.click()
    assert len(fired) == 1
    assert fired[0]["type"] == "run_analysis"


def test_action_hides_after_click(page: ChatPage) -> None:
    """پس از اجرا، دکمه نباید بماند تا دوباره کلیک نشود."""
    page.show()
    page.show_action({"type": "show_markets", "label": "بازارها"})
    page.action_button.click()
    assert page.action_button.isHidden()


def test_empty_action_is_ignored(page: ChatPage) -> None:
    """اقدام بدون نوع نباید دکمه بسازد."""
    page.show_action({})
    assert page.action_button.isHidden()


def test_new_message_hides_pending_action(page: ChatPage) -> None:
    """با پرسش تازه، پیشنهاد قبلی دیگر معتبر نیست."""
    page.show()
    page.show_action({"type": "generate_signal", "symbol": "BTC/USDT", "label": "x"})
    page.input.setText("سؤال جدید")
    page.send_current()
    assert page.action_button.isHidden()


# ----------------------------------------------------------------------
# پاک کردن و تغییر زبان
# ----------------------------------------------------------------------
def test_clear_resets_to_welcome(page: ChatPage) -> None:
    """گفتگوی جدید باید همه چیز را پاک کند و خوش‌آمد را برگرداند."""
    fired: list[bool] = []
    page.chat_cleared.connect(lambda: fired.append(True))

    page.input.setText("یک")
    page.send_current()
    page.begin_reply()
    page.finish_reply("دو")
    assert page.message_count > 1

    page.clear_conversation()
    assert page.message_count == 1
    assert fired == [True]


def test_language_switch_updates_texts(qt_app: QApplication) -> None:
    """تغییر زبان در زمان اجرا نباید رشته‌ای جا بگذارد."""
    translator = Translator("fa")
    page = ChatPage(translator)
    persian_send = page.send_button.text()

    translator.set_language("en")
    page.retranslate()

    assert page.send_button.text() != persian_send
    assert page.send_button.text() == "Send"


def test_bubble_alignment_follows_direction(qt_app: QApplication) -> None:
    """
    در فارسی جای حباب‌ها آینه‌ای می‌شود.

    اگر این را نادیده بگیریم، پیام کاربر و دستیار در RTL روی هم می‌افتند.
    """
    translator = Translator("fa")
    page = ChatPage(translator)
    fa_user = page._bubble_alignment(True)

    translator.set_language("en")
    en_user = page._bubble_alignment(True)

    assert fa_user != en_user
