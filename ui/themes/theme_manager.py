"""
مدیریت پوسته ظاهری برنامه.

از نسخهٔ ۱٫۵ پوسته‌ها نام‌دار و مبتنی بر توکن‌اند: «شیشه‌ای تیره»،
«روشن مینیمال»، «سرمه‌ای اداری» و «بنفش روشن». پوستهٔ پیش‌فرض
«شیشه‌ای تیره» است.

چرا QSS به‌جای رنگ‌آمیزی دستی؟
    با یک برگه سبک متمرکز، تغییر پوسته در زمان اجرا بدون بازسازی ویجت‌ها
    ممکن می‌شود و ظاهر همه صفحات یکدست می‌ماند.

سازگاری با نسخه‌های پیشین:
    نام‌های `dark`/`light`/`system` هنوز پذیرفته می‌شوند و به پوستهٔ
    متناظر نگاشت می‌گردند، بنابراین تنظیمات ذخیره‌شدهٔ کاربران قدیمی
    هرگز نمی‌شکند.

**قاعده:** پوسته فقط ظاهر را تعیین می‌کند. هیچ قابلیتی نباید به پوسته
وابسته باشد؛ همهٔ امکانات در همهٔ پوسته‌ها در دسترس‌اند.
"""

from __future__ import annotations

from typing import Any

from app.core.constants import Theme
from app.logging import get_logger
from ui.themes.catalog import (
    DEFAULT_THEME,
    THEME_CATALOG,
    get_theme,
    list_themes,
    resolve_key,
)
from ui.themes.fonts import (
    DEFAULT_FONT_KEY,
    apply_default_font,
    font_stack,
    list_fonts,
    load_application_fonts,
    resolve_font_key,
)
from ui.themes.stylesheet import STYLESHEET_TEMPLATE, build_stylesheet
from ui.themes.tokens import ThemeTokens

logger = get_logger(__name__)

#: پالت پوستهٔ تیره — برای سازگاری با کدهای قدیمی که مستقیم واردش می‌کردند
DARK_PALETTE: dict[str, str] = dict(vars(THEME_CATALOG["glass_dark"].colors))

#: پالت پوستهٔ روشن — همان سازگاری
LIGHT_PALETTE: dict[str, str] = dict(vars(THEME_CATALOG["minimal_light"].colors))


