"""
تعریف سلسله‌مراتب استثناهای نرم‌افزار.

همه استثناها از AppError ارث می‌برند تا بتوان در بالاترین سطح، تنها با
گرفتن AppError تمام خطاهای «قابل انتظار» برنامه را مدیریت کرد و از Crash
کامل نرم‌افزار جلوگیری نمود.

هر استثنا دو بخش دارد:
    message     : پیام فنی برای لاگ (انگلیسی، قابل جستجو)
    user_key    : کلید ترجمه برای نمایش به کاربر (فضای‌نام errors)
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """
    کلاس پایه تمام خطاهای نرم‌افزار.

    پارامترها:
        message  : توضیح فنی خطا که در لاگ ثبت می‌شود.
        user_key : کلید ترجمه پیام کاربرپسند (در فایل‌های localization).
        details  : اطلاعات تکمیلی مانند نام Symbol یا کد خطای صرافی.
    """

    default_user_key = "errors.generic"

    def __init__(
        self,
        message: str,
        *,
        user_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.user_key = user_key or self.default_user_key
        self.details: dict[str, Any] = details or {}

    def __str__(self) -> str:  # pragma: no cover - نمایش ساده
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message


# ---------------------------------------------------------------------------
# خطاهای زیرساخت / Infrastructure
# ---------------------------------------------------------------------------
class ConfigurationError(AppError):
    """خطا در خواندن، اعتبارسنجی یا نوشتن پیکربندی نرم‌افزار."""

    default_user_key = "errors.configuration"


class DatabaseError(AppError):
    """خطا در ارتباط با پایگاه داده یا اجرای Query/Migration."""

    default_user_key = "errors.database"


class SecurityError(AppError):
    """خطا در ذخیره یا بازیابی امن اطلاعات حساس (Keyring / DPAPI)."""

    default_user_key = "errors.security"


class BackupError(AppError):
    """خطا در تهیه یا بازگردانی نسخه پشتیبان."""

    default_user_key = "errors.backup"


class ValidationError(AppError):
    """داده ورودی یا خروجی، ساختار مورد انتظار را ندارد."""

    default_user_key = "errors.validation"


# ---------------------------------------------------------------------------
# خطاهای شبکه و صرافی / Network & Exchange
# ---------------------------------------------------------------------------
class NetworkError(AppError):
    """خطای عمومی شبکه؛ شامل قطعی اینترنت و عدم دسترسی به سرور."""

    default_user_key = "errors.network"


class TimeoutErrorApp(NetworkError):
    """درخواست در مهلت تعیین‌شده پاسخ نداد."""

    default_user_key = "errors.timeout"


class RateLimitError(NetworkError):
    """تعداد درخواست‌ها از حد مجاز صرافی عبور کرده است."""

    default_user_key = "errors.rate_limit"


class AuthenticationError(AppError):
    """کلید API نامعتبر است یا امضای درخواست پذیرفته نشد."""

    default_user_key = "errors.authentication"


class ExchangeError(AppError):
    """
    خطای سمت صرافی.

    کد خطای اصلی صرافی در details["error_code"] نگهداری می‌شود تا لایه‌های
    بالاتر بتوانند تصمیم بگیرند که آیا درخواست قابل تکرار (Retry) است یا خیر.
    """

    default_user_key = "errors.exchange"


class TransientExchangeError(ExchangeError):
    """
    خطای گذرای صرافی که تکرار درخواست منطقی است (مثلاً شلوغی موقت سرور).

    فقط این دسته Retry می‌شود. خطاهای دائمی مانند «جفت‌ارز پشتیبانی نمی‌شود»
    از نوع ExchangeError ساده هستند و بی‌درنگ برمی‌گردند تا وقت کاربر تلف نشود.
    """

    default_user_key = "errors.exchange"


class WebSocketError(NetworkError):
    """خطا در برقراری یا نگهداری اتصال WebSocket."""

    default_user_key = "errors.websocket"


# ---------------------------------------------------------------------------
# خطاهای تحلیل / Analysis
# ---------------------------------------------------------------------------
class TimeframeError(AppError):
    """تایم‌فریم درخواستی پشتیبانی نمی‌شود یا قابل ساخت (Aggregate) نیست."""

    default_user_key = "errors.timeframe"


class IndicatorError(AppError):
    """خطا در محاسبه یک اندیکاتور (پارامتر نامعتبر یا داده ناکافی)."""

    default_user_key = "errors.indicator"


class InsufficientDataError(AppError):
    """
    داده کافی برای انجام تحلیل وجود ندارد.

    این خطا بسیار مهم است: طبق قانون پروژه، در نبود داده معتبر نباید تحلیل
    ساختگی تولید شود، بلکه وضعیت INSUFFICIENT_DATA برگردانده می‌شود.
    """

    default_user_key = "errors.insufficient_data"


# ---------------------------------------------------------------------------
# خطاهای هوش مصنوعی و سیگنال / AI & Signal
# ---------------------------------------------------------------------------
class AIError(AppError):
    """خطای عمومی لایه هوش مصنوعی."""

    default_user_key = "errors.ai"


class AIProviderError(AIError):
    """ارائه‌دهنده هوش مصنوعی در دسترس نیست یا پاسخ خطا برگرداند."""

    default_user_key = "errors.ai_provider"


class AIResponseValidationError(AIError):
    """خروجی مدل، JSON معتبر یا مطابق Schema مورد انتظار نبود."""

    default_user_key = "errors.ai_invalid_response"


class SignalEngineError(AppError):
    """خطا در تولید سیگنال معاملاتی."""

    default_user_key = "errors.signal_engine"
