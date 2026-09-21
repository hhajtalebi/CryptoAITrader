"""
آزمون‌های مخزن گفت‌وگوهای چت.

تمرکز: ذخیره، بازیابی، عنوان خودکار، جست‌وجو، سنجاق و حذف.
"""

from __future__ import annotations

import pytest

from app.database.repositories import ChatRepository
from app.database.repositories.chat_repository import TITLE_MAX_LENGTH


@pytest.fixture()
def repository(database) -> ChatRepository:
    """مخزن چت روی پایگاه دادهٔ موقت آزمون."""
    return ChatRepository(database)


def test_create_and_list(repository: ChatRepository) -> None:
    """گفت‌وگوی تازه ساخته و در فهرست دیده می‌شود."""
    conversation_id = repository.create_conversation(symbol="BTC/USDT", timeframe="4h")
    assert conversation_id > 0

    conversations = repository.list_conversations()
    assert len(conversations) == 1
    assert conversations[0]["symbol"] == "BTC/USDT"
    assert conversations[0]["timeframe"] == "4h"
    assert conversations[0]["message_count"] == 0


def test_title_generated_from_first_user_message(repository: ChatRepository) -> None:
    """عنوان گفت‌وگو از نخستین پیام کاربر ساخته می‌شود."""
    conversation_id = repository.create_conversation()
    repository.add_message(conversation_id, role="user", content="تحلیل بیت‌کوین را بگو")

    conversation = repository.get_conversation(conversation_id)
    assert conversation is not None
    assert conversation["title"] == "تحلیل بیت‌کوین را بگو"


def test_long_title_is_truncated(repository: ChatRepository) -> None:
    """عنوان بلند بریده می‌شود تا فهرست به‌هم نریزد."""
    conversation_id = repository.create_conversation()
    repository.add_message(conversation_id, role="user", content="سلام " * 100)

    conversation = repository.get_conversation(conversation_id)
    assert conversation is not None
    assert len(conversation["title"]) <= TITLE_MAX_LENGTH


def test_assistant_message_does_not_set_title(repository: ChatRepository) -> None:
    """پاسخ دستیار نباید عنوان گفت‌وگو شود."""
    conversation_id = repository.create_conversation()
    repository.add_message(conversation_id, role="assistant", content="پاسخ دستیار")

    conversation = repository.get_conversation(conversation_id)
    assert conversation is not None
    assert conversation["title"] == ""


def test_messages_keep_order_and_tools(repository: ChatRepository) -> None:
    """پیام‌ها به ترتیب و همراه با ابزارها برمی‌گردند."""
    conversation_id = repository.create_conversation()
    repository.add_message(conversation_id, role="user", content="اول")
    repository.add_message(
        conversation_id,
        role="assistant",
        content="دوم",
        tools=["get_ticker", "detect_trend"],
        provider="ollama",
        model="llama3",
    )

    messages = repository.messages(conversation_id)
    assert [m["content"] for m in messages] == ["اول", "دوم"]
    assert messages[1]["tools"] == ["get_ticker", "detect_trend"]
    assert messages[1]["provider"] == "ollama"
    assert messages[1]["model"] == "llama3"


def test_message_count_increments(repository: ChatRepository) -> None:
    """شمارندهٔ پیام‌ها با هر پیام بالا می‌رود."""
    conversation_id = repository.create_conversation()
    for index in range(3):
        repository.add_message(conversation_id, role="user", content=f"پیام {index}")

    conversation = repository.get_conversation(conversation_id)
    assert conversation is not None
    assert conversation["message_count"] == 3


def test_delete_removes_conversation_and_messages(repository: ChatRepository) -> None:
    """حذف گفت‌وگو، پیام‌هایش را هم پاک می‌کند."""
    conversation_id = repository.create_conversation()
    repository.add_message(conversation_id, role="user", content="متن")

    assert repository.delete_conversation(conversation_id) is True
    assert repository.get_conversation(conversation_id) is None
    assert repository.messages(conversation_id) == []


def test_delete_missing_conversation_is_safe(repository: ChatRepository) -> None:
    """حذف گفت‌وگوی ناموجود خطا نمی‌دهد."""
    assert repository.delete_conversation(9999) is False


def test_rename_conversation(repository: ChatRepository) -> None:
    """تغییر نام گفت‌وگو ذخیره می‌شود."""
    conversation_id = repository.create_conversation()
    assert repository.rename_conversation(conversation_id, "نام تازه") is True

    conversation = repository.get_conversation(conversation_id)
    assert conversation is not None
    assert conversation["title"] == "نام تازه"


def test_pinned_conversations_come_first(repository: ChatRepository) -> None:
    """گفت‌وگوی سنجاق‌شده بالای فهرست می‌آید."""
    first = repository.create_conversation(title="اولی")
    second = repository.create_conversation(title="دومی")

    repository.set_pinned(first, True)
    conversations = repository.list_conversations()
    assert conversations[0]["id"] == first
    assert any(c["id"] == second for c in conversations)


def test_search_finds_by_message_content(repository: ChatRepository) -> None:
    """جست‌وجو گفت‌وگو را از روی متن پیام پیدا می‌کند."""
    first = repository.create_conversation()
    repository.add_message(first, role="user", content="دربارهٔ اتریوم بگو")
    second = repository.create_conversation()
    repository.add_message(second, role="user", content="دربارهٔ بیت‌کوین بگو")

    found = repository.search("اتریوم")
    assert [c["id"] for c in found] == [first]


def test_search_with_empty_term_returns_all(repository: ChatRepository) -> None:
    """جست‌وجوی خالی یعنی «همه»."""
    repository.create_conversation(title="یک")
    repository.create_conversation(title="دو")
    assert len(repository.search("  ")) == 2


def test_add_message_to_missing_conversation_raises(repository: ChatRepository) -> None:
    """افزودن پیام به گفت‌وگوی ناموجود باید صریح خطا بدهد."""
    with pytest.raises(ValueError):
        repository.add_message(4242, role="user", content="متن")


def test_clear_all(repository: ChatRepository) -> None:
    """پاک کردن کامل تاریخچه."""
    first = repository.create_conversation()
    repository.add_message(first, role="user", content="متن")
    repository.create_conversation()

    assert repository.clear_all() == 2
    assert repository.list_conversations() == []


def test_make_title_collapses_whitespace() -> None:
    """فاصله‌های اضافی در عنوان جمع می‌شوند."""
    assert ChatRepository.make_title("  سلام   دنیا \n خوبی؟ ") == "سلام دنیا خوبی؟"


def test_make_title_of_empty_text() -> None:
    """متن خالی عنوان خالی می‌دهد."""
    assert ChatRepository.make_title("   ") == ""
