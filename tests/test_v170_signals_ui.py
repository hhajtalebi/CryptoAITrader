"""
آزمون‌های رابط کاربری نسخهٔ ۱٫۷٫۰.

پوشش:
    * بخش «پویش همهٔ نمادها» در صفحهٔ سیگنال
    * رنگ‌آمیزی جدول‌ها بر پایهٔ پوستهٔ فعال
    * شبکهٔ رسپانسیو کارت‌های پوسته (۴ ستون بزرگ / ۲ ستون کوچک)
    * وسط‌چین‌بودن ورودی‌های عددی
"""

from __future__ import annotations

import pytest

from localization import Translator
from ui.pages.signals_page import SignalsPage
from ui.signal_grading import confidence_grade, direction_grade
from ui.themes.catalog import THEME_CATALOG


@pytest.fixture()
def signals_page(qt_application):
    """یک صفحهٔ سیگنال با پوستهٔ تیره اعمال‌شده."""
    page = SignalsPage(Translator("fa"))
    page.apply_theme(THEME_CATALOG["glass_dark"])
    return page


SCAN_ROWS = [
    {"symbol": "BTC/USDT", "direction": "LONG", "confidence": 72, "risk_reward": 2.8,
     "leverage": 3, "risk": {"stop_distance_percent": 1.8}},
    {"symbol": "ETH/USDT", "direction": "SHORT", "confidence": 55, "risk_reward": 1.6,
     "leverage": 8, "risk": {"stop_distance_percent": 4.0}},
    {"symbol": "SOL/USDT", "direction": "LONG", "confidence": 41, "risk_reward": 1.2,
     "leverage": 15, "risk": {"stop_distance_percent": 7.5}},
    {"symbol": "XRP/USDT", "direction": "WAIT", "confidence": 18, "risk_reward": None,
     "leverage": 1, "risk": {}},
]


# ---------------------------------------------------------------------------
# بخش پویش
# ---------------------------------------------------------------------------
def test_scan_button_exists_and_emits(signals_page) -> None:
    """دکمهٔ پویش باید وجود داشته باشد و سیگنال بدهد."""
    fired: list[bool] = []
    signals_page.scan_requested.connect(lambda: fired.append(True))
    signals_page.scan_button.click()
    assert fired == [True]


def test_scan_options_are_read_from_the_page(signals_page) -> None:
    """گزینه‌های پویش باید از خود صفحه خوانده شوند، نه حدس زده شوند."""
    signals_page.scan_limit_spin.setValue(120)
    signals_page.scan_confidence_spin.setValue(65)
    signals_page.scan_wait_check.setChecked(True)

    assert signals_page.scan_options() == {
        "limit": 120,
        "min_confidence": 65,
        "include_wait": True,
    }


def test_default_minimum_confidence_matches_the_green_threshold(signals_page) -> None:
    """پیش‌فرض فیلتر باید همان مرزی باشد که رنگ سبز از آن شروع می‌شود."""
    from ui.signal_grading import CONFIDENCE_GOOD

    assert signals_page.scan_confidence_spin.value() == CONFIDENCE_GOOD


def test_scanning_state_locks_controls_and_shows_stop(signals_page) -> None:
    """
    هنگام پویش، گزینه‌ها قفل و دکمهٔ توقف نمایان می‌شود.

    دکمهٔ توقفِ همیشه‌روی‌صفحه ولی غیرفعال، کاربر را گیج می‌کند؛ پس
    فقط در حالت پویش دیده می‌شود.
    """
    signals_page.set_scanning(True)
    assert not signals_page.scan_button.isEnabled()
    assert not signals_page.scan_limit_spin.isEnabled()
    assert not signals_page.scan_wait_check.isEnabled()

    signals_page.set_scanning(False)
    assert signals_page.scan_button.isEnabled()
    assert signals_page.scan_limit_spin.isEnabled()


def test_scan_progress_updates_bar_and_status(signals_page) -> None:
    """پیشرفت باید هم روی نوار و هم در متن دیده شود."""
    signals_page.set_scanning(True)
    signals_page.set_scan_progress(12, 60, "BTC/USDT", 4)

    assert signals_page.scan_progress.value() == 12
    assert signals_page.scan_progress.maximum() == 60
    assert "BTC/USDT" in signals_page.scan_status.text()


