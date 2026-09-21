"""
ربات ساخت APK — نسخهٔ موبایل معامله‌گر هوشمند رمزارز.

یک واقعیت که باید صریح گفته شود:
    **buildozer روی خودِ ویندوز اجرا نمی‌شود.** زنجیرهٔ ساخت اندروید به
    ابزارهای POSIX نیاز دارد. راه رسمی روی ویندوز، WSL است (اوبونتو
    داخل ویندوز). این ربات خودش تشخیص می‌دهد کجاست و اگر روی ویندوز
    باشد، فرمان را داخل WSL اجرا می‌کند.

گام‌ها:
    ۱. بررسی محیط (WSL، جاوا، buildozer)
    ۲. آزمون هم‌ارزی ریاضی موبایل با دسکتاپ — با شکست، ساخت متوقف
    ۳. اجرای buildozer
    ۴. کپی APK در `dist/apk/`

چرا گام ۲ اجباری است؟
    قلب نسخهٔ موبایل یک پیاده‌سازی دوباره از اندیکاتورهاست. اگر این
    ریاضی با دسکتاپ فرق کند، کاربر روی گوشی سیگنالی می‌بیند که روی
    کامپیوتر وجود ندارد — بدترین نوع اشکال، چون بی‌صداست.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOBILE_DIR = PROJECT_ROOT / "mobile"
OUTPUT_DIR = PROJECT_ROOT / "dist" / "apk"


@dataclass
class Step:
    """یک گام از ساخت."""

    name: str
    ok: bool = False
    skipped: bool = False
    detail: str = ""


@dataclass
class ApkReport:
    """نتیجهٔ کامل ساخت."""

    steps: list[Step] = field(default_factory=list)
    apk_path: Path | None = None

    @property
    def succeeded(self) -> bool:
        """آیا هیچ گامی شکست نخورده است؟"""
        return all(step.ok or step.skipped for step in self.steps)


def is_windows() -> bool:
    """آیا روی ویندوز هستیم؟"""
    return platform.system() == "Windows"


def has_wsl() -> bool:
    """آیا WSL در دسترس است؟"""
    if not is_windows():
        return False
    if shutil.which("wsl") is None:
        return False
    try:
        result = subprocess.run(  # noqa: S603
            ["wsl", "--status"], capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def wrap_for_platform(command: list[str], workdir: str) -> list[str]:
    """
    آماده‌سازی فرمان برای محیط جاری.

    روی لینوکس/مک مستقیم اجرا می‌شود؛ روی ویندوز داخل WSL.
    """
    if not is_windows():
        return command
    joined = " ".join(command)
    return ["wsl", "bash", "-lc", f"cd '{workdir}' && {joined}"]


def to_wsl_path(path: Path) -> str:
    """
    تبدیل `D:\\x\\y` به `/mnt/d/x/y` برای استفاده داخل WSL.

    بدون این تبدیل، WSL مسیر ویندوزی را پیدا نمی‌کند و ساخت با خطای
    مبهم «پوشه وجود ندارد» می‌ایستد.
    """
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = str(resolved)[len(resolved.drive) :].replace("\\", "/")
    return f"/mnt/{drive}{rest}" if drive else str(resolved).replace("\\", "/")


def _run(command: list[str], step: Step, cwd: Path | None = None) -> bool:
    """اجرای یک فرمان و ثبت نتیجه."""
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=14400,  # ساخت نخست تا دو ساعت طول می‌کشد.
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        step.detail = f"{exc.__class__.__name__}: {exc}"
        return False
    step.ok = completed.returncode == 0
    if not step.ok:
        output = (completed.stderr or completed.stdout or "").strip().splitlines()
        step.detail = " | ".join(output[-6:])[:600]
    return step.ok


def check_environment(report: ApkReport) -> bool:
    """بررسی اینکه ابزارهای لازم هستند."""
    step = Step("بررسی محیط ساخت")

    if is_windows():
        if not has_wsl():
            step.detail = (
                "buildozer روی ویندوز اجرا نمی‌شود و WSL پیدا نشد. "
                "در PowerShell با دسترسی مدیر اجرا کنید: wsl --install -d Ubuntu "
                "سپس ویندوز را ری‌استارت کنید."
            )
            report.steps.append(step)
            return False
        step.detail = "ویندوز + WSL — ساخت داخل WSL انجام می‌شود"
    else:
        step.detail = f"{platform.system()} — ساخت مستقیم"

    step.ok = True
    report.steps.append(step)
    return True


def verify_math_equivalence(report: ApkReport) -> bool:
    """
    اجرای آزمون هم‌ارزی ریاضی موبایل با دسکتاپ.

    این گام روی همین دستگاه (نه WSL) اجرا می‌شود چون فقط پایتون
    می‌خواهد و سریع است.
    """
    step = Step("آزمون هم‌ارزی ریاضی موبایل با دسکتاپ")
    test_file = PROJECT_ROOT / "tests" / "test_v1912_mobile.py"
    if not test_file.exists():
        step.skipped = True
        step.detail = "فایل آزمون پیدا نشد"
        report.steps.append(step)
        return True

    ok = _run(
        [sys.executable, "-m", "pytest", str(test_file), "-q", "-o", "addopts="],
        step,
        PROJECT_ROOT,
    )
    report.steps.append(step)
    return ok


def build_apk(report: ApkReport, *, release: bool = False, clean: bool = False) -> None:
    """اجرای buildozer."""
    step = Step("ساخت APK با buildozer")
    workdir = to_wsl_path(MOBILE_DIR) if is_windows() else str(MOBILE_DIR)

    if clean:
        clean_step = Step("پاک‌سازی ساخت قبلی")
        clean_step.ok = _run(
            wrap_for_platform(["buildozer", "android", "clean"], workdir),
            clean_step,
            None if is_windows() else MOBILE_DIR,
        )
        report.steps.append(clean_step)

    mode = "release" if release else "debug"
    command = wrap_for_platform(["buildozer", "-v", "android", mode], workdir)
    step.ok = _run(command, step, None if is_windows() else MOBILE_DIR)
    report.steps.append(step)
    if not step.ok:
        return

    collect = Step("جمع‌آوری فایل APK")
    bin_dir = MOBILE_DIR / "bin"
    candidates = sorted(
        bin_dir.glob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        collect.detail = f"هیچ فایل APK در {bin_dir} پیدا نشد"
        report.steps.append(collect)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / candidates[0].name
    shutil.copy2(candidates[0], target)
    report.apk_path = target
    collect.ok = True
    report.steps.append(collect)


def build(*, release: bool = False, clean: bool = False, skip_tests: bool = False) -> ApkReport:
    """زنجیرهٔ کامل ساخت APK."""
    report = ApkReport()

    if not check_environment(report):
        return report

    if skip_tests:
        step = Step("آزمون هم‌ارزی ریاضی موبایل با دسکتاپ")
        step.skipped = True
        step.detail = "با درخواست کاربر رد شد"
        report.steps.append(step)
    elif not verify_math_equivalence(report):
        return report

    build_apk(report, release=release, clean=clean)
    return report


def main() -> int:
    """پوستهٔ خط فرمان."""
    parser = argparse.ArgumentParser(description="ربات ساخت APK")
    parser.add_argument("--release", action="store_true", help="ساخت نسخهٔ انتشار")
    parser.add_argument("--clean", action="store_true", help="پاک‌سازی ساخت قبلی")
    parser.add_argument("--skip-tests", action="store_true", help="رد کردن آزمون‌ها")
    args = parser.parse_args()

    print("=" * 66)
    print("ربات ساخت APK — معامله‌گر هوشمند رمزارز")
    print("=" * 66)
    print()
    if not (MOBILE_DIR / "main.py").exists():
        print(f"خطا: پوشهٔ موبایل پیدا نشد: {MOBILE_DIR}")
        return 1

    skip = args.skip_tests or os.environ.get("SKIP_TESTS") == "1"
    report = build(release=args.release, clean=args.clean, skip_tests=skip)

    for step in report.steps:
        mark = "رد شد" if step.skipped else ("موفق" if step.ok else "شکست")
        print(f"  [{mark}] {step.name}")
        if step.detail:
            print(f"         {step.detail}")

    print()
    if report.apk_path:
        size_mb = report.apk_path.stat().st_size / (1024 * 1024)
        print(f"فایل APK: {report.apk_path}  ({size_mb:.1f} مگابایت)")
        print()
        print("نصب روی گوشی:")
        print("  ۱. فایل را به گوشی منتقل کنید")
        print("  ۲. «نصب از منابع ناشناس» را برای فایل‌منیجر فعال کنید")
        print("  ۳. روی فایل بزنید و نصب کنید")
    else:
        print("APK ساخته نشد. پیام‌های بالا را بخوانید.")
    print("=" * 66)
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
