"""
پوسته‌های سفارشی کاربر.

چرا؟
    کاربر خواست بتواند «همهٔ جزئیات ظاهری برنامه» را تغییر دهد و نتیجه
    را به‌عنوان پوستهٔ خودش ذخیره کند. پوستهٔ سفارشی یعنی یک پوستهٔ پایه
    به‌علاوهٔ فهرستی از مقادیر بازنویسی‌شده.

چرا «پایه + بازنویسی» و نه کپی کامل؟
    اگر همهٔ ده‌ها توکن کپی شوند، پوستهٔ ذخیره‌شدهٔ کاربر با افزوده‌شدن
    هر توکن جدید در نسخه‌های بعدی برنامه می‌شکند یا کهنه می‌ماند. با
    نگه‌داشتن فقط تفاوت‌ها، توکن‌های تازه خودبه‌خود از پوستهٔ پایه
    می‌آیند.

پوسته‌ها در `data_dir/themes/*.json` ذخیره می‌شوند — کنار تنظیمات کاربر،
نه داخل پوشهٔ برنامه؛ چون نصب دوبارهٔ برنامه نباید کار کاربر را پاک کند.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.logging import get_logger
from ui.themes.catalog import DEFAULT_THEME, THEME_CATALOG, get_theme
from ui.themes.tokens import ColorTokens, EffectTokens, MetricTokens, ThemeTokens

logger = get_logger(__name__)

#: پیشوند شناسهٔ پوسته‌های سفارشی — تضمین می‌کند با پوسته‌های داخلی
#: تداخل نکنند و در رابط کاربری قابل تشخیص باشند.
CUSTOM_PREFIX = "custom_"

#: نام پوشهٔ ذخیره‌سازی زیر پوشهٔ دادهٔ کاربر
THEMES_DIRNAME = "themes"

#: قالب رنگ معتبر: #rgb یا #rrggbb یا rgba(...)
_COLOR_PATTERN = re.compile(r"^(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|qlineargradient\([^)]*\))$")

#: بازهٔ مجاز هر گروه از سنجه‌ها؛ مقدار بیرون از بازه رابط را خراب می‌کند
METRIC_LIMITS: dict[str, tuple[int, int]] = {
    "radius_sm": (0, 40),
    "radius_md": (0, 40),
    "radius_lg": (0, 48),
    "radius_xl": (0, 64),
    "radius_pill": (0, 999),
    "space_xs": (0, 24),
    "space_sm": (0, 32),
    "space_md": (0, 40),
    "space_lg": (0, 56),
    "space_xl": (0, 72),
    "border_width": (0, 6),
    "card_top_accent": (0, 8),
    "font_xs": (8, 24),
    "font_sm": (8, 26),
    "font_md": (9, 28),
    "font_lg": (10, 32),
    "font_xl": (12, 44),
    "font_metric": (12, 60),
    "sidebar_width": (140, 400),
    "topbar_height": (36, 120),
    "row_height": (22, 90),
}

#: نام توکن‌های رنگی که کاربر می‌تواند تغییر دهد
COLOR_FIELDS: tuple[str, ...] = tuple(ColorTokens.__dataclass_fields__)

#: نام سنجه‌های قابل تغییر
METRIC_FIELDS: tuple[str, ...] = tuple(MetricTokens.__dataclass_fields__)

#: جلوه‌های بولی قابل تغییر
EFFECT_FLAGS: tuple[str, ...] = ("glass", "elevation")


def is_custom(key: str | None) -> bool:
    """آیا این شناسه به یک پوستهٔ سفارشی اشاره دارد؟"""
    return str(key or "").startswith(CUSTOM_PREFIX)


def slugify(name: str) -> str:
    """
    ساخت شناسهٔ فایل‌پسند از نام انتخابی کاربر.

    نام فارسی هم پذیرفته است؛ حروف غیرمجاز به خط زیر تبدیل می‌شوند و
    اگر چیزی باقی نماند، شناسهٔ عمومی برگردانده می‌شود.
    """
    cleaned = re.sub(r"[^\w\u0600-\u06ff]+", "_", str(name or "").strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("_").lower()
    return cleaned or "theme"


def _valid_colour(value: Any) -> bool:
    """آیا مقدار یک رنگ پذیرفتنی برای QSS است؟"""
    return bool(isinstance(value, str) and _COLOR_PATTERN.match(value.strip()))


def sanitise_overrides(overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    پاک‌سازی مقادیر بازنویسی پیش از ذخیره یا اعمال.

    مقدار نامعتبر بی‌صدا حذف می‌شود نه اینکه برنامه را بشکند: یک رنگ
    غلط در QSS، کل برگهٔ سبک را از کار می‌اندازد و رابط کاربری سفید
    می‌شود. کلید ناشناخته هم کنار گذاشته می‌شود تا فایل دستکاری‌شده
    نتواند چیزی به توکن‌ها تزریق کند.
    """
    result: dict[str, dict[str, Any]] = {"colors": {}, "metrics": {}, "effects": {}}

    for name, value in dict(overrides.get("colors") or {}).items():
        if name in COLOR_FIELDS and _valid_colour(value):
            result["colors"][name] = str(value).strip()
        elif name in COLOR_FIELDS:
            logger.debug("Rejected invalid colour for %s", name)

    for name, value in dict(overrides.get("metrics") or {}).items():
        if name not in METRIC_FIELDS:
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        low, high = METRIC_LIMITS.get(name, (0, 999))
        result["metrics"][name] = max(low, min(high, number))

    for name, value in dict(overrides.get("effects") or {}).items():
        if name in EFFECT_FLAGS:
            result["effects"][name] = bool(value)
        elif name in ("primary_gradient", "sidebar_active_gradient"):
            text = str(value or "").strip()
            # گرادیان خالی یعنی «رنگ تخت» و مقدار معتبری است
            if not text or _valid_colour(text):
                result["effects"][name] = text

    return {group: values for group, values in result.items() if values}


