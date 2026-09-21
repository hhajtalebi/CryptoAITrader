"""
آزمون پیمایش صفحه و اندازه‌های صفحهٔ سیگنال‌ها (نسخهٔ ۱.۹.۳).

کاربر گزارش داد صفحهٔ سیگنال‌ها «در هم برهم» است و اسکرول نمی‌خورد.
ریشه‌اش این بود که مجموع حداقل‌ ارتفاع بخش‌های صفحه از ارتفاع پنجره
بیشتر می‌شد و Qt به‌جای پیمایش، همه‌چیز را فشرده می‌کرد: جدول‌ها به چند
ردیف می‌رسیدند و متن‌های چندخطی نصفه می‌شدند.

این آزمون‌ها روی چیزی تمرکز دارند که اگر بشکند کاربر دوباره همان صفحهٔ
له‌شده را می‌بیند:

    • هیچ صفحه‌ای نباید ارتفاعی بیش از یک نمایشگر معمولی طلب کند
    • صفحهٔ اسکرول‌پذیر باید واقعاً نوار پیمایش عمودی بدهد
    • سرآیند صفحه نباید با محتوا اسکرول شود
    • جدول نتیجهٔ پویش باید با تعداد نتیجه‌ها رشد کند، ولی بی‌نهایت نه
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea

from localization import Translator

#: ارتفاع کاری یک نمایشگر ۷۶۸ پیکسلی پس از کسر نوار وظیفه و کروم پنجره.
#: هیچ صفحه‌ای نباید بیش از این طلب کند، وگرنه روی لپ‌تاپ بریده می‌شود.
LAPTOP_HEIGHT = 660

PAGE_IMPORTS = [
    ("ui.pages.dashboard_page", "DashboardPage"),
    ("ui.pages.markets_page", "MarketsPage"),
    ("ui.pages.analysis_page", "AnalysisPage"),
    ("ui.pages.signals_page", "SignalsPage"),
    ("ui.pages.chat_page", "ChatPage"),
    ("ui.pages.trades_page", "TradesPage"),
    ("ui.pages.wallet_page", "WalletPage"),
    ("ui.pages.reports_page", "ReportsPage"),
    ("ui.pages.settings_page", "SettingsPage"),
    ("ui.pages.help_page", "HelpPage"),
]


@pytest.fixture()
def translator() -> Translator:
    """مترجم فارسی — حالت پیش‌فرض کاربر."""
    return Translator("fa")


def build_page(module: str, name: str, translator: Translator):  # noqa: ANN201
    """ساخت یک نمونه از صفحه."""
    page_cls = getattr(__import__(module, fromlist=[name]), name)
    return page_cls(translator)


@pytest.mark.parametrize(("module", "name"), PAGE_IMPORTS)
def test_page_fits_a_laptop_screen(
    qt_application,  # noqa: ARG001 - نیاز به QApplication
    translator: Translator,
    module: str,
    name: str,
) -> None:
    """
    هیچ صفحه‌ای نباید ارتفاع بیشتر از نمایشگر لپ‌تاپ تحمیل کند.

    این همان نقصی است که کاربر دید: صفحهٔ سیگنال‌ها حداقل ۱۱۸۱ پیکسل
    می‌خواست، پس در پنجرهٔ ۸۰۰ پیکسلی محتوا روی هم فشرده می‌شد.
    """
    page = build_page(module, name, translator)
    assert page.minimumSizeHint().height() <= LAPTOP_HEIGHT


def test_signals_page_is_marked_scrollable(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """شلوغ‌ترین صفحهٔ برنامه باید پیمایش داشته باشد."""
    from ui.pages.signals_page import SignalsPage

    assert SignalsPage.scrollable is True


def test_signals_page_really_scrolls(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    در ارتفاع واقعی یک لپ‌تاپ، نوار پیمایش باید بازهٔ مثبت داشته باشد.

    وجود `QScrollArea` به‌تنهایی کافی نیست؛ اگر محتوا کوچک‌تر از
    دیدگاه بماند یا `setWidgetResizable` جا بیفتد، پیمایش عملاً کار
    نمی‌کند.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    page.resize(1250, 700)
    page.show()

    area = page.findChild(QScrollArea)
    assert area is not None
    assert area.widgetResizable() is True
    assert area.verticalScrollBar().maximum() > 0


def test_signals_page_has_no_horizontal_scrollbar(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    پیمایش افقی خاموش است.

    اگر روشن بماند، نوار افقی برای چند پیکسل سرریز ظاهر می‌شود و صفحه
    شلخته به نظر می‌رسد.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    area = page.findChild(QScrollArea)
    assert area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_header_stays_outside_the_scroll_area(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    عنوان صفحه نباید با محتوا اسکرول شود.

    کاربری که تا پایین فهرست می‌رود باید همچنان بداند کجاست.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    area = page.findChild(QScrollArea)
    assert page.header not in area.widget().findChildren(type(page.header))


def test_wait_note_is_not_clipped(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    توضیح «انتظار» چندخطی است و باید کامل جا شود.

    ‏`setWordWrap` ارتفاع لازم را به چیدمان اعلام نمی‌کند، پس برچسب به
    یک خط فشرده می‌شد و متن نصفه می‌ماند.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    page.resize(1250, 800)
    page.show()
    assert page.wait_note.minimumHeight() >= page.wait_note.sizeHint().height()


def make_scan_rows(count: int) -> list[dict]:
    """چند ردیف نتیجهٔ پویش ساختگی."""
    return [
        {
            "symbol": f"SYM{index}/USDT",
            "direction": "LONG",
            "confidence": 70,
            "risk_reward": 2.0,
            "stop_distance_percent": 1.5,
            "leverage": 3,
        }
        for index in range(count)
    ]


@pytest.mark.parametrize("rows", [1, 3, 5, 12])
def test_scan_table_grows_with_results(
    qt_application,  # noqa: ARG001
    translator: Translator,
    rows: int,
) -> None:
    """
    جدول پویش باید همهٔ نتیجه‌ها را بدون اسکرول داخلی نشان دهد.

    صفحه خودش پیمایش دارد؛ اسکرول داخل اسکرول کاربر را گیج می‌کند و
    ردیف‌های پایین عملاً دیده نمی‌شوند.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    page.resize(1250, 800)
    page.show()
    page.set_scan_results(make_scan_rows(rows))

    table = page.scan_table
    needed = table.horizontalHeader().height() + table.rowHeight(0) * rows
    assert table.height() >= needed


