"""
آزمون کنترل تمام‌صفحهٔ جدول‌ها و کارت وضعیت هوش مصنوعی.

خواستهٔ کاربر دو چیز بود: این کنترل روی **تمام** جدول‌های سیستم باشد و
بازگشت از تمام‌صفحه، جدول را دقیقاً به حالت قبل برگرداند. هر دو اینجا
سنجیده می‌شوند — نه صرفاً وجود دکمه، بلکه سالم‌ماندن داده و جای جدول
پس از رفت و برگشت.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from localization import Translator
from ui.widgets.table_toolbar import (
    FullscreenTableDialog,
    TableToolbar,
    attach_table_toolbar,
    attach_table_toolbars,
)

PAGE_IMPORTS = [
    ("ui.pages.dashboard_page", "DashboardPage", 2),
    ("ui.pages.signals_page", "SignalsPage", 2),
    # v2.0: سه جدول — تاریخچه + پایش فرصت‌ها + موقعیت‌های باز
    ("ui.pages.trades_page", "TradesPage", 3),
    ("ui.pages.wallet_page", "WalletPage", 1),
    ("ui.pages.markets_page", "MarketsPage", 2),
    # سه جدول: پیش‌نمایش گزارش، تفکیک عملکرد و سابقهٔ نتیجه‌ها
    # ۴ جدول از ۱.۹.۱۹: گزارش، عملکرد (۲ جدول) و دفترچهٔ نتیجه
    ("ui.pages.reports_page", "ReportsPage", 4),
    ("ui.pages.analysis_page", "AnalysisPage", 2),
    ("ui.pages.settings_page", "SettingsPage", 2),
]


@pytest.fixture()
def translator() -> Translator:
    """مترجم فارسی برای ساخت صفحات."""
    return Translator("fa")


@pytest.fixture()
def host(qt_application, translator) -> QWidget:  # noqa: ARG001 - نیاز به QApplication
    """ویجت میزبان با یک جدول درون چیدمان عمودی."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    table = QTableWidget(0, 2, widget)
    layout.addWidget(table)
    widget.table = table  # type: ignore[attr-defined]
    return widget


def test_attach_inserts_toolbar_directly_above_table(host, translator) -> None:
    """نوار ابزار باید دقیقاً یک ردیف بالای جدول بنشیند."""
    layout = host.layout()
    table_index = layout.indexOf(host.table)

    toolbar = attach_table_toolbar(host.table, translator)

    assert toolbar is not None
    assert layout.indexOf(toolbar) == table_index
    assert layout.indexOf(host.table) == table_index + 1


def test_attach_returns_none_for_table_without_layout(qt_application, translator) -> None:  # noqa: ARG001
    """جدول بی‌چیدمان قابل بازگرداندن نیست، پس نوار نمی‌گیرد."""
    orphan = QTableWidget(0, 2)

    assert attach_table_toolbar(orphan, translator) is None


def test_fullscreen_roundtrip_restores_position_and_data(host, translator) -> None:
    """پس از بازگشت، جدول باید سرجای خودش و با همان داده‌ها باشد."""
    toolbar = attach_table_toolbar(host.table, translator)
    assert toolbar is not None
    host.show()

    host.table.setRowCount(1)
    host.table.setItem(0, 0, QTableWidgetItem("BTC/USDT"))
    original_parent = host.table.parentWidget()
    original_index = host.layout().indexOf(host.table)

    toolbar.enter_fullscreen()
    assert toolbar.is_fullscreen
    assert isinstance(host.table.window(), FullscreenTableDialog)

    toolbar.exit_fullscreen()

    assert not toolbar.is_fullscreen
    assert host.table.parentWidget() is original_parent
    assert host.layout().indexOf(host.table) == original_index
    assert host.table.item(0, 0).text() == "BTC/USDT"
    assert host.table.isVisibleTo(host)


def test_toggle_emits_state_changes(host, translator) -> None:
    """سیگنال باید هر دو جهت تغییر حالت را گزارش کند."""
    toolbar = attach_table_toolbar(host.table, translator)
    assert toolbar is not None
    states: list[bool] = []
    toolbar.fullscreen_toggled.connect(states.append)

    toolbar.toggle_fullscreen()
    toolbar.toggle_fullscreen()

    assert states == [True, False]


def test_button_label_follows_state(host, translator) -> None:
    """متن دکمه باید کنش بعدی را نشان دهد، نه حالت فعلی را."""
    toolbar = attach_table_toolbar(host.table, translator)
    assert toolbar is not None
    enter_text = translator.tr("common.fullscreen")
    exit_text = translator.tr("common.exit_fullscreen")

    assert enter_text in toolbar.fullscreen_button.text()

    toolbar.enter_fullscreen()
    assert exit_text in toolbar.fullscreen_button.text()

    toolbar.exit_fullscreen()
    assert enter_text in toolbar.fullscreen_button.text()


def test_closing_dialog_directly_restores_table(host, translator) -> None:
    """بستن پنجره از راه خودش هم باید جدول را برگرداند، نه فقط دکمه."""
    toolbar = attach_table_toolbar(host.table, translator)
    assert toolbar is not None
    toolbar.enter_fullscreen()
    dialog = host.table.window()

    dialog.close()

    assert not toolbar.is_fullscreen
    assert host.table.parentWidget() is host


def test_attach_all_skips_already_attached_tables(host, translator) -> None:
    """اجرای دوبارهٔ پیوست نباید نوار تکراری بسازد."""
    first = attach_table_toolbars(host, translator)
    second = attach_table_toolbars(host, translator)

    assert len(first) == 1
    assert second == []
    assert len(host.findChildren(TableToolbar)) == 1


@pytest.mark.parametrize(("module", "name", "expected"), PAGE_IMPORTS)
def test_every_page_table_has_a_toolbar(
    qt_application,  # noqa: ARG001 - نیاز به QApplication
    translator,
    module: str,
    name: str,
    expected: int,
) -> None:
    """خواستهٔ کاربر: این کنترل روی تمام جدول‌های سیستم باشد."""
    page_cls = getattr(__import__(module, fromlist=[name]), name)
    page = page_cls(translator)

    tables = page.findChildren(QTableWidget)
    toolbars = page.table_toolbars()

    assert len(tables) == expected
    assert len(toolbars) == expected


def test_fullscreen_title_comes_from_enclosing_card(qt_application, translator) -> None:  # noqa: ARG001
    """عنوان پنجره باید نام همان بخش باشد تا کاربر گم نشود."""
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    titles = {toolbar._resolve_title() for toolbar in page.table_toolbars()}  # noqa: SLF001

    assert translator.tr("common.table") not in titles
    assert all(title.strip() for title in titles)


def test_retranslate_updates_toolbar_text(qt_application) -> None:  # noqa: ARG001
    """تغییر زبان نباید متن دکمه را فارسی جا بگذارد."""
    from ui.pages.trades_page import TradesPage

    english = Translator("en")
    page = TradesPage(english)
    toolbar = page.table_toolbars()[0]

    assert english.tr("common.fullscreen") in toolbar.fullscreen_button.text()
    assert "تمام‌صفحه" not in toolbar.fullscreen_button.text()
