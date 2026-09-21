"""
مدیریت متمرکز مسیرهای فایل و پوشه‌های نرم‌افزار.

چرا وجود دارد؟
    مسیرها نباید در کد پراکنده و Hard-Code شوند. همچنین در حالت اجرای
    بسته‌شده با PyInstaller، مسیر «کنار فایل اجرایی» با مسیر سورس تفاوت
    دارد و باید یکجا مدیریت شود.

ارتباط با ماژول‌های دیگر:
    Config، Database، Logging، Backup و Reports همگی مسیرها را از اینجا
    می‌گیرند.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """
    مشخص می‌کند برنامه به‌صورت فایل اجرایی (PyInstaller) اجرا شده است یا خیر.
    """
    return bool(getattr(sys, "frozen", False))


def get_base_dir() -> Path:
    """
    پوشه پایه نرم‌افزار را برمی‌گرداند.

    در حالت اجرای معمولی، ریشه پروژه و در حالت بسته‌شده، پوشه کنار فایل
    اجرایی در نظر گرفته می‌شود تا داده‌های کاربر کنار برنامه باقی بمانند.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """
    پوشه داده‌های کاربر (پایگاه داده، لاگ، پشتیبان، خروجی گزارش‌ها).

    امکان بازنویسی با متغیر محیطی CAT_DATA_DIR وجود دارد تا در تست‌ها
    بتوان از پوشه موقت استفاده کرد و داده واقعی کاربر دست‌نخورده بماند.
    """
    override = os.environ.get("CAT_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return get_base_dir() / "data"


class AppPaths:
    """
    نگهدارنده تمام مسیرهای مورد نیاز نرم‌افزار.

    نمونه‌سازی این کلاس هیچ پوشه‌ای نمی‌سازد؛ ساخت پوشه‌ها فقط با فراخوانی
    ensure() انجام می‌شود تا وارد کردن (Import) ماژول عارضه جانبی نداشته باشد.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.base_dir: Path = get_base_dir()
        self.data_dir: Path = data_dir or get_data_dir()

        # زیرپوشه‌های داده
        self.logs_dir: Path = self.data_dir / "logs"
        self.backups_dir: Path = self.data_dir / "backups"
        self.exports_dir: Path = self.data_dir / "exports"
        self.cache_dir: Path = self.data_dir / "cache"

        # فایل‌های کلیدی
        self.database_file: Path = self.data_dir / "crypto_ai_trader.db"
        self.settings_file: Path = self.data_dir / "settings.json"
        self.secret_store_file: Path = self.data_dir / ".secret_store.bin"
        self.log_file: Path = self.logs_dir / "app.log"

        # منابع داخل پروژه (فقط خواندنی)
        self.localization_dir: Path = self.base_dir / "localization"
        self.prompts_dir: Path = self.base_dir / "ai" / "prompts"
        self.docs_dir: Path = self.base_dir / "docs"

    def ensure(self) -> "AppPaths":
        """
        تمام پوشه‌های قابل نوشتن را در صورت نبود ایجاد می‌کند.
        """
        for directory in (
            self.data_dir,
            self.logs_dir,
            self.backups_dir,
            self.exports_dir,
            self.cache_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def database_url(self) -> str:
        """
        نشانی اتصال SQLAlchemy به پایگاه داده SQLite را می‌سازد.
        """
        return f"sqlite:///{self.database_file.as_posix()}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"AppPaths(base_dir={self.base_dir}, data_dir={self.data_dir})"


# نمونه پیش‌فرض برای استفاده ساده در سراسر برنامه.
# توجه: این نمونه پوشه‌ای نمی‌سازد؛ ساخت پوشه‌ها در Bootstrap انجام می‌شود.
app_paths = AppPaths()
