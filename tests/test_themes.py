"""
آزمون سامانهٔ پوسته.

نکتهٔ کلیدی که این آزمون‌ها محافظت می‌کنند: **پوسته نباید هیچ قابلیتی را
محدود کند.** همهٔ پوسته‌ها باید برگه سبک معتبر بسازند و همهٔ نقش‌های
ظاهری را پوشش دهند.
"""

from __future__ import annotations

import re

import pytest

from ui.themes import (
    DEFAULT_THEME,
    THEME_CATALOG,
    ThemeManager,
    build_stylesheet,
    get_theme,
    list_themes,
    resolve_key,
)
from ui.themes.tokens import ThemeTokens


def test_catalog_has_all_named_themes() -> None:
    """همهٔ پوسته‌های نام‌دار باید موجود باشند."""
    assert set(THEME_CATALOG) == {
        "glass_dark",
        "gold_dark",
        "carbon_neon",
        "orchid_indigo",
        "royal_silk",
        "midnight_aurora",
        "minimal_light",
        "corporate_navy",
        "violet_light",
    }


def test_default_theme_is_corporate_navy() -> None:
    """
    کاربر خواسته است پوستهٔ پیش‌فرض «سرمه‌ای اداری» باشد.

    این دستور، دستور پیشین («شیشه‌ای تیره») را نسخ می‌کند. پوستهٔ
    شیشه‌ای تیره حذف نشده و همچنان در فهرست انتخاب هست؛ فقط دیگر
    پیش‌فرض نیست.
    """
    assert DEFAULT_THEME == "corporate_navy"
    # مقدار خالی هم باید به همان پیش‌فرض برسد، وگرنه برنامه با یک
    # پوسته بالا می‌آید و با پوستهٔ دیگری رنگ می‌شود.
    assert get_theme(None).key == "corporate_navy"
    # شیشه‌ای تیره حذف نشده؛ فقط دیگر پیش‌فرض نیست.
    assert get_theme("glass_dark").is_dark is True


def test_every_theme_has_a_name_in_both_languages() -> None:
    """هر پوسته باید نام فارسی و انگلیسی داشته باشد تا در تنظیمات دیده شود."""
    for theme in list_themes():
        assert theme.name_fa.strip()
        assert theme.name_en.strip()


@pytest.mark.parametrize("key", sorted(THEME_CATALOG))
def test_stylesheet_builds_without_leftover_placeholders(key: str) -> None:
    """
    برگه سبک هر پوسته باید کامل ساخته شود.

    اگر توکنی جا بماند، رشتهٔ `{name}` در خروجی باقی می‌ماند و آن قاعده
    در Qt بی‌اثر می‌شود — دقیقاً همان اشکالی که دیدنش سخت است.
    """
    qss = build_stylesheet(get_theme(key))
    assert len(qss) > 5000
    leftovers = re.findall(r"\{[a-z_]+\}", qss)
    assert not leftovers, f"placeholder باقی‌مانده در پوستهٔ {key}: {leftovers}"


@pytest.mark.parametrize("key", sorted(THEME_CATALOG))
def test_stylesheet_covers_all_component_roles(key: str) -> None:
    """
    همهٔ نقش‌های مشترک باید در هر پوسته تعریف شده باشند.

    این آزمون تضمین می‌کند افزودن پوستهٔ تازه بدون پوشش یک مؤلفه (مثلاً
    جدول یا زبانه) از قلم نیفتد.
    """
    qss = build_stylesheet(get_theme(key))
    required = [
        "QPushButton",
        'QPushButton[role="primary"]',
        'QPushButton[role="nav"]',
        'QPushButton[role="chip"]',
        'QPushButton[role="segment"]',
        "QLineEdit",
        "QComboBox",
        "QCheckBox",
        "QTableWidget",
        "QHeaderView::section",
        "QTabBar::tab",
        "QScrollBar:vertical",
        "QProgressBar",
        "QStatusBar",
        "QMenu",
        'QFrame[role="card"]',
        'QFrame[role="sidebar"]',
        'QFrame[role="topbar"]',
        'QFrame[role="chat_user"]',
        'QFrame[role="chat_ai"]',
        "QToolTip",
    ]
    missing = [item for item in required if item not in qss]
    assert not missing, f"نقش‌های پوشش‌داده‌نشده در {key}: {missing}"


def test_legacy_theme_names_still_resolve() -> None:
    """تنظیم ذخیره‌شدهٔ کاربران نسخه‌های پیشین نباید بشکند."""
    assert resolve_key("dark") == "glass_dark"
    assert resolve_key("light") == "minimal_light"
    assert resolve_key("") == DEFAULT_THEME
    assert resolve_key(None) == DEFAULT_THEME
    assert resolve_key("nonexistent-theme") == DEFAULT_THEME


def test_manager_resolves_and_reports_current() -> None:
    """مدیر پوسته باید نام معتبر برگرداند و پالت بدهد."""
    manager = ThemeManager()
    assert manager.current == DEFAULT_THEME
    assert manager.resolve("corporate_navy") == "corporate_navy"
    assert manager.resolve("dark") == "glass_dark"
    palette = manager.palette
    for key in ("bg", "surface", "text", "primary", "success", "danger"):
        assert key in palette
        assert palette[key].startswith("#")


def test_font_scale_changes_metrics_not_colors() -> None:
    """
    بزرگ‌نمایی قلم فقط اندازه‌ها را عوض می‌کند.

    اگر رنگ هم عوض شود یعنی جایی توکن‌ها قاطی شده‌اند.
    """
    base = get_theme("glass_dark")
    scaled = base.scaled(150)
    assert scaled.metrics.font_md > base.metrics.font_md
    assert scaled.colors == base.colors
    assert base.scaled(100) is base


def test_compact_mode_reduces_spacing() -> None:
    """حالت فشرده باید فاصله‌ها و ارتفاع ردیف را کم کند."""
    base = get_theme("glass_dark")
    compact = base.compact()
    assert compact.metrics.row_height < base.metrics.row_height
    assert compact.metrics.space_lg < base.metrics.space_lg


def test_all_themes_define_the_same_color_tokens() -> None:
    """
    همهٔ پوسته‌ها باید مجموعهٔ یکسانی از رنگ‌ها داشته باشند.

    این همان تضمینی است که اجازه می‌دهد صفحه‌ها بدون شرط‌گذاری روی نام
    پوسته کار کنند.
    """
    reference = set(vars(get_theme("glass_dark").colors))
    for theme in list_themes():
        assert set(vars(theme.colors)) == reference, f"توکن ناقص در {theme.key}"


def test_theme_tokens_are_immutable() -> None:
    """توکن‌ها باید تغییرناپذیر باشند تا یک صفحه پوستهٔ سراسری را خراب نکند."""
    theme = get_theme("glass_dark")
    assert isinstance(theme, ThemeTokens)
    with pytest.raises(Exception):
        theme.colors.bg = "#ffffff"  # type: ignore[misc]
