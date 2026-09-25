"""
ربات ساخت فایل نصبی ویندوز — از سورس تا `setup.exe` با یک دستور.

اجرا (روی ویندوز):
    python tools\\build_installer.py

چه می‌کند؟
    ۱. نسخه را از `app/core/constants.py` می‌خواند (یک منبع حقیقت).
    ۲. وابستگی‌ها را نصب می‌کند.
    ۳. بررسی سلامت کد بدون باز کردن هیچ پنجره (کامپایل همهٔ ماژول‌ها و
       بارگذاری برنامه با Qt بی‌صفحه). آزمون‌های کامل فقط با
       `--with-tests` و همیشه بی‌پنجره اجرا می‌شوند (نسخهٔ ۲.۵.۳: قبلاً
       همهٔ آزمون‌ها روی دسکتاپ واقعی اجرا می‌شد و صدها پنجره باز می‌کرد؛
       هر آزمون وابسته به محیط، ساخت را پیش از PyInstaller می‌کشت).
    ۴. با PyInstaller فایل اجرایی می‌سازد.
    ۵. با Inno Setup فایل نصبی می‌سازد.
    ۶. یک فایل `latest.json` کنار خروجی می‌گذارد تا ربات به‌روزرسانی
       بداند تازه‌ترین نسخه کدام است.

چرا پایتون و نه فقط `.bat`؟
    چون همین منطق باید روی این محیط هم **آزمودنی** باشد. گام‌ها توابع
    جدا هستند و آزمون‌ها بدون اجرای واقعی PyInstaller صحتشان را
    می‌سنجند. یک اسکریپت بت فقط روی ویندوز و فقط دستی آزموده می‌شود —
    یعنی عملاً هرگز.

اگر Inno Setup نصب نباشد، گام آخر با پیام روشن رد می‌شود و فایل
اجرایی (که خودش قابل استفاده است) سر جایش می‌ماند.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.build_common import headless_env, open_log, run_streaming, summarize  # noqa: E402

#: بارگذاری برنامه بدون پنجره — خطای import/وابستگی را پیش از PyInstaller می‌گیرد.
SMOKE_CODE = (
    "import main, app.application, ui.controllers.main_controller, "
    "signals.compute_pool; print('smoke ok')"
)

#: جاهایی که Inno Setup معمولاً نصب می‌شود.
ISCC_CANDIDATES = (
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
)


@dataclass
class BuildStep:
    """یک گام از ساخت، با نتیجه‌اش."""

    name: str
    ok: bool = False
    detail: str = ""
    skipped: bool = False


@dataclass
class BuildReport:
    """گزارش کامل ساخت."""

    version: str = ""
    steps: list[BuildStep] = field(default_factory=list)
    exe_path: Path | None = None
    installer_path: Path | None = None

    @property
    def succeeded(self) -> bool:
        """آیا هیچ گامی شکست نخورده است؟"""
        return all(step.ok or step.skipped for step in self.steps)


def read_version(root: Path | None = None) -> str:
    """
    خواندن نسخه از `app/core/constants.py`.

    عمداً فایل را می‌خوانیم و `import` نمی‌کنیم: وارد کردن بستهٔ برنامه،
    کل زنجیرهٔ وابستگی‌ها را بالا می‌آورد و ساخت را به محیطی که هنوز
    نصب نشده گره می‌زند.
    """
    base = root or PROJECT_ROOT
    text = (base / "app" / "core" / "constants.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not match:
        raise RuntimeError("APP_VERSION در app/core/constants.py پیدا نشد")
    return match.group(1)


def find_iscc() -> str | None:
    """یافتن کامپایلر Inno Setup؛ `None` یعنی نصب نیست."""
    found = shutil.which("iscc") or shutil.which("ISCC.exe")
    if found:
        return found
    for candidate in ISCC_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    # آخرین تلاش: رجیستری ویندوز. کاربری که Inno Setup را جای دیگری
    # (مثلاً درایو D) نصب کرده باشد، در هیچ‌کدام از مسیرهای بالا پیدا
    # نمی‌شود و ساخت بی‌دلیل رد می‌شد.
    return _iscc_from_registry()


def _iscc_from_registry() -> str | None:
    """یافتن مسیر نصب Inno Setup از رجیستری ویندوز."""
    if sys.platform != "win32":
        return None
    try:
        import winreg  # noqa: PLC0415
    except ImportError:
        return None

    keys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 5_is1",
    )
    roots = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
    for root_key in roots:
        for key in keys:
            for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                try:
                    with winreg.OpenKey(
                        root_key, key, 0, winreg.KEY_READ | view
                    ) as handle:
                        location, _ = winreg.QueryValueEx(handle, "InstallLocation")
                except OSError:
                    continue
                candidate = Path(str(location)) / "ISCC.exe"
                if candidate.exists():
                    return str(candidate)
    return None


def file_checksum(path: Path) -> str:
    """اثر انگشت SHA-256 برای تأیید سلامت دانلود در ربات به‌روزرسانی."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(destination: Path, version: str, installer: Path | None) -> Path:
    """
    نوشتن `latest.json` که ربات به‌روزرسانی می‌خواند.

    نگه‌داشتن اندازه و checksum مهم است: به‌روزرسانی باید بتواند پیش از
    اجرا مطمئن شود فایل کامل و دست‌نخورده دانلود شده است.
    """
    payload: dict[str, object] = {"version": version}
    if installer is not None and installer.exists():
        payload.update(
            {
                "installer": installer.name,
                "size_bytes": installer.stat().st_size,
                "sha256": file_checksum(installer),
            }
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination


_LOG: IO[str] | None = None


def _run(
    command: list[str], step: BuildStep, cwd: Path, *, env: dict[str, str] | None = None
) -> bool:
    """اجرای یک فرمان با خروجی زنده و ثبت نتیجه در گام."""
    print(f"\n>>> {step.name}", flush=True)
    code, tail = run_streaming(command, cwd=cwd, env=env, log=_LOG, timeout=3600)
    step.ok = code == 0
    if not step.ok:
        step.detail = summarize(tail) or f"exit code {code}"
    return step.ok


def build(
    *, skip_tests: bool = True, root: Path | None = None, run_tests: bool | None = None
) -> BuildReport:
    """
    اجرای کامل زنجیرهٔ ساخت.

    پیش‌فرض: بدون آزمون‌های کامل (`run_tests=True` یا `skip_tests=False`
    برای اجرای آن‌ها، همیشه بی‌پنجره).
    """
    if run_tests is None:
        run_tests = not skip_tests
    base = root or PROJECT_ROOT
    report = BuildReport(version=read_version(base))
    python = sys.executable

    deps = BuildStep("نصب وابستگی‌ها")
    deps.ok = _run(
        [python, "-m", "pip", "install", "-q", "-r", "requirements.txt"], deps, base
    )
    report.steps.append(deps)
    if not deps.ok:
        return report

    smoke = BuildStep("بررسی سلامت کد (بدون پنجره)")
    smoke.ok = _run(
        [python, "-m", "compileall", "-q", "-x", r"(\.venv|build|dist|mobile|\.cache)", "."],
        smoke, base,
    ) and _run([python, "-c", SMOKE_CODE], smoke, base, env=headless_env())
    report.steps.append(smoke)
    if not smoke.ok:
        return report

    tests = BuildStep("اجرای آزمون‌ها (بی‌پنجره)")
    if not run_tests:
        tests.skipped = True
        tests.detail = "پیش‌فرض رد می‌شود؛ برای اجرا: --with-tests"
    else:
        tests.ok = _run(
            [python, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"],
            tests, base, env=headless_env(),
        )
    report.steps.append(tests)
    if not (tests.ok or tests.skipped):
        return report

    package = BuildStep("بسته‌بندی با PyInstaller")
    for folder in ("build", "dist"):
        shutil.rmtree(base / folder, ignore_errors=True)
    package.ok = _run(
        [python, "-m", "PyInstaller", "CryptoAITrader.spec", "--noconfirm", "--clean"],
        package,
        base,
    )
    if not package.ok:
        # روی بعضی نصب‌ها فقط اسکریپت `pyinstaller.exe` هست و ماژول با
        # `-m` بالا نمی‌آید. پیش از تسلیم، شکل دوم را هم امتحان می‌کنیم.
        fallback = shutil.which("pyinstaller")
        if fallback:
            package.ok = _run(
                [fallback, "CryptoAITrader.spec", "--noconfirm", "--clean"],
                package,
                base,
            )
    report.steps.append(package)
    if not package.ok:
        return report

    exe = base / "dist" / "CryptoAITrader" / "CryptoAITrader.exe"
    report.exe_path = exe if exe.exists() else None
    if report.exe_path is None and sys.platform == "win32":
        package.ok = False
        package.detail = f"PyInstaller تمام شد ولی فایل اجرایی ساخته نشد: {exe}"
        return report

    installer_step = BuildStep("ساخت فایل نصبی با Inno Setup")
    iscc = find_iscc()
    if iscc is None:
        installer_step.skipped = True
        installer_step.detail = (
            "Inno Setup نصب نیست. از jrsoftware.org/isdl.php نصبش کنید؛ "
            "فایل اجرایی در dist\\CryptoAITrader آمادهٔ استفاده است."
        )
    else:
        installer_step.ok = _run(
            [
                iscc,
                f"/DAppVersion={report.version}",
                str(base / "installer" / "CryptoAITrader.iss"),
            ],
            installer_step,
            base,
        )
        candidate = (
            base / "dist" / "installer" / f"CryptoAITrader-Setup-{report.version}.exe"
        )
        report.installer_path = candidate if candidate.exists() else None
        if installer_step.ok and report.installer_path is None:
            # ISCC با کد ۰ برگشت ولی فایلی نیست. قبلاً این حالت بی‌صدا
            # رد می‌شد و کاربر «موفق» می‌دید بدون آنکه فایلی بسازد.
            installer_step.ok = False
            installer_step.detail = (
                "ISCC بدون خطا تمام شد ولی فایل نصبی ساخته نشد. "
                f"انتظار می‌رفت: {candidate}"
            )
    report.steps.append(installer_step)

    manifest = BuildStep("نوشتن latest.json")
    try:
        write_manifest(
            base / "dist" / "installer" / "latest.json",
            report.version,
            report.installer_path,
        )
        manifest.ok = True
    except OSError as exc:
        manifest.detail = str(exc)
    report.steps.append(manifest)

    return report


def main() -> int:
    """پوستهٔ خط فرمان."""
    global _LOG
    # `--skip-tests` (قدیمی) همچنان پذیرفته می‌شود؛ حالا پیش‌فرض همین است.
    run_tests = os.environ.get("RUN_TESTS") == "1" or "--with-tests" in sys.argv
    if os.environ.get("SKIP_TESTS") == "1" or "--skip-tests" in sys.argv:
        run_tests = False
    print("=" * 66)
    print("ربات ساخت فایل نصبی — Crypto AI Trader")
    print("=" * 66)

    log_path, _LOG = open_log("installer")
    print(f"گزارش کامل ساخت: {log_path}", flush=True)
    try:
        report = build(run_tests=run_tests)
    finally:
        _LOG.close()
        _LOG = None
    print(f"\nنسخه: {report.version}\n")
    for step in report.steps:
        mark = "رد شد" if step.skipped else ("موفق" if step.ok else "شکست")
        print(f"  [{mark}] {step.name}")
        if step.detail:
            print(f"         {step.detail}")

    print()
    if report.exe_path:
        print(f"فایل اجرایی : {report.exe_path}")
    if report.installer_path:
        print(f"فایل نصبی   : {report.installer_path}")
    if not report.succeeded:
        print(f"گزارش کامل  : {log_path}  (در صورت نیاز همین فایل را بفرستید)")
    print("=" * 66)
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
