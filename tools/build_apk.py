"""
ربات ساخت APK — نسخهٔ موبایل معامله‌گر هوشمند رمزارز.

یک واقعیت که باید صریح گفته شود:
    **buildozer روی خودِ ویندوز اجرا نمی‌شود.** زنجیرهٔ ساخت اندروید به
    ابزارهای POSIX نیاز دارد. راه رسمی روی ویندوز، WSL است (اوبونتو
    داخل ویندوز). این ربات خودش تشخیص می‌دهد کجاست و اگر روی ویندوز
    باشد، فرمان را داخل WSL اجرا می‌کند.

نسخهٔ ۲.۵.۳ (گزارش کاربر: «APK ساخته نشد» بدون علت):
    * خروجی زنده + گزارش کامل در `build_logs/apk-*.log` (قبلاً ۴۰–۹۰ دقیقه
      سکوت و فقط ۶ خط آخر).
    * بررسی ابزارهای لازم **داخل** WSL با فرمان دقیق نصب؛ buildozer خودکار
      در محیط مجازی جدا نصب می‌شود (`pip install --user` روی اوبونتوی
      جدید با PEP 668 رد می‌شود).
    * ساخت روی فایل‌سیستم لینوکس (`~/cryptoaitrader-apk`) نه `/mnt/c`؛
      buildozer روی NTFS به خطای مجوز/پیوند نمادین و کندی شدید می‌خورد.
    * نبود numpy/pandas/pytest در پایتون اجراکننده، آزمون هم‌ارزی را «رد
      شده» می‌کند نه کل ساخت را.

گام‌ها:
    ۱. بررسی محیط (WSL، جاوا، ابزارهای ساخت، buildozer)
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
import importlib.util
import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.build_common import headless_env, open_log, run_streaming, summarize  # noqa: E402

MOBILE_DIR = PROJECT_ROOT / "mobile"
OUTPUT_DIR = PROJECT_ROOT / "dist" / "apk"

#: پوشهٔ ساخت روی فایل‌سیستم لینوکس (داخل WSL).
WSL_BUILD_DIR = "$HOME/cryptoaitrader-apk"
#: محیط مجازی جدای buildozer داخل WSL/لینوکس (بدون نیاز به sudo).
BUILDOZER_VENV = "$HOME/.cai-buildozer"
BUILDOZER_PACKAGES = "buildozer 'cython>=3.0,<3.1' setuptools wheel"
#: فرمان‌هایی که زنجیرهٔ اندروید لازم دارد ← بستهٔ apt متناظر.
REQUIRED_TOOLS: dict[str, str] = {
    "git": "git", "zip": "zip", "unzip": "unzip", "java": "openjdk-17-jdk",
    "javac": "openjdk-17-jdk", "autoconf": "autoconf", "libtoolize": "libtool",
    "pkg-config": "pkg-config", "cmake": "cmake", "make": "build-essential",
    "gcc": "build-essential",
}
APT_BASE = ("python3-pip python3-venv zlib1g-dev libncurses-dev libffi-dev "
            "libssl-dev lld")
PATH_PREFIX = f'export PATH="{BUILDOZER_VENV}/bin:$HOME/.local/bin:$PATH"'

_LOG: IO[str] | None = None


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


def _run(
    command: list[str], step: Step, cwd: Path | None = None, *, env: dict[str, str] | None = None
) -> bool:
    """اجرای یک فرمان با خروجی زنده و ثبت نتیجه."""
    print(f"\n>>> {step.name}", flush=True)
    # ساخت نخست تا دو ساعت طول می‌کشد (دانلود SDK/NDK).
    code, tail = run_streaming(command, cwd=cwd, env=env, log=_LOG, timeout=14400)
    step.ok = code == 0
    if not step.ok:
        step.detail = summarize(tail) or f"exit code {code}"
    return step.ok


def shell_command(script: str) -> list[str]:
    """اجرای یک اسکریپت bash: روی ویندوز داخل WSL، وگرنه bash محلی."""
    if is_windows():
        return ["wsl", "bash", "-lc", script]
    return ["bash", "-lc", script]


def probe_script() -> str:
    """
    اسکریپت بررسی ابزارها؛ خروجی خط‌های `MISSING <tool> <apt-package>`.

    buildozer اگر نبود در محیط مجازی جدا نصب می‌شود (بدون sudo)؛ فقط
    بسته‌های سیستمی دستور `sudo apt install` لازم دارند.
    """
    checks = "\n".join(
        f'command -v {tool} >/dev/null 2>&1 || echo "MISSING {tool} {package}"'
        for tool, package in REQUIRED_TOOLS.items()
    )
    return "\n".join([
        "set +e",
        PATH_PREFIX,
        checks,
        'python3 -c "import ensurepip, venv" >/dev/null 2>&1 || echo "MISSING python3-venv python3-venv"',
        "if ! command -v buildozer >/dev/null 2>&1; then",
        '  echo "buildozer not found - installing into ' + BUILDOZER_VENV + ' ..."',
        f"  python3 -m venv {BUILDOZER_VENV} && {BUILDOZER_VENV}/bin/pip install -q --upgrade pip"
        f" && {BUILDOZER_VENV}/bin/pip install -q {BUILDOZER_PACKAGES}",
        "fi",
        'command -v buildozer >/dev/null 2>&1 && buildozer --version 2>/dev/null | head -1'
        ' || echo "MISSING buildozer buildozer"',
        "exit 0",
    ])


def apt_command(packages: list[str]) -> str:
    """فرمان نصب بسته‌های سیستمی لازم (یک خط، قابل کپی)."""
    unique = sorted({p for p in packages if p and p != "buildozer"} | set(APT_BASE.split()))
    return "sudo apt update && sudo apt install -y " + " ".join(unique)


def check_toolchain(report: ApkReport) -> bool:
    """بررسی جاوا/ابزارهای ساخت/buildozer در محیطی که buildozer اجرا می‌شود."""
    step = Step("بررسی ابزارهای ساخت اندروید" + (" داخل WSL" if is_windows() else ""))
    print(f"\n>>> {step.name}", flush=True)
    code, lines = run_streaming(shell_command(probe_script()), log=_LOG, timeout=1800,
                                tail_lines=200)
    missing = [line.split()[1:3] for line in lines if line.startswith("MISSING ")]
    if code != 0 and not missing:
        step.detail = summarize(lines) or f"exit code {code}"
        report.steps.append(step)
        return False
    if missing:
        tools = ", ".join(sorted({m[0] for m in missing}))
        packages = [m[1] if len(m) > 1 else m[0] for m in missing]
        where = "داخل WSL (Ubuntu)" if is_windows() else "در ترمینال"
        step.detail = (
            f"این ابزارها نیستند: {tools}. یک بار {where} اجرا کنید و دوباره بسازید:  "
            + apt_command(packages)
        )
        if any(m[0] == "buildozer" for m in missing):
            step.detail += (f"  — سپس: python3 -m venv {BUILDOZER_VENV} && "
                            f"{BUILDOZER_VENV}/bin/pip install {BUILDOZER_PACKAGES}")
        report.steps.append(step)
        return False
    step.ok = True
    step.detail = "جاوا، ابزارهای ساخت و buildozer آماده‌اند"
    report.steps.append(step)
    return True


def build_script(mode: str, *, clean: bool = False) -> str:
    """
    اسکریپت ساخت buildozer.

    روی ویندوز: کپی سورس موبایل به `~/cryptoaitrader-apk` (بدون `.buildozer`
    و `bin` قبلی)، ساخت روی فایل‌سیستم لینوکس و کپی APK به `mobile/bin`.
    کش `.buildozer` در پوشهٔ لینوکسی می‌ماند تا ساخت‌های بعدی چند دقیقه‌ای باشند.
    """
    buildozer = "buildozer -v android " + ("clean" if clean else mode)
    if not is_windows():
        return f"set -e\n{PATH_PREFIX}\ncd {shlex.quote(str(MOBILE_DIR))}\n{buildozer}"
    source = shlex.quote(to_wsl_path(MOBILE_DIR))
    return "\n".join([
        "set -e",
        PATH_PREFIX,
        f"mkdir -p {WSL_BUILD_DIR}",
        f"tar -C {source} --exclude=./.buildozer --exclude=./bin -cf - . | tar -C {WSL_BUILD_DIR} -xf -",
        f"cd {WSL_BUILD_DIR}",
        buildozer,
        *(
            [] if clean else [
                f"mkdir -p {source}/bin",
                f"cp -f bin/*.apk {source}/bin/",
                f'echo "APK copied to {to_wsl_path(MOBILE_DIR)}/bin"',
            ]
        ),
    ])


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

    missing = [name for name in ("pytest", "numpy", "pandas")
               if importlib.util.find_spec(name) is None]
    if missing:
        # این آزمون فقط هم‌خوانی ریاضی موبایل با دسکتاپ را می‌سنجد و برای
        # خود ساخت لازم نیست؛ نبود بسته‌ها نباید کل ساخت را بکشد (نسخهٔ ۲.۵.۳).
        step.skipped = True
        step.detail = (f"بسته‌های {', '.join(missing)} در این پایتون نیستند "
                       f"({sys.executable}); آزمون رد شد. برای اجرا ابتدا "
                       "scripts\\build_installer.bat را یک بار اجرا کنید تا .venv ساخته شود.")
        report.steps.append(step)
        return True

    ok = _run(
        [sys.executable, "-m", "pytest", str(test_file), "-q", "-o", "addopts=",
         "-p", "no:cacheprovider"],
        step,
        PROJECT_ROOT,
        env=headless_env(),
    )
    report.steps.append(step)
    return ok


def build_apk(report: ApkReport, *, release: bool = False, clean: bool = False) -> None:
    """اجرای buildozer."""
    step = Step("ساخت APK با buildozer" + (" (داخل WSL)" if is_windows() else ""))
    mode = "release" if release else "debug"

    if clean:
        clean_step = Step("پاک‌سازی ساخت قبلی")
        clean_step.ok = _run(shell_command(build_script(mode, clean=True)), clean_step)
        report.steps.append(clean_step)

    step.ok = _run(shell_command(build_script(mode)), step)
    report.steps.append(step)
    if not step.ok:
        if "license" in step.detail.lower():
            step.detail += "  — مجوز SDK پذیرفته نشد؛ android.accept_sdk_license در buildozer.spec را بررسی کنید."
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
    if not check_toolchain(report):
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
    global _LOG
    log_path, _LOG = open_log("apk")
    print(f"گزارش کامل ساخت: {log_path}", flush=True)
    print("ساخت نخست APK ۴۰ تا ۹۰ دقیقه طول می‌کشد (دانلود SDK/NDK)؛ پنجره را نبندید.", flush=True)
    try:
        report = build(release=args.release, clean=args.clean, skip_tests=skip)
    finally:
        _LOG.close()
        _LOG = None

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
        print("APK ساخته نشد. علت در گام «شکست» بالا آمده است.")
        print(f"گزارش کامل: {log_path}  (در صورت نیاز همین فایل را بفرستید)")
    print("=" * 66)
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