def build_tokens(
    key: str,
    name_fa: str,
    name_en: str,
    base_key: str,
    overrides: dict[str, Any],
) -> ThemeTokens:
    """
    ساخت توکن‌های کامل یک پوستهٔ سفارشی از پایه و بازنویسی‌ها.

    هر مقداری که کاربر تعیین نکرده باشد، از پوستهٔ پایه می‌آید؛ پس
    پوستهٔ حاصل همیشه کامل است.
    """
    base = get_theme(base_key)
    clean = sanitise_overrides(overrides)

    colour_overrides = clean.get("colors", {})
    effect_overrides = dict(clean.get("effects", {}))

    # اگر کاربر رنگ اصلی را عوض کند ولی پوستهٔ پایه گرادیان داشته باشد،
    # گرادیانِ کهنه روی رنگ تازه می‌نشیند و کاربر فکر می‌کند انتخاب رنگ
    # کار نمی‌کند. در این حالت گرادیان کنار می‌رود تا رنگ انتخابی واقعاً
    # دیده شود — مگر اینکه خود کاربر گرادیانی تعیین کرده باشد.
    if "primary" in colour_overrides and "primary_gradient" not in effect_overrides:
        effect_overrides["primary_gradient"] = ""
    if "sidebar_active_bg" in colour_overrides and "sidebar_active_gradient" not in effect_overrides:
        effect_overrides["sidebar_active_gradient"] = ""

    colors = replace(base.colors, **colour_overrides)
    metrics = replace(base.metrics, **clean.get("metrics", {}))
    effects = replace(base.effects, **effect_overrides)

    return ThemeTokens(
        key=key,
        name_fa=name_fa or name_en or key,
        name_en=name_en or name_fa or key,
        is_dark=base.is_dark,
        colors=colors,
        metrics=metrics,
        effects=effects,
    )


