"""
ارسال ایمیل از طریق SMTP کاربر.

چرا SMTP خودِ کاربر؟
    این برنامه یک نرم‌افزار دسکتاپ است و هیچ سرور پشتیبانی ندارد. برای
    فرستادن کد بازیابی، یا باید سرویس ابری اجاره شود (که یعنی وابستگی و
    هزینهٔ دائمی و ارسال ایمیل کاربران به سرور ثالث)، یا خود کاربر حساب
    ایمیلش را وصل کند. راه دوم انتخاب شد: داده جایی نمی‌رود، و کاربر
    ایرانی می‌تواند هر سرویسی را که در دسترسش هست بگذارد.

امنیت:
    رمز SMTP مثل کلید صرافی در انبار رمزنگاری‌شده (`SecretStore`) ذخیره
    می‌شود، نه در جدول تنظیمات. هرگز در گزارش‌ها نوشته یا در رابط کاربری
    نمایش داده نمی‌شود.

نمونهٔ استفاده:
    service = EmailService(settings, secrets)
    ok, error = service.send(
        to="user@gmail.com", subject="کد بازیابی", body="کد شما: 123456"
    )
"""

from __future__ import annotations

import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: فضای‌نام و نام رمز SMTP در انبار امن
SMTP_NAMESPACE = "email"
SMTP_SECRET_KEY = "smtp_password"

#: مهلت اتصال؛ سرور ایمیل کند نباید رابط کاربری را قفل کند
SMTP_TIMEOUT = 20.0

#: تنظیمات آمادهٔ سرویس‌های پرکاربرد تا کاربر دنبال پورت نگردد
SMTP_PRESETS: dict[str, dict[str, Any]] = {
    "gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True},
    "outlook": {"host": "smtp-mail.outlook.com", "port": 587, "tls": True},
    "yahoo": {"host": "smtp.mail.yahoo.com", "port": 587, "tls": True},
    "yandex": {"host": "smtp.yandex.com", "port": 465, "tls": False},
    "chmail": {"host": "mail.chmail.ir", "port": 465, "tls": False},
    "custom": {"host": "", "port": 587, "tls": True},
}

#: الگوی سادهٔ اعتبارسنجی ایمیل — سخت‌گیری بیش از حد، آدرس‌های معتبر را رد می‌کند
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def is_valid_email(address: str) -> bool:
    """آیا نشانی ایمیل شکل درستی دارد؟"""
    return bool(EMAIL_PATTERN.match((address or "").strip()))


def mask_email(address: str) -> str:
    """
    پنهان‌کردن بخش میانی ایمیل برای نمایش امن.

    در صفحهٔ بازیابی رمز باید به کاربر گفته شود کد کجا رفت، ولی نمایش
    کامل نشانی به کسی که پشت دستگاه نشسته و صاحب حساب نیست، نشت اطلاعات
    است. «ho…i@gmail.com» هم راهنماست هم بی‌خطر.
    """
    address = (address or "").strip()
    if "@" not in address:
        return address
    name, _, domain = address.partition("@")
    if len(name) <= 2:
        hidden = name[:1] + "…"
    else:
        hidden = f"{name[:2]}…{name[-1:]}"
    return f"{hidden}@{domain}"


@dataclass(frozen=True)
class SmtpConfig:
    """پیکربندی سرور ایمیل خروجی."""

    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    sender: str = ""
    sender_name: str = ""

    @property
    def configured(self) -> bool:
        """آیا اطلاعات برای ارسال کافی است؟"""
        return bool(self.host and self.port and self.username and self.password)

    @property
    def from_address(self) -> str:
        """نشانی فرستنده؛ اگر جدا وارد نشده باشد همان نام کاربری است."""
        return (self.sender or self.username).strip()


