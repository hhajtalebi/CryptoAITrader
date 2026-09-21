"""
ماژول استثناهای اختصاصی نرم‌افزار.

چرا وجود دارد؟
    برای اینکه لایه‌های مختلف بتوانند خطاها را با معنای دقیق منتشر کنند و
    لایه UI بتواند بر اساس «نوع» خطا پیام مناسب و ترجمه‌شده نمایش دهد،
    نه اینکه صرفاً متن خام Exception را چاپ کند.

ارتباط با ماژول‌های دیگر:
    تقریباً همه لایه‌ها از این استثناها استفاده می‌کنند؛ این ماژول هیچ
    وابستگی‌ای به لایه‌های دیگر ندارد تا از ایجاد وابستگی دوری جلوگیری شود.
"""

from app.exceptions.errors import (
    AIError,
    AIProviderError,
    AIResponseValidationError,
    AppError,
    AuthenticationError,
    BackupError,
    ConfigurationError,
    DatabaseError,
    ExchangeError,
    IndicatorError,
    InsufficientDataError,
    NetworkError,
    RateLimitError,
    SecurityError,
    SignalEngineError,
    TimeframeError,
    TimeoutErrorApp,
    ValidationError,
    WebSocketError,
)

__all__ = [
    "AppError",
    "ConfigurationError",
    "DatabaseError",
    "SecurityError",
    "NetworkError",
    "TimeoutErrorApp",
    "RateLimitError",
    "AuthenticationError",
    "ExchangeError",
    "WebSocketError",
    "TimeframeError",
    "IndicatorError",
    "InsufficientDataError",
    "AIError",
    "AIProviderError",
    "AIResponseValidationError",
    "SignalEngineError",
    "BackupError",
    "ValidationError",
]
