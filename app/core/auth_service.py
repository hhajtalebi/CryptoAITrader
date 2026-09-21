"""
سرویس احراز هویت و مدیریت کاربر.

مسئولیت‌ها: ثبت‌نام، ورود، خروج، «مرا به خاطر بسپار»، پروفایل، تغییر رمز،
مدیریت نشست و ترجیحات هر کاربر.

طراحی «کاربر مهمان»:
    برنامه بدون ورود هم کار می‌کند. تا وقتی کاربری وارد نشده، حالت مهمان
    فعال است و تنظیمات سراسری به کار می‌رود. به‌محض ورود، ترجیحات همان
    کاربر (پوسته، زبان، منطقه زمانی) بار می‌شود. این‌طور کاربر فعلی که
    نسخهٔ قبلی را بدون حساب استفاده می‌کرده، مجبور به ثبت‌نام نمی‌شود.

قاعدهٔ امنیتی:
    رمز عبور و توکن نشست هرگز لاگ نمی‌شوند و در استثناها منعکس نمی‌گردند.
"""

from __future__ import annotations

import platform
from collections.abc import Callable
from typing import Any

from app.config.settings_service import SettingsService
from app.database.repositories.user_repository import UserRepository
from app.logging import get_logger
from app.security.passwords import generate_token, validate_password

logger = get_logger(__name__)

#: کلید تنظیمی که توکن نشست «مرا به خاطر بسپار» را نگه می‌دارد
SESSION_TOKEN_KEY = "auth.session_token"

#: کلید تنظیمی که آخرین نام کاربری واردشده را نگه می‌دارد (فقط راحتی کاربر)
LAST_USERNAME_KEY = "auth.last_username"

#: ترجیحاتی که کاربر می‌تواند شخصی‌سازی کند
PREFERENCE_KEYS = (
    "ui.theme",
    "ui.language",
    "ui.timezone",
    "ui.font_family",
    "ui.font_scale",
    "ui.compact_mode",
    "ui.show_toman",
    "general.notifications_enabled",
    # نمایش تدریجی پاسخ چت؛ سلیقهٔ کاربر است و باید با حساب او بماند
    "ai.chat_streaming",
    # چیدمان دلخواه کاربر در داشبورد (ترتیب و نمایان‌بودن بخش‌ها)
    "ui.dashboard_layout",
)


