"""
سرویس تنظیمات کاربر: لایه‌ای بالاتر از SettingsRepository.

چرا وجود دارد؟
    مخزن فقط کلید/مقدار خام می‌دهد. این سرویس علاوه بر آن:
      • حافظه نهان (Cache) دارد تا خواندن‌های مکرر به SQLite فشار نیاورد.
      • مقدار را با نوع درست برمی‌گرداند (int / float / bool / list).
      • هنگام تغییر تنظیم، رویداد منتشر می‌کند تا UI به‌روزرسانی شود.
      • قانون «عدم بازنویسی تنظیمات کاربر» را اجرا می‌کند.

ارتباط با ماژول‌های دیگر:
    تقریباً همه سرویس‌ها (بازار، هوش مصنوعی، سیگنال، ریسک) پیکربندی خود را
    از این سرویس می‌گیرند، نه از مقادیر Hard-Code.
"""

from __future__ import annotations

import threading
from typing import Any

from app.config.defaults import DEFAULT_SETTINGS, SETTING_CATEGORIES, SettingKey
from app.core.constants import Language, Theme
from app.core.events import EventBus, EventType
from app.core.models import RiskParameters
from app.database.repositories.settings_repository import SettingsRepository
from app.logging import get_logger

logger = get_logger(__name__)