class CustomThemeStore:
    """
    خواندن، نوشتن و ثبت پوسته‌های سفارشی.

    نمونه‌سازی:
        store = CustomThemeStore(paths.data_dir)
        store.load_all()                    # ثبت در فهرست پوسته‌ها
        store.save("طلایی من", "glass_dark", {"colors": {"primary": "#d4a537"}})
    """

    def __init__(self, data_dir: Path) -> None:
        self.directory = Path(data_dir) / THEMES_DIRNAME
        self._registered: set[str] = set()

    # ------------------------------------------------------------------ IO
    def _path_for(self, key: str) -> Path:
        """مسیر فایل یک پوسته."""
        return self.directory / f"{key}.json"

    def load_all(self) -> list[str]:
        """
        خواندن همهٔ پوسته‌های ذخیره‌شده و ثبتشان در فهرست پوسته‌ها.

        بازگشتی: شناسهٔ پوسته‌هایی که با موفقیت ثبت شدند. فایل خراب فقط
        نادیده گرفته و گزارش می‌شود؛ یک فایل معیوب نباید مانع بالا آمدن
        برنامه شود.
        """
        if not self.directory.exists():
            return []

        loaded: list[str] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Invalid custom theme %s: %s", path.name, exc.__class__.__name__)
                continue
            key = self._register(data)
            if key:
                loaded.append(key)
        return loaded

    def _register(self, data: dict[str, Any]) -> str:
        """ساخت و ثبت یک پوسته از دادهٔ خام."""
        if not isinstance(data, dict):
            return ""
        key = str(data.get("key") or "").strip()
        if not is_custom(key):
            logger.warning("Custom theme without a valid key was skipped")
            return ""

        base_key = str(data.get("base") or DEFAULT_THEME)
        tokens = build_tokens(
            key,
            str(data.get("name_fa") or ""),
            str(data.get("name_en") or ""),
            base_key,
            dict(data.get("overrides") or {}),
        )
        THEME_CATALOG[key] = tokens
        self._registered.add(key)
        return key

    def save(
        self,
        name: str,
        base_key: str,
        overrides: dict[str, Any],
        *,
        key: str = "",
        name_en: str = "",
    ) -> str:
        """
        ذخیرهٔ یک پوستهٔ سفارشی و ثبت بی‌درنگ آن.

        اگر `key` داده شود همان پوسته به‌روزرسانی می‌شود؛ وگرنه شناسهٔ
        تازه‌ای از روی نام ساخته می‌شود و در صورت تکراری‌بودن، شماره
        می‌گیرد تا پوستهٔ قبلی کاربر پاک نشود.

        بازگشتی: شناسهٔ پوستهٔ ذخیره‌شده.
        """
        self.directory.mkdir(parents=True, exist_ok=True)

        target = key if is_custom(key) else self._unique_key(name)
        payload = {
            "key": target,
            "name_fa": name or target,
            "name_en": name_en or name or target,
            "base": str(base_key or DEFAULT_THEME),
            "overrides": sanitise_overrides(overrides),
        }

        path = self._path_for(target)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._register(payload)
        logger.info("Custom theme saved: %s", target)
        return target

    def delete(self, key: str) -> bool:
        """
        حذف یک پوستهٔ سفارشی.

        پوسته‌های داخلی برنامه هرگز حذف نمی‌شوند؛ درخواست حذفشان
        نادیده گرفته می‌شود.
        """
        if not is_custom(key):
            return False
        path = self._path_for(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.error("Could not delete theme %s: %s", key, exc.__class__.__name__)
            return False
        THEME_CATALOG.pop(key, None)
        self._registered.discard(key)
        return True

    def read(self, key: str) -> dict[str, Any]:
        """خواندن دادهٔ خام یک پوسته (برای بازکردنش در ویرایشگر)."""
        if not is_custom(key):
            return {}
        path = self._path_for(key)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    # --------------------------------------------------------------- کمکی
    @property
    def registered(self) -> set[str]:
        """شناسهٔ پوسته‌های سفارشی ثبت‌شده در این نشست."""
        return set(self._registered)

    def _unique_key(self, name: str) -> str:
        """ساخت شناسه‌ای که با پوسته‌های موجود تداخل نکند."""
        stem = f"{CUSTOM_PREFIX}{slugify(name)}"
        if stem not in THEME_CATALOG:
            return stem
        index = 2
        while f"{stem}_{index}" in THEME_CATALOG:
            index += 1
        return f"{stem}_{index}"


__all__ = [
    "COLOR_FIELDS",
    "CUSTOM_PREFIX",
    "EFFECT_FLAGS",
    "METRIC_FIELDS",
    "METRIC_LIMITS",
    "CustomThemeStore",
    "build_tokens",
    "is_custom",
    "sanitise_overrides",
    "slugify",
]