class ThemeManager:
    """
    اعمال‌کننده پوسته روی برنامه.

    نمونه‌سازی:
        manager = ThemeManager()
        manager.apply(qt_app, "glass_dark")

    پارامترهای نمایشی (اندازهٔ قلم و حالت فشرده) جدا از پوسته نگهداری
    می‌شوند تا تغییرشان روی هر پوسته‌ای اثر کند.
    """

    def __init__(self) -> None:
        self._current: str = DEFAULT_THEME
        self._font_scale: int = 100
        self._compact: bool = False
        self._app: Any = None
        #: خانوادهٔ قلم — ترجیح کاربر، مستقل از پوسته
        self._font_key: str = DEFAULT_FONT_KEY

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    @property
    def current(self) -> str:
        """شناسهٔ پوستهٔ فعال."""
        return self._current

    @property
    def tokens(self) -> ThemeTokens:
        """توکن‌های پوستهٔ فعال با اعمال اندازهٔ قلم و حالت فشرده."""
        return self._effective(self._current)

    @property
    def palette(self) -> dict[str, str]:
        """
        پالت رنگ پوستهٔ فعال.

        نمودارها (pyqtgraph) برگهٔ سبک نمی‌گیرند و رنگ را از همین‌جا
        می‌خوانند.
        """
        return dict(vars(get_theme(self._current).colors))

    @property
    def is_dark(self) -> bool:
        """آیا پوستهٔ فعال تیره است؟ (برای انتخاب آیکون و رنگ نمودار)"""
        return get_theme(self._current).is_dark

    @property
    def font_scale(self) -> int:
        """درصد اندازهٔ قلم فعال."""
        return self._font_scale

    @property
    def compact_mode(self) -> bool:
        """آیا حالت فشرده فعال است؟"""
        return self._compact

    @property
    def font_key(self) -> str:
        """شناسهٔ خانوادهٔ قلم فعال."""
        return self._font_key

    @property
    def font_stack(self) -> str:
        """زنجیرهٔ قلم فعال به قالب QSS."""
        return font_stack(self._font_key)

    @staticmethod
    def available_fonts() -> list[Any]:
        """فهرست قلم‌های قابل انتخاب برای صفحهٔ تنظیمات."""
        return list_fonts()

    def set_font_family(self, key: str | None, app: Any = None) -> str:
        """
        تغییر خانوادهٔ قلم و اعمال بی‌درنگ روی کل برنامه.

        قلم جزو پوسته نیست: کاربر باید بتواند «ب کودک» را انتخاب کند و
        بعد پوسته را عوض کند بدون آنکه قلمش برگردد. بازگشتی شناسهٔ قلمی
        است که واقعاً اعمال شد.
        """
        resolved = resolve_font_key(key)
        target = app or self._app
        # حتی وقتی مقدار عوض نشده، قلم پیش‌فرض QApplication را دوباره
        # می‌نشانیم؛ در اولین اجرا مقدار ذخیره‌شده با پیش‌فرض یکی است ولی
        # هنوز روی برنامه ننشسته.
        self._font_key = resolved
        if target is not None:
            apply_default_font(target, resolved)
            self._reapply(target)
        return resolved

    # ------------------------------------------------------------------
    # فهرست پوسته‌ها
    # ------------------------------------------------------------------
    @staticmethod
    def available() -> list[ThemeTokens]:
        """فهرست پوسته‌های در دسترس برای نمایش در تنظیمات."""
        return list_themes()

    @staticmethod
    def display_name(key: str, language: str = "fa") -> str:
        """نام نمایشی پوسته در زبان خواسته‌شده."""
        theme = get_theme(key)
        return theme.name_fa if str(language).lower().startswith("fa") else theme.name_en

    @staticmethod
    def tokens_for(key: str) -> ThemeTokens:
        """توکن‌های یک پوستهٔ مشخص (بدون تغییر پوستهٔ فعال)."""
        return get_theme(key)

    # ------------------------------------------------------------------
    # تشخیص و تبدیل
    # ------------------------------------------------------------------
    @staticmethod
    def detect_system_theme(app: Any = None) -> str:
        """
        تشخیص پوسته سیستم‌عامل.

        روش: روشنایی رنگ پس‌زمینه پیش‌فرض بررسی می‌شود. اگر تیره بود،
        پوستهٔ شیشه‌ای تیره و در غیر این صورت روشن مینیمال انتخاب می‌گردد.
        """
        try:
            from PySide6.QtWidgets import QApplication

            instance = app or QApplication.instance()
            if instance is None:
                return DEFAULT_THEME
            window_color = instance.palette().window().color()
            brightness = (
                window_color.red() * 299
                + window_color.green() * 587
                + window_color.blue() * 114
            ) / 1000
            return "minimal_light" if brightness > 128 else DEFAULT_THEME
        except Exception:  # noqa: BLE001 - تشخیص پوسته نباید برنامه را متوقف کند
            return DEFAULT_THEME

    def resolve(self, theme: str | Theme, app: Any = None) -> str:
        """
        تبدیل نام درخواستی به شناسهٔ پوستهٔ واقعی.

        «مطابق سیستم» به پوستهٔ متناسب با سیستم‌عامل و نام‌های قدیمی به
        معادل تازه‌شان تبدیل می‌شوند.
        """
        value = theme.value if isinstance(theme, Theme) else str(theme or "").strip().lower()
        if value in ("system", Theme.SYSTEM.value):
            return self.detect_system_theme(app)
        return resolve_key(value)

    # ------------------------------------------------------------------
    # ساخت و اعمال
    # ------------------------------------------------------------------
    def stylesheet(self, theme: str | Theme, app: Any = None) -> str:
        """ساخت برگه سبک کامل برای پوستهٔ خواسته‌شده."""
        return build_stylesheet(self._effective(self.resolve(theme, app)), self.font_stack)

    def apply(self, app: Any, theme: str | Theme) -> str:
        """
        اعمال پوسته روی برنامه.

        بازگشتی: شناسهٔ پوستهٔ واقعی اعمال‌شده (پس از تبدیل حالت سیستم).
        """
        resolved = self.resolve(theme, app)
        self._current = resolved
        self._app = app
        # قلم‌های همراه برنامه باید پیش از ساخت QSS ثبت شده باشند، وگرنه
        # Qt نام خانواده را نمی‌شناسد و بی‌صدا به قلم سیستم برمی‌گردد.
        load_application_fonts()
        apply_default_font(app, self._font_key)
        app.setStyleSheet(build_stylesheet(self._effective(resolved), self.font_stack))
        logger.info("Theme applied: %s (font=%s)", resolved, self._font_key)
        return resolved

    def set_font_scale(self, percent: int, app: Any = None) -> None:
        """
        تغییر اندازهٔ قلم و اعمال دوبارهٔ پوسته.

        مقدار خارج از بازهٔ ۶۰ تا ۲۰۰ درصد بریده می‌شود تا رابط کاربری
        غیرقابل‌استفاده نشود.
        """
        try:
            value = int(percent)
        except (TypeError, ValueError):
            return
        value = max(60, min(200, value))
        if value == self._font_scale:
            return
        self._font_scale = value
        self._reapply(app)

    def set_compact_mode(self, enabled: bool, app: Any = None) -> None:
        """فعال/غیرفعال کردن حالت فشرده و اعمال دوبارهٔ پوسته."""
        value = bool(enabled)
        if value == self._compact:
            return
        self._compact = value
        self._reapply(app)

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    def _effective(self, key: str) -> ThemeTokens:
        """توکن‌های پوسته پس از اعمال اندازهٔ قلم و حالت فشرده."""
        theme = get_theme(key).scaled(self._font_scale)
        return theme.compact() if self._compact else theme

    def _reapply(self, app: Any = None) -> None:
        """اعمال دوبارهٔ پوستهٔ فعال روی برنامه (پس از تغییر پارامترها)."""
        target = app or self._app
        if target is None:
            try:
                from PySide6.QtWidgets import QApplication

                target = QApplication.instance()
            except Exception:  # noqa: BLE001
                target = None
        if target is None:
            return
        self._app = target
        target.setStyleSheet(build_stylesheet(self._effective(self._current), self.font_stack))


#: مدیر پوسته سراسری
_manager = ThemeManager()


def apply_theme(app: Any, theme: str | Theme) -> str:
    """میان‌بر اعمال پوسته با مدیر سراسری."""
    return _manager.apply(app, theme)


__all__ = [
    "DARK_PALETTE",
    "LIGHT_PALETTE",
    "STYLESHEET_TEMPLATE",
    "ThemeManager",
    "apply_theme",
]
