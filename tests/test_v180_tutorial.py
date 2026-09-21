"""
آزمون آموزش معامله‌گری در صفحهٔ راهنما.

کاربر «آموزش کامل معامله‌گری» خواست. «کامل» یعنی هم پوشش موضوعی و هم
دوزبانه‌بودن؛ هر دو اینجا سنجیده می‌شوند، نه صرفاً وجود ویجت.
"""

from __future__ import annotations

import pytest

from localization import Translator
from ui.widgets.tutorial_view import LEVEL_KEYS, TutorialView

#: موضوع‌هایی که یک آموزش معامله‌گری بدون آن‌ها ناقص است
REQUIRED_TOPICS = (
    "leverage",
    "risk",
    "sizing",
    "rr",
    "structure",
    "candles",
    "indicators",
    "psychology",
    "plan",
    "glossary",
)


@pytest.fixture(params=["fa", "en"])
def view(request, qt_application) -> TutorialView:  # noqa: ARG001 - نیاز به QApplication
    """نمای آموزش در هر دو زبان."""
    return TutorialView(Translator(request.param))


def test_tutorial_covers_the_essential_topics(view: TutorialView) -> None:
    """نبودِ هر کدام از این فصل‌ها یعنی آموزش ناقص است."""
    keys = {chapter.get("key") for chapter in view.chapters}

    missing = [topic for topic in REQUIRED_TOPICS if topic not in keys]
    assert not missing, f"فصل‌های جاافتاده: {missing}"


def test_chapters_have_substantial_text(view: TutorialView) -> None:
    """فصل یک‌خطی، آموزش نیست."""
    for chapter in view.chapters:
        assert len(chapter.get("body", "")) > 400, chapter.get("key")


def test_every_chapter_declares_a_known_level(view: TutorialView) -> None:
    """سطح ناشناخته یعنی برچسب خالی روی صفحه."""
    for chapter in view.chapters:
        assert chapter.get("level") in LEVEL_KEYS, chapter.get("key")


def test_both_languages_have_the_same_chapters(qt_application) -> None:  # noqa: ARG001
    """آموزش انگلیسی نباید نسخهٔ خلاصه‌شده باشد."""
    fa = [chapter["key"] for chapter in TutorialView(Translator("fa")).chapters]
    en = [chapter["key"] for chapter in TutorialView(Translator("en")).chapters]

    assert fa == en


def test_selecting_a_chapter_shows_its_text(view: TutorialView) -> None:
    """کلیک روی فهرست باید واقعاً متن را عوض کند."""
    assert view.select_chapter("sizing")

    chapter = next(item for item in view.chapters if item["key"] == "sizing")
    assert view.title_label.text() == chapter["title"]
    assert view.body_label.text() == chapter["body"]


def test_navigation_moves_between_chapters(view: TutorialView) -> None:
    """دکمه‌های قبلی/بعدی باید واقعاً جابه‌جا کنند."""
    view.chapter_list.setCurrentRow(0)
    first = view.title_label.text()

    view.go_next()
    second = view.title_label.text()
    view.go_previous()

    assert second != first
    assert view.title_label.text() == first


def test_navigation_stops_at_the_edges(view: TutorialView) -> None:
    """در ابتدا و انتهای آموزش نباید دکمهٔ بی‌اثر فعال بماند."""
    view.chapter_list.setCurrentRow(0)
    assert not view.prev_button.isEnabled()

    view.chapter_list.setCurrentRow(view.chapter_list.count() - 1)
    assert not view.next_button.isEnabled()


def test_search_narrows_the_chapter_list(view: TutorialView) -> None:
    """جست‌وجو باید در متن هم بگردد، نه فقط در عنوان."""
    total = view.chapter_list.count()
    needle = "ATR"

    view.search.setText(needle)

    assert 0 < view.chapter_list.count() < total


def test_search_with_no_match_shows_a_message(view: TutorialView) -> None:
    """نتیجهٔ خالی نباید صفحهٔ سفید بی‌توضیح بدهد."""
    view.search.setText("qqqzzzxxx")

    assert view.chapter_list.count() == 0
    assert view.title_label.text() == view.tr_.tr("tutorial.no_results")
    assert not view.next_button.isEnabled()


def test_clearing_search_restores_every_chapter(view: TutorialView) -> None:
    """پاک‌کردن جست‌وجو باید همه‌چیز را برگرداند."""
    total = view.chapter_list.count()

    view.search.setText("qqqzzzxxx")
    view.search.setText("")

    assert view.chapter_list.count() == total


def test_help_page_exposes_the_tutorial_tab(qt_application) -> None:  # noqa: ARG001
    """آموزش باید در صفحهٔ راهنما در دسترس باشد، نه جای دیگر."""
    from ui.pages.help_page import HelpPage

    page = HelpPage(Translator("fa"))

    assert page.tabs.count() == 2
    page.open_tutorial("psychology")
    assert page.tabs.currentIndex() == 1
    assert "روان" in page.tutorial.title_label.text()


def test_help_page_keeps_its_original_sections(qt_application) -> None:  # noqa: ARG001
    """افزودن آموزش نباید راهنمای قبلی را حذف کرده باشد."""
    from ui.pages.help_page import HelpPage

    page = HelpPage(Translator("fa"))

    assert len(page._cards) == len(HelpPage.SECTIONS)  # noqa: SLF001
    titles = [card.title_label.text() for card, _, _, _ in page._cards]  # noqa: SLF001
    assert all(title.strip() for title in titles)


def test_language_change_reloads_the_tutorial(qt_application) -> None:  # noqa: ARG001
    """تغییر زبان نباید متن فارسی را در حالت انگلیسی جا بگذارد."""
    from ui.pages.help_page import HelpPage

    page = HelpPage(Translator("fa"))
    page.open_tutorial("risk")
    persian_title = page.tutorial.title_label.text()

    page.tr_.set_language("en")
    page.retranslate()

    english_title = page.tutorial.title_label.text()
    assert english_title != persian_title
    # علامت نگارشی مثل خط تیرهٔ بلند غیرASCII است ولی اشکالی ندارد؛
    # آنچه نباید بماند، حرف فارسی است.
    assert not any("\u0600" <= char <= "\u06ff" for char in english_title)


def test_reload_keeps_the_reader_on_the_same_chapter(qt_application) -> None:  # noqa: ARG001
    """کاربر نباید پس از تغییر زبان جای خودش را در آموزش گم کند."""
    view = TutorialView(Translator("fa"))
    view.select_chapter("plan")

    view.tr_.set_language("en")
    view.reload()

    index = view.current_index()
    assert view.chapters[index]["key"] == "plan"
