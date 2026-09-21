"""
لایه پشتیبان‌گیری و بازیابی.

طبق بند ۳۶ سند پروژه، پیش از هر مهاجرت پایگاه داده باید پشتیبان خودکار
گرفته شود و کاربر باید بتواند هر زمان نسخه پشتیبان بسازد یا بازگرداند.
"""

from backup.manager import BackupManager, BackupInfo

__all__ = ["BackupManager", "BackupInfo"]
