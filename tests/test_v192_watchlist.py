"""
آزمون فهرست‌های دیده‌بانی چندگانه (مورد ۵.۳ نقشهٔ راه).

پیش از این نسخه، برنامه فقط یک فهرست ثابت به نام «default» داشت و هیچ
راهی برای مرتب‌کردن دستی آن نبود. این آزمون‌ها روی چیزهایی تمرکز دارند
که اگر بشکنند کاربر **داده از دست می‌دهد** یا ترتیبی که خودش چیده به‌هم
می‌ریزد:

    • فهرست «پیش‌فرض» هرگز نباید حذف شود، فقط خالی شود
    • تغییر نام روی نام تکراری نباید بی‌صدا دو فهرست را ادغام کند
    • ترتیب دستی باید پایدار بماند و شماره‌ها پشت سر هم باشند
    • جابه‌جایی در دو سر فهرست نباید از محدوده بیرون بزند
    • رابط قدیمی (`get_watchlist`) باید دست‌نخورده کار کند
"""

from __future__ import annotations

import pytest

from app.core.models import SymbolInfo
from app.database.repositories.symbol_repository import (
    DEFAULT_LIST,
    SymbolRepository,
)
from localization import Translator

EXCHANGE = "lbank"
SYMBOLS = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT")


def make_symbols() -> list[SymbolInfo]:
    """چند نماد نمونه برای پر کردن جدول نمادها."""
    return [
        SymbolInfo(
            symbol=symbol,
            exchange_symbol=symbol.replace("/", "_").lower(),
            base_asset=symbol.split("/")[0],
            quote_asset="USDT",
        )
        for symbol in SYMBOLS
    ]


@pytest.fixture()
def repo(database):  # noqa: ANN001, ANN201
    """مخزن نمادها با نمادهای همگام‌شده روی پایگاه دادهٔ موقت."""
    repository = SymbolRepository(database)
    repository.sync_symbols(EXCHANGE, make_symbols())
    return repository


@pytest.fixture()
def filled(repo):  # noqa: ANN001, ANN201
    """مخزنی که سه نماد در فهرست پیش‌فرض دارد."""
    for symbol in SYMBOLS[:3]:
        repo.add_to_watchlist(symbol, EXCHANGE)
    return repo


# ---------------------------------------------------------------------------
# نام‌ها و شمارش
# ---------------------------------------------------------------------------


def test_names_empty_database_still_offers_default(repo: SymbolRepository) -> None:
    """حتی با پایگاه دادهٔ خالی، فهرست پیش‌فرض باید وجود داشته باشد."""
    assert repo.watchlist_names() == [DEFAULT_LIST]


def test_default_list_is_always_first(filled: SymbolRepository) -> None:
    """پیش‌فرض همیشه اول است، بقیه الفبایی."""
    filled.add_to_watchlist("XRP/USDT", EXCHANGE, list_name="زد")
    filled.add_to_watchlist("DOGE/USDT", EXCHANGE, list_name="الف")
    names = filled.watchlist_names()
    assert names[0] == DEFAULT_LIST
    assert names[1:] == sorted(names[1:])


def test_counts_are_per_list(filled: SymbolRepository) -> None:
    """شمارش هر فهرست جدا محاسبه می‌شود."""
    filled.add_to_watchlist("XRP/USDT", EXCHANGE, list_name="آلت")
    counts = filled.watchlist_counts()
    assert counts[DEFAULT_LIST] == 3
    assert counts["آلت"] == 1


def test_same_symbol_can_live_in_two_lists(filled: SymbolRepository) -> None:
    """یک نماد می‌تواند هم‌زمان در چند فهرست باشد."""
    filled.add_to_watchlist("BTC/USDT", EXCHANGE, list_name="بلندمدت")
    assert sorted(filled.find_symbol_lists("BTC/USDT", EXCHANGE)) == sorted(
        [DEFAULT_LIST, "بلندمدت"]
    )


# ---------------------------------------------------------------------------
# ساخت، تغییر نام و حذف
# ---------------------------------------------------------------------------


def test_create_rejects_blank_name(repo: SymbolRepository) -> None:
    """نام خالی یا فاصله‌ای پذیرفته نمی‌شود."""
    assert repo.create_watchlist("") is False
    assert repo.create_watchlist("   ") is False


def test_create_rejects_duplicate(filled: SymbolRepository) -> None:
    """نام تکراری رد می‌شود تا فهرست موجود پاک نشود."""
    assert filled.create_watchlist(DEFAULT_LIST) is False


