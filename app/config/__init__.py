"""
ماژول پیکربندی نرم‌افزار.

دو سطح پیکربندی وجود دارد:
  1) AppSettings   : تنظیمات پایه و محیطی (از فایل .env و متغیرهای محیطی).
  2) SettingsService : تنظیمات کاربر که در پایگاه داده ذخیره و ویرایش می‌شوند.

قانون مهم: مقادیر پیش‌فرض فقط زمانی نوشته می‌شوند که تنظیم موجود نباشد؛
هیچ Migration یا اجرای مجددی نباید تنظیمات کاربر را بازنویسی کند.
"""

from app.config.defaults import DEFAULT_SETTINGS, SettingKey
from app.config.settings import AppSettings, get_app_settings
from app.config.settings_service import SettingsService

__all__ = ["AppSettings", "get_app_settings", "SettingsService", "DEFAULT_SETTINGS", "SettingKey"]