class AuthService:
    """
    نقطهٔ واحد احراز هویت.

    نمونه‌سازی:
        auth = AuthService(user_repository, settings_service)
        auth.restore_session()
        auth.login("hossein", "secret", remember=True)
    """

    def __init__(
        self,
        repository: UserRepository,
        settings: SettingsService,
        *,
        on_change: Callable[[dict[str, Any] | None], None] | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._current: dict[str, Any] | None = None
        self._listeners: list[Callable[[dict[str, Any] | None], None]] = []
        if on_change is not None:
            self._listeners.append(on_change)

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    @property
    def current_user(self) -> dict[str, Any] | None:
        """کاربر واردشده، یا `None` در حالت مهمان."""
        return dict(self._current) if self._current else None

    @property
    def is_authenticated(self) -> bool:
        """آیا کاربری وارد شده است؟"""
        return self._current is not None

    @property
    def user_id(self) -> int | None:
        """شناسهٔ کاربر جاری."""
        return int(self._current["id"]) if self._current else None

    @property
    def display_name(self) -> str:
        """
        نام نمایشی برای نوار بالا.

        در حالت مهمان کلید ترجمه برگردانده می‌شود تا رشتهٔ فارسی
        سخت‌کدشده‌ای در سرویس نباشد.
        """
        if self._current:
            return self._current.get("display_name") or self._current.get("username", "")
        return "auth.guest"

    @property
    def has_users(self) -> bool:
        """آیا اصلاً حسابی ساخته شده است؟ (برای نمایش «ثبت‌نام» یا «ورود»)"""
        return self._repository.count_users() > 0

    def add_listener(self, callback: Callable[[dict[str, Any] | None], None]) -> None:
        """
        ثبت شنونده برای تغییر کاربر.

        رابط کاربری با این شنونده نوار بالا، پوسته و داده‌های وابسته به
        کاربر را تازه می‌کند.
        """
        if callback not in self._listeners:
            self._listeners.append(callback)

    # ------------------------------------------------------------------
    # ثبت‌نام و ورود
    # ------------------------------------------------------------------
    def register(
        self,
        username: str,
        password: str,
        *,
        email: str = "",
        display_name: str = "",
        login_after: bool = True,
    ) -> tuple[dict[str, Any] | None, str]:
        """
        ساخت حساب تازه.

        بازگشتی: `(کاربر یا None, کلید ترجمهٔ خطا)`.
        """
        problem = validate_password(password)
        if problem:
            return None, problem
        try:
            user = self._repository.create_user(
                username=username,
                password=password,
                email=email,
                display_name=display_name,
                # نخستین کاربر مدیر است تا بتواند دیگران را مدیریت کند
                is_admin=not self.has_users,
                preferences=self._snapshot_preferences(),
            )
        except ValueError as exc:
            return None, str(exc)

        logger.info("Registration completed for user id=%s", user["id"])
        if login_after:
            self._activate(user, remember=False)
        return user, ""

    def login(
        self, username: str, password: str, *, remember: bool = False
    ) -> tuple[dict[str, Any] | None, str]:
        """
        ورود با نام کاربری و رمز.

        بازگشتی: `(کاربر یا None, کلید ترجمهٔ خطا)`.
        """
        user, error = self._repository.authenticate(username, password)
        if user is None:
            return None, error
        self._activate(user, remember=remember)
        self._settings.set(LAST_USERNAME_KEY, user["username"])
        return user, ""

    def logout(self, *, revoke_all: bool = False) -> None:
        """
        خروج از حساب.

        توکن «مرا به خاطر بسپار» همیشه پاک می‌شود تا اجرای بعدی برنامه
        دوباره وارد نشود.
        """
        if self._current and revoke_all:
            self._repository.revoke_all_sessions(int(self._current["id"]))
        self._settings.set(SESSION_TOKEN_KEY, "")
        previous = self._current
        self._current = None
        if previous:
            logger.info("User logged out: id=%s", previous.get("id"))
        self._notify()

    def restore_session(self) -> dict[str, Any] | None:
        """
        بازیابی نشست ذخیره‌شده هنگام راه‌اندازی برنامه.

        نشست نامعتبر یا منقضی بی‌سروصدا نادیده گرفته می‌شود و برنامه در
        حالت مهمان بالا می‌آید.
        """
        token = str(self._settings.get(SESSION_TOKEN_KEY, "") or "")
        if not token:
            return None
        user = self._repository.resolve_session(token)
        if user is None:
            self._settings.set(SESSION_TOKEN_KEY, "")
            return None
        self._current = user
        self._apply_preferences(user)
        logger.info("Session restored for user id=%s", user["id"])
        self._notify()
        return user

    # ------------------------------------------------------------------
    # پروفایل و امنیت
    # ------------------------------------------------------------------
    def update_profile(self, *, display_name: str | None = None, email: str | None = None) -> bool:
        """به‌روزرسانی پروفایل کاربر جاری."""
        if not self._current:
            return False
        ok = self._repository.update_profile(
            int(self._current["id"]), display_name=display_name, email=email
        )
        if ok:
            refreshed = self._repository.get_user(int(self._current["id"]))
            if refreshed:
                self._current = refreshed
                self._notify()
        return ok

    def change_password(self, current_password: str, new_password: str) -> tuple[bool, str]:
        """
        تغییر رمز عبور کاربر جاری.

        پس از تغییر، همهٔ نشست‌ها باطل و کاربر در همین جلسه فعال می‌ماند
        اما «مرا به خاطر بسپار» بازنشانی می‌شود.
        """
        if not self._current:
            return False, "auth.error.not_authenticated"
        problem = validate_password(new_password)
        if problem:
            return False, problem
        ok, error = self._repository.change_password(
            int(self._current["id"]),
            current_password=current_password,
            new_password=new_password,
        )
        if ok:
            self._settings.set(SESSION_TOKEN_KEY, "")
        return ok, error

    def sessions(self) -> list[dict[str, Any]]:
        """فهرست نشست‌های فعال کاربر جاری."""
        if not self._current:
            return []
        return self._repository.list_sessions(int(self._current["id"]))

    def revoke_session(self, session_id: int) -> bool:
        """باطل‌کردن یک نشست از صفحهٔ امنیت."""
        return self._repository.revoke_session(int(session_id))

    def revoke_other_sessions(self) -> int:
        """خروج از همهٔ دستگاه‌های دیگر."""
        if not self._current:
            return 0
        count = self._repository.revoke_all_sessions(int(self._current["id"]))
        self._settings.set(SESSION_TOKEN_KEY, "")
        return count

    # ------------------------------------------------------------------
    # ترجیحات
    # ------------------------------------------------------------------
    def preference(self, key: str, default: Any = None) -> Any:
        """
        خواندن یک ترجیح.

        اولویت: ترجیح کاربر ← تنظیم سراسری ← مقدار پیش‌فرض. در حالت مهمان
        مستقیم از تنظیمات سراسری خوانده می‌شود.
        """
        if self._current:
            preferences = self._current.get("preferences") or {}
            if key in preferences and preferences[key] is not None:
                return preferences[key]
        return self._settings.get(key, default)

    def set_preference(self, key: str, value: Any) -> None:
        """
        ذخیرهٔ یک ترجیح.

        برای کاربر واردشده در پروفایل او و همیشه در تنظیمات سراسری ذخیره
        می‌شود تا حالت مهمان هم همان ظاهر را داشته باشد.
        """
        self._settings.set(key, value)
        if self._current:
            self._repository.set_preferences(int(self._current["id"]), {key: value})
            preferences = dict(self._current.get("preferences") or {})
            preferences[key] = value
            self._current["preferences"] = preferences

    def set_preferences(self, values: dict[str, Any]) -> None:
        """ذخیرهٔ چند ترجیح یک‌جا."""
        for key, value in (values or {}).items():
            self.set_preference(key, value)

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    def _activate(self, user: dict[str, Any], *, remember: bool) -> None:
        """فعال‌کردن کاربر، ساخت نشست و اعمال ترجیحات."""
        self._current = user
        if remember:
            token = generate_token()
            self._repository.create_session(
                int(user["id"]), token, device_label=self._device_label()
            )
            self._settings.set(SESSION_TOKEN_KEY, token)
        self._apply_preferences(user)
        logger.info("User logged in: id=%s", user["id"])
        self._notify()

    def _apply_preferences(self, user: dict[str, Any]) -> None:
        """
        نوشتن ترجیحات کاربر روی تنظیمات فعال.

        فقط کلیدهای مجاز اعمال می‌شوند تا یک پروفایل نتواند تنظیمات
        حساس (مثلاً ریسک) را بی‌اجازه تغییر دهد.
        """
        preferences = user.get("preferences") or {}
        for key in PREFERENCE_KEYS:
            if key in preferences and preferences[key] is not None:
                self._settings.set(key, preferences[key])

    def _snapshot_preferences(self) -> dict[str, Any]:
        """گرفتن ترجیحات فعلی برنامه برای کاربر تازه‌ساخته."""
        return {key: self._settings.get(key) for key in PREFERENCE_KEYS}

    def _device_label(self) -> str:
        """برچسب دستگاه برای فهرست نشست‌ها."""
        try:
            return f"{platform.system()} {platform.release()}".strip()
        except Exception:  # noqa: BLE001 - برچسب نباید ورود را خراب کند
            return "unknown"

    def _notify(self) -> None:
        """اطلاع به شنوندگان دربارهٔ تغییر کاربر."""
        snapshot = self.current_user
        for callback in list(self._listeners):
            try:
                callback(snapshot)
            except Exception:  # noqa: BLE001 - خطای یک شنونده بقیه را متوقف نکند
                logger.exception("Auth listener failed")


__all__ = ["PREFERENCE_KEYS", "SESSION_TOKEN_KEY", "AuthService"]
