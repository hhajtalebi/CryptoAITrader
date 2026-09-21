"""
آزمون‌های تنظیمات گسترش‌یافته (نسخهٔ ۱.۴).

کاربر گفت: «بخش تنظیمات را گسترش بده که کاربر بتواند تنظیمات بیشتری
انجام دهد و انعطاف سیستم بیشتر باشد».
"""

from __future__ import annotations

import pytest

from app.config.defaults import DEFAULT_SETTINGS
from localization import Translator
from ui.pages.settings_page import SettingsPage

pytestmark = pytest.mark.usefixtures("qt_application")


NEW_KEYS = [
    "ai.signal_mode",
    "ai.narrative_enabled",
    "ai.narrative_language",
    "ai.save_chat_history",
    "ai.chat_history_limit",
    "signals.ai_timeout",
    "ui.markets_sort",
    "ui.font_scale",
    "ui.compact_mode",
    "ui.confirm_actions",
    "ui.show_toman",
    "performance.parallel_requests",
    "performance.candle_cache_ttl",
    "performance.dashboard_refresh_seconds",
    "performance.markets_refresh_seconds",
    "performance.http_timeout",
    "performance.max_retries",
]


@pytest.fixture()
def page() -> SettingsPage:
    """صفحهٔ تنظیمات فارسی."""
    translator = Translator()
    translator.set_language("fa")
    return SettingsPage(translator)


# ---------------------------------------------------------------------------
# پیش‌فرض‌ها
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("key", NEW_KEYS)
def test_new_setting_has_default(key: str) -> None:
    """هر کلید تازه باید پیش‌فرض داشته باشد وگرنه برنامه هنگام خواندن می‌شکند."""
    assert key in DEFAULT_SETTINGS


def test_default_signal_mode_is_hybrid() -> None:
    """حالت پیش‌فرض سیگنال «ترکیبی» است؛ موتور همیشه جواب می‌دهد."""
    assert DEFAULT_SETTINGS["ai.signal_mode"] == "hybrid"


def test_default_markets_sort_is_value() -> None:
    """بازارها به‌طور پیش‌فرض بر پایهٔ ارزش مرتب می‌شوند."""
    assert DEFAULT_SETTINGS["ui.markets_sort"] == "value"


def test_narrative_enabled_by_default() -> None:
    """تحلیل نوشتاری فارسی پیش‌فرض روشن است."""
    assert DEFAULT_SETTINGS["ai.narrative_enabled"] is True


def test_chat_history_saved_by_default() -> None:
    """تاریخچهٔ چت پیش‌فرض ذخیره می‌شود."""
    assert DEFAULT_SETTINGS["ai.save_chat_history"] is True


# ---------------------------------------------------------------------------
# ساختار صفحه
# ---------------------------------------------------------------------------
def test_page_has_eight_tabs(page: SettingsPage) -> None:
    """
    هر زبانهٔ اعلام‌شده باید ساخته شود.

    شمارش ثابت اینجا شکننده بود؛ افزودن زبانهٔ «امنیت» آن را شکست. حالا
    تعداد از خود فهرست کلیدها خوانده می‌شود تا آزمون، جاافتادنِ زبانه را
    بگیرد ولی افزودن زبانهٔ تازه را جریمه نکند.
    """
    assert page.tabs.count() == len(SettingsPage.TAB_KEYS)
    assert page.tabs.count() >= 8


def test_appearance_tab_exists_with_theme_cards(page: SettingsPage) -> None:
    """انتخاب پوسته باید بخش اختصاصی خودش را داشته باشد، نه ته زبانهٔ عمومی."""
    titles = [page.tabs.tabText(i) for i in range(page.tabs.count())]
    assert any("ظاهر" in t or "Appearance" in t for t in titles)
    # هر پوستهٔ موجود در کاتالوگ باید کارت انتخاب داشته باشد. این را از
    # خود کاتالوگ می‌خوانیم تا افزودن پوستهٔ تازه، آزمون را نشکند ولی
    # جاافتادن کارت را همچنان بگیرد.
    from ui.themes import THEME_CATALOG

    assert set(page._theme_cards) == set(THEME_CATALOG)


def test_selecting_theme_card_emits_live_preview(page: SettingsPage) -> None:
    """کلیک روی کارت باید فوراً درخواست تعویض بدهد (بدون فشردن «ذخیره»)."""
    seen: list[str] = []
    page.theme_preview_requested.connect(seen.append)
    page._theme_cards["corporate_navy"].selected.emit("corporate_navy")
    assert seen == ["corporate_navy"]


def test_tab_titles_are_translated(page: SettingsPage) -> None:
    """هیچ عنوان زبانه‌ای نباید کلید خام یا خالی باشد."""
    for index in range(page.tabs.count()):
        title = page.tabs.tabText(index)
        assert title.strip()
        assert "settings." not in title


def test_tab_titles_change_with_language(page: SettingsPage) -> None:
    """تغییر زبان عنوان زبانه‌ها را عوض می‌کند."""
    before = [page.tabs.tabText(i) for i in range(page.tabs.count())]
    page.tr_.set_language("en")
    page.retranslate()
    after = [page.tabs.tabText(i) for i in range(page.tabs.count())]
    assert before != after
    assert all(title.strip() for title in after)


def test_signal_mode_combo_has_three_modes(page: SettingsPage) -> None:
    """سه حالت تولید سیگنال در دسترس است."""
    modes = {page.signal_mode_combo.itemData(i) for i in range(page.signal_mode_combo.count())}
    assert modes == {"hybrid", "ai_only", "engine"}


