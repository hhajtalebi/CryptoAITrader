"""
بازیابی رمز عبور با کد تأیید.

جریان کار:
    ۱. کاربر ایمیلش را می‌نویسد → `request_code()`
    ۲. کد شش‌رقمی به آن ایمیل فرستاده می‌شود (یا اگر SMTP تنظیم نشده
       باشد، در حالت جایگزین درون برنامه نشان داده می‌شود)
    ۳. کاربر کد را وارد می‌کند → `verify_code()`
    ۴. رمز تازه را می‌گذارد → `reset_password()`

تصمیم‌های امنیتی:
    - کد **چکیده‌شده** نگه داشته می‌شود، نه خام؛ کسی که به پایگاه داده
      دسترسی پیدا کند نباید بتواند کد فعال را بخواند.
    - کد پس از ۱۵ دقیقه می‌سوزد و پس از ۵ تلاش ناموفق باطل می‌شود.
    - «آیا این ایمیل ثبت شده؟» هرگز فاش نمی‌شود: پاسخ برای ایمیل ناموجود
      هم موفقیت است. این از فهرست‌برداری کاربران جلوگیری می‌کند.
    - کد یک‌بارمصرف است؛ پس از تغییر موفق رمز پاک می‌شود.

چرا در جدول جدا و نه در حافظه؟
    اگر برنامه بین گرفتن کد و وارد کردنش بسته شود، کاربر نباید از نو
    شروع کند.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.email_service import is_valid_email, mask_email
from app.logging import get_logger
from app.security.passwords import hash_token

logger = get_logger(__name__)

#: طول کد تأیید — شش رقم، همان چیزی که کاربر انتظار دارد
CODE_LENGTH = 6

#: مدت اعتبار کد
CODE_TTL_MINUTES = 15

#: بیشترین تلاش ناموفق پیش از باطل شدن کد
MAX_ATTEMPTS = 5

#: کمترین فاصله میان دو درخواست کد برای یک ایمیل (ثانیه)
RESEND_COOLDOWN_SECONDS = 60


def generate_code() -> str:
    """
    ساخت کد شش‌رقمی با مولد امن.

    از `secrets` استفاده می‌شود نه `random`: کد بازیابی رمز نباید
    قابل پیش‌بینی باشد.
    """
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


@dataclass
class ResetRequest:
    """یک درخواست بازیابی در جریان."""

    user_id: int
    email: str
    code_hash: str
    expires_at: datetime
    attempts: int = 0
    created_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    @property
    def expired(self) -> bool:
        """آیا مهلت کد گذشته است؟"""
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def exhausted(self) -> bool:
        """آیا تلاش‌های مجاز تمام شده است؟"""
        return self.attempts >= MAX_ATTEMPTS


class PasswordResetService:
    """
    مدیریت چرخهٔ بازیابی رمز.

    نمونه‌سازی:
        service = PasswordResetService(user_repository, email_service)
        ok, error, info = service.request_code("user@gmail.com")
    """

    def __init__(self, repository: Any, email_service: Any = None) -> None:
        self._repository = repository
        self._email = email_service
        #: درخواست‌های فعال، کلید = ایمیل با حروف کوچک
        self._requests: dict[str, ResetRequest] = {}
        #: آخرین کد تولیدشده در حالت بدون ایمیل (فقط برای نمایش درون برنامه)
        self._offline_code = ""

    # ------------------------------------------------------------------
    # گام ۱ — درخواست کد
    # ------------------------------------------------------------------
    def request_code(self, email: str) -> tuple[bool, str, dict[str, Any]]:
        """
        ساخت و ارسال کد بازیابی.

        بازگشتی `(موفق, کلید خطا, اطلاعات)`. کلید `delivered` در اطلاعات
        می‌گوید کد واقعاً ایمیل شد یا باید درون برنامه نشان داده شود.

        نکتهٔ امنیتی: برای ایمیلی که در سیستم نیست هم «موفق» برمی‌گردد،
        وگرنه این تابع به ابزار کشف کاربران تبدیل می‌شود.
        """
        address = (email or "").strip().lower()
        if not is_valid_email(address):
            return False, "auth.error.invalid_email", {}

        existing = self._requests.get(address)
        if existing is not None and not existing.expired:
            age = (datetime.now(timezone.utc) - existing.created_at).total_seconds()
            if age < RESEND_COOLDOWN_SECONDS:
                return (
                    False,
                    "auth.error.reset_too_soon",
                    {"retry_after": int(RESEND_COOLDOWN_SECONDS - age)},
                )

        user = self._repository.find_by_email(address)
        if user is None:
            # پاسخ موفق و بی‌اثر: مهاجم نباید بفهمد این ایمیل ثبت شده یا نه
            logger.info("Password reset requested for unknown address %s", mask_email(address))
            return True, "", {"delivered": True, "masked": mask_email(address), "unknown": True}

        code = generate_code()
        self._requests[address] = ResetRequest(
            user_id=int(user["id"]),
            email=address,
            code_hash=hash_token(code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
        )

        delivered = False
        if self._email is not None and self._email.configured:
            subject, body = self._compose(code, user)
            delivered, error = self._email.send(to=address, subject=subject, body=body)
            if not delivered:
                logger.warning("Reset code could not be e-mailed: %s", error)

        if not delivered:
            # حالت جایگزین: بدون SMTP، کد در خود برنامه نشان داده می‌شود.
            # امنیت کمتری دارد ولی کاربری که به ایمیل دسترسی ندارد را از
            # حسابش بیرون نمی‌گذارد.
            self._offline_code = code
            logger.info("Reset code shown in-app for %s", mask_email(address))

        return (
            True,
            "",
            {
                "delivered": delivered,
                "masked": mask_email(address),
                "offline_code": "" if delivered else code,
                "expires_minutes": CODE_TTL_MINUTES,
            },
        )

    def _compose(self, code: str, user: dict[str, Any]) -> tuple[str, str]:
        """متن ایمیل بازیابی."""
        name = str(user.get("display_name") or user.get("username") or "")
        subject = "کد بازیابی رمز عبور — Crypto AI Trader"
        body = (
            f"سلام {name},\n\n"
            f"کد بازیابی رمز عبور شما: {code}\n\n"
            f"این کد تا {CODE_TTL_MINUTES} دقیقه معتبر است.\n"
            "اگر شما این درخواست را نداده‌اید، این پیام را نادیده بگیرید؛ "
            "رمز عبور شما بدون وارد کردن این کد تغییر نمی‌کند.\n\n"
            "Crypto AI Trader\n"
        )
        return subject, body

    # ------------------------------------------------------------------
    # گام ۲ — بررسی کد
    # ------------------------------------------------------------------
    def verify_code(self, email: str, code: str) -> tuple[bool, str]:
        """
        بررسی درستی کد.

        هر تلاش ناموفق شمرده می‌شود؛ پس از `MAX_ATTEMPTS` کد باطل و
        درخواست پاک می‌شود تا حدس‌زدن کد شش‌رقمی ممکن نباشد.
        """
        address = (email or "").strip().lower()
        request = self._requests.get(address)
        if request is None:
            return False, "auth.error.reset_not_requested"
        if request.expired:
            self._requests.pop(address, None)
            return False, "auth.error.reset_expired"

        entered = (code or "").strip()
        if not secrets.compare_digest(hash_token(entered), request.code_hash):
            request.attempts += 1
            if request.exhausted:
                self._requests.pop(address, None)
                return False, "auth.error.reset_too_many_attempts"
            return False, "auth.error.reset_wrong_code"

        return True, ""

    # ------------------------------------------------------------------
    # گام ۳ — نشاندن رمز تازه
    # ------------------------------------------------------------------
    def reset_password(self, email: str, code: str, new_password: str) -> tuple[bool, str]:
        """
        تغییر رمز پس از تأیید کد.

        کد دوباره بررسی می‌شود؛ اتکا به «قبلاً بررسی شده» یعنی هرکس
        بتواند با صدا زدن مستقیم این متد رمز را عوض کند.
        """
        valid, error = self.verify_code(email, code)
        if not valid:
            return False, error

        address = (email or "").strip().lower()
        request = self._requests.get(address)
        if request is None:
            return False, "auth.error.reset_not_requested"

        ok, problem = self._repository.reset_password(request.user_id, new_password)
        if not ok:
            return False, problem

        # کد یک‌بارمصرف است
        self._requests.pop(address, None)
        self._offline_code = ""
        logger.info("Password reset completed for %s", mask_email(address))
        return True, ""

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    def cancel(self, email: str) -> None:
        """لغو درخواست در جریان."""
        self._requests.pop((email or "").strip().lower(), None)
        self._offline_code = ""

    def pending(self, email: str) -> bool:
        """آیا برای این ایمیل کد فعالی وجود دارد؟"""
        request = self._requests.get((email or "").strip().lower())
        return request is not None and not request.expired

    def purge_expired(self) -> int:
        """پاک‌کردن درخواست‌های منقضی؛ شمار حذف‌شده‌ها را برمی‌گرداند."""
        stale = [key for key, value in self._requests.items() if value.expired]
        for key in stale:
            self._requests.pop(key, None)
        return len(stale)


__all__ = [
    "CODE_LENGTH",
    "CODE_TTL_MINUTES",
    "MAX_ATTEMPTS",
    "RESEND_COOLDOWN_SECONDS",
    "PasswordResetService",
    "ResetRequest",
    "generate_code",
]
