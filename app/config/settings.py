"""
تنظیمات پایه و محیطی نرم‌افزار مبتنی بر Pydantic Settings.

چرا وجود دارد؟
    نشانی‌ها، سطح لاگ و مسیر پایگاه داده نباید در کد Hard-Code شوند. این
    کلاس آن‌ها را از متغیرهای محیطی یا فایل .env می‌خواند و اعتبارسنجی
    می‌کند.

ارتباط با ماژول‌های دیگر:
    Bootstrap از این کلاس برای راه‌اندازی لاگ و پایگاه داده استفاده می‌کند
    و لایه بازار نشانی REST/WebSocket را از اینجا می‌گیرد.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import Language, Theme
from app.core.paths import app_paths


class AppSettings(BaseSettings):
    """
    تنظیمات سطح برنامه که از محیط اجرا خوانده می‌شوند.

    تمام متغیرها با پیشوند CAT_ شناخته می‌شوند تا با متغیرهای محیطی دیگر
    برنامه‌ها تداخل نداشته باشند.
    """

    model_config = SettingsConfigDict(
        env_prefix="CAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- عمومی ---
    app_env: str = Field(default="production", description="محیط اجرا: production یا development")
    log_level: str = Field(default="INFO", description="سطح لاگ‌گیری")
    language: Language = Field(default=Language.FA, description="زبان پیش‌فرض رابط کاربری")
    theme: Theme = Field(default=Theme.GLASS_DARK, description="پوسته پیش‌فرض")

    # --- پایگاه داده ---
    database_url: str = Field(default="", description="نشانی اتصال SQLAlchemy؛ خالی یعنی مسیر پیش‌فرض")

    # --- صرافی LBank ---
    lbank_rest_url: str = Field(default="https://api.lbkex.com", description="نشانی پایه REST صرافی")
    lbank_ws_url: str = Field(default="wss://www.lbkex.net/ws/V2/", description="نشانی WebSocket صرافی")
    lbank_api_key: str = Field(default="", description="کلید API (فقط برای توسعه؛ ترجیحاً از Keyring)")
    lbank_api_secret: str = Field(default="", description="Secret API (فقط برای توسعه)")

    # --- هوش مصنوعی ---
    ollama_base_url: str = Field(default="http://localhost:11434", description="نشانی سرویس محلی Ollama")
    ollama_model: str = Field(default="llama3.1", description="نام مدل محلی پیش‌فرض")
    openai_base_url: str = Field(default="https://api.openai.com/v1", description="نشانی سرویس سازگار با OpenAI")
    openai_api_key: str = Field(default="", description="کلید سرویس سازگار با OpenAI")
    openai_model: str = Field(default="gpt-4o-mini", description="نام مدل سرویس سازگار با OpenAI")

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        """سطح لاگ را به حروف بزرگ تبدیل و اعتبارسنجی می‌کند."""
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            return "INFO"
        return normalized

    @property
    def effective_database_url(self) -> str:
        """
        نشانی نهایی پایگاه داده.

        اگر کاربر مقداری تعیین نکرده باشد، مسیر پیش‌فرض داخل پوشه data
        استفاده می‌شود.
        """
        return self.database_url or app_paths.database_url

    @property
    def is_development(self) -> bool:
        """آیا برنامه در حالت توسعه اجرا می‌شود؟"""
        return self.app_env.lower() in {"development", "dev", "debug"}


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """
    نمونه Singleton تنظیمات برنامه.

    استفاده از حافظه نهان (Cache) باعث می‌شود فایل .env فقط یک بار خوانده
    شود. در تست‌ها می‌توان با get_app_settings.cache_clear() آن را بازنشانی کرد.
    """
    return AppSettings()