def test_rename_moves_every_member(filled: SymbolRepository) -> None:
    """تغییر نام همهٔ اعضا را با خود می‌برد."""
    filled.add_to_watchlist("XRP/USDT", EXCHANGE, list_name="قدیم")
    assert filled.rename_watchlist("قدیم", "جدید") is True
    assert "قدیم" not in filled.watchlist_names()
    assert [row["symbol"] for row in filled.watchlist_details("جدید")] == ["XRP/USDT"]


def test_rename_onto_existing_name_is_refused(filled: SymbolRepository) -> None:
    """
    ادغام خاموش ممنوع است.

    اگر «الف» را به «ب» تغییر نام دهیم و «ب» از قبل باشد، کاربر انتظار
    ادغام ندارد؛ رد کردن امن‌تر از قاطی کردن دو فهرست است.
    """
    filled.add_to_watchlist("XRP/USDT", EXCHANGE, list_name="الف")
    filled.add_to_watchlist("DOGE/USDT", EXCHANGE, list_name="ب")
    assert filled.rename_watchlist("الف", "ب") is False
    assert [row["symbol"] for row in filled.watchlist_details("ب")] == ["DOGE/USDT"]


def test_default_list_cannot_be_renamed(filled: SymbolRepository) -> None:
    """فهرست پیش‌فرض نام ثابتی دارد."""
    assert filled.rename_watchlist(DEFAULT_LIST, "هرچیز") is False


def test_delete_removes_named_list(filled: SymbolRepository) -> None:
    """حذف فهرست نام‌دار، اعضایش را هم برمی‌دارد."""
    filled.add_to_watchlist("XRP/USDT", EXCHANGE, list_name="موقت")
    assert filled.delete_watchlist("موقت") == 1
    assert "موقت" not in filled.watchlist_names()


def test_delete_default_empties_but_keeps_it(filled: SymbolRepository) -> None:
    """پیش‌فرض خالی می‌شود ولی از فهرست نام‌ها بیرون نمی‌رود."""
    assert filled.delete_watchlist(DEFAULT_LIST) == 3
    assert filled.watchlist_names() == [DEFAULT_LIST]
    assert filled.watchlist_details(DEFAULT_LIST) == []


def test_delete_unknown_list_is_harmless(filled: SymbolRepository) -> None:
    """حذف فهرست ناموجود صفر برمی‌گرداند و چیزی را خراب نمی‌کند."""
    assert filled.delete_watchlist("نیست") == 0
    assert len(filled.watchlist_details(DEFAULT_LIST)) == 3


# ---------------------------------------------------------------------------
# ترتیب دستی
# ---------------------------------------------------------------------------


def test_details_are_ordered_by_position(filled: SymbolRepository) -> None:
    """ترتیب خروجی همان ترتیب افزودن است."""
    assert [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)] == list(
        SYMBOLS[:3]
    )


def test_positions_are_contiguous(filled: SymbolRepository) -> None:
    """شماره‌ها باید پشت سر هم باشند نه پرشی."""
    rows = filled.watchlist_details(DEFAULT_LIST)
    positions = [row["position"] for row in rows]
    assert positions == list(range(positions[0], positions[0] + len(rows)))


def test_move_down_swaps_with_next(filled: SymbolRepository) -> None:
    """جابه‌جایی به پایین با عضو بعدی تعویض می‌کند."""
    assert filled.move_in_watchlist(DEFAULT_LIST, "BTC/USDT", 1) is True
    assert [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)] == [
        "ETH/USDT",
        "BTC/USDT",
        "SOL/USDT",
    ]


def test_move_up_swaps_with_previous(filled: SymbolRepository) -> None:
    """جابه‌جایی به بالا با عضو قبلی تعویض می‌کند."""
    assert filled.move_in_watchlist(DEFAULT_LIST, "SOL/USDT", -1) is True
    assert [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)] == [
        "BTC/USDT",
        "SOL/USDT",
        "ETH/USDT",
    ]


def test_move_up_at_top_is_refused(filled: SymbolRepository) -> None:
    """عضو اول جایی بالاتر ندارد."""
    assert filled.move_in_watchlist(DEFAULT_LIST, "BTC/USDT", -1) is False
    assert [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)] == list(
        SYMBOLS[:3]
    )


def test_move_down_at_bottom_is_refused(filled: SymbolRepository) -> None:
    """عضو آخر جایی پایین‌تر ندارد."""
    assert filled.move_in_watchlist(DEFAULT_LIST, "SOL/USDT", 1) is False


