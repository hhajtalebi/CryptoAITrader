"""
آزمون صفحه‌های تازه و پوستهٔ بیرونی پنجره.

مهم‌ترین چیزی که این آزمون‌ها محافظت می‌کنند: **هیچ قابلیتی وابسته به
پوسته نیست.** همهٔ ده صفحه در هر چهار پوسته ساخته می‌شوند و تغییر پوسته
نباید داده یا وضعیت صفحه را از بین ببرد.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from localization import Translator
from tests.conftest import destroy_window
from ui.pages import TradesPage, WalletPage
from ui.themes import THEME_CATALOG, ThemeManager, get_theme
from ui.windows import MainWindow


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    """
    یک نمونهٔ QApplication برای کل ماژول.

    ساختن دو QApplication در یک فرایند، pytest را می‌کشد.
    """
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def translator() -> Translator:
    """مترجم فارسی بارگذاری‌شده."""
    instance = Translator("fa")
    instance.load()
    return instance


@pytest.fixture()
def window(qt_app: QApplication, translator: Translator) -> MainWindow:
    """
    پنجرهٔ اصلی با پوستهٔ پیش‌فرض.

    پس از هر آزمون پنجره **قطعی** حذف می‌شود، نه فقط `deleteLater`.
    دلیلش در `conftest.destroy_window` نوشته شده؛ خلاصه‌اش این است که
    درخت ویجت نشتی‌شده باعث می‌شد `setStyleSheet` آزمون بعدی هر بار
    کندتر شود و این فایل از سقف زمانی رد برود.
    """
    manager = ThemeManager()
    manager.apply(qt_app, "glass_dark")
    main_window = MainWindow(translator, manager)
    try:
        yield main_window
    finally:
        destroy_window(main_window, qt_app)


# ---------------------------------------------------------------------------
# پنجرهٔ اصلی
# ---------------------------------------------------------------------------
def test_window_exposes_core_pages(window: MainWindow) -> None:
    """یازده صفحهٔ برنامه باید موجود باشند (پیش‌بینی از v1.11.0)."""
    keys = [key for key, _ in window.PAGES]
    assert keys == [
        "nav.dashboard",
        "nav.markets",
        "nav.analysis",
        "nav.signals",
        "nav.prediction",
        "nav.chat",
        "nav.trades",
        "nav.wallet",
        "nav.reports",
        "nav.settings",
        "nav.help",
    ]
    assert window.stack.count() == 11


def test_every_page_is_reachable(window: MainWindow) -> None:
    """هر صفحه باید با ناوبری باز شود."""
    for index in range(len(window.PAGES)):
        window.go_to_page(index)
        assert window.stack.currentIndex() == index


def test_page_index_lookup(window: MainWindow) -> None:
    """جستجوی نمایهٔ صفحه بر پایهٔ کلید."""
    assert window.page_index("nav.wallet") == 7
    assert window.page_index("nav.trades") == 6
    assert window.page_index("nav.prediction") == 4
    # کلید ناشناس نباید خطا بدهد
    assert window.page_index("nav.nonexistent") == 0


def test_shortcuts_registry_is_populated(window: MainWindow) -> None:
    """ثبت‌گاه میان‌برها باید پر باشد تا صفحهٔ راهنما بتواند آن را بخواند."""
    assert "Ctrl+K" in window.shortcuts
    assert "Ctrl+B" in window.shortcuts
    assert "Ctrl+T" in window.shortcuts
    # یک میان‌بر برای هر صفحه
    assert len(window.shortcuts) >= len(window.PAGES) + 5


def test_focus_mode_hides_chrome_but_keeps_pages(window: MainWindow) -> None:
    """
    حالت تمرکز فقط فضا آزاد می‌کند.

    هیچ صفحه‌ای نباید حذف شود — همان قاعدهٔ «پوسته قابلیت را محدود
    نمی‌کند».
    """
    window.set_focus_mode(True)
    assert window.sidebar.width() < 100
    assert window.stack.count() == 11

    window.set_focus_mode(False)
    assert window.sidebar.width() > 200


@pytest.mark.parametrize("theme_key", sorted(THEME_CATALOG))
def test_all_pages_survive_every_theme(
    window: MainWindow, qt_app: QApplication, theme_key: str
) -> None:
    """
    تعویض پوسته نباید هیچ صفحه‌ای را بشکند.

    این آزمون همان قول اصلی را می‌سنجد: قابلیت‌ها در همهٔ پوسته‌ها
    یکسان‌اند.
    """
    manager = ThemeManager()
    manager.apply(qt_app, theme_key)
    window._themes = manager
    window.apply_theme_tokens()

    for index in range(len(window.PAGES)):
        window.go_to_page(index)
        assert window.stack.currentWidget() is not None


def test_theme_switch_preserves_table_data(
    window: MainWindow, qt_app: QApplication
) -> None:
    """داده‌های روی صفحه پس از تعویض پوسته باید سر جای خود بمانند."""
    trades = window.pages["nav.trades"]
    trades.set_trades(
        [
            {
                "id": 1,
                "symbol": "BTC/USDT",
                "side": "long",
                "status": "closed",
                "pnl": 120.0,
                "date_text": "۱۴۰۵/۰۶/۲۰",
                "pnl_text": "+۱۲۰",
                "pnl_percent_text": "+۲٪",
            }
        ],
        page=1,
        pages=1,
    )
    assert trades.table.rowCount() == 1

    for key in sorted(THEME_CATALOG):
        manager = ThemeManager()
        manager.apply(qt_app, key)
        window._themes = manager
        window.apply_theme_tokens()

    assert trades.table.rowCount() == 1
    assert trades.table.item(0, 1).text() == "BTC/USDT"


def test_language_switch_updates_navigation(window: MainWindow) -> None:
    """تغییر زبان باید برچسب‌های ناوبری را عوض کند و چیزی جا نماند."""
    window.tr_.set_language("en")
    window.retranslate()
    assert window.sidebar._labels[0] == "Dashboard"
    assert window.sidebar._labels[4] == "Predictions"
    assert window.sidebar._labels[7] == "Wallet"

    window.tr_.set_language("fa")
    window.retranslate()
    assert window.sidebar._labels[0] == "داشبورد"
    assert window.sidebar._labels[4] == "پیش‌بینی"
    assert window.sidebar._labels[6] == "تاریخچه معاملات"


# ---------------------------------------------------------------------------
# صفحهٔ کیف پول
# ---------------------------------------------------------------------------
def test_wallet_shows_guidance_when_no_account(
    qt_app: QApplication, translator: Translator
) -> None:
    """
    بدون حساب صرافی باید راهنما دیده شود، نه جدول خالی.

    حالت خالی معنادار یکی از خواسته‌های صریح کاربر است.
    """
    page = WalletPage(translator)
    page.set_connected(False)
    assert page.stack.currentIndex() == 1

    page.set_connected(True)
    assert page.stack.currentIndex() == 0


def test_wallet_populates_assets_and_donut(
    qt_app: QApplication, translator: Translator
) -> None:
    """جدول دارایی و نمودار سهم باید پر شوند."""
    page = WalletPage(translator)
    page.apply_theme(get_theme("glass_dark"))
    page.set_assets(
        [
            {"asset": "USDT", "amount_text": "۸۰۰", "value_text": "۸۰۰ $", "share": 66.0,
             "share_text": "۶۶٪", "change": 0.0, "change_text": "۰٪"},
            {"asset": "BTC", "amount_text": "۰٫۰۵", "value_text": "۴۰۰ $", "share": 34.0,
             "share_text": "۳۴٪", "change": 1.5, "change_text": "+۱٫۵٪"},
        ]
    )
    assert page.assets_table.rowCount() == 2
    assert page.assets_table.item(0, 0).text() == "USDT"
    assert page.asset_row(1)["asset"] == "BTC"


def test_wallet_emits_connect_request(
    qt_app: QApplication, translator: Translator
) -> None:
    """دکمهٔ «اتصال حساب» باید سیگنال بدهد تا کاربر به تنظیمات برود."""
    page = WalletPage(translator)
    received: list[bool] = []
    page.connect_requested.connect(lambda: received.append(True))
    page.empty_state.action_clicked.emit()
    assert received == [True]


# ---------------------------------------------------------------------------
# صفحهٔ تاریخچهٔ معاملات
# ---------------------------------------------------------------------------
def test_trades_page_shows_empty_state(
    qt_app: QApplication, translator: Translator
) -> None:
    """بدون معامله باید پیام خالی دیده شود و جدول پنهان بماند."""
    page = TradesPage(translator)
    page.set_trades([], page=1, pages=1)
    assert page.table.isVisible() is False


def test_trades_filters_default_to_all(
    qt_app: QApplication, translator: Translator
) -> None:
    """فیلترهای پیش‌فرض نباید چیزی را حذف کنند."""
    page = TradesPage(translator)
    filters = page.filters()
    assert filters["side"] == ""
    assert filters["status"] == ""
    assert filters["symbol"] == ""
    assert filters["page"] == 1


def test_trades_filter_change_resets_to_first_page(
    qt_app: QApplication, translator: Translator
) -> None:
    """
    با تغییر فیلتر باید به صفحهٔ اول برگردیم.

    وگرنه کاربر در صفحهٔ ۵ فیلتری می‌زند که فقط دو صفحه نتیجه دارد و
    جدول خالی می‌بیند.
    """
    page = TradesPage(translator)
    page._page = 4
    captured: list[dict] = []
    page.filters_changed.connect(captured.append)

    page.side_combo.setCurrentIndex(1)
    assert captured
    assert captured[-1]["page"] == 1


def test_trades_symbol_filter_keeps_selection_on_refresh(
    qt_app: QApplication, translator: Translator
) -> None:
    """تازه‌سازی فهرست نمادها نباید انتخاب کاربر را دور بیندازد."""
    page = TradesPage(translator)
    page.set_symbols(["BTC/USDT", "ETH/USDT"])
    position = page.symbol_combo.findData("ETH/USDT")
    page.symbol_combo.setCurrentIndex(position)

    page.set_symbols(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    assert page.symbol_combo.currentData() == "ETH/USDT"


def test_trades_page_carries_paper_mode_notice(
    qt_app: QApplication, translator: Translator
) -> None:
    """کاربر باید ببیند معاملات شبیه‌سازی‌شده‌اند."""
    page = TradesPage(translator)
    assert page.notice.text().strip()
    assert page.notice.text() == translator.tr("trades.paper_notice")
