"""
آزمون‌های مرتب‌سازی و کلیک صفحهٔ بازارها و مدال جزئیات ارز.

کاربر گفت: «ترتیب قرارگیری ارزها اصلاً خوب نیست، ارزها ابتدا باید بر
اساس ارزش آن‌ها دسته‌بندی بشه … و قابلیت کلیک روی هر ارز هم فعال بشه که
مدال جزئیات نمایش داده بشه».
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import Qt

from localization import Translator
from ui.dialogs.coin_detail_dialog import CoinDetailDialog
from ui.pages.markets_page import (
    COL_PRICE_USD,
    COL_SYMBOL,
    SORT_MODES,
    MarketsPage,
    NumericItem,
)

pytestmark = pytest.mark.usefixtures("qt_application")


ROWS: list[dict[str, Any]] = [
    # ارز ارزان با حجم عظیم: ارزش معاملات پایین است
    {"symbol": "TINY/USDT", "price": 0.00001, "volume": 900_000_000, "change_percent": 5.0, "high": 0.000012},
    {"symbol": "BTC/USDT", "price": 79000.0, "volume": 1200.0, "change_percent": -1.2, "high": 80000.0},
    {"symbol": "ETH/USDT", "price": 3000.0, "volume": 50000.0, "change_percent": 8.4, "high": 3100.0},
]


@pytest.fixture()
def page() -> MarketsPage:
    """صفحهٔ بازارها با سه ردیف نمونه."""
    translator = Translator()
    translator.set_language("fa")
    widget = MarketsPage(translator)
    widget.set_rows(ROWS)
    return widget


def order_of(page: MarketsPage) -> list[str]:
    """ترتیب فعلی نمادها در جدول."""
    return [
        page.table.item(row, COL_SYMBOL).text().split("/")[0]
        for row in range(page.table.rowCount())
    ]


# ---------------------------------------------------------------------------
# مرتب‌سازی
# ---------------------------------------------------------------------------
def test_default_sort_is_market_cap_then_volume(page: MarketsPage) -> None:
    """
    v2.5.1: پیش‌فرض «ارزش بازار + حجم» است — خواستهٔ کاربر: «بیت‌کوین،
    اتریوم و… نمادهای باارزش‌اند و باید اول بیایند». TINY با وجود بیشترین
    حجم خام آخر است.
    """
    assert page._sort_mode == "market_cap"
    assert order_of(page) == ["BTC", "ETH", "TINY"]


def test_value_sort_is_by_quote_value(page: MarketsPage) -> None:
    """
    حالت «ارزش معاملات»: ETH بیشترین ارزش (۱۵۰ میلیون) و TINY کمترین (۹
    هزار) را دارد، هرچند حجم TINY از همه بیشتر است.
    """
    page._sort_mode = "value"
    page._filter("")
    assert order_of(page) == ["ETH", "BTC", "TINY"]


def test_sort_by_volume(page: MarketsPage) -> None:
    """مرتب‌سازی بر پایهٔ حجم خام."""
    page._sort_mode = "volume"
    page._filter("")
    assert order_of(page) == ["TINY", "ETH", "BTC"]


def test_sort_by_gainers(page: MarketsPage) -> None:
    """بیشترین رشد در بالا."""
    page._sort_mode = "gainers"
    page._filter("")
    assert order_of(page) == ["ETH", "TINY", "BTC"]


def test_sort_by_losers(page: MarketsPage) -> None:
    """بیشترین افت در بالا."""
    page._sort_mode = "losers"
    page._filter("")
    assert order_of(page) == ["BTC", "TINY", "ETH"]


def test_sort_by_price_descending(page: MarketsPage) -> None:
    """قیمت زیاد به کم."""
    page._sort_mode = "price_desc"
    page._filter("")
    assert order_of(page) == ["BTC", "ETH", "TINY"]


def test_sort_by_price_ascending(page: MarketsPage) -> None:
    """قیمت کم به زیاد."""
    page._sort_mode = "price_asc"
    page._filter("")
    assert order_of(page) == ["TINY", "ETH", "BTC"]


def test_sort_by_name(page: MarketsPage) -> None:
    """ترتیب الفبایی."""
    page._sort_mode = "name"
    page._filter("")
    assert order_of(page) == ["BTC", "ETH", "TINY"]


def test_explicit_quote_volume_field_wins(page: MarketsPage) -> None:
    """اگر صرافی خودش ارزش معاملات را داده باشد، همان مبنا است."""
    page.set_rows([
        {"symbol": "AAA/USDT", "price": 1.0, "volume": 10.0, "quote_volume": 5.0},
        {"symbol": "BBB/USDT", "price": 1.0, "volume": 10.0, "quote_volume": 500.0},
    ])
    assert order_of(page) == ["BBB", "AAA"]


def test_sort_combo_has_all_modes(page: MarketsPage) -> None:
    """همهٔ حالت‌های مرتب‌سازی در فهرست کشویی هستند."""
    assert page.sort_combo.count() == len(SORT_MODES)
    modes = {page.sort_combo.itemData(i) for i in range(page.sort_combo.count())}
    assert modes == {mode for mode, _key in SORT_MODES}


def test_changing_combo_reorders_table(page: MarketsPage) -> None:
    """انتخاب کاربر در فهرست کشویی واقعاً جدول را عوض می‌کند."""
    index = page.sort_combo.findData("name")
    page.sort_combo.setCurrentIndex(index)
    assert order_of(page) == ["BTC", "ETH", "TINY"]


def test_sorting_survives_filtering(page: MarketsPage) -> None:
    """فیلتر جست‌وجو نباید ترتیب انتخابی را از بین ببرد."""
    page._sort_mode = "price_desc"
    page._filter("T")  # BTC/USDT و ETH/USDT و TINY/USDT همگی T دارند
    prices = [
        page.table.item(row, COL_SYMBOL).text()
        for row in range(page.table.rowCount())
    ]
    assert prices[0].startswith("BTC")


# ---------------------------------------------------------------------------
# مرتب‌سازی عددی سرستون
# ---------------------------------------------------------------------------
def test_numeric_item_compares_by_number() -> None:
    """
    مقایسهٔ سلول‌ها باید عددی باشد نه متنی.

    متن «۹» از «۱۰» بزرگ‌تر است اگر متنی مقایسه شود؛ عدد ۹ کوچک‌تر است.
    """
    assert NumericItem("۹", 9.0) < NumericItem("۱۰", 10.0)
    assert not NumericItem("۱۰۰", 100.0) < NumericItem("۲۰", 20.0)


def test_header_click_sorts_numerically(page: MarketsPage) -> None:
    """کلیک روی سرستون قیمت، عددی مرتب می‌کند."""
    page._on_header_clicked(COL_PRICE_USD)
    assert order_of(page) == ["TINY", "ETH", "BTC"]
    page._on_header_clicked(COL_PRICE_USD)
    assert order_of(page) == ["BTC", "ETH", "TINY"]


def test_header_click_rebuilds_index(page: MarketsPage) -> None:
    """پس از مرتب‌سازی، نمایهٔ ردیف‌ها باید درست باشد."""
    page._on_header_clicked(COL_PRICE_USD)
    for symbol, row in page._row_index.items():
        assert page.table.item(row, COL_SYMBOL).text() == symbol


# ---------------------------------------------------------------------------
# کلیک روی ارز
# ---------------------------------------------------------------------------
def test_clicking_row_emits_symbol(page: MarketsPage) -> None:
    """کلیک روی هر سلول، نماد همان ردیف را منتشر می‌کند."""
    received: list[str] = []
    page.coin_activated.connect(received.append)
    page._on_cell_clicked(0, COL_PRICE_USD)
    assert received == [page.table.item(0, COL_SYMBOL).text()]


def test_row_data_returns_raw_row(page: MarketsPage) -> None:
    """دادهٔ خام ردیف برای پر کردن مدال در دسترس است."""
    data = page.row_data("BTC/USDT")
    assert data["price"] == 79000.0
    assert data["volume"] == 1200.0


def test_row_data_of_unknown_symbol(page: MarketsPage) -> None:
    """نماد ناشناخته باید دیکشنری خالی بدهد، نه خطا."""
    assert page.row_data("NOPE/USDT") == {}


# ---------------------------------------------------------------------------
# مدال جزئیات
# ---------------------------------------------------------------------------
@pytest.fixture()
def dialog() -> CoinDetailDialog:
    """مدال جزئیات با دادهٔ نمونه."""
    translator = Translator()
    translator.set_language("fa")
    return CoinDetailDialog(
        "BTC/USDT",
        {"price": 79000.0, "change_percent": -1.2, "volume": 1200.0, "high": 80000.0},
        translator,
    )


def test_dialog_shows_symbol(dialog: CoinDetailDialog) -> None:
    """نماد در سربرگ پنجره دیده می‌شود."""
    assert dialog.symbol == "BTC/USDT"
    assert "BTC/USDT" in dialog.windowTitle()


def test_dialog_default_timeframe(dialog: CoinDetailDialog) -> None:
    """تایم‌فریم پیش‌فرض ۴ ساعته است."""
    assert dialog.selected_timeframe() == "4h"


def test_dialog_has_all_timeframes(dialog: CoinDetailDialog) -> None:
    """هر ۱۴ تایم‌فریم در دسترس است."""
    assert dialog.timeframe_combo.count() == 14


def test_dialog_analyze_button_emits(dialog: CoinDetailDialog) -> None:
    """دکمهٔ تحلیل، نماد و تایم‌فریم را منتشر می‌کند."""
    received: list[tuple[str, str]] = []
    dialog.analyze_requested.connect(lambda s, t: received.append((s, t)))
    dialog.analyze_button.click()
    assert received == [("BTC/USDT", "4h")]


def test_dialog_signal_button_emits(dialog: CoinDetailDialog) -> None:
    """دکمهٔ تولید سیگنال کار می‌کند."""
    received: list[tuple[str, str]] = []
    dialog.signal_requested.connect(lambda s, t: received.append((s, t)))
    dialog.signal_button.click()
    assert received == [("BTC/USDT", "4h")]


def test_dialog_respects_selected_timeframe(dialog: CoinDetailDialog) -> None:
    """اگر کاربر تایم‌فریم را عوض کند، همان منتشر می‌شود."""
    index = dialog.timeframe_combo.findData("1d")
    dialog.timeframe_combo.setCurrentIndex(index)
    received: list[tuple[str, str]] = []
    dialog.signal_requested.connect(lambda s, t: received.append((s, t)))
    dialog.signal_button.click()
    assert received == [("BTC/USDT", "1d")]


def test_dialog_chat_and_market_buttons(dialog: CoinDetailDialog) -> None:
    """دکمه‌های گفت‌وگو و نمایش در بازارها سیگنال می‌دهند."""
    chats: list[str] = []
    markets: list[str] = []
    dialog.chat_requested.connect(lambda s, _t: chats.append(s))
    dialog.open_market_requested.connect(markets.append)
    dialog.chat_button.click()
    dialog.market_button.click()
    assert chats == ["BTC/USDT"]
    assert markets == ["BTC/USDT"]


def test_dialog_watchlist_toggles(dialog: CoinDetailDialog) -> None:
    """دکمهٔ واچ‌لیست وضعیت را عوض و منتشر می‌کند."""
    events: list[tuple[str, bool]] = []
    dialog.watchlist_toggled.connect(lambda s, added: events.append((s, added)))
    dialog.watchlist_button.click()
    assert events == [("BTC/USDT", True)]
    dialog.watchlist_button.click()
    assert events[-1] == ("BTC/USDT", False)


def test_dialog_apply_details(dialog: CoinDetailDialog) -> None:
    """جزئیات فنی پس از دریافت نمایش داده می‌شوند."""
    dialog.apply_details({"trend": "صعودی", "rsi": "۶۲"})
    assert set(dialog._detail_rows) == {"trend", "rsi"}


def test_dialog_details_error_keeps_window_usable(dialog: CoinDetailDialog) -> None:
    """اگر دریافت جزئیات شکست بخورد، پیام نشان داده می‌شود."""
    dialog.set_details_error("خطا")
    assert dialog.details_hint.isVisible() or dialog.details_hint.text() == "خطا"


def test_dialog_snapshot_updates_price(dialog: CoinDetailDialog) -> None:
    """دادهٔ تازه قیمت را به‌روز می‌کند."""
    dialog.apply_snapshot({"price": 81000.0, "change_percent": 2.5})
    assert dialog.price_label.text() != "—"


def test_dialog_rtl_layout() -> None:
    """در فارسی چیدمان راست‌به‌چپ است."""
    translator = Translator()
    translator.set_language("fa")
    widget = CoinDetailDialog("BTC/USDT", {}, translator)
    assert widget.layoutDirection() == Qt.LayoutDirection.RightToLeft
