"""
یافتن و راه‌اندازی خودکار اولامای نصب‌شده روی دستگاه — نسخهٔ ۲.۵.۹.

گزارش کاربر: «اولاما هنوز وصل نمی‌شود؛ سیستم باید اولامای روی دستگاه را
شناسایی کند و مدل را اجرا کند.»

دو حالت رایج که پیش‌تر کاربر خودش باید حل می‌کرد:
    ۱. اولاما نصب است ولی سرویسش بالا نیست (برنامهٔ سینی بسته شده، یا
       پس از ری‌استارت هنوز اجرا نشده). حالا فایل اجرایی پیدا و
       `ollama serve` بی‌پنجره اجرا می‌شود.
    ۲. سرویس بالاست ولی مدل در حافظه نیست؛ اولین درخواست تحلیل یا چت
       باید ده‌ها ثانیه منتظر بارگذاری چند گیگابایت بماند و از مهلت
       می‌گذرد. `warm_up` مدل را در پس‌زمینه بارگذاری می‌کند.

همهٔ تابع‌ها بی‌استثنا هستند: نبود اولاما خطای برنامه نیست.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.logging import get_logger

logger = get_logger(__name__)

#: مهلت انتظار برای بالا آمدن سرویس پس از اجرای `ollama serve`
START_WAIT_SECONDS = 20.0
#: فاصلهٔ بررسی سرویس هنگام انتظار
POLL_INTERVAL = 0.5
#: بارگذاری اولیهٔ مدل روی CPU می‌تواند چند دقیقه طول بکشد
WARM_UP_TIMEOUT = 600.0
#: مدت نگه‌داشتن مدل در حافظه (هم‌خوان با ارائه‌دهنده)
KEEP_ALIVE = "30m"

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def is_local_url(base_url: str) -> bool:
    """آیا نشانی به همین دستگاه اشاره می‌کند؟ (فقط اولامای محلی راه‌اندازی می‌شود)"""
    raw = (base_url or "").strip() or "http://127.0.0.1:11434"
    if "://" not in raw:
        raw = f"http://{raw}"
    try:
        host = (urlsplit(raw).hostname or "").lower()
    except ValueError:
        return False
    return host in LOCAL_HOSTS


def candidate_paths() -> list[Path]:
    """مسیرهای نصب پیش‌فرض اولاما روی هر سیستم‌عامل."""
    system = platform.system()
    paths: list[Path] = []
    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            paths.append(Path(local) / "Programs" / "Ollama" / "ollama.exe")
        for root in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramW6432", "")):
            if root:
                paths.append(Path(root) / "Ollama" / "ollama.exe")
        home = os.environ.get("USERPROFILE", "")
        if home:
            paths.append(Path(home) / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe")
    elif system == "Darwin":
        paths += [
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            Path("/usr/local/bin/ollama"),
            Path("/opt/homebrew/bin/ollama"),
        ]
    else:
        paths += [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama"), Path.home() / ".local/bin/ollama"]
    return paths


def find_ollama_executable() -> str:
    """مسیر فایل اجرایی اولاما یا رشتهٔ خالی."""
    found = shutil.which("ollama")
    if found:
        return found
    for path in candidate_paths():
        try:
            if path.is_file():
                return str(path)
        except OSError:
            continue
    return ""


async def service_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """آیا `/api/tags` پاسخ می‌دهد؟"""
    url = (base_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{url}/api/tags")
        return response.status_code < 400
    except (httpx.HTTPError, OSError):
        return False


def start_service(executable: str) -> bool:
    """
    اجرای `ollama serve` به‌صورت جدا از برنامه و بدون پنجره.

    فرایند جدا می‌ماند تا بستن برنامه اولاما را نبندد (کاربر ممکن است در
    ترمینال هم از آن استفاده کند).
    """
    if not executable:
        return False
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if platform.system() == "Windows":
        flags = 0
        for name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
            flags |= int(getattr(subprocess, name, 0))
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([executable, "serve"], **kwargs)  # noqa: S603
    except OSError as exc:
        logger.warning("Could not start Ollama (%s): %s", executable, exc)
        return False
    logger.info("Started Ollama service: %s serve", executable)
    return True


async def ensure_running(base_url: str, *, wait_seconds: float = START_WAIT_SECONDS) -> tuple[bool, str]:
    """
    اطمینان از بالا بودن سرویس محلی اولاما.

    بازگشتی: (بالا است؟، توضیح). نشانی غیرمحلی هرگز راه‌اندازی نمی‌شود.
    """
    url = (base_url or "http://127.0.0.1:11434").rstrip("/")
    if await service_reachable(url):
        return True, "running"
    if not is_local_url(url):
        return False, "remote Ollama is not reachable"
    executable = find_ollama_executable()
    if not executable:
        return False, "Ollama is not installed on this machine (https://ollama.com/download)"
    if not start_service(executable):
        return False, f"Ollama was found at {executable} but could not be started"
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(1.0, wait_seconds)
    while loop.time() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        if await service_reachable(url):
            return True, f"started automatically ({executable})"
    return False, f"Ollama was started ({executable}) but did not answer within {int(wait_seconds)}s"


async def warm_up(base_url: str, model: str, *, timeout: float = WARM_UP_TIMEOUT) -> tuple[bool, float, str]:
    """
    بارگذاری مدل در حافظه بدون تولید متن (درخواست خالی به `/api/generate`).

    بازگشتی: (موفق؟، ثانیه، توضیح خطا).
    """
    url = (base_url or "http://127.0.0.1:11434").rstrip("/")
    if not model:
        return False, 0.0, "no model"
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=3.0)) as client:
            response = await client.post(
                f"{url}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": KEEP_ALIVE, "stream": False},
            )
        elapsed = loop.time() - started
        if response.status_code >= 400:
            try:
                reason = str(response.json().get("error") or "")
            except ValueError:
                reason = response.text[:200]
            return False, elapsed, reason or f"HTTP {response.status_code}"
        return True, elapsed, ""
    except (httpx.HTTPError, OSError) as exc:
        return False, loop.time() - started, exc.__class__.__name__


__all__ = [
    "candidate_paths",
    "ensure_running",
    "find_ollama_executable",
    "is_local_url",
    "service_reachable",
    "start_service",
    "warm_up",
]