def test_scan_results_are_displayed_in_given_order(signals_page) -> None:
    """
    ردیف نخست باید بالاترین ضریب اطمینان باشد.

    مرتب‌سازی در پویشگر انجام می‌شود؛ صفحه نباید دوباره مرتب کند یا
    ترتیب را به‌هم بزند.
    """
    signals_page.set_scan_results(SCAN_ROWS)

    assert signals_page.scan_table.rowCount() == 4
    assert signals_page.scan_table.item(0, 1).text() == "BTC/USDT"
    assert signals_page.scan_table.item(0, 0).text() == "1"


def test_high_confidence_rows_are_green_and_bold(signals_page) -> None:
    """خواستهٔ صریح کاربر: ۶۰ به بالا سبز و با علامت."""
    signals_page.set_scan_results(SCAN_ROWS)
    theme = THEME_CATALOG["glass_dark"]

    strong = signals_page.scan_table.item(0, 3)  # 72%
    assert strong.foreground().color().name() == theme.colors.success
    assert strong.font().bold()
    assert confidence_grade(72).mark in strong.text()


def test_confidence_fifty_five_is_also_green(signals_page) -> None:
    """کاربر گفت «از ۵۰ یا ۶۰ به بالا» — پس ۵۵ هم باید سبز باشد."""
    signals_page.set_scan_results(SCAN_ROWS)
    theme = THEME_CATALOG["glass_dark"]

    good = signals_page.scan_table.item(1, 3)  # 55%
    assert good.foreground().color().name() == theme.colors.success


def test_mid_confidence_is_amber_not_green(signals_page) -> None:
    """۴۱٪ نباید سبز دیده شود وگرنه مرز ۵۰ بی‌معنا می‌شد."""
    signals_page.set_scan_results(SCAN_ROWS)
    theme = THEME_CATALOG["glass_dark"]

    fair = signals_page.scan_table.item(2, 3)  # 41%
    assert fair.foreground().color().name() == theme.colors.warning
    assert fair.foreground().color().name() != theme.colors.success


def test_risk_column_uses_three_distinct_colours(signals_page) -> None:
    """ریسک کم سبز، متوسط کهربایی، زیاد قرمز."""
    signals_page.set_scan_results(SCAN_ROWS)
    theme = THEME_CATALOG["glass_dark"]

    assert signals_page.scan_table.item(0, 4).foreground().color().name() == theme.colors.success
    assert signals_page.scan_table.item(1, 4).foreground().color().name() == theme.colors.warning
    assert signals_page.scan_table.item(2, 4).foreground().color().name() == theme.colors.danger


def test_wait_row_has_its_own_colour(signals_page) -> None:
    """«انتظار» نه سبز است نه قرمز — کاربر «رنگ مناسب» خواست."""
    signals_page.set_scan_results(SCAN_ROWS)
    theme = THEME_CATALOG["glass_dark"]

    wait_cell = signals_page.scan_table.item(3, 2)
    colour = wait_cell.foreground().color().name()
    assert colour not in {theme.colors.success, theme.colors.danger}
    assert colour == theme.colors.info
    assert direction_grade("WAIT").mark in wait_cell.text()


def test_colours_follow_the_active_theme(signals_page) -> None:
    """
    رنگ‌ها از توکن پوسته می‌آیند، نه از مقدار ثابت.

    این تضمین می‌کند درجه‌بندی در هر هشت پوسته درست دیده شود، نه فقط
    در پوستهٔ تیره.
    """
    signals_page.set_scan_results(SCAN_ROWS)
    dark_colour = signals_page.scan_table.item(0, 3).foreground().color().name()

    signals_page.apply_theme(THEME_CATALOG["minimal_light"])
    light_colour = signals_page.scan_table.item(0, 3).foreground().color().name()

    assert dark_colour == THEME_CATALOG["glass_dark"].colors.success
    assert light_colour == THEME_CATALOG["minimal_light"].colors.success


