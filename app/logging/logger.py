"""
پیکربندی سامانه لاگ‌گیری.

چرا وجود دارد؟
    خطاها باید قابل ردیابی باشند، اما هرگز نباید کلید API یا Secret در
    فایل لاگ نوشته شود. این ماژول هر دو نیاز را هم‌زمان برآورده می‌کند.

ارتباط با ماژول‌های دیگر:
    در ابتدای اجرای برنامه (Bootstrap) یک بار configure_logging فراخوانی
    می‌شود و بقیه ماژول‌ها فقط get_logger(__name__) را صدا می‌زنند.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from pathlib import Path

# سطوح لاگ قابل انتخاب توسط کاربر در تنظیمات
LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-38s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# الگوهایی که نشان‌دهنده داده حساس هستند و باید پنهان شوند.
_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(api[_-]?key\"?\s*[:=]\s*\"?)([A-Za-z0-9\-_.]{6,})", re.IGNORECASE),
    re.compile(r"(secret[_-]?key\"?\s*[:=]\s*\"?)([A-Za-z0-9\-_./+]{6,})", re.IGNORECASE),
    re.compile(r"(api[_-]?secret\"?\s*[:=]\s*\"?)([A-Za-z0-9\-_./+]{6,})", re.IGNORECASE),
    re.compile(r"(secret\"?\s*[:=]\s*\"?)([A-Za-z0-9\-_./+]{6,})", re.IGNORECASE),
    re.compile(r"(sign\"?\s*[:=]\s*\"?)([A-Za-z0-9\-_./+=]{16,})", re.IGNORECASE),
    re.compile(r"(Bearer\s+)([A-Za-z0-9\-_.]{10,})", re.IGNORECASE),
    re.compile(r"(sk-)([A-Za-z0-9\-_]{10,})"),
)

_MASK = "***REDACTED***"


class SensitiveDataFilter(logging.Filter):
    """
    فیلتری که پیش از نوشتن لاگ، مقادیر حساس را با ماسک جایگزین می‌کند.

    این فیلتر هم روی متن پیام و هم روی آرگومان‌های آن اعمال می‌شود، چون
    logging به‌صورت تنبل (Lazy) قالب‌بندی می‌کند و ممکن است مقدار حساس در
    آرگومان‌ها باشد.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """همیشه True برمی‌گرداند؛ فقط محتوای رکورد را پاک‌سازی می‌کند."""
        try:
            if isinstance(record.msg, str):
                record.msg = self.mask(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: self._mask_value(v) for k, v in record.args.items()}
                elif isinstance(record.args, tuple):
                    record.args = tuple(self._mask_value(a) for a in record.args)
        except Exception:  # noqa: BLE001 - خطای فیلتر نباید لاگ را از بین ببرد
            return True
        return True

    @staticmethod
    def mask(text: str) -> str:
        """جایگزینی الگوهای حساس در یک رشته."""
        masked = text
        for pattern in _SENSITIVE_PATTERNS:
            masked = pattern.sub(lambda m: f"{m.group(1)}{_MASK}", masked)
        return masked

    def _mask_value(self, value: object) -> object:
        """پاک‌سازی یک آرگومان در صورتی که رشته باشد."""
        return self.mask(value) if isinstance(value, str) else value


def configure_logging(
    log_file: Path | None = None,
    level: str = "INFO",
    *,
    console: bool = True,
    max_bytes: int = 2 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    پیکربندی لاگر ریشه نرم‌افزار.

    پارامترها:
        log_file     : مسیر فایل لاگ؛ در صورت None فقط کنسول فعال می‌شود.
        level        : سطح لاگ (یکی از LOG_LEVELS).
        console      : نوشتن هم‌زمان روی خروجی استاندارد.
        max_bytes    : حداکثر حجم هر فایل لاگ پیش از چرخش.
        backup_count : تعداد فایل‌های پشتیبان لاگ.

    این تابع «Idempotent» است: فراخوانی مجدد، Handlerهای قبلی را پاک
    می‌کند تا لاگ تکراری تولید نشود.
    """
    normalized_level = level.upper() if level.upper() in LOG_LEVELS else "INFO"
    root = logging.getLogger()
    root.setLevel(getattr(logging, normalized_level))

    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    sensitive_filter = SensitiveDataFilter()

    if console:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.addFilter(sensitive_filter)
        root.addHandler(stream_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root.addHandler(file_handler)

    # کاهش نویز کتابخانه‌های بیرونی که در سطح DEBUG بسیار پرحرف هستند.
    for noisy in ("httpx", "httpcore", "websockets", "urllib3", "asyncio", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root


def get_logger(name: str) -> logging.Logger:
    """
    دریافت یک لاگر نام‌گذاری‌شده برای ماژول جاری.

    استفاده پیشنهادی: logger = get_logger(__name__)
    """
    return logging.getLogger(name)
