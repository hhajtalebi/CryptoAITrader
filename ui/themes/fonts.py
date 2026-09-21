"""
بارگذاری و انتخاب قلم‌های فارسی برنامه.

چرا این ماژول جدا است؟
    پیش از این هیچ قلمی در رابط کاربری ثبت نمی‌شد و Qt هر چه در سیستم‌عامل
    بود استفاده می‌کرد. نتیجه روی ویندوزهای فارسی «تاهوما» بود که برای یک
    پنل معاملاتی نه زیباست و نه ارقام فارسی‌اش یکدست است. حالا قلم‌ها همراه
    برنامه توزیع و در زمان اجرا ثبت می‌شوند، پس ظاهر روی همهٔ دستگاه‌ها
    یکسان است.

قاعدهٔ مهم دربارهٔ نمادهای بازار:
    قلم «کودک» و «B Koodak» حروف لاتین ندارند (فقط ارقام و نشانه‌ها). این
    عیب نیست بلکه به‌سود ماست: Qt برای `BTC/USDT` خودش به قلم بعدی زنجیره
    می‌رود، پس نماد بازار همیشه با قلم لاتین خوانا نمایش داده می‌شود و
    فارسیِ متن با قلم کودک. به همین دلیل هر زنجیره حتماً به «Vazirmatn»
    ختم می‌شود.

افزودن قلم تازه = یک ردیف در `FONT_CHOICES`؛ نه کد تازه‌ای لازم است و نه
دست‌زدن به صفحه‌ها.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: پوشهٔ قلم‌های همراه برنامه
FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

#: پوشهٔ قلم‌های شخصیِ کاربر — قلم‌هایی که اجازهٔ توزیع ندارند (مثل
#: ایران‌سنس) را کاربر خودش اینجا می‌گذارد و برنامه خودکار می‌یابدشان.
USER_FONTS_DIR = FONTS_DIR / "user"

#: فایل‌هایی که هنگام اجرا در Qt ثبت می‌شوند
FONT_FILES: tuple[str, ...] = (
    "Koodak.ttf",
    "BKoodakBd.ttf",
    "Vazirmatn-Regular.ttf",
    "Vazirmatn-Bold.ttf",
    "Sahel.ttf",
    "Sahel-Bold.ttf",
)


@dataclass(frozen=True, slots=True)
class FontChoice:
    """
    یک گزینهٔ قلم در تنظیمات.

    فیلدها:
        key       : شناسهٔ ذخیره‌شده در تنظیمات (`ui.font_family`)
        name_fa   : نامی که کاربر فارسی‌زبان می‌بیند
        name_en   : همان نام برای رابط انگلیسی
        stack     : زنجیرهٔ آمادهٔ QSS (شامل قلم پشتیبان لاتین)
        families  : خانواده‌هایی که باید ثبت شده باشند تا این گزینه معنا بدهد
    """

    key: str
    name_fa: str
    name_en: str
    stack: str
    families: tuple[str, ...] = ()
    #: آیا فایل قلم همراه برنامه توزیع می‌شود؟
    #: ایران‌سنس قلم تجاری fontiran.com است و اجازهٔ توزیع مجدد ندارد، پس
    #: `bundled=False` می‌گیرد: اگر کاربر آن را روی ویندوز نصب کرده باشد
    #: (یا فایلش را در `assets/fonts/user/` بگذارد) خودکار پیدا و فعال
    #: می‌شود، وگرنه گزینه‌اش در تنظیمات «در دسترس نیست» علامت می‌خورد.
    bundled: bool = True


#: زنجیرهٔ پشتیبان مشترک — همیشه انتهای هر زنجیره می‌آید
_FALLBACK = '"Vazirmatn", "Segoe UI", "Tahoma", sans-serif'

#: گزینه‌های قلم؛ ترتیب همان ترتیب نمایش در تنظیمات است.
#: قلم پیش‌فرض (وزیرمتن) عمداً نخست می‌آید تا وقتی هنوز مقداری ذخیره
#: نشده، فهرست روی همان چیزی بایستد که برنامه واقعاً استفاده می‌کند.
FONT_CHOICES: tuple[FontChoice, ...] = (
    FontChoice(
        key="vazirmatn",
        name_fa="وزیرمتن",
        name_en="Vazirmatn",
        stack=_FALLBACK,
        families=("Vazirmatn",),
    ),
    FontChoice(
        key="sahel",
        name_fa="ساحل",
        name_en="Sahel",
        stack=f'"Sahel", {_FALLBACK}',
        families=("Sahel",),
    ),
    FontChoice(
        key="iransans",
        name_fa="ایران‌سنس",
        name_en="IRANSans",
        # نام‌های گوناگونی که نسخه‌های مختلف ایران‌سنس با آن ثبت می‌شوند؛
        # هر کدام موجود باشد همان استفاده می‌شود.
        stack=(
            '"IRANSans", "IRANSansX", "IRANSansWeb", "IRAN Sans", '
            '"IRANSans(FaNum)", ' + _FALLBACK
        ),
        families=("IRANSans", "IRANSansX", "IRANSansWeb", "IRAN Sans", "IRANSans(FaNum)"),
        bundled=False,
    ),
    FontChoice(
        key="koodak",
        name_fa="ب کودک",
        name_en="B Koodak",
        stack=f'"B Koodak", "Koodak", {_FALLBACK}',
        families=("B Koodak", "Koodak"),
    ),
    FontChoice(
        key="koodak_light",
        name_fa="کودک (نازک‌تر)",
        name_en="Koodak",
        stack=f'"Koodak", "B Koodak", {_FALLBACK}',
        families=("Koodak",),
    ),
    FontChoice(
        key="system",
        name_fa="قلم سیستم",
        name_en="System font",
        stack='"Segoe UI", "Tahoma", "Vazirmatn", sans-serif',
    ),
)

#: دسترسی سریع بر پایهٔ کلید
FONT_MAP: dict[str, FontChoice] = {choice.key: choice for choice in FONT_CHOICES}

#: قلم پیش‌فرض. کاربر پس از دیدن نتیجه گفت «فونت پیش‌فرض وزیرمتن باشه،
#: این خوبه»، پس پیش‌فرض از «ب کودک» به وزیرمتن تغییر کرد. «ب کودک»
#: حذف نشد و همچنان یکی از گزینه‌هاست.
DEFAULT_FONT_KEY = "vazirmatn"

#: خانواده‌های ثبت‌شده در این اجرا (پس از فراخوانی `load_application_fonts`)
_loaded_families: set[str] = set()
_load_attempted = False


def load_application_fonts(force: bool = False) -> set[str]:
    """
    ثبت قلم‌های همراه برنامه در پایگاه قلم Qt.

    چرا فقط یک بار؟ ثبت دوباره همان فایل، نسخهٔ تکراری در فهرست قلم‌ها
    می‌سازد. نتیجه در حافظه نگهداری می‌شود و فراخوانی‌های بعدی رایگان‌اند.

    اگر Qt در دسترس نباشد (آزمون‌های بدون رابط گرافیکی) مجموعهٔ خالی
    برمی‌گردد و هیچ استثنایی بیرون نمی‌زند؛ سبک‌ها همچنان کار می‌کنند و
    فقط به قلم سیستم برمی‌گردند.
    """
    global _load_attempted

    if _load_attempted and not force:
        return set(_loaded_families)

    _load_attempted = True
    try:
        from PySide6.QtGui import QFontDatabase
    except Exception:  # noqa: BLE001 - محیط بدون Qt
        logger.debug("Qt is unavailable; application fonts were not registered")
        return set()

    def _register(path: Path, *, required: bool) -> None:
        """ثبت یک فایل قلم؛ نبودنش هرگز برنامه را متوقف نمی‌کند."""
        if not path.exists():
            if required:
                logger.warning("Font file is missing: %s", path.name)
            return
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            logger.warning("Qt refused to load font: %s", path.name)
            return
        for family in QFontDatabase.applicationFontFamilies(font_id):
            _loaded_families.add(str(family))

    for file_name in FONT_FILES:
        _register(FONTS_DIR / file_name, required=True)

    # قلم‌های شخصی کاربر (مثل ایران‌سنس که حق توزیعش را نداریم). هر فایل
    # ttf/otf در این پوشه ثبت می‌شود؛ نیازی به تغییر کد نیست.
    if USER_FONTS_DIR.is_dir():
        for path in sorted(USER_FONTS_DIR.iterdir()):
            if path.suffix.lower() in {".ttf", ".otf"}:
                _register(path, required=False)

    # قلم‌های نصب‌شده در سیستم‌عامل هم باید دیده شوند، وگرنه کاربری که
    # ایران‌سنس را روی ویندوز نصب کرده گزینه‌اش را «در دسترس نیست»
    # می‌دید. این کار فقط نام‌های موردنیاز را اضافه می‌کند، نه همه را.
    try:
        installed = {str(name) for name in QFontDatabase.families()}
    except Exception:  # noqa: BLE001 - نسخه‌های قدیمی‌تر Qt
        installed = set()
    for choice in FONT_CHOICES:
        for family in choice.families:
            if family in installed:
                _loaded_families.add(family)

    if _loaded_families:
        logger.info("Application fonts registered: %s", ", ".join(sorted(_loaded_families)))
    return set(_loaded_families)


def loaded_families() -> set[str]:
    """خانواده‌های قلمی که با موفقیت ثبت شده‌اند."""
    return set(_loaded_families)


def resolve_font_key(key: str | None) -> str:
    """
    تبدیل مقدار ذخیره‌شده به شناسهٔ معتبر قلم.

    مقدار ناشناخته (مثلاً تنظیمات یک نسخهٔ آینده که کاربر برگشته) به قلم
    پیش‌فرض نگاشت می‌شود تا برنامه هرگز به‌خاطر یک رشته خطا ندهد.
    """
    value = str(key or "").strip().lower()
    return value if value in FONT_MAP else DEFAULT_FONT_KEY


def font_stack(key: str | None) -> str:
    """زنجیرهٔ QSS یک گزینهٔ قلم."""
    return FONT_MAP[resolve_font_key(key)].stack


def font_name(key: str | None, language: str = "fa") -> str:
    """نام نمایشی یک گزینهٔ قلم در زبان خواسته‌شده."""
    choice = FONT_MAP[resolve_font_key(key)]
    return choice.name_fa if str(language).lower().startswith("fa") else choice.name_en


def list_fonts() -> list[FontChoice]:
    """فهرست گزینه‌های قلم برای ساخت انتخابگر تنظیمات."""
    return list(FONT_CHOICES)


def is_available(key: str | None, *, strict: bool = False) -> bool:
    """
    آیا قلم این گزینه واقعاً ثبت شده است؟

    `strict=False` یعنی وقتی هنوز هیچ قلمی بارگذاری نشده (محیط بدون Qt)
    همه‌چیز «در دسترس» فرض می‌شود؛ چون در آن حالت زنجیرهٔ QSS بی‌ضرر است.
    """
    choice = FONT_MAP[resolve_font_key(key)]
    if not choice.families:
        return True
    if not choice.bundled:
        # قلم‌های غیرهمراه (ایران‌سنس) واقعاً ممکن است نباشند. اینجا
        # آسان‌گیری معنا ندارد: باید صادقانه بگوییم نصب نیست، وگرنه کاربر
        # گزینه را می‌زند و هیچ تغییری نمی‌بیند.
        return any(family in _loaded_families for family in choice.families)
    if not _loaded_families and not strict:
        return True
    return any(family in _loaded_families for family in choice.families)


def apply_default_font(app: Any, key: str | None = None) -> str:
    """
    تنظیم قلم پیش‌فرض خودِ QApplication.

    برگهٔ سبک برای ویجت‌ها کافی است، ولی اجزایی که خودشان نقاشی می‌شوند
    (نمودارهای سبک، متن روی بوم) از `app.font()` می‌خوانند. بدون این،
    همان اجزا با قلم سیستم می‌ماندند و ظاهر دوگانه می‌شد.

    بازگشتی: شناسهٔ قلمی که واقعاً اعمال شد.
    """
    resolved = resolve_font_key(key)
    choice = FONT_MAP[resolved]
    if app is None or not choice.families:
        return resolved

    load_application_fonts()
    family = next((name for name in choice.families if name in _loaded_families), "")
    if not family:
        return resolved

    try:
        from PySide6.QtGui import QFont

        current = app.font()
        font = QFont(current)
        # خانواده‌های پشتیبان را هم می‌دهیم تا حروف لاتینِ نبوده در قلم
        # فارسی از قلم بعدی بیایند و مربع خالی دیده نشود.
        font.setFamilies([family, *choice.families, "Vazirmatn"])
        font.setFamily(family)
        app.setFont(font)
    except Exception:  # noqa: BLE001 - قلم نباید اجرای برنامه را متوقف کند
        logger.debug("Could not set the application default font", exc_info=True)
    return resolved


__all__ = [
    "DEFAULT_FONT_KEY",
    "USER_FONTS_DIR",
    "FONT_CHOICES",
    "FONT_FILES",
    "FONT_MAP",
    "FontChoice",
    "apply_default_font",
    "font_name",
    "font_stack",
    "is_available",
    "list_fonts",
    "load_application_fonts",
    "loaded_families",
    "resolve_font_key",
]
