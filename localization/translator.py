"""
موتور ترجمه.

چرا وجود دارد؟
    برنامه باید کاملاً دوزبانه باشد و جهت چیدمان (RTL/LTR) با زبان تغییر
    کند. این ماژول:
        • فایل‌های JSON زبان را بارگذاری و در حافظه نگه می‌دارد
        • کلیدهای نقطه‌ای مانند `nav.dashboard` را ترجمه می‌کند
        • در نبود ترجمه، به انگلیسی و سپس به خود کلید بازمی‌گردد
          (هرگز رشته خالی یا خطا به کاربر نشان داده نمی‌شود)
        • اعداد را در صورت نیاز به ارقام فارسی تبدیل می‌کند

نکته درباره تغییر زبان:
    تغییر زبان نباید نیازمند راه‌اندازی مجدد برنامه باشد؛ به همین دلیل
    مترجم یک شیء سراسری است و رابط کاربری با رویداد از تغییر آن آگاه
    می‌شود.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.constants import Language
from app.logging import get_logger

logger = get_logger(__name__)

#: ارقام فارسی برای نمایش اعداد در حالت فارسی
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"

#: زبان‌هایی که راست‌به‌چپ نوشته می‌شوند
RTL_LANGUAGES = {"fa", "ar", "he", "ur"}


class Translator:
    """
    مترجم متن‌های رابط کاربری.

    نمونه‌سازی:
        translator = Translator(Language.FA)
        translator.tr("nav.dashboard")  →  "داشبورد"
    """

    def __init__(self, language: str | Language = Language.FA, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path(__file__).parent
        self._language = self._normalize(language)
        self._catalog: dict[str, Any] = {}
        self._fallback: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------
    # بارگذاری
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(language: str | Language) -> str:
        """تبدیل ورودی به کد زبان دو حرفی."""
        if isinstance(language, Language):
            return language.value
        return str(language).strip().lower()[:2] or Language.FA.value

    def load(self) -> int:
        """
        بارگذاری همه فایل‌های JSON زبان جاری و زبان پشتیبان.

        بازگشتی: تعداد کلیدهای بارگذاری‌شده در زبان جاری.
        """
        self._catalog = self._load_language(self._language)
        self._fallback = (
            self._load_language(Language.EN.value)
            if self._language != Language.EN.value
            else {}
        )
        count = self._count_keys(self._catalog)
        logger.info("Loaded %d translation keys for '%s'", count, self._language)
        return count

    def _load_language(self, language: str) -> dict[str, Any]:
        """خواندن و ادغام همه فایل‌های JSON یک زبان."""
        directory = self._base_dir / language
        if not directory.exists():
            logger.warning("Translation directory not found: %s", directory)
            return {}

        catalog: dict[str, Any] = {}
        for path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Invalid translation file %s: %s", path.name, exc.__class__.__name__)
                continue
            if isinstance(data, dict):
                # نام فایل، فضای‌نام کلیدها می‌شود: common.json → common.*
                catalog[path.stem] = data
        return catalog

    @classmethod
    def _count_keys(cls, node: Any) -> int:
        """شمارش بازگشتی کلیدهای برگ."""
        if isinstance(node, dict):
            return sum(cls._count_keys(value) for value in node.values())
        return 1

    # ------------------------------------------------------------------
    # زبان
    # ------------------------------------------------------------------
    @property
    def language(self) -> str:
        """کد زبان جاری."""
        return self._language

    @property
    def is_rtl(self) -> bool:
        """آیا زبان جاری راست‌به‌چپ است؟"""
        return self._language in RTL_LANGUAGES

    @property
    def direction(self) -> str:
        """جهت چیدمان، برای استفاده در Qt و HTML."""
        return "rtl" if self.is_rtl else "ltr"

    def set_language(self, language: str | Language) -> None:
        """تغییر زبان و بارگذاری مجدد کاتالوگ."""
        normalized = self._normalize(language)
        if normalized == self._language:
            return
        self._language = normalized
        self.load()

    def available_languages(self) -> list[str]:
        """فهرست زبان‌های موجود بر اساس پوشه‌های این ماژول."""
        return sorted(
            item.name
            for item in self._base_dir.iterdir()
            if item.is_dir() and not item.name.startswith("_") and any(item.glob("*.json"))
        )

    # ------------------------------------------------------------------
    # ترجمه
    # ------------------------------------------------------------------
    def tr(self, key: str, default: str | None = None, **variables: Any) -> str:
        """
        ترجمه یک کلید نقطه‌ای.

        ترتیب جست‌وجو: زبان جاری → انگلیسی → مقدار پیش‌فرض → خود کلید.
        هرگز خطا نمی‌دهد؛ نبود ترجمه نباید برنامه را متوقف کند.

        متغیرها با نحو {name} جای‌گذاری می‌شوند:
            tr("errors.not_found", name="BTC")
        """
        value = self._lookup(self._catalog, key)
        if value is None:
            value = self._lookup(self._fallback, key)
        if value is None:
            value = default if default is not None else key
            if default is None:
                logger.debug("Missing translation key: %s (%s)", key, self._language)

        if variables and isinstance(value, str):
            try:
                value = value.format(**variables)
            except (KeyError, IndexError, ValueError):
                logger.debug("Could not interpolate variables into key: %s", key)
        return str(value)

    @staticmethod
    def _lookup(catalog: dict[str, Any], key: str) -> Any:
        """پیمایش کلید نقطه‌ای در ساختار تودرتو."""
        node: Any = catalog
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node if not isinstance(node, dict) else None

    def raw(self, key: str, default: Any = None) -> Any:
        """
        گرفتن مقدار خام یک کلید، بدون تبدیل به رشته.

        بعضی محتواها ساختار دارند نه یک جمله — مثل فهرست فصل‌های آموزش.
        `tr` آن‌ها را با `str()` به متن بدریخت تبدیل می‌کند، پس برای این
        موارد باید مقدار اصلی برگردد. ترتیب جست‌وجو مثل `tr` است.
        """
        value = self._lookup(self._catalog, key)
        if value is None:
            value = self._lookup(self._fallback, key)
        return default if value is None else value

    def has(self, key: str) -> bool:
        """آیا کلید در زبان جاری وجود دارد؟"""
        return self._lookup(self._catalog, key) is not None

    def missing_keys(self, reference_language: str = "en") -> list[str]:
        """
        فهرست کلیدهایی که در زبان مرجع هستند ولی در زبان جاری نیستند.

        برای کنترل کیفیت ترجمه و آزمون‌های خودکار استفاده می‌شود.
        """
        reference = self._load_language(reference_language)
        missing: list[str] = []

        def walk(node: Any, prefix: str) -> None:
            if isinstance(node, dict):
                for name, value in node.items():
                    walk(value, f"{prefix}.{name}" if prefix else name)
            elif self._lookup(self._catalog, prefix) is None:
                missing.append(prefix)

        walk(reference, "")
        return sorted(missing)

    # ------------------------------------------------------------------
    # قالب‌بندی اعداد
    # ------------------------------------------------------------------
    def format_number(self, value: float | int, decimals: int = 2, *, persian_digits: bool = True) -> str:
        """
        قالب‌بندی عدد با جداکننده هزارگان و ارقام محلی.

        در فارسی، ارقام فارسی استفاده می‌شود مگر آنکه صریحاً غیرفعال شود
        (مثلاً در فایل‌های خروجی CSV که باید ماشین‌خوان بمانند).
        """
        text = f"{value:,.{decimals}f}"
        if self.is_rtl and persian_digits:
            text = self.to_persian_digits(text)
        return text

    @staticmethod
    def to_persian_digits(text: str) -> str:
        """تبدیل ارقام لاتین به فارسی."""
        return text.translate(str.maketrans("0123456789", PERSIAN_DIGITS))

    @staticmethod
    def to_latin_digits(text: str) -> str:
        """تبدیل ارقام فارسی به لاتین (برای پردازش ورودی کاربر)."""
        return text.translate(str.maketrans(PERSIAN_DIGITS, "0123456789"))


#: مترجم سراسری برنامه
_translator: Translator | None = None


def get_translator(language: str | Language | None = None) -> Translator:
    """
    دریافت مترجم سراسری (الگوی Singleton تنبل).

    اگر زبان داده شود و با زبان فعلی فرق داشته باشد، زبان تغییر می‌کند.
    """
    global _translator
    if _translator is None:
        _translator = Translator(language or Language.FA)
    elif language is not None:
        _translator.set_language(language)
    return _translator


def tr(key: str, default: str | None = None, **variables: Any) -> str:
    """میان‌بر سراسری ترجمه، برای استفاده در کد رابط کاربری."""
    return get_translator().tr(key, default, **variables)