def test_ai_analysis_button_emits_symbol(signals_page) -> None:
    """
    هر ردیف دکمهٔ تحلیل هوشمند جداگانه دارد.

    این همان «بعداً هرکدام را که خواستم جداگانه بدهم هوش مصنوعی تحلیل
    کند» است.
    """
    signals_page.set_scan_results(SCAN_ROWS)
    captured: list[str] = []
    signals_page.scan_ai_requested.connect(captured.append)

    # شمارهٔ ستون ثابت نوشته نمی‌شود: هر بار جدول ستون تازه‌ای گرفت،
    # آزمون‌های با عدد خام شکستند. ثابت نام‌دار خودش جابه‌جا می‌شود.
    signals_page.scan_table.cellWidget(1, SignalsPage.SCAN_COL_ACTION).click()
    assert captured == ["ETH/USDT"]


def test_history_table_uses_the_same_colour_language(signals_page) -> None:
    """کاربر گفت «به همین ترتیب» — سابقه هم باید همان رنگ‌ها را بگیرد."""
    signals_page.set_history([
        {"id": 1, "created_at": "2026-01-01", "symbol": "BTC/USDT", "direction": "LONG",
         "confidence": 70, "risk_reward": 2.5, "leverage": 3},
    ])
    theme = THEME_CATALOG["glass_dark"]
    assert signals_page.history_table.item(0, 3).foreground().color().name() == theme.colors.success


def test_scan_rows_survive_language_change(signals_page) -> None:
    """تغییر زبان نباید نتیجهٔ پویش را پاک کند."""
    signals_page.set_scan_results(SCAN_ROWS)
    signals_page.tr_.set_language("en")
    signals_page.retranslate()

    assert signals_page.scan_table.rowCount() == 4
    assert signals_page.scan_button.text() == "Scan all symbols"


# ---------------------------------------------------------------------------
# شبکهٔ رسپانسیو
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("width", "expected"),
    [(280, 2), (400, 2), (520, 3), (700, 4), (1200, 4)],
)
def test_theme_grid_column_count_is_responsive(qt_application, width, expected) -> None:
    """
    کاربر خواست «در حالت بزرگ چهارتا و در کوچک‌ترین حالت ۲ تا».

    پیش‌تر شبکه همیشه دو ستون بود و در پنجرهٔ بزرگ نیمی از عرض هدر
    می‌رفت.
    """
    from PySide6.QtWidgets import QLabel

    from ui.widgets.responsive_grid import ResponsiveGrid

    grid = ResponsiveGrid(min_columns=2, max_columns=4, item_min_width=150, spacing=10)
    grid.set_widgets([QLabel(f"c{i}") for i in range(8)])
    assert grid.columns_for_width(width) == expected


def test_theme_grid_never_drops_below_two_columns(qt_application) -> None:
    """حتی در باریک‌ترین حالت هم دو کارت کنار هم می‌مانند."""
    from PySide6.QtWidgets import QLabel

    from ui.widgets.responsive_grid import ResponsiveGrid

    grid = ResponsiveGrid(min_columns=2, max_columns=4, item_min_width=150)
    grid.set_widgets([QLabel("a"), QLabel("b")])
    assert grid.columns_for_width(10) == 2
    assert grid.columns_for_width(0) == 2


def test_theme_grid_keeps_all_items_after_relayout(qt_application) -> None:
    """بازچینش نباید هیچ کارتی را گم کند."""
    from PySide6.QtWidgets import QLabel

    from ui.widgets.responsive_grid import ResponsiveGrid

    grid = ResponsiveGrid(min_columns=2, max_columns=4, item_min_width=150)
    labels = [QLabel(f"c{i}") for i in range(7)]
    grid.set_widgets(labels)
    grid.resize(1200, 400)
    grid.resize(300, 800)

    assert len(grid.items()) == 7
    assert all(label.parent() is grid for label in labels)