def test_move_unknown_symbol_is_refused(filled: SymbolRepository) -> None:
    """نماد بیرون از فهرست جابه‌جا نمی‌شود."""
    assert filled.move_in_watchlist(DEFAULT_LIST, "XRP/USDT", 1) is False


def test_reorder_applies_given_order(filled: SymbolRepository) -> None:
    """ترتیب دلخواه کاربر عیناً ذخیره می‌شود."""
    filled.reorder_watchlist(DEFAULT_LIST, ["SOL/USDT", "BTC/USDT", "ETH/USDT"])
    assert [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)] == [
        "SOL/USDT",
        "BTC/USDT",
        "ETH/USDT",
    ]


def test_reorder_keeps_unlisted_members_at_the_end(filled: SymbolRepository) -> None:
    """
    نمادی که در فهرستِ ترتیب نیامده نباید ناپدید شود.

    این همان جایی است که یک پیاده‌سازی ساده‌انگارانه داده را قربانی
    می‌کند: اگر رابط کاربری فقط ردیف‌های دیده‌شده را بفرستد، بقیه باید
    سر جایشان بمانند، نه اینکه حذف شوند.
    """
    filled.reorder_watchlist(DEFAULT_LIST, ["SOL/USDT"])
    symbols = [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)]
    assert symbols[0] == "SOL/USDT"
    assert set(symbols) == set(SYMBOLS[:3])


def test_removing_middle_member_keeps_order_of_rest(filled: SymbolRepository) -> None:
    """حذف عضو میانی ترتیب بقیه را به‌هم نمی‌ریزد."""
    filled.remove_from_watchlist("ETH/USDT", EXCHANGE)
    assert [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)] == [
        "BTC/USDT",
        "SOL/USDT",
    ]


def test_order_is_independent_per_list(filled: SymbolRepository) -> None:
    """ترتیب هر فهرست مستقل است."""
    for symbol in ("SOL/USDT", "BTC/USDT"):
        filled.add_to_watchlist(symbol, EXCHANGE, list_name="دوم")
    filled.move_in_watchlist("دوم", "SOL/USDT", 1)
    assert [row["symbol"] for row in filled.watchlist_details(DEFAULT_LIST)] == list(
        SYMBOLS[:3]
    )
    assert [row["symbol"] for row in filled.watchlist_details("دوم")] == [
        "BTC/USDT",
        "SOL/USDT",
    ]


# ---------------------------------------------------------------------------
# یادداشت‌ها
# ---------------------------------------------------------------------------


def test_note_round_trips(filled: SymbolRepository) -> None:
    """یادداشت ذخیره و خوانده می‌شود."""
    assert filled.set_watchlist_note("BTC/USDT", EXCHANGE, "منتظر شکست") is True
    rows = {row["symbol"]: row["note"] for row in filled.watchlist_details(DEFAULT_LIST)}
    assert rows["BTC/USDT"] == "منتظر شکست"


def test_note_is_capped(filled: SymbolRepository) -> None:
    """یادداشت بیش از حد بلند بریده می‌شود تا جدول را نترکاند."""
    filled.set_watchlist_note("BTC/USDT", EXCHANGE, "ب" * 900)
    rows = {row["symbol"]: row["note"] for row in filled.watchlist_details(DEFAULT_LIST)}
    assert len(rows["BTC/USDT"]) <= 500


def test_note_on_unknown_member_is_refused(filled: SymbolRepository) -> None:
    """یادداشت روی نمادی که در فهرست نیست ثبت نمی‌شود."""
    assert filled.set_watchlist_note("XRP/USDT", EXCHANGE, "سلام") is False


# ---------------------------------------------------------------------------
# سازگاری با رابط قدیمی
# ---------------------------------------------------------------------------


def test_legacy_get_watchlist_reads_default_list(filled: SymbolRepository) -> None:
    """رفتار نسخه‌های پیشین نباید تغییر کرده باشد."""
    assert set(filled.get_watchlist()) == set(SYMBOLS[:3])


def test_legacy_get_watchlist_ignores_other_lists(filled: SymbolRepository) -> None:
    """
    ستارهٔ صفحهٔ بازارها فقط فهرست پیش‌فرض را نشان می‌دهد.

    اگر این بشکند، کاربر ستارهٔ پر می‌بیند برای نمادی که در فهرست
    پیش‌فرضش نیست و با کلیک، عضویت دیگری را ناخواسته برمی‌دارد.
    """
    filled.add_to_watchlist("XRP/USDT", EXCHANGE, list_name="دیگر")
    assert "XRP/USDT" not in filled.get_watchlist()