class EmailService:
    """
    ارسال ایمیل با تنظیمات SMTP کاربر.

    این کلاس عمداً هیچ رشتهٔ رابط کاربری نمی‌سازد؛ خطاها کلید ترجمه‌اند تا
    برنامه بتواند پیام را به زبان کاربر نشان دهد.
    """

    def __init__(self, settings: Any, secrets: Any = None) -> None:
        self._settings = settings
        self._secrets = secrets

    # ------------------------------------------------------------------
    # پیکربندی
    # ------------------------------------------------------------------
    def config(self) -> SmtpConfig:
        """خواندن پیکربندی جاری از تنظیمات و انبار رمز."""
        get = self._settings.get
        return SmtpConfig(
            host=str(get("email.smtp_host", "") or "").strip(),
            port=int(get("email.smtp_port", 587) or 587),
            username=str(get("email.smtp_username", "") or "").strip(),
            password=self._password(),
            use_tls=bool(get("email.smtp_tls", True)),
            sender=str(get("email.sender", "") or "").strip(),
            sender_name=str(get("email.sender_name", "") or "").strip(),
        )

    @property
    def configured(self) -> bool:
        """آیا برنامه می‌تواند همین حالا ایمیل بفرستد؟"""
        return self.config().configured

    def _password(self) -> str:
        """خواندن رمز از انبار رمزنگاری‌شده."""
        if self._secrets is None:
            return ""
        try:
            return str(self._secrets.get_secret(SMTP_NAMESPACE, SMTP_SECRET_KEY) or "")
        except Exception:  # noqa: BLE001 - نبودن رمز نباید برنامه را بیندازد
            logger.debug("SMTP password unavailable")
            return ""

    def set_password(self, password: str) -> None:
        """ذخیرهٔ رمز SMTP به‌صورت رمزنگاری‌شده."""
        if self._secrets is None:
            raise RuntimeError("secret store unavailable")
        if password:
            self._secrets.set_secret(SMTP_NAMESPACE, SMTP_SECRET_KEY, password)
        else:
            self._secrets.delete_secret(SMTP_NAMESPACE, SMTP_SECRET_KEY)

    # ------------------------------------------------------------------
    # ارسال
    # ------------------------------------------------------------------
    def send(self, *, to: str, subject: str, body: str) -> tuple[bool, str]:
        """
        فرستادن یک ایمیل ساده.

        بازگشتی `(موفق, کلید خطا)`. استثنا پرتاب نمی‌کند چون فراخوان
        معمولاً داخل یک جریان کاربری است و باید بتواند پیام نشان دهد.
        """
        config = self.config()
        if not config.configured:
            return False, "email.error.not_configured"
        if not is_valid_email(to):
            return False, "email.error.invalid_recipient"

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = (
            formataddr((config.sender_name, config.from_address))
            if config.sender_name
            else config.from_address
        )
        message["To"] = to
        message.set_content(body)

        try:
            self._deliver(config, message)
        except smtplib.SMTPAuthenticationError:
            # پرتکرارترین خطا: کاربر رمز عادی جیمیل را گذاشته، نه App Password
            logger.warning("SMTP authentication failed for %s", mask_email(config.username))
            return False, "email.error.auth"
        except smtplib.SMTPRecipientsRefused:
            return False, "email.error.invalid_recipient"
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("SMTP delivery failed: %s", exc)
            return False, "email.error.connection"

        logger.info("Email sent to %s", mask_email(to))
        return True, ""

    def _deliver(self, config: SmtpConfig, message: EmailMessage) -> None:
        """
        اتصال و تحویل پیام.

        پورت ۴۶۵ از ابتدا رمزنگاری‌شده است (SMTPS) ولی ۵۸۷ با STARTTLS
        ارتقا می‌یابد؛ اشتباه گرفتن این دو، رایج‌ترین علت شکست اتصال است.
        """
        context = ssl.create_default_context()
        if config.port == 465 or not config.use_tls:
            if config.port == 465:
                with smtplib.SMTP_SSL(
                    config.host, config.port, timeout=SMTP_TIMEOUT, context=context
                ) as server:
                    server.login(config.username, config.password)
                    server.send_message(message)
                return

        with smtplib.SMTP(config.host, config.port, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            if config.use_tls:
                server.starttls(context=context)
                server.ehlo()
            server.login(config.username, config.password)
            server.send_message(message)

    def test_connection(self) -> tuple[bool, str]:
        """
        آزمودن تنظیمات بدون فرستادن ایمیل واقعی.

        دکمهٔ «آزمایش اتصال» در تنظیمات از این استفاده می‌کند تا کاربر
        پیش از نیاز واقعی بفهمد رمز درست است یا نه.
        """
        config = self.config()
        if not config.configured:
            return False, "email.error.not_configured"
        try:
            context = ssl.create_default_context()
            if config.port == 465:
                with smtplib.SMTP_SSL(
                    config.host, config.port, timeout=SMTP_TIMEOUT, context=context
                ) as server:
                    server.login(config.username, config.password)
            else:
                with smtplib.SMTP(config.host, config.port, timeout=SMTP_TIMEOUT) as server:
                    server.ehlo()
                    if config.use_tls:
                        server.starttls(context=context)
                        server.ehlo()
                    server.login(config.username, config.password)
        except smtplib.SMTPAuthenticationError:
            return False, "email.error.auth"
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("SMTP test failed: %s", exc)
            return False, "email.error.connection"
        return True, ""


__all__ = [
    "EMAIL_PATTERN",
    "SMTP_NAMESPACE",
    "SMTP_PRESETS",
    "SMTP_SECRET_KEY",
    "EmailService",
    "SmtpConfig",
    "is_valid_email",
    "mask_email",
]
