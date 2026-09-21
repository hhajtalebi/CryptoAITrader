"""
نگهداری رازها به‌صورت رمزنگاری‌شده در پایگاه داده.

کاربر خواست کلید و رمز صرافی داخل پایگاه داده بماند تا با تعویض صرافی
خودکار خوانده شود. چون برنامه روی دستگاه شخصی خودش اجرا می‌شود این
پذیرفتنی است، ولی «ذخیره در پایگاه داده» دلیل نمی‌شود مقدار خام نوشته
شود: اگر کسی فایل `.db` را بردارد نباید کلید صرافی را ببیند. پس مقدارها
پیش از نوشتن با Fernet رمز می‌شوند.

کلید رمزنگاری در پایگاه داده **نیست**؛ از مشخصات دستگاه مشتق می‌شود.
یعنی کپی‌کردن فایل پایگاه داده به رایانه‌ای دیگر، رازها را قابل خواندن
نمی‌کند.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
from typing import Any

from app.core.paths import app_paths
from app.exceptions import SecurityError
from app.logging import get_logger
from app.security.secret_store import KEYRING_SERVICE_NAME, SecretStoreBackend

logger = get_logger(__name__)

#: کلیدی که کل نگاشت رازها زیر آن در جدول تنظیمات ذخیره می‌شود
SECRETS_SETTING_KEY = "security.encrypted_secrets"


class DatabaseBackend(SecretStoreBackend):
    """
    پشتوانه‌ای که رازها را رمزنگاری‌شده در جدول تنظیمات نگه می‌دارد.

    مثال:
        backend = DatabaseBackend(settings_repository)
        store = SecretStore(backend)
        store.set_exchange_credentials("lbank", "key", "secret")
    """

    name = "encrypted_database"

    def __init__(self, repository: Any) -> None:
        self._repository = repository
        self._fernet: Any | None = None
        try:
            from cryptography.fernet import Fernet  # noqa: PLC0415

            self._fernet = Fernet(self._derive_key())
        except Exception as exc:  # noqa: BLE001 - نبود کتابخانه نباید برنامه را بخواباند
            logger.error("Database secret backend init failed: %s", exc)

    @staticmethod
    def _derive_key() -> bytes:
        """
        ساخت کلید متقارن از مشخصات دستگاه.

        عمداً همان روش `EncryptedFileBackend` به کار رفته تا رفتار قابل
        پیش‌بینی بماند: راز روی دستگاه سازنده‌اش خوانده می‌شود و بس.
        """
        material = "|".join(
            [
                KEYRING_SERVICE_NAME,
                os.environ.get("USERNAME") or os.environ.get("USER") or "user",
                platform.node() or "host",
                str(app_paths.base_dir),
            ]
        ).encode("utf-8")
        return base64.urlsafe_b64encode(hashlib.sha256(material).digest())

    def is_available(self) -> bool:
        """آیا رمزنگاری و مخزن هر دو آماده‌اند؟"""
        return self._fernet is not None and self._repository is not None

    # ------------------------------------------------------------------
    # خواندن و نوشتن
    # ------------------------------------------------------------------
    def _read_all(self) -> dict[str, str]:
        """خواندن و رمزگشایی نگاشت رازها از پایگاه داده."""
        if self._fernet is None:
            raise SecurityError("Encryption backend is not initialized")
        try:
            raw = self._repository.get(SECRETS_SETTING_KEY)
        except Exception as exc:  # noqa: BLE001
            logger.error("Reading secrets from database failed: %s", type(exc).__name__)
            return {}
        if not raw:
            return {}
        try:
            decrypted = self._fernet.decrypt(str(raw).encode("utf-8"))
            data = json.loads(decrypted.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:  # noqa: BLE001
            # پایگاه داده از دستگاه دیگری آمده یا مقدار خراب است.
            # برنامه باید بدون کلید به کار ادامه دهد، نه اینکه از کار بیفتد.
            logger.error(
                "Stored secrets could not be decrypted (different machine?); treating as empty: %s",
                type(exc).__name__,
            )
            return {}

    def _write_all(self, data: dict[str, str]) -> None:
        """رمزنگاری و نوشتن کل نگاشت رازها."""
        if self._fernet is None:
            raise SecurityError("Encryption backend is not initialized")
        try:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            encrypted = self._fernet.encrypt(payload).decode("utf-8")
            self._repository.set(
                SECRETS_SETTING_KEY, encrypted, category="security", user_modified=False
            )
        except Exception as exc:  # noqa: BLE001
            raise SecurityError("Failed to write secrets to the database") from exc

    def get(self, key: str) -> str | None:
        """خواندن یک راز."""
        return self._read_all().get(key)

    def set(self, key: str, value: str) -> None:
        """نوشتن یک راز."""
        data = self._read_all()
        data[key] = value
        self._write_all(data)

    def delete(self, key: str) -> None:
        """حذف یک راز."""
        data = self._read_all()
        if key in data:
            del data[key]
            self._write_all(data)
