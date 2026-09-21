"""
پوسته‌های ظاهری برنامه.

چهار پوستهٔ نام‌دار: شیشه‌ای تیره (پیش‌فرض)، روشن مینیمال، سرمه‌ای اداری
و بنفش روشن. همهٔ آن‌ها از یک مجموعه توکن مشترک ساخته می‌شوند و هیچ‌کدام
قابلیتی را محدود نمی‌کنند.
"""

from ui.themes.fonts import (
    DEFAULT_FONT_KEY,
    FONT_CHOICES,
    FontChoice,
    apply_default_font,
    font_stack,
    list_fonts,
    load_application_fonts,
    resolve_font_key,
)
from ui.themes.catalog import (
    DEFAULT_THEME,
    THEME_CATALOG,
    get_theme,
    list_themes,
    resolve_key,
)
from ui.themes.stylesheet import build_stylesheet
from ui.themes.theme_manager import ThemeManager, apply_theme
from ui.themes.tokens import ColorTokens, EffectTokens, MetricTokens, ThemeTokens

__all__ = [
    "DEFAULT_FONT_KEY",
    "DEFAULT_THEME",
    "FONT_CHOICES",
    "THEME_CATALOG",
    "ColorTokens",
    "FontChoice",
    "EffectTokens",
    "MetricTokens",
    "ThemeManager",
    "ThemeTokens",
    "apply_default_font",
    "apply_theme",
    "build_stylesheet",
    "font_stack",
    "list_fonts",
    "load_application_fonts",
    "get_theme",
    "list_themes",
    "resolve_font_key",
    "resolve_key",
]