def test_scan_table_is_capped_for_long_results(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    رشد جدول بی‌نهایت نیست.

    شصت نتیجه نباید صفحه‌ای چند هزار پیکسلی بسازد؛ از سقف به بعد خود
    جدول اسکرول می‌گیرد.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    page.resize(1250, 800)
    page.show()
    page.set_scan_results(make_scan_rows(60))

    table = page.scan_table
    unbounded = table.horizontalHeader().height() + table.rowHeight(0) * 60
    assert table.height() < unbounded
    assert table.rowCount() == 60


def test_scan_table_shrinks_back_when_cleared(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """پس از پاک‌شدن نتیجه‌ها، جدول نباید ارتفاع قبلی را نگه دارد."""
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    page.resize(1250, 800)
    page.show()
    page.set_scan_results(make_scan_rows(12))
    tall = page.scan_table.height()
    page.set_scan_results([])
    assert page.scan_table.height() < tall


def test_hidden_progress_bar_takes_no_space(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    نوار پیشرفت مخفی نباید ارتفاع ببلعد.

    پیش‌تر این ویجت‌های نامرئی ۴۸۰ پیکسل می‌گرفتند و بخشی از شلوغی
    صفحه از همین‌جا می‌آمد.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    page.resize(1250, 800)
    page.show()
    assert page.progress.isVisibleTo(page) is False
    assert page.progress.height() <= 10


def test_table_toolbars_survive_inside_the_scroll_area(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    کنترل تمام‌صفحه باید داخل ناحیهٔ پیمایش هم به جدول‌ها وصل شود.

    ‏`BasePage` جدول‌ها را با `findChildren` پیدا می‌کند؛ اگر روزی به
    پیمایش فرزندان مستقیم تغییر کند، این آزمون می‌شکند.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    assert len(page.table_toolbars()) == 2


def test_non_scrollable_pages_keep_their_layout(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    صفحه‌ای که `scrollable` را روشن نکرده نباید ناحیهٔ پیمایش بگیرد.

    تغییر `BasePage` نباید رفتار صفحه‌های موجود را عوض کند.
    """
    from ui.pages.trades_page import TradesPage

    page = TradesPage(translator)
    assert page.scrollable is False
    assert page.layout_root().parentWidget() is page


def test_reports_report_tab_is_scrollable(
    qt_application,  # noqa: ARG001
    translator: Translator,
) -> None:
    """
    هر دو زبانهٔ صفحهٔ گزارش‌ها باید پیمایش داشته باشند.

    زبانهٔ «عملکرد» از ابتدا داشت ولی زبانهٔ «گزارش» نه، و همان یکی
    حداقل ارتفاع کل صفحه را به ۹۷۵ پیکسل می‌رساند.
    """
    from ui.pages.reports_page import ReportsPage

    page = ReportsPage(translator)
    for index in range(page.tabs.count()):
        assert isinstance(page.tabs.widget(index), QScrollArea)
