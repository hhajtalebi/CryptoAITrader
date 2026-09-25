"""
آزمون‌های نسخهٔ ۲.۵.۳ — ربات‌های ساخت فایل نصبی ویندوز و APK.

گزارش کاربر:
    * ویندوز: «تعداد زیادی پنجره از قسمت‌های مختلف نرم‌افزار باز می‌کند و
      فایل نصبی را نمی‌سازد» ← ربات همهٔ آزمون‌ها را روی دسکتاپ واقعی اجرا
      می‌کرد (هر آزمون رابط یک پنجره) و هر شکست، ساخت را پیش از PyInstaller
      می‌کشت.
    * APK: «APK ساخته نشد» و همهٔ فرمان‌ها در کنسول تکرار می‌شد ← BOM در
      ابتدای فایل bat، آیکون/پیش‌نمایش ناموجود، پذیرش مجوز SDK، pip --user
      روی اوبونتوی جدید، ساخت روی /mnt/c و خروجی پنهان.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOM = b"\xef\xbb\xbf"


# ---------------------------------------------------------------------------
# فایل‌های bat و Inno Setup
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["build_installer.bat", "build_apk.bat", "build_windows.bat"])
def test_bat_files_have_no_bom_so_echo_off_works(name: str) -> None:
    """BOM جزو فرمان اول خوانده می‌شد و `@echo off` اجرا نمی‌شد (همهٔ فرمان‌ها تکرار می‌شد)."""
    content = (ROOT / "scripts" / name).read_bytes()
    assert not content.startswith(BOM)
    assert content.startswith(b"@echo off\r\n")
    assert b"chcp 65001" in content
    assert b"\n" not in content.replace(b"\r\n", b"")


def test_build_windows_delegates_to_the_robot() -> None:
    content = (ROOT / "scripts" / "build_windows.bat").read_bytes()
    assert b"build_installer.bat" in content
    assert b"pytest" not in content  # دیگر آزمون‌ها را روی دسکتاپ اجرا نمی‌کند


def test_inno_script_has_bom_for_persian_text() -> None:
    """Inno Setup 6 بدون BOM فایل را ANSI می‌خواند و برچسب‌های فارسی خراب می‌شوند."""
    assert (ROOT / "installer" / "CryptoAITrader.iss").read_bytes().startswith(BOM)


def test_spec_disables_upx() -> None:
    spec = (ROOT / "CryptoAITrader.spec").read_text(encoding="utf-8")
    assert "upx=True" not in spec and spec.count("upx=False") == 2


def test_tests_are_headless_by_default() -> None:
    """conftest پیش از Qt سکوی بی‌صفحه را تنظیم می‌کند."""
    assert os.environ.get("QT_QPA_PLATFORM")
    conftest = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert 'setdefault("QT_QPA_PLATFORM", "offscreen")' in conftest


# ---------------------------------------------------------------------------
# اجرای زنده
# ---------------------------------------------------------------------------
def test_run_streaming_echoes_logs_and_keeps_tail(tmp_path: Path, capsys) -> None:  # noqa: ANN001
    from tools.build_common import run_streaming

    log_path = tmp_path / "b.log"
    with log_path.open("w", encoding="utf-8") as log:
        code, tail = run_streaming(
            [sys.executable, "-c", "import sys\nfor i in range(30): print('line', i)\nsys.exit(3)"],
            log=log, tail_lines=5,
        )
    assert code == 3
    assert tail == [f"line {i}" for i in range(25, 30)]
    assert "line 0" in capsys.readouterr().out  # زنده چاپ شد
    assert "line 29" in log_path.read_text(encoding="utf-8")


def test_run_streaming_missing_command_and_timeout() -> None:
    from tools.build_common import run_streaming

    code, tail = run_streaming(["definitely-not-a-command-xyz"], echo=False)
    assert code == 127 and tail
    code, _ = run_streaming([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1, echo=False)
    assert code == 124


def test_headless_env() -> None:
    from tools.build_common import headless_env

    env = headless_env()
    assert env["QT_QPA_PLATFORM"] == "offscreen" and env["CRYPTOAI_NO_PROCESS_POOL"] == "1"


# ---------------------------------------------------------------------------
# ربات فایل نصبی
# ---------------------------------------------------------------------------
def _root(tmp_path: Path) -> Path:
    constants = tmp_path / "app" / "core" / "constants.py"
    constants.parent.mkdir(parents=True)
    constants.write_text('APP_VERSION = "9.9.9"\n', encoding="utf-8")
    return tmp_path


def _fake_run(calls: list[tuple[list[str], dict | None]], fail_on: str | None = None):
    def run(command, step, cwd, *, env=None):  # noqa: ANN001, ANN202, ARG001
        calls.append((list(command), env))
        step.ok = not (fail_on and any(fail_on in str(part) for part in command))
        if not step.ok:
            step.detail = "boom"
        return step.ok
    return run


def test_installer_default_skips_full_tests_but_smoke_checks(tmp_path: Path) -> None:
    import tools.build_installer as bi

    calls: list = []
    with patch.object(bi, "_run", _fake_run(calls)), patch.object(bi, "find_iscc", return_value=None):
        report = bi.build(root=_root(tmp_path))
    flat = [" ".join(c) for c, _ in calls]
    assert not any("pytest" in c for c in flat)
    assert any("compileall" in c for c in flat)
    smoke = [env for c, env in calls if "-c" in c]
    assert smoke and smoke[0]["QT_QPA_PLATFORM"] == "offscreen"
    assert any("PyInstaller" in c for c in flat)
    tests_step = next(s for s in report.steps if "آزمون" in s.name)
    assert tests_step.skipped and "--with-tests" in tests_step.detail


def test_installer_with_tests_runs_them_headless(tmp_path: Path) -> None:
    import tools.build_installer as bi

    calls: list = []
    with patch.object(bi, "_run", _fake_run(calls)), patch.object(bi, "find_iscc", return_value=None):
        bi.build(root=_root(tmp_path), run_tests=True)
    pytest_calls = [(c, env) for c, env in calls if "pytest" in c]
    assert pytest_calls and pytest_calls[0][1]["QT_QPA_PLATFORM"] == "offscreen"


def test_installer_smoke_failure_stops_before_pyinstaller(tmp_path: Path) -> None:
    import tools.build_installer as bi

    calls: list = []
    with patch.object(bi, "_run", _fake_run(calls, fail_on="compileall")):
        report = bi.build(root=_root(tmp_path))
    assert not report.succeeded
    assert not any("PyInstaller" in " ".join(c) for c, _ in calls)


def test_installer_cli_flags(monkeypatch) -> None:  # noqa: ANN001
    import tools.build_installer as bi

    seen: dict = {}

    def fake_build(**kwargs):  # noqa: ANN003, ANN202
        seen.update(kwargs)
        return bi.BuildReport(version="x")

    monkeypatch.setattr(bi, "build", fake_build)
    monkeypatch.setattr(bi, "open_log", lambda name: (Path(os.devnull), open(os.devnull, "w")))  # noqa: SIM115
    monkeypatch.setattr(sys, "argv", ["build_installer.py"])
    monkeypatch.delenv("RUN_TESTS", raising=False)
    monkeypatch.delenv("SKIP_TESTS", raising=False)
    bi.main()
    assert seen["run_tests"] is False
    monkeypatch.setattr(sys, "argv", ["build_installer.py", "--with-tests"])
    bi.main()
    assert seen["run_tests"] is True


# ---------------------------------------------------------------------------
# APK
# ---------------------------------------------------------------------------
def _spec() -> str:
    return (ROOT / "mobile" / "buildozer.spec").read_text(encoding="utf-8")


def test_buildozer_spec_is_non_interactive_and_buildable() -> None:
    spec = _spec()
    assert "android.accept_sdk_license = True" in spec
    assert "warn_on_root = 0" in spec
    requirements = next(line for line in spec.splitlines() if line.startswith("requirements"))
    assert "python-bidi==0.4.2" in requirements  # نسخه‌های Rust با p4a ساخته نمی‌شوند


def test_mobile_assets_referenced_by_spec_and_app_exist() -> None:
    """آیکون و پیش‌نمایش ناموجود ساخت buildozer را می‌کشت؛ قلم فارسی هم نبود."""
    mobile = ROOT / "mobile"
    for key in ("presplash.filename", "icon.filename"):
        line = next(item for item in _spec().splitlines() if item.startswith(key))
        rel = line.split("=", 1)[1].strip().replace("%(source.dir)s/", "")
        assert (mobile / rel).is_file(), rel
    assert (mobile / "assets" / "Vazirmatn-Regular.ttf").is_file()
    assert "assets/Vazirmatn-Regular.ttf" in (mobile / "main.py").read_text(encoding="utf-8")
    # PNG معتبر با اندازهٔ درست
    from struct import unpack

    head = (mobile / "assets" / "icon.png").read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n" and unpack(">II", head[16:24]) == (512, 512)


def test_windows_build_script_uses_linux_filesystem() -> None:
    import tools.build_apk as ba

    with patch.object(ba, "is_windows", return_value=True), \
            patch.object(ba, "to_wsl_path", return_value="/mnt/c/Users/me/CryptoAITrader/mobile"):
        script = ba.build_script("debug")
        command = ba.shell_command(script)
    assert "cd $HOME/cryptoaitrader-apk" in script
    assert "--exclude=./.buildozer" in script and "--exclude=./bin" in script
    assert "buildozer -v android debug" in script
    assert "cp -f bin/*.apk /mnt/c/Users/me/CryptoAITrader/mobile/bin/" in script
    assert ".cai-buildozer/bin" in script
    assert command[:3] == ["wsl", "bash", "-lc"]
    assert "/mnt/" not in script.split("cd $HOME/cryptoaitrader-apk")[1].split("buildozer -v")[0]


def test_probe_installs_buildozer_in_venv_not_pip_user() -> None:
    import tools.build_apk as ba

    script = ba.probe_script()
    assert "python3 -m venv $HOME/.cai-buildozer" in script
    assert "--user" not in script
    assert 'echo "MISSING java openjdk-17-jdk"' in script


def test_toolchain_reports_exact_apt_command() -> None:
    import tools.build_apk as ba

    report = ba.ApkReport()
    lines = ["MISSING java openjdk-17-jdk", "MISSING libtoolize libtool", "buildozer 1.5.0"]
    with patch.object(ba, "run_streaming", return_value=(0, lines)):
        assert ba.check_toolchain(report) is False
    detail = report.steps[-1].detail
    assert "java" in detail and "libtoolize" in detail
    assert "sudo apt update && sudo apt install -y" in detail and "openjdk-17-jdk" in detail
    report = ba.ApkReport()
    with patch.object(ba, "run_streaming", return_value=(0, ["buildozer 1.5.0"])):
        assert ba.check_toolchain(report) is True


def test_math_check_is_skipped_not_fatal_without_packages() -> None:
    import tools.build_apk as ba

    report = ba.ApkReport()
    with patch("importlib.util.find_spec", side_effect=lambda name: None):
        assert ba.verify_math_equivalence(report) is True
    assert report.steps[-1].skipped and "pandas" in report.steps[-1].detail


def test_failed_toolchain_stops_before_buildozer() -> None:
    import tools.build_apk as ba

    called: list = []
    with patch.object(ba, "check_environment", return_value=True), \
            patch.object(ba, "check_toolchain", return_value=False), \
            patch.object(ba, "build_apk", lambda *a, **k: called.append(1)):
        report = ba.build()
    assert not called and report.apk_path is None


def test_apk_bat_prefers_project_venv() -> None:
    content = (ROOT / "scripts" / "build_apk.bat").read_bytes().decode("utf-8")
    assert '.venv\\Scripts\\python.exe' in content
    assert "pip3 install --user" not in content
