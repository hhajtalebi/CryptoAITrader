"""
عیب‌یاب سازنده‌ها — می‌گوید دقیقاً چه چیزی کم است.

چرا این ابزار لازم شد؟
    سه بار پشت سر هم دربارهٔ ویندوز حدس زدم و هر سه بار اشتباه بود.
    من ویندوز ندارم و نمی‌توانم ببینم روی دستگاه شما چه می‌گذرد. پس
    به‌جای حدس چهارم، این برنامه **خود دستگاه را می‌پرسد** و یک گزارش
    می‌دهد.

هر بررسی سه چیز دارد: نام، نتیجه، و اگر ناموفق بود **دقیقاً چه باید
کرد**. پیام «خطا رخ داد» بی‌فایده است.

اجرا:
    python tools\\build_doctor.py
یا دوبار کلیک روی:
    scripts\\doctor.bat
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OK = "موفق"
FAIL = "ناموفق"
WARN = "هشدار"


@dataclass
class Check:
    """نتیجهٔ یک بررسی."""

    name: str
    status: str = FAIL
    detail: str = ""
    fix: str = ""


@dataclass
class DoctorReport:
    """گزارش کامل."""

    checks: list[Check] = field(default_factory=list)

    @property
    def failures(self) -> list[Check]:
        """بررسی‌های ناموفق، به ترتیب."""
        return [check for check in self.checks if check.status == FAIL]

    @property
    def healthy(self) -> bool:
        """آیا همه‌چیز آمادهٔ ساخت است؟"""
        return not self.failures

    @property
    def first_problem(self) -> Check | None:
        """
        نخستین مشکل — معمولاً علت اصلی است.

        بقیهٔ خطاها اغلب نتیجهٔ همین یکی‌اند؛ نمایش همه با هم کاربر را
        سردرگم می‌کند.
        """
        problems = self.failures
        return problems[0] if problems else None


def _run(command: list[str], timeout: int = 60) -> tuple[bool, str]:
    """اجرای یک فرمان؛ خروجی کوتاه‌شده برمی‌گردد."""
    try:
        completed = subprocess.run(  # noqa: S603
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return False, "فرمان پیدا نشد"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{exc.__class__.__name__}: {exc}"
    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode == 0, output.splitlines()[0] if output else ""


def check_python(report: DoctorReport) -> None:
    """پایتون باید ۳٫۱۱ یا بالاتر باشد."""
    check = Check("نسخهٔ پایتون")
    version = sys.version_info
    check.detail = f"{version.major}.{version.minor}.{version.micro} — {sys.executable}"
    if (version.major, version.minor) >= (3, 11):
        check.status = OK
    else:
        check.fix = "پایتون ۳٫۱۱ یا بالاتر را از python.org نصب کنید."
    report.checks.append(check)


def check_platform(report: DoctorReport) -> None:
    """ثبت سیستم‌عامل — بقیهٔ بررسی‌ها به آن وابسته‌اند."""
    check = Check("سیستم‌عامل", status=OK)
    check.detail = f"{platform.system()} {platform.release()} ({platform.machine()})"
    if platform.system() != "Windows":
        check.status = WARN
        check.detail += " — سازندهٔ ویندوز فقط روی ویندوز کار می‌کند"
    report.checks.append(check)


def check_dependencies(report: DoctorReport) -> None:
    """بسته‌های لازم باید نصب باشند."""
    check = Check("وابستگی‌های پایتون")
    missing: list[str] = []
    for module in ("PySide6", "sqlalchemy", "pandas", "httpx"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        check.detail = "نصب‌نشده: " + "، ".join(missing)
        check.fix = "اجرا کنید: pip install -r requirements.txt"
    else:
        check.status = OK
        check.detail = "همهٔ بسته‌های اصلی نصب‌اند"
    report.checks.append(check)


def check_pyinstaller(report: DoctorReport) -> None:
    """PyInstaller فایل اجرایی را می‌سازد."""
    check = Check("PyInstaller")
    module_ok, _ = _run([sys.executable, "-m", "PyInstaller", "--version"])
    script = shutil.which("pyinstaller")
    if module_ok:
        check.status = OK
        check.detail = "به‌صورت ماژول در دسترس است"
    elif script:
        check.status = OK
        check.detail = f"فقط به‌صورت اسکریپت: {script}"
    else:
        check.detail = "پیدا نشد"
        check.fix = "اجرا کنید: pip install pyinstaller"
    report.checks.append(check)


def check_spec_file(report: DoctorReport) -> None:
    """بدون فایل spec، PyInstaller نمی‌داند چه بسازد."""
    check = Check("فایل CryptoAITrader.spec")
    spec = PROJECT_ROOT / "CryptoAITrader.spec"
    if spec.exists():
        check.status = OK
        check.detail = str(spec)
    else:
        check.detail = "پیدا نشد"
        check.fix = "فایل از آرشیو حذف شده؛ نسخهٔ کامل را دوباره باز کنید."
    report.checks.append(check)


def check_inno_setup(report: DoctorReport) -> None:
    """Inno Setup فایل نصبی می‌سازد."""
    check = Check("Inno Setup (ISCC)")
    try:
        from tools.build_installer import find_iscc

        found = find_iscc()
    except ImportError:
        found = None
    if found:
        check.status = OK
        check.detail = found
    else:
        check.status = WARN if platform.system() != "Windows" else FAIL
        check.detail = "پیدا نشد"
        check.fix = (
            "Inno Setup 6 را از https://jrsoftware.org/isdl.php نصب کنید. "
            "بدون آن فقط فایل اجرایی ساخته می‌شود، نه فایل نصبی."
        )
    report.checks.append(check)


def check_wsl(report: DoctorReport) -> None:
    """WSL برای ساخت APK لازم است."""
    check = Check("WSL (برای ساخت APK)")
    if platform.system() != "Windows":
        check.status = WARN
        check.detail = "روی ویندوز نیستیم"
        report.checks.append(check)
        return
    if shutil.which("wsl") is None:
        check.detail = "فرمان wsl پیدا نشد"
        check.fix = (
            "در PowerShell با دسترسی مدیر: wsl --install -d Ubuntu "
            "سپس ویندوز را ری‌استارت کنید."
        )
    else:
        ok, output = _run(["wsl", "--status"], timeout=45)
        if ok:
            check.status = OK
            check.detail = output or "در دسترس"
        else:
            check.detail = output or "پاسخ نداد"
            check.fix = "اجرا کنید: wsl --install -d Ubuntu"
    report.checks.append(check)


def check_buildozer(report: DoctorReport) -> None:
    """buildozer داخل WSL باید نصب باشد."""
    check = Check("buildozer (داخل WSL)")
    if platform.system() != "Windows":
        ok, output = _run(["buildozer", "--version"], timeout=60)
        check.status = OK if ok else WARN
        check.detail = output or "پیدا نشد"
        if not ok:
            check.fix = "اجرا کنید: pip3 install --user buildozer cython"
        report.checks.append(check)
        return
    if shutil.which("wsl") is None:
        check.status = WARN
        check.detail = "بدون WSL قابل بررسی نیست"
        report.checks.append(check)
        return
    ok, output = _run(["wsl", "bash", "-lc", "buildozer --version"], timeout=90)
    if ok:
        check.status = OK
        check.detail = output
    else:
        check.status = WARN
        check.detail = output or "نصب نیست"
        check.fix = (
            "داخل WSL اجرا کنید: pip3 install --user buildozer cython "
            "و سپس: sudo apt install -y openjdk-17-jdk zip unzip"
        )
    report.checks.append(check)


def check_scripts(report: DoctorReport) -> None:
    """
    فایل‌های `.bat` باید سالم باشند.

    سه دام واقعی که قبلاً باعث شد سازنده بی‌صدا بسته شود: نبود `pause`،
    خط‌پایان یونیکسی، و نبود `chcp` برای متن فارسی.
    """
    for name in ("build_installer.bat", "build_apk.bat"):
        check = Check(f"اسکریپت {name}")
        path = PROJECT_ROOT / "scripts" / name
        if not path.exists():
            check.detail = "پیدا نشد"
            check.fix = "نسخهٔ کامل را دوباره از آرشیو باز کنید."
            report.checks.append(check)
            continue
        data = path.read_bytes()
        problems: list[str] = []
        if b"pause" not in data:
            problems.append("بدون pause (پنجره بی‌صدا بسته می‌شود)")
        if b"\r\n" not in data:
            problems.append("خط‌پایان یونیکسی")
        if b"chcp" not in data:
            problems.append("بدون chcp (متن فارسی خراب می‌شود)")
        if problems:
            check.detail = "، ".join(problems)
            check.fix = "نسخهٔ کامل را دوباره از آرشیو باز کنید."
        else:
            check.status = OK
            check.detail = "سالم"
        report.checks.append(check)


def check_disk_space(report: DoctorReport) -> None:
    """ساخت اندروید چند گیگابایت می‌خواهد."""
    check = Check("فضای دیسک")
    try:
        usage = shutil.disk_usage(str(PROJECT_ROOT))
    except OSError as exc:
        check.status = WARN
        check.detail = str(exc)
        report.checks.append(check)
        return
    free_gb = usage.free / (1024**3)
    check.detail = f"{free_gb:.1f} گیگابایت آزاد"
    if free_gb >= 15:
        check.status = OK
    elif free_gb >= 5:
        check.status = WARN
        check.detail += " — برای ساخت APK کم است (۱۵ گیگابایت لازم است)"
    else:
        check.fix = "دست‌کم ۱۵ گیگابایت فضا آزاد کنید."
    report.checks.append(check)


def run_diagnosis() -> DoctorReport:
    """اجرای همهٔ بررسی‌ها به ترتیب منطقی."""
    report = DoctorReport()
    check_platform(report)
    check_python(report)
    check_dependencies(report)
    check_spec_file(report)
    check_pyinstaller(report)
    check_inno_setup(report)
    check_scripts(report)
    check_wsl(report)
    check_buildozer(report)
    check_disk_space(report)
    return report


def main() -> int:
    """پوستهٔ خط فرمان."""
    print("=" * 68)
    print("عیب‌یاب سازنده‌ها — معامله‌گر هوشمند رمزارز")
    print("=" * 68)
    print()

    report = run_diagnosis()
    for check in report.checks:
        print(f"  [{check.status}] {check.name}")
        if check.detail:
            print(f"          {check.detail}")
        if check.fix and check.status != OK:
            print(f"          چاره: {check.fix}")
    print()
    print("=" * 68)
    if report.healthy:
        print("همه‌چیز آماده است. می‌توانید سازنده‌ها را اجرا کنید:")
        print("   scripts\\build_installer.bat   (فایل نصبی ویندوز)")
        print("   scripts\\build_apk.bat         (فایل APK اندروید)")
    else:
        problem = report.first_problem
        print(f"مهم‌ترین مشکل: {problem.name}")
        if problem.fix:
            print(f"چاره: {problem.fix}")
        print()
        print("این گزارش را برای من بفرستید تا دقیقاً بدانم چه شده.")
    print("=" * 68)
    return 0 if report.healthy else 1


if __name__ == "__main__":
    sys.exit(main())