class SettingsService:
    """
    نقطه واحد دسترسی به تنظیمات کاربر.

    نمونه‌سازی:
        service = SettingsService(repository, event_bus)
        service.initialize_defaults()
    """

    def __init__(self, repository: SettingsRepository, event_bus: EventBus | None = None) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._cache: dict[str, Any] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # راه‌اندازی
    # ------------------------------------------------------------------
    def initialize_defaults(self) -> int:
        """
        درج مقادیر پیش‌فرض برای کلیدهای غایب و بارگذاری حافظه نهان.

        بازگشتی: تعداد کلیدهای تازه اضافه‌شده. مقدار صفر یعنی تمام تنظیمات
        از قبل وجود داشته و چیزی بازنویسی نشده است.
        """
        inserted = self._repository.ensure_defaults(DEFAULT_SETTINGS, SETTING_CATEGORIES)
        self.reload()
        self._repair_stale_defaults()
        return inserted

    #: مقادیر پیش‌فرضِ قدیمی که خراب بودند و باید بالا کشیده شوند.
    #: ساختار: کلید → (مقدار معیوب قدیمی، مقدار درست تازه)
    #:
    #: قاعدهٔ سخت: فقط وقتی جایگزین می‌شود که مقدار ذخیره‌شده **دقیقاً**
    #: همان پیش‌فرض معیوب باشد. اگر کاربر خودش عددی گذاشته باشد — حتی
    #: عددی کوچک‌تر — دست نمی‌خورد. تنظیمات کاربر هرگز بازنویسی نمی‌شود.
    STALE_DEFAULTS: dict[str, tuple[Any, Any]] = {
        # ۴۵ ثانیه برای مدل محلی کافی نبود: نخستین درخواست شامل بارگذاری
        # وزنه‌ها در حافظه است. تحلیل سیگنال همیشه تسلیم می‌شد در حالی که
        # چت (با مهلت ۱۲۰) کار می‌کرد.
        SettingKey.SIGNAL_AI_TIMEOUT.value: (45, 120),
    }

    def _repair_stale_defaults(self) -> None:
        """
        بالا کشیدن پیش‌فرض‌های قدیمیِ معیوب در نصب‌های موجود.

        تغییر `DEFAULT_SETTINGS` فقط روی نصب تازه اثر دارد؛ کسی که از
        نسخهٔ قبل ارتقا می‌دهد مقدار قدیمی را در پایگاه داده دارد و
        همچنان باگ را می‌بیند.
        """
        for key, (broken, fixed) in self.STALE_DEFAULTS.items():
            current = self._repository.get(key, None)
            if current is None:
                continue
            try:
                unchanged = int(current) == int(broken)
            except (TypeError, ValueError):
                continue
            if unchanged:
                self.set(key, fixed)
                logger.info(
                    "Raised stale default for '%s' from %s to %s", key, broken, fixed
                )

    def reload(self) -> None:
        """بارگذاری مجدد تمام تنظیمات در حافظه نهان."""
        with self._lock:
            self._cache = self._repository.get_all()
        logger.debug("Settings cache reloaded (%d keys)", len(self._cache))

    # ------------------------------------------------------------------
    # خواندن
    # ------------------------------------------------------------------
    def get(self, key: SettingKey | str, default: Any = None) -> Any:
        """
        خواندن یک تنظیم با اولویت: حافظه نهان ← پایگاه داده ← مقدار پیش‌فرض.
        """
        key_str = key.value if isinstance(key, SettingKey) else key
        with self._lock:
            if key_str in self._cache:
                value = self._cache[key_str]
                if value is not None:
                    return value
        value = self._repository.get(key_str, None)
        if value is None:
            value = DEFAULT_SETTINGS.get(key_str, default)
        with self._lock:
            self._cache[key_str] = value
        return value

    def get_int(self, key: SettingKey | str, default: int = 0) -> int:
        """خواندن یک تنظیم عددی صحیح با تبدیل امن."""
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            logger.warning("Setting '%s' is not a valid integer; using default", key)
            return default

    def get_float(self, key: SettingKey | str, default: float = 0.0) -> float:
        """خواندن یک تنظیم اعشاری با تبدیل امن."""
        try:
            return float(self.get(key, default))
        except (TypeError, ValueError):
            logger.warning("Setting '%s' is not a valid float; using default", key)
            return default

    def get_bool(self, key: SettingKey | str, default: bool = False) -> bool:
        """خواندن یک تنظیم بولین (رشته‌های "true"/"1" نیز پذیرفته می‌شوند)."""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "on"}
        return bool(value)

    def get_list(self, key: SettingKey | str, default: list[Any] | None = None) -> list[Any]:
        """خواندن یک تنظیم فهرستی."""
        value = self.get(key, default if default is not None else [])
        return list(value) if isinstance(value, (list, tuple)) else (default or [])

    def get_dict(self, key: SettingKey | str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """خواندن یک تنظیم دیکشنری."""
        value = self.get(key, default if default is not None else {})
        return dict(value) if isinstance(value, dict) else (default or {})

    # ------------------------------------------------------------------
    # نوشتن
    # ------------------------------------------------------------------
    def set(self, key: SettingKey | str, value: Any, *, notify: bool = True) -> None:
        """
        ذخیره یک تنظیم و انتشار رویداد تغییر.

        این متد مقدار را به‌عنوان «تنظیم کاربر» علامت می‌زند؛ بنابراین در
        اجراهای بعدی هرگز با مقدار پیش‌فرض جایگزین نمی‌شود.
        """
        key_str = key.value if isinstance(key, SettingKey) else key
        category = self._category_for(key_str)
        self._repository.set(key_str, value, category=category, user_modified=True)
        with self._lock:
            self._cache[key_str] = value

        if notify and self._event_bus is not None:
            self._event_bus.publish(
                EventType.SETTINGS_CHANGED, {"key": key_str, "value": value}, source="SettingsService"
            )
            if key_str == SettingKey.LANGUAGE.value:
                self._event_bus.publish(EventType.LANGUAGE_CHANGED, {"language": value})
            elif key_str == SettingKey.THEME.value:
                self._event_bus.publish(EventType.THEME_CHANGED, {"theme": value})

    def set_many(self, values: dict[SettingKey | str, Any]) -> None:
        """ذخیره گروهی چند تنظیم (مثلاً هنگام تأیید صفحه تنظیمات)."""
        for key, value in values.items():
            self.set(key, value, notify=False)
        if self._event_bus is not None:
            self._event_bus.publish(
                EventType.SETTINGS_CHANGED, {"bulk": True, "count": len(values)}, source="SettingsService"
            )

    @staticmethod
    def _category_for(key: str) -> str:
        """تشخیص دسته یک کلید تنظیم بر اساس نگاشت تعریف‌شده."""
        for category, keys in SETTING_CATEGORIES.items():
            if key in keys:
                return category
        return key.split(".", 1)[0]

    # ------------------------------------------------------------------
    # میان‌برهای پرکاربرد
    # ------------------------------------------------------------------
    @property
    def language(self) -> Language:
        """زبان فعلی رابط کاربری."""
        raw = str(self.get(SettingKey.LANGUAGE, "fa"))
        try:
            return Language(raw)
        except ValueError:
            return Language.FA

    @property
    def theme(self) -> Theme:
        """پوسته فعلی رابط کاربری."""
        raw = str(self.get(SettingKey.THEME, Theme.GLASS_DARK.value))
        try:
            return Theme(raw)
        except ValueError:
            return Theme.GLASS_DARK

    @property
    def is_first_run_completed(self) -> bool:
        """آیا جادوگر راه‌اندازی اولیه قبلاً کامل شده است؟"""
        return self.get_bool(SettingKey.FIRST_RUN_COMPLETED, False)

    def mark_first_run_completed(self) -> None:
        """علامت‌گذاری پایان موفق جادوگر راه‌اندازی."""
        self.set(SettingKey.FIRST_RUN_COMPLETED, True)

    @property
    def active_exchange(self) -> str:
        """نام صرافی فعال."""
        return str(self.get(SettingKey.ACTIVE_EXCHANGE, "lbank"))

    @property
    def analysis_timeframes(self) -> list[str]:
        """تایم‌فریم‌هایی که در تحلیل چندگانه استفاده می‌شوند."""
        return [str(t) for t in self.get_list(SettingKey.SIGNAL_TIMEFRAMES, ["15m", "1h", "4h", "12h", "1d"])]

    @property
    def timeframe_roles(self) -> dict[str, str]:
        """نگاشت نقش هر تایم‌فریم (ورود، روند کوتاه‌مدت، کلان و ...)."""
        return {str(k): str(v) for k, v in self.get_dict(SettingKey.SIGNAL_TIMEFRAME_ROLES).items()}

    def get_risk_parameters(self) -> RiskParameters:
        """
        ساخت شیء پارامترهای ریسک از روی تنظیمات کاربر.

        موتور ریسک به جای خواندن تک‌تک کلیدها، از این شیء استفاده می‌کند.
        """
        return RiskParameters(
            account_balance=self.get_float(SettingKey.RISK_ACCOUNT_BALANCE, 1000.0),
            risk_percent=self.get_float(SettingKey.RISK_PERCENT, 1.0),
            max_leverage=self.get_int(SettingKey.RISK_MAX_LEVERAGE, 5),
            min_risk_reward=self.get_float(SettingKey.RISK_MIN_RR, 1.5),
            atr_stop_multiplier=self.get_float(SettingKey.RISK_ATR_MULTIPLIER, 1.5),
            max_stop_distance_percent=self.get_float(SettingKey.RISK_MAX_STOP_DISTANCE, 5.0),
        )

    def export_all(self) -> dict[str, Any]:
        """خروجی گرفتن از تمام تنظیمات (برای پشتیبان‌گیری یا عیب‌یابی)."""
        return dict(self._repository.get_all())
