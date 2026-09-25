"""
ابزار مشترک ربات‌های ساخت (فایل نصبی ویندوز و APK) — نسخهٔ ۲.۵.۳.

دو مشکل گزارش‌شدهٔ کاربر ریشهٔ مشترک داشتند:
    * خروجی هر گام با `capture_output=True` پنهان می‌شد: کاربر ده‌ها دقیقه
      صفحهٔ ساکت می‌دید و در پایان فقط «ساخت نشد» — بدون علت واقعی
      (فقط ۴ تا ۶ خط آخر، که اغلب علت را نداشت).
    * هیچ فایل گزارشی نمی‌ماند که بشود فرستاد.

`run_streaming` خروجی را **همان لحظه** در کنسول نشان می‌دهد، همه را در
فایل گزارش می‌نویسد و چند خط آخر را برای خلاصهٔ پایانی نگه می‌دارد.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
#: پوشهٔ گزارش‌های ساخت؛ بیرون از build/ و dist/ که هر بار پاک می‌شوند.
LOG_DIR = PROJECT_ROOT / "build_logs"


def open_log(name: str) -> tuple[Path, IO[str]]:
    """ساخت فایل گزارش تازه با مهر زمانی (`build_logs/<name>-YYYYmmdd-HHMMSS.log`)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.log"
    return path, path.open("w", encoding="utf-8", errors="replace")


def headless_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """
    محیط اجرای آزمون/بررسی بدون پنجره.

    بدون `QT_QPA_PLATFORM=offscreen` هر آزمون رابط کاربری روی ویندوز یک
    پنجرهٔ واقعی باز می‌کند — همان «تعداد زیادی پنجره از بخش‌های مختلف
    نرم‌افزار» که کاربر دید. استخر فرایند هم خاموش می‌شود.
    """
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["CRYPTOAI_NO_PROCESS_POOL"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONUTF8", "1")
    if extra:
        env.update(extra)
    return env


def run_streaming(
    command: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    log: IO[str] | None = None,
    timeout: float | None = None,
    tail_lines: int = 12,
    echo: bool = True,
) -> tuple[int, list[str]]:
    """
    اجرای فرمان با نمایش زندهٔ خروجی.

    خروجی: (کد بازگشت، چند خط آخر). اگر فرمان پیدا نشود کد ۱۲۷ و اگر از
    مهلت بگذرد کد ۱۲۴ برمی‌گردد — هرگز استثنا به بیرون نمی‌رود تا خلاصهٔ
    پایانی همیشه چاپ شود.
    """
    tail: deque[str] = deque(maxlen=max(1, tail_lines))

    def emit(line: str) -> None:
        tail.append(line)
        if echo:
            try:
                print(f"   | {line}", flush=True)
            except UnicodeEncodeError:
                print(f"   | {line.encode('ascii', 'replace').decode()}", flush=True)
        if log is not None:
            log.write(line + "\n")
            log.flush()

    if log is not None:
        log.write(f"\n$ {' '.join(str(part) for part in command)}\n")
        log.flush()
    try:
        process = subprocess.Popen(  # noqa: S603
            [str(part) for part in command],
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env is not None else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        emit(f"{exc.__class__.__name__}: {exc}")
        return 127, list(tail)

    timed_out = threading.Event()

    def _kill() -> None:
        timed_out.set()
        process.kill()

    timer = threading.Timer(timeout, _kill) if timeout else None
    if timer is not None:
        timer.daemon = True
        timer.start()
    try:
        assert process.stdout is not None
        for raw in process.stdout:
            emit(raw.rstrip("\r\n"))
        code = process.wait()
    finally:
        if timer is not None:
            timer.cancel()
    if timed_out.is_set():
        emit(f"[مهلت {int(timeout or 0)} ثانیه تمام شد و فرمان متوقف شد]")
        return 124, list(tail)
    return code, list(tail)


def summarize(lines: Sequence[str], limit: int = 600) -> str:
    """خلاصهٔ یک‌خطی چند خط آخر برای گزارش پایانی."""
    useful = [line.strip() for line in lines if line.strip()]
    return " | ".join(useful[-6:])[:limit]