def test_markets_sort_combo_matches_markets_page(page: SettingsPage) -> None:
    """حالت‌های مرتب‌سازی تنظیمات با صفحهٔ بازارها یکی است."""
    from ui.pages.markets_page import SORT_MODES

    modes = {page.markets_sort_combo.itemData(i) for i in range(page.markets_sort_combo.count())}
    assert modes == {mode for mode, _key in SORT_MODES}


def test_font_scale_range(page: SettingsPage) -> None:
    """اندازهٔ قلم بین ۸۰ تا ۱۶۰ درصد محدود است."""
    assert page.font_scale_spin.minimum() == 80
    assert page.font_scale_spin.maximum() == 160


def test_refresh_interval_has_sane_minimum(page: SettingsPage) -> None:
    """
    فاصلهٔ تازه‌سازی نباید صفر یا خیلی کم باشد.

    عدد کوچک یعنی بمباران درخواست به صرافی و محدود شدن حساب کاربر.
    """
    assert page.dashboard_interval_spin.minimum() >= 5
    assert page.markets_interval_spin.minimum() >= 5


def test_parallel_requests_bounded(page: SettingsPage) -> None:
    """تعداد درخواست هم‌زمان کران دارد."""
    assert page.parallel_spin.minimum() >= 1
    assert page.parallel_spin.maximum() <= 32


# ---------------------------------------------------------------------------
# رفت و برگشت مقادیر
# ---------------------------------------------------------------------------
def test_round_trip_of_new_keys(page: SettingsPage) -> None:
    """
    هر چه بارگذاری شد باید دقیقاً همان جمع‌آوری شود.

    این آزمون از اشکال کلاسیک «تنظیم ذخیره می‌شود ولی موقع باز کردن
    دوباره پیش‌فرض نشان داده می‌شود» جلوگیری می‌کند.
    """
    values = {
        "ai.signal_mode": "ai_only",
        "ai.narrative_enabled": False,
        "ai.save_chat_history": False,
        "signals.ai_timeout": 90,
        "ui.markets_sort": "gainers",
        "ui.font_scale": 130,
        "ui.compact_mode": True,
        "ui.confirm_actions": False,
        "ui.show_toman": False,
        "performance.parallel_requests": 12,
        "performance.dashboard_refresh_seconds": 45,
        "performance.markets_refresh_seconds": 60,
        "performance.http_timeout": 25,
        "performance.max_retries": 5,
    }
    page.load_values(values)
    collected = page.collect_values()
    for key, expected in values.items():
        assert collected[key] == expected, key


def test_collect_covers_all_new_keys(page: SettingsPage) -> None:
    """همهٔ کلیدهای تازه در خروجی ذخیره حاضرند."""
    collected = page.collect_values()
    missing = [key for key in NEW_KEYS if key not in collected and key != "ai.narrative_language"]
    assert missing == [], f"missing from collect_values: {missing}"


def test_load_with_missing_keys_uses_defaults(page: SettingsPage) -> None:
    """اگر تنظیمی در پایگاه داده نباشد، صفحه نباید بشکند."""
    page.load_values({})
    collected = page.collect_values()
    assert collected["ui.markets_sort"] in {mode for mode, _ in __import__(
        "ui.pages.markets_page", fromlist=["SORT_MODES"]
    ).SORT_MODES}


def test_load_with_unknown_sort_mode_is_safe(page: SettingsPage) -> None:
    """مقدار نامعتبر در پایگاه داده نباید صفحه را خراب کند."""
    page.load_values({"ui.markets_sort": "nonsense", "ai.signal_mode": "nonsense"})
    assert page.collect_values()["ui.markets_sort"] in {"value", "volume", "gainers", "losers", "price_desc", "price_asc", "name"}


def test_boolean_settings_round_trip_true(page: SettingsPage) -> None:
    """گزینه‌های بله/خیر در حالت روشن هم درست ذخیره می‌شوند."""
    page.load_values({"ui.compact_mode": True, "ui.confirm_actions": True, "ui.show_toman": True})
    collected = page.collect_values()
    assert collected["ui.compact_mode"] is True
    assert collected["ui.confirm_actions"] is True
    assert collected["ui.show_toman"] is True


# ---------------------------------------------------------------------------
# بومی‌سازی
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key",
    [
        "settings.display",
        "settings.performance",
        "settings.markets_sort",
        "settings.font_scale",
        "settings.compact_mode",
        "settings.confirm_actions",
        "settings.show_toman",
        "settings.signal_mode",
        "settings.mode_hybrid",
        "settings.mode_ai_only",
        "settings.mode_engine",
        "settings.narrative_enabled",
        "settings.signal_ai_timeout",
        "settings.save_chat_history",
        "settings.parallel_requests",
        "settings.dashboard_interval",
        "settings.markets_interval",
        "settings.http_timeout",
        "settings.max_retries",
    ],
)
@pytest.mark.parametrize("language", ["fa", "en"])
def test_new_translation_keys_exist(key: str, language: str) -> None:
    """
    هر رشتهٔ تازهٔ رابط کاربری در هر دو زبان ترجمه دارد.

    قانون پروژه: هیچ متن سخت‌کدشده‌ای در رابط کاربری نباشد.
    """
    translator = Translator()
    translator.set_language(language)
    value = translator.tr(key)
    assert value and value != key, f"missing {key} in {language}"
