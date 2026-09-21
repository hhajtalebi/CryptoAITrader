"""
مخزن امن اطلاعات حساس (کلید API، Secret و توکن‌ها).

چرا وجود دارد؟
    طبق بند ۹ سند پروژه، کلیدها نباید در SQLite به‌صورت Plain Text ذخیره
    شوند. این ماژول یک واسط یکنواخت ارائه می‌دهد و پیاده‌سازی واقعی را بر
    اساس سیستم‌عامل انتخاب می‌کند (الگوی Strategy).

راهبردهای موجود:
    KeyringBackend        : ویندوز Credential Manager / DPAPI، macOS Keychain،
                            یا Secret Service در لینوکس. گزینه ارجح.
    EncryptedFileBackend  : فایل رمزنگاری‌شده با Fernet؛ زمانی استفاده می‌شود
                            که Keyring در دسترس نباشد (مثلاً سرور بدون
                            نشست گرافیکی).

ارتباط با ماژول‌های دیگر:
    market.providers.* برای دریافت کلید صرافی و ai.providers.* برای دریافت
    کلید سرویس هوش مصنوعی از این ماژول استفاده می‌کنند. هیچ‌کدام نباید
    کلید را در پایگاه داده بنویسند.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import stat
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.core.constants import KEYRING_SERVICE_NAME
from app.core.paths import app_paths
from app.exceptions import SecurityError
from app.logging import get_logger

logger = get_logger(__name__)


class SecretStoreBackend(ABC):
    """
    واسط انتزاعی نگهداری اطلاعات حساس.

    پیاده‌سازی‌ها باید سه عمل خواندن، نوشتن و حذف را پشتیبانی کنند و هرگز
    مقدار واقعی راز را در لاگ ننویسند.
    """

    name: str = "abstract"

    @abstractmethod
    def get(self, key: str) -> str | None:
        """مقدار راز را برمی‌گرداند یا در صورت نبود None."""

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """مقدار راز را ذخیره یا جایگزین می‌کند."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """راز را حذف می‌کند؛ نبودن آن خطا محسوب نمی‌شود."""

    @abstractmethod
    def is_available(self) -> bool:
        """آیا این راهبرد در سیستم فعلی قابل استفاده است؟"""


class KeyringBackend(SecretStoreBackend):
    """
    نگهداری راز در انباره امن سیستم‌عامل از طریق کتابخانه keyring.

    در ویندوز این کار به Credential Manager می‌رسد که داده را با DPAPI و
    مرتبط با حساب کاربری ویندوز رمزنگاری می‌کند؛ یعنی کاربر دیگر سیستم
    نمی‌تواند آن را بخواند.
    """

    name = "keyring"

    def __init__(self, service_name: str = KEYRING_SERVICE_NAME) -> None:
        self._service = service_name
        self._keyring: Any | None = None
        try:
            import keyring  # noqa: PLC0415 - وارد کردن تنبل برای محیط‌های بدون keyring

            backend = keyring.get_keyring()
            backend_name = backend.__class__.__name__
            # backendهای «Fail» یا «Null» عملاً کار نمی‌کنند و نباید انتخاب شوند.
            if "Fail" in backend_name or "Null" in backend_name:
                logger.debug("Keyring backend unusable: %s", backend_name)
            else:
                self._keyring = keyring
                logger.debug("Keyring backend detected: %s", backend_name)
        except Exception as exc:  # noqa: BLE001 - نبود keyring نباید برنامه را متوقف کند
            logger.debug("Keyring unavailable: %s", exc)

    def is_available(self) -> bool:
        """در دسترس بودن انباره امن سیستم‌عامل را بررسی می‌کند."""
        if self._keyring is None:
            return False
        try:
            # یک نوشتن/خواندن/حذف آزمایشی برای اطمینان از کارکرد واقعی.
            probe_key = "__availability_probe__"
            self._keyring.set_password(self._service, probe_key, "1")
            ok = self._keyring.get_password(self._service, probe_key) == "1"
            self._keyring.delete_password(self._service, probe_key)
            return ok
        except Exception as exc:  # noqa: BLE001
            logger.debug("Keyring probe failed: %s", exc)
            return False

    def get(self, key: str) -> str | None:
        """خواندن راز از انباره سیستم‌عامل."""
        if self._keyring is None:
            raise SecurityError("Keyring backend is not available", details={"key": key})
        try:
            return self._keyring.get_password(self._service, key)
        except Exception as exc:  # noqa: BLE001
            raise SecurityError(f"Failed to read secret '{key}' from keyring") from exc

    def set(self, key: str, value: str) -> None:
        """نوشتن راز در انباره سیستم‌عامل."""
        if self._keyring is None:
            raise SecurityError("Keyring backend is not available", details={"key": key})
        try:
            self._keyring.set_password(self._service, key, value)
        except Exception as exc:  # noqa: BLE001
            raise SecurityError(f"Failed to store secret '{key}' in keyring") from exc

    def delete(self, key: str) -> None:
        """حذف راز؛ در صورت نبودِ کلید، خطا نادیده گرفته می‌شود."""
        if self._keyring is None:
            return
        try:
            self._keyring.delete_password(self._service, key)
        except Exception as exc:  # noqa: BLE001 - نبود کلید خطا نیست
            logger.debug("Delete secret '%s' skipped: %s", key, exc)


class EncryptedFileBackend(SecretStoreBackend):
    """
    نگهداری راز در یک فایل رمزنگاری‌شده محلی (راهبرد جایگزین).

    کلید رمزنگاری از ترکیب نام کاربر، نام دستگاه و مسیر نصب مشتق می‌شود.
    این روش به اندازه DPAPI امن نیست و فقط زمانی به کار می‌رود که انباره
    سیستم‌عامل در دسترس نباشد؛ همین موضوع در رابط کاربری به کاربر هشدار
    داده می‌شود.
    """

    name = "encrypted_file"

    def __init__(self, file_path: Path | None = None) -> None:
        self._path = file_path or app_paths.secret_store_file
        self._fernet: Any | None = None
        try:
            from cryptography.fernet import Fernet  # noqa: PLC0415

            self._fernet = Fernet(self._derive_key())
        except Exception as exc:  # noqa: BLE001
            logger.error("Encrypted file backend init failed: %s", exc)

    def _derive_key(self) -> bytes:
        """
        ساخت کلید متقارن ۳۲ بایتی از مشخصات محیط اجرا.

        نکته: این کلید در فایل ذخیره نمی‌شود و هر بار محاسبه می‌گردد.
        """
        material = "|".join(
            [
                KEYRING_SERVICE_NAME,
                os.environ.get("USERNAME") or os.environ.get("USER") or "user",
                platform.node() or "host",
                str(app_paths.base_dir),
            ]
        ).encode("utf-8")
        digest = hashlib.sha256(material).digest()
        return base64.urlsafe_b64encode(digest)

    def is_available(self) -> bool:
        """آیا کتابخانه رمزنگاری بارگذاری شده و آماده است؟"""
        return self._fernet is not None

    def _read_all(self) -> dict[str, str]:
        """خواندن و رمزگشایی کل محتوای فایل رازها."""
        if self._fernet is None:
            raise SecurityError("Encryption backend is not initialized")
        if not self._path.exists():
            return {}
        try:
            raw = self._path.read_bytes()
            if not raw:
                return {}
            decrypted = self._fernet.decrypt(raw)
            data = json.loads(decrypted.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as exc:  # noqa: BLE001
            # فایل خراب یا متعلق به دستگاه دیگر است؛ نباید برنامه از کار بیفتد.
            logger.error("Secret store file unreadable, treating as empty: %s", type(exc).__name__)
            return {}

    def _write_all(self, data: dict[str, str]) -> None:
        """رمزنگاری و نوشتن کل رازها به‌صورت اتمیک."""
        if self._fernet is None:
            raise SecurityError("Encryption backend is not initialized")
        try:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            encrypted = self._fernet.encrypt(payload)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_suffix(".tmp")
            temp_path.write_bytes(encrypted)
            os.replace(temp_path, self._path)
            # محدود کردن دسترسی فایل به کاربر جاری (در سیستم‌های POSIX مؤثر است)
            try:
                self._path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        except SecurityError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SecurityError("Failed to write encrypted secret store") from exc

    def get(self, key: str) -> str | None:
        """خواندن یک راز از فایل رمزنگاری‌شده."""
        return self._read_all().get(key)

    def set(self, key: str, value: str) -> None:
        """نوشتن یک راز در فایل رمزنگاری‌شده."""
        data = self._read_all()
        data[key] = value
        self._write_all(data)

    def delete(self, key: str) -> None:
        """حذف یک راز از فایل رمزنگاری‌شده."""
        data = self._read_all()
        if key in data:
            del data[key]
            self._write_all(data)


class SecretStore:
    """
    نمای بیرونی (Facade) نگهداری رازها.

    این کلاس بهترین راهبرد موجود را انتخاب می‌کند و کلیدها را با فضای‌نام
    مشخص می‌سازد تا کلید صرافی و کلید هوش مصنوعی با هم قاطی نشوند.
    """

    def __init__(self, backend: SecretStoreBackend | None = None) -> None:
        self._backend: SecretStoreBackend = backend or self._select_backend()
        logger.info("Secret store backend in use: %s", self._backend.name)

    @staticmethod
    def _select_backend() -> SecretStoreBackend:
        """
        انتخاب خودکار راهبرد: ابتدا انباره سیستم‌عامل، سپس فایل رمزنگاری‌شده.
        """
        keyring_backend = KeyringBackend()
        if keyring_backend.is_available():
            return keyring_backend
        logger.warning(
            "OS keyring is unavailable; falling back to encrypted local file. "
            "On Windows the OS Credential Manager is expected to be used."
        )
        file_backend = EncryptedFileBackend()
        if not file_backend.is_available():
            raise SecurityError("No usable secret storage backend was found")
        return file_backend

    @property
    def backend_name(self) -> str:
        """نام راهبرد فعال، جهت نمایش در بخش امنیت تنظیمات."""
        return self._backend.name

    @staticmethod
    def make_key(namespace: str, name: str) -> str:
        """ساخت کلید یکتا، مثلاً exchange.lbank.api_key"""
        return f"{namespace}.{name}"

    def get(self, key: str) -> str | None:
        """
        خواندن راز با کلید کامل (مثلاً `exchange.lbank.api_key`).

        میان‌بری برای جاهایی که کلید از قبل به‌صورت کامل ساخته شده و
        تفکیک آن به فضای‌نام و نام، کار را بی‌جهت پیچیده می‌کند.
        """
        try:
            return self._backend.get(key)
        except SecurityError as exc:
            logger.error("Reading secret failed: %s", exc.message)
            return None

    def set(self, key: str, value: str) -> None:
        """نوشتن راز با کلید کامل؛ مقدار خالی یعنی حذف."""
        try:
            if value == "":
                self._backend.delete(key)
            else:
                self._backend.set(key, value)
        except SecurityError as exc:
            logger.error("Writing secret failed: %s", exc.message)

    def delete(self, key: str) -> None:
        """
        حذف راز با کلید کامل.

        قرینهٔ `get`/`set` است تا فراخوان‌هایی که کلید کامل می‌سازند
        (مانند سرویس حساب صرافی) مجبور به تفکیک فضای‌نام نشوند. نبودِ
        کلید خطا نیست.
        """
        try:
            self._backend.delete(key)
        except SecurityError as exc:
            logger.error("Deleting secret failed: %s", exc.message)

    def use_backend(self, backend: SecretStoreBackend) -> None:
        """
        تعویض پشتوانه ذخیره‌سازی در زمان اجرا.

        برای وقتی است که پایگاه داده آماده شده و می‌خواهیم رازها آنجا
        نگهداری شوند، نه در فایل محلی.
        """
        if backend.is_available():
            self._backend = backend
            logger.info("Secret store backend switched to: %s", backend.name)
        else:
            logger.warning("Requested secret backend '%s' is unavailable; keeping %s",
                           backend.name, self._backend.name)

    def get_secret(self, namespace: str, name: str) -> str | None:
        """
        خواندن یک راز.

        در صورت بروز خطای غیرمنتظره، None برمی‌گردد تا برنامه در حالت
        «بدون کلید» به کار خود ادامه دهد (داده عمومی بازار همچنان کار می‌کند).
        """
        try:
            return self._backend.get(self.make_key(namespace, name))
        except SecurityError as exc:
            logger.error("Reading secret failed: %s", exc.message)
            return None

    def set_secret(self, namespace: str, name: str, value: str) -> None:
        """ذخیره یک راز؛ مقدار خالی به معنی حذف راز است."""
        key = self.make_key(namespace, name)
        if value == "":
            self._backend.delete(key)
            return
        self._backend.set(key, value)

    def delete_secret(self, namespace: str, name: str) -> None:
        """حذف یک راز."""
        self._backend.delete(self.make_key(namespace, name))

    def has_secret(self, namespace: str, name: str) -> bool:
        """آیا راز موردنظر ذخیره شده است؟ (بدون افشای مقدار)"""
        return bool(self.get_secret(namespace, name))

    # ---------------- میان‌برهای پرکاربرد ----------------
    def get_exchange_credentials(self, exchange: str) -> tuple[str | None, str | None]:
        """دریافت زوج (کلید، رمز) برای یک صرافی مشخص."""
        namespace = f"exchange.{exchange}"
        return self.get_secret(namespace, "api_key"), self.get_secret(namespace, "api_secret")

    def set_exchange_credentials(self, exchange: str, api_key: str, api_secret: str) -> None:
        """ذخیره زوج (کلید، رمز) یک صرافی."""
        namespace = f"exchange.{exchange}"
        self.set_secret(namespace, "api_key", api_key)
        self.set_secret(namespace, "api_secret", api_secret)

    def get_ai_api_key(self, provider: str) -> str | None:
        """دریافت کلید یک ارائه‌دهنده هوش مصنوعی."""
        return self.get_secret(f"ai.{provider}", "api_key")

    def set_ai_api_key(self, provider: str, api_key: str) -> None:
        """ذخیره کلید یک ارائه‌دهنده هوش مصنوعی."""
        self.set_secret(f"ai.{provider}", "api_key", api_key)


_secret_store: SecretStore | None = None


def get_secret_store() -> SecretStore:
    """
    دریافت نمونه مشترک مخزن رازها (ساخت تنبل در اولین استفاده).
    """
    global _secret_store  # noqa: PLW0603 - Singleton کنترل‌شده
    if _secret_store is None:
        _secret_store = SecretStore()
    return _secret_store
