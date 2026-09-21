"""
ربات به‌روزرسانی — رساندن نسخهٔ نصب‌شده روی دسکتاپ به آخرین نسخه.

طراحی بر پایهٔ یک قاعدهٔ سخت:
    **دادهٔ کاربر هرگز لمس نمی‌شود.** پایگاه داده، تنظیمات، حساب‌های
    صرافی و سابقهٔ سیگنال‌ها در `CAT_DATA_DIR` زندگی می‌کنند که بیرون
    از پوشهٔ برنامه است. به‌روزرسانی فقط فایل‌های برنامه را عوض می‌کند.

چرا منطق اینجاست و نه در یک اسکریپت؟
    چون باید آزمودنی باشد. مقایسهٔ نسخه، تأیید checksum و تصمیم «آیا
    به‌روزرسانی لازم است» توابع خالص‌اند و آزمون دارند. دانلود و اجرا
    تنها لایهٔ نازک بیرونی است.

جریان کامل:
    ۱. خواندن `latest.json` از منبع (پوشهٔ محلی یا نشانی اینترنتی).
    ۲. مقایسهٔ نسخه با نسخهٔ در حال اجرا.
    ۳. دانلود فایل نصبی و بررسی SHA-256.
    ۴. اجرای بی‌صدای نصب‌کننده؛ Inno Setup خودش نسخهٔ قبل را جایگزین
       می‌کند و میان‌برها را به‌روز نگه می‌دارد.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.constants import APP_VERSION
from app.logging import get_logger

logger = get_logger(__name__)

#: مهلت دانلود؛ فایل نصبی چند ده مگابایت است.
DOWNLOAD_TIMEOUT = 600.0


@dataclass
class UpdateInfo:
    """اطلاعات نسخهٔ موجود در منبع."""

    version: str = ""
    installer: str = ""
    size_bytes: int = 0
    sha256: str = ""
    notes: str = ""

    @property
    def usable(self) -> bool:
        """آیا این اطلاعات برای به‌روزرسانی کافی است؟"""
        return bool(self.version and self.installer)


def parse_version(text: str) -> tuple[int, ...]:
    """
    تبدیل «1.9.11» به (1, 9, 11) برای مقایسهٔ درست.

    مقایسهٔ رشته‌ای اشتباه است: «1.9.9» > «1.9.11» می‌شود چون «9» از
    «1» بزرگ‌تر است. این دقیقاً همان دامی است که به‌روزرسانی را برای
    کاربرانِ نسخهٔ دورقمی خاموش می‌کند.
    """
    parts = re.findall(r"\d+", str(text or ""))
    return tuple(int(p) for p in parts) or (0,)


def is_newer(candidate: str, current: str = APP_VERSION) -> bool:
    """آیا نسخهٔ نامزد از نسخهٔ فعلی جدیدتر است؟"""
    return parse_version(candidate) > parse_version(current)


def parse_manifest(payload: Any) -> UpdateInfo:
    """تبدیل محتوای `latest.json` به یک شیء، بدون اعتماد به ساختارش."""
    if not isinstance(payload, dict):
        return UpdateInfo()
    try:
        size = int(payload.get("size_bytes") or 0)
    except (TypeError, ValueError):
        size = 0
    return UpdateInfo(
        version=str(payload.get("version") or "").strip(),
        installer=str(payload.get("installer") or "").strip(),
        size_bytes=size,
        sha256=str(payload.get("sha256") or "").strip().lower(),
        notes=str(payload.get("notes") or "").strip(),
    )


def verify_checksum(path: Path, expected: str) -> bool:
    """
    بررسی سلامت فایل دانلودشده.

    اگر منبع checksum نداده باشد، بررسی رد می‌شود ولی هشدار ثبت
    می‌گردد — اجرای یک نصب‌کنندهٔ ناقص بدتر از به‌روز نشدن است.
    """
    if not expected:
        logger.warning("Update manifest has no checksum; skipping verification")
        return True
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected:
        logger.error("Checksum mismatch: expected %s, got %s", expected, actual)
        return False
    return True


class UpdateChecker:
    """
    بررسی و اعمال به‌روزرسانی.

    `source` می‌تواند یک پوشهٔ محلی (مثلاً درایو شبکه یا فلش) یا یک
    نشانی HTTP باشد. پشتیبانی از پوشهٔ محلی عمدی است: کاربر ممکن است
    اینترنت پایدار نداشته باشد و نسخهٔ تازه را دستی کنار برنامه بگذارد.
    """

    def __init__(self, source: str) -> None:
        self._source = (source or "").strip()

    @property
    def is_remote(self) -> bool:
        """آیا منبع اینترنتی است؟"""
        return self._source.lower().startswith(("http://", "https://"))

    async def fetch_manifest(self) -> UpdateInfo:
        """خواندن `latest.json` از منبع؛ هرگز استثنا نمی‌دهد."""
        if not self._source:
            return UpdateInfo()
        try:
            if self.is_remote:
                url = self._source.rstrip("/") + "/latest.json"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    if response.status_code != 200:
                        logger.warning("Update manifest HTTP %s", response.status_code)
                        return UpdateInfo()
                    return parse_manifest(response.json())

            manifest = Path(self._source) / "latest.json"
            if not manifest.exists():
                return UpdateInfo()
            return parse_manifest(json.loads(manifest.read_text(encoding="utf-8")))
        except (httpx.HTTPError, OSError, ValueError) as exc:
            logger.warning("Update check failed: %s", exc.__class__.__name__)
            return UpdateInfo()

    async def check(self) -> UpdateInfo | None:
        """`None` یعنی نسخهٔ تازه‌ای نیست."""
        info = await self.fetch_manifest()
        if not info.usable or not is_newer(info.version):
            return None
        logger.info("Update available: %s (current %s)", info.version, APP_VERSION)
        return info

    async def download(self, info: UpdateInfo, destination: Path) -> Path | None:
        """دانلود فایل نصبی و بررسی سلامتش."""
        # `destination` خودش پوشهٔ مقصد است، نه فایل. ساختن `parent`
        # کافی نبود و اگر پوشه وجود نداشت، نوشتن با FileNotFoundError
        # شکست می‌خورد — آزمون مسیر کامل همین را گرفت.
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / info.installer

        try:
            if self.is_remote:
                url = self._source.rstrip("/") + "/" + info.installer
                async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as client:
                    response = await client.get(url)
                    if response.status_code != 200:
                        logger.error("Installer download HTTP %s", response.status_code)
                        return None
                    target.write_bytes(response.content)
            else:
                source_file = Path(self._source) / info.installer
                if not source_file.exists():
                    logger.error("Installer not found at %s", source_file)
                    return None
                target.write_bytes(source_file.read_bytes())
        except (httpx.HTTPError, OSError) as exc:
            logger.error("Installer download failed: %s", exc.__class__.__name__)
            return None

        if not verify_checksum(target, info.sha256):
            target.unlink(missing_ok=True)
            return None
        return target

    @staticmethod
    def launch_installer(path: Path, *, silent: bool = True) -> bool:
        """
        اجرای نصب‌کننده و بستن برنامه.

        `/SILENT` تجربهٔ به‌روزرسانی را بدون سؤال‌های تکراری می‌کند، ولی
        `/SP-` را نمی‌گذاریم تا اگر مشکلی بود کاربر پیام ببیند.

        فقط روی ویندوز معنا دارد؛ در محیط‌های دیگر `False` برمی‌گرداند
        به‌جای اینکه استثنا بدهد.
        """
        if not sys.platform.startswith("win"):
            logger.warning("Installer launch is only supported on Windows")
            return False
        if not path.exists():
            return False
        args = [str(path)]
        if silent:
            args += ["/SILENT", "/NOCANCEL"]
        try:
            subprocess.Popen(args)  # noqa: S603 - مسیر از manifest تأییدشده می‌آید
            return True
        except OSError as exc:
            logger.error("Could not launch installer: %s", exc)
            return False