def test_duplicate_add_is_idempotent(filled: SymbolRepository) -> None:
    """افزودن دوبارهٔ یک نماد، ردیف تکراری نمی‌سازد."""
    filled.add_to_watchlist("BTC/USDT", EXCHANGE)
    assert len(filled.watchlist_details(DEFAULT_LIST)) == 3


# ---------------------------------------------------------------------------
# ویجت
# ---------------------------------------------------------------------------


@pytest.fixture()
def panel(qt_application):  # noqa: ANN001, ANN201
    """پنل دیده‌بانی با مترجم فارسی."""
    from ui.widgets.watchlist_panel import WatchlistPanel

    return WatchlistPanel(Translator("fa"))


def test_panel_starts_empty(panel) -> None:  # noqa: ANN001
    """بدون داده، جدول خالی و پیام خالی‌بودن دیده می‌شود."""
    assert panel.table.rowCount() == 0
    assert panel.empty_label.isVisibleTo(panel)


def test_panel_lists_carry_counts(panel) -> None:  # noqa: ANN001
    """تعداد اعضا کنار نام فهرست نوشته می‌شود."""
    panel.set_lists([DEFAULT_LIST, "آلت"], {DEFAULT_LIST: 3, "آلت": 1})
    assert panel.list_combo.count() == 2
    assert "۳" in panel.list_combo.itemText(0) or "3" in panel.list_combo.itemText(0)


def test_panel_combo_stores_raw_name_as_data(panel) -> None:
    """
    نام واقعی فهرست در `data` می‌ماند، نه در متن.

    متن شامل شمارش و ترجمه است؛ اگر کد از متن نام را دربیاورد، با
    عوض‌شدن زبان یا تعداد، همه‌چیز می‌شکند.
    """
    panel.set_lists([DEFAULT_LIST, "آلت"], {DEFAULT_LIST: 3, "آلت": 1})
    assert panel.list_combo.itemData(0) == DEFAULT_LIST
    assert panel.list_combo.itemData(1) == "آلت"


def test_panel_rows_match_items(panel) -> None:  # noqa: ANN001
    """هر عضو یک ردیف می‌شود."""
    panel.set_items(
        [
            {"symbol": "BTC/USDT", "note": "یادداشت", "position": 0},
            {"symbol": "ETH/USDT", "note": "", "position": 1},
        ]
    )
    assert panel.table.rowCount() == 2
    assert not panel.empty_label.isVisibleTo(panel)


def test_panel_symbol_cells_are_ltr_marked(panel) -> None:
    """
    نماد باید با نشانهٔ چپ‌به‌راست شروع شود.

    بدون آن، `BTC/USDT` در چیدمان فارسی به شکل `USDT/BTC` دیده می‌شود.
    """
    panel.set_items([{"symbol": "BTC/USDT", "note": "", "position": 0}])
    text = panel.table.item(0, 1).text()
    assert text.startswith("\u200e")
    assert "BTC/USDT" in text


def test_panel_disables_actions_without_selection(panel) -> None:  # noqa: ANN001
    """دکمه‌های ردیفی تا وقتی چیزی انتخاب نشده خاموش‌اند."""
    panel.set_items([{"symbol": "BTC/USDT", "note": "", "position": 0}])
    panel.table.clearSelection()
    panel.table.setCurrentCell(-1, -1)
    for button in (panel.up_button, panel.down_button, panel.remove_button):
        assert button.isEnabled() is False


def test_panel_protects_the_default_list(panel) -> None:  # noqa: ANN001
    """حذف و تغییر نام فهرست پیش‌فرض غیرفعال است."""
    panel.set_lists([DEFAULT_LIST], {DEFAULT_LIST: 1})
    assert panel.delete_button.isEnabled() is False
    assert panel.rename_button.isEnabled() is False


def test_panel_enables_delete_for_named_list(panel) -> None:  # noqa: ANN001
    """برای فهرست نام‌دار، حذف و تغییر نام روشن می‌شود."""
    panel.set_lists([DEFAULT_LIST, "آلت"], {DEFAULT_LIST: 1, "آلت": 2})
    panel.list_combo.setCurrentIndex(1)
    assert panel.delete_button.isEnabled() is True
    assert panel.rename_button.isEnabled() is True