def test_theme_cards_keep_an_aspect_ratio(qt_application) -> None:
    """
    کارت‌ها باید به مربع نزدیک بمانند.

    کاربر گفت «سعی بر مربعی بودن باشه یعنی رسپانسیو حفظ بشه»: ارتفاع
    از عرض پیروی می‌کند، پس در هر شمار ستونی نسبت حفظ می‌شود.
    """
    from ui.widgets.theme_card import ThemeSwatch

    swatch = ThemeSwatch(THEME_CATALOG["glass_dark"])
    assert swatch.hasHeightForWidth()
    # مینیاتور پهن‌تر از مربع است (یک پنجره را نشان می‌دهد) ولی با نام
    # زیرش، خودِ کارت به مربع نزدیک می‌شود.
    ratio = swatch.heightForWidth(200) / 200
    assert 0.4 <= ratio <= 0.65
    assert swatch.heightForWidth(100) < swatch.heightForWidth(200)


def test_theme_cards_have_a_width_cap(qt_application) -> None:
    """
    کارت‌ها نباید تمام عرض پنجره را بین خود پخش کنند.

    بدون سقف عرض، در پنجرهٔ عریض هر کارت پهن و کم‌ارتفاع می‌شد — همان
    «پالت بزرگ» که کاربر از آن گله داشت.
    """
    from ui.pages.settings_page import SettingsPage

    page = SettingsPage(Translator("fa"))
    card = next(iter(page._theme_cards.values()))  # noqa: SLF001 - آزمون داخلی
    assert card.maximumWidth() <= 220
    assert card.minimumWidth() <= 150


def test_settings_theme_grid_holds_every_theme(qt_application) -> None:
    """همهٔ پوسته‌ها — از جمله پوستهٔ تازه — باید کارت داشته باشند."""
    from ui.pages.settings_page import SettingsPage

    page = SettingsPage(Translator("fa"))
    assert set(page._theme_cards) == set(THEME_CATALOG)  # noqa: SLF001 - آزمون داخلی
    assert page.theme_grid.column_count() >= 2


# ---------------------------------------------------------------------------
# ورودی‌های عددی
# ---------------------------------------------------------------------------
def test_numeric_inputs_are_centred(qt_application) -> None:
    """
    کاربر گفت «مقدار را در این پوت‌های عددی سنتر کن».

    در چیدمان راست‌به‌چپ، عدد به لبه می‌چسبید و با فلش‌ها تداخل
    می‌کرد.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QAbstractSpinBox

    from ui.pages.settings_page import SettingsPage

    page = SettingsPage(Translator("fa"))
    boxes = page.findChildren(QAbstractSpinBox)
    assert boxes, "صفحهٔ تنظیمات باید ورودی عددی داشته باشد"
    for box in boxes:
        assert box.alignment() & Qt.AlignmentFlag.AlignHCenter, box.objectName()


def test_font_scale_has_a_slider_and_stays_in_sync(qt_application) -> None:
    """
    اندازهٔ متن با اسلایدر تنظیم می‌شود و عدد کنارش همگام می‌ماند.

    کاربر این ورودی را «خراب» خواند: رسیدن از ۱۰۰ به ۱۴۰ با فلش‌های
    ریز هشت کلیک می‌خواست.
    """
    from ui.pages.settings_page import SettingsPage

    page = SettingsPage(Translator("fa"))
    emitted: list[int] = []
    page.font_scale_changed.connect(emitted.append)

    page.font_scale_slider.setValue(130)
    assert page.font_scale_spin.value() == 130
    assert emitted[-1] == 130

    page.font_scale_spin.setValue(95)
    assert page.font_scale_slider.value() == 95
    assert emitted[-1] == 95


def test_font_scale_sync_does_not_loop_forever(qt_application) -> None:
    """
    دو کنترل به یک متد وصل‌اند؛ بدون `blockSignals` بی‌پایان
    یکدیگر را صدا می‌زدند.
    """
    from ui.pages.settings_page import SettingsPage

    page = SettingsPage(Translator("fa"))
    emitted: list[int] = []
    page.font_scale_changed.connect(emitted.append)

    page.font_scale_slider.setValue(120)
    # یک تغییر = دقیقاً یک اعلام، نه دو تا و نه بی‌نهایت
    assert emitted == [120]
