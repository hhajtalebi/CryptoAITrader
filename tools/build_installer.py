"""
ربات ساخت فایل نصبی ویندوز — از سورس تا `setup.exe` با یک دستور.

اجرا (روی ویندوز):
    python tools\\build_installer.py

چه می‌کند؟
    ۱. نسخه را از `app/core/constants.py` می‌خواند (یک منبع حقیقت).
    ۲. وابستگی‌ها را نصب می‌کند.
    ۳. آزمون‌ها را اجرا می‌کند — با شکست آزمون، ساخت متوقف می‌شود.
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
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

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


def _run(command: list[str], step: BuildStep, cwd: Path) -> bool:
    """اجرای یک فرمان و ثبت نتیجه در گام."""
    try:
        completed = subprocess.run(  # noqa: S603
            command, cwd=str(cwd), capture_output=True, text=True, timeout=3600
        )
    except (OSError, subprocess.SubprocessError) as exc:
        step.detail = f"{exc.__class__.__name__}: {exc}"
        return False
    step.ok = completed.returncode == 0
    if not step.ok:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()
        step.detail = " | ".join(tail[-4:])[:400]
    return step.ok


def build(*, skip_tests: bool = False, root: Path | None = None) -> BuildReport:
    """اجرای کامل زنجیرهٔ ساخت."""
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

    tests = BuildStep("اجرای آزمون‌ها")
    if skip_tests:
        tests.skipped = True
        tests.detail = "با درخواست کاربر رد شد"
    else:
        tests.ok = _run([python, "-m", "pytest", "tests", "-q"], tests, base)
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
    skip = os.environ.get("SKIP_TESTS") == "1" or "--skip-tests" in sys.argv
    print("=" * 66)
    print("ربات ساخت فایل نصبی — Crypto AI Trader")
    print("=" * 66)

    report = build(skip_tests=skip)
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
    print("=" * 66)
    return 0 if report.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