def test_panel_select_symbol_works_in_rtl(panel, qt_application) -> None:
    """
    انتخاب برنامه‌ای باید در چیدمان راست‌به‌چپ هم کار کند.

    ‏`QTableWidget.selectRow` وقتی جهت کل برنامه راست‌به‌چپ است بی‌صدا
    شکست می‌خورد؛ این آزمون همان دام را نگه می‌دارد تا کسی دوباره
    به `selectRow` برنگردد.
    """
    from PySide6.QtCore import Qt

    previous = qt_application.layoutDirection()
    qt_application.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    try:
        panel.set_items(
            [
                {"symbol": "BTC/USDT", "note": "", "position": 0},
                {"symbol": "ETH/USDT", "note": "", "position": 1},
            ]
        )
        assert panel.select_symbol("ETH/USDT") is True
        assert panel.selected_symbol() == "ETH/USDT"
    finally:
        qt_application.setLayoutDirection(previous)


def test_panel_select_unknown_symbol_returns_false(panel) -> None:  # noqa: ANN001
    """نماد ناموجود انتخاب نمی‌شود."""
    panel.set_items([{"symbol": "BTC/USDT", "note": "", "position": 0}])
    assert panel.select_symbol("ETH/USDT") is False


def test_panel_emits_moved_signal(panel, qt_application) -> None:  # noqa: ANN001
    """دکمهٔ پایین، سیگنال جابه‌جایی با علامت درست می‌فرستد."""
    panel.set_lists([DEFAULT_LIST], {DEFAULT_LIST: 2})
    panel.set_items(
        [
            {"symbol": "BTC/USDT", "note": "", "position": 0},
            {"symbol": "ETH/USDT", "note": "", "position": 1},
        ]
    )
    panel.select_symbol("BTC/USDT")
    captured: list[tuple] = []
    panel.symbol_moved.connect(lambda *args: captured.append(args))
    panel.down_button.click()
    assert captured == [(DEFAULT_LIST, "BTC/USDT", 1)]


def test_panel_emits_removed_signal(panel) -> None:  # noqa: ANN001
    """دکمهٔ حذف نماد، سیگنال درست می‌فرستد."""
    panel.set_lists([DEFAULT_LIST], {DEFAULT_LIST: 1})
    panel.set_items([{"symbol": "BTC/USDT", "note": "", "position": 0}])
    panel.select_symbol("BTC/USDT")
    captured: list[tuple] = []
    panel.symbol_removed.connect(lambda *args: captured.append(args))
    panel.remove_button.click()
    assert captured == [(DEFAULT_LIST, "BTC/USDT")]


def test_panel_current_list_defaults_when_empty(panel) -> None:  # noqa: ANN001
    """بدون هیچ فهرستی، نام پیش‌فرض برگردانده می‌شود."""
    assert panel.current_list() == DEFAULT_LIST


def test_panel_retranslate_keeps_selection(panel) -> None:  # noqa: ANN001
    """تغییر زبان نباید فهرست انتخاب‌شده را عوض کند."""
    panel.set_lists([DEFAULT_LIST, "آلت"], {DEFAULT_LIST: 1, "آلت": 2})
    panel.list_combo.setCurrentIndex(1)
    panel.retranslate()
    assert panel.current_list() == "آلت"


# ---------------------------------------------------------------------------
# ترجمه
# ---------------------------------------------------------------------------


WATCHLIST_KEYS = (
    "title",
    "list",
    "new",
    "rename",
    "delete",
    "move_up",
    "move_down",
    "edit_note",
    "remove_symbol",
    "empty",
    "position",
    "note",
    "count",
    "default_name",
    "name_prompt",
    "note_prompt",
)


@pytest.mark.parametrize("language", ["fa", "en"])
@pytest.mark.parametrize("key", WATCHLIST_KEYS)
def test_watchlist_keys_exist(language: str, key: str) -> None:
    """هیچ کلید ترجمه‌ای نباید جا افتاده باشد."""
    translator = Translator(language)
    value = translator.tr(f"watchlist.{key}")
    assert value and value != f"watchlist.{key}"


@pytest.mark.parametrize("language", ["fa", "en"])
def test_markets_tab_keys_exist(language: str) -> None:
    """نام زبانه‌های صفحهٔ بازارها ترجمه دارد."""
    from ui.pages.markets_page import TAB_KEYS

    translator = Translator(language)
    for key in TAB_KEYS:
        assert translator.tr(key) != key


def test_both_languages_share_watchlist_keys() -> None:
    """کلیدهای فارسی و انگلیسی باید یکسان باشند."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "localization"
    fa = json.loads((root / "fa" / "watchlist.json").read_text(encoding="utf-8"))
    en = json.loads((root / "en" / "watchlist.json").read_text(encoding="utf-8"))
    assert set(fa) == set(en)
