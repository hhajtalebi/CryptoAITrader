"""
چکیده‌سازی و راستی‌آزمایی رمز عبور.

روش: PBKDF2-HMAC-SHA256 با نمک تصادفی ۱۶ بایتی و ۳۹۰٬۰۰۰ تکرار
(هم‌راستا با توصیهٔ OWASP برای SHA-256).

چرا PBKDF2 و نه bcrypt/argon2؟
    PBKDF2 در کتابخانهٔ استاندارد پایتون هست و هیچ وابستگی باینری تازه‌ای
    به بستهٔ ویندوزی اضافه نمی‌کند. تعداد تکرار در خود رکورد ذخیره می‌شود،
    پس در آینده می‌توان آن را بالا برد بدون آنکه رمزهای موجود باطل شوند.

قاعدهٔ امنیتی:
    رمز عبور هرگز لاگ، چاپ یا در استثناها منعکس نمی‌شود.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass

#: الگوریتم پیش‌فرض
DEFAULT_ALGORITHM = "pbkdf2_sha256"

#: تعداد تکرار پیش‌فرض
DEFAULT_ITERATIONS = 390_000

#: طول نمک به بایت
SALT_BYTES = 16

#: کمینهٔ طول رمز عبور
MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class PasswordHash:
    """نتیجهٔ چکیده‌سازی: مقادیر آمادهٔ ذخیره در جدول `users`."""

    hash_value: str
    salt: str
    iterations: int
    algorithm: str = DEFAULT_ALGORITHM


def hash_password(
    password: str,
    *,
    salt: str | None = None,
    iterations: int = DEFAULT_ITERATIONS,
) -> PasswordHash:
    """
    ساخت چکیدهٔ رمز عبور.

    پارامترها:
        password: رمز خام کاربر.
        salt: نمک هگزادسیمال؛ در حالت عادی خالی می‌ماند تا تصادفی ساخته شود.
        iterations: تعداد تکرار PBKDF2.

    بازگشتی: شیء `PasswordHash` برای ذخیره در پایگاه داده.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("رمز عبور نمی‌تواند خالی باشد")

    salt_hex = salt or secrets.token_hex(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations
    )
    return PasswordHash(
        hash_value=derived.hex(),
        salt=salt_hex,
        iterations=iterations,
        algorithm=DEFAULT_ALGORITHM,
    )


def verify_password(
    password: str,
    *,
    hash_value: str,
    salt: str,
    iterations: int = DEFAULT_ITERATIONS,
    algorithm: str = DEFAULT_ALGORITHM,
) -> bool:
    """
    راستی‌آزمایی رمز عبور در برابر چکیدهٔ ذخیره‌شده.

    مقایسه با `hmac.compare_digest` انجام می‌شود تا حمله زمان‌سنجی ممکن
    نباشد. هر ورودی نامعتبر به‌جای استثنا، «نادرست» برمی‌گرداند تا پیام
    خطا اطلاعاتی لو ندهد.
    """
    if not password or not hash_value or not salt:
        return False
    if algorithm != DEFAULT_ALGORITHM:
        return False
    try:
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, hash_value)


def needs_rehash(iterations: int, algorithm: str = DEFAULT_ALGORITHM) -> bool:
    """
    آیا چکیده با معیارهای امروز ساخته شده است؟

    اگر نه، پس از ورود موفق باید دوباره چکیده‌سازی شود.
    """
    return algorithm != DEFAULT_ALGORITHM or int(iterations or 0) < DEFAULT_ITERATIONS


def password_strength(password: str) -> tuple[int, str]:
    """
    سنجش قدرت رمز عبور.

    بازگشتی: `(امتیاز ۰ تا ۴, کلید ترجمه)`. کلید ترجمه در رابط کاربری به
    متن محلی تبدیل می‌شود تا رشتهٔ سخت‌کدشده‌ای در اینجا نباشد.
    """
    if not password:
        return 0, "auth.strength.empty"

    score = 0
    if len(password) >= MIN_PASSWORD_LENGTH:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[A-Z]", password) and re.search(r"[a-z]", password):
        score += 1
    if re.search(r"\d", password) and re.search(r"[^\w\s]", password):
        score += 1

    key = {
        0: "auth.strength.very_weak",
        1: "auth.strength.weak",
        2: "auth.strength.fair",
        3: "auth.strength.good",
        4: "auth.strength.strong",
    }[score]
    return score, key


def validate_password(password: str) -> str | None:
    """
    بررسی حداقل‌های پذیرش رمز.

    بازگشتی: کلید ترجمهٔ خطا، یا `None` اگر رمز پذیرفته شود.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return "auth.error.password_too_short"
    if password.isdigit() or password.isalpha():
        return "auth.error.password_too_simple"
    return None


def generate_token(length: int = 32) -> str:
    """ساخت توکن تصادفی امن برای نشست کاربر."""
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """
    چکیدهٔ توکن نشست.

    خود توکن ذخیره نمی‌شود تا دسترسی به پایگاه داده امکان جعل نشست ندهد.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def mask_secret(value: str, *, visible: int = 4) -> str:
    """
    پوشاندن یک مقدار حساس برای نمایش.

    نمونه: ``abcd••••wxyz``. مقدارهای کوتاه کاملاً پوشانده می‌شوند تا
    چیزی لو نرود.
    """
    if not value:
        return ""
    text = str(value)
    if len(text) <= visible * 2:
        return "•" * len(text)
    return f"{text[:visible]}{'•' * 8}{text[-visible:]}"


__all__ = [
    "DEFAULT_ALGORITHM",
    "DEFAULT_ITERATIONS",
    "MIN_PASSWORD_LENGTH",
    "PasswordHash",
    "generate_token",
    "hash_password",
    "hash_token",
    "mask_secret",
    "needs_rehash",
    "password_strength",
    "validate_password",
    "verify_password",
]
