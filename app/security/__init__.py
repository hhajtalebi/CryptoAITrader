"""
ماژول امنیت: نگهداری امن اطلاعات حساس.

این ماژول تضمین می‌کند کلید API و Secret هرگز به‌صورت متن ساده در پایگاه
داده SQLite ذخیره نشوند. در ویندوز از Credential Manager (که پشت صحنه از
DPAPI استفاده می‌کند) و در نبود آن از یک فایل رمزنگاری‌شده محلی استفاده
می‌شود.
"""

from app.security.passwords import (
    PasswordHash,
    generate_token,
    hash_password,
    hash_token,
    mask_secret,
    needs_rehash,
    password_strength,
    validate_password,
    verify_password,
)
from app.security.secret_store import (
    EncryptedFileBackend,
    KeyringBackend,
    SecretStore,
    SecretStoreBackend,
    get_secret_store,
)

__all__ = [
    "PasswordHash",
    "generate_token",
    "hash_password",
    "hash_token",
    "mask_secret",
    "needs_rehash",
    "password_strength",
    "validate_password",
    "verify_password",
    "SecretStore",
    "SecretStoreBackend",
    "KeyringBackend",
    "EncryptedFileBackend",
    "get_secret_store",
]
