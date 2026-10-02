"""
نسخهٔ ۲.۷.۰ — دو گزارش کاربر از ابزارهای ساخت ویندوز:

1. doctor.bat خروجی عیب‌یاب را به doctor_report.txt هدایت می‌کند؛ پایتون ویندوز
   برای فایل cp1252 به کار می‌برد و اولین print فارسی UnicodeEncodeError می‌داد.
2. build_apk.bat: «WSL نصب است ولی توزیعی نیست» ← فایل گزارش ساخت کاملاً خالی بود
   و پیشنهاد نصب Ubuntu (بله/خیر) نشان داده نمی‌شد.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["build_doctor.py", "ollama_doctor.py"])
def test_doctor_output_redirected_to_cp1252_file_does_not_crash(tmp_path, script):
    out = tmp_path / "report.txt"
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0", QT_QPA_PLATFORM="offscreen")
    with out.open("wb") as handle:
        proc = subprocess.run(  # noqa: S603
            [sys.executable, str(ROOT / "tools" / script)],
            stdout=handle, stderr=subprocess.STDOUT, cwd=ROOT, env=env, timeout=240, check=False,
        )
    text = out.read_bytes().decode("utf-8", errors="replace")
    assert "UnicodeEncodeError" not in text
    assert proc.returncode in (0, 1, 2)
    assert any("\u0600" <= ch <= "\u06ff" for ch in text)  # متن فارسی واقعاً نوشته شد


def test_all_python_tools_force_utf8_stdio():
    missing = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if 'if __name__ == "__main__":' in source and "print(" in source:
            if "reconfigure(encoding=\"utf-8\"" not in source and path.name != "serve_downloads.py":
                missing.append(path.name)
    assert not missing, missing


@pytest.mark.parametrize("name", ["doctor.bat", "build_apk.bat", "build_installer.bat", "build_windows.bat"])
def test_bat_files_set_utf8_python(name):
    data = (ROOT / "scripts" / name).read_bytes()
    assert b'set "PYTHONUTF8=1"' in data
    assert b"\r\n" in data and not data.startswith(b"\xef\xbb\xbf")


def test_build_apk_bat_routes_exit_code_3_to_ubuntu_install():
    data = (ROOT / "scripts" / "build_apk.bat").read_bytes().decode("utf-8")
    assert 'if "%RESULT%"=="3" goto :no_distro' in data
    assert data.index('if "%RESULT%"=="3"') < data.index('if "%RESULT%"=="0"')
    assert ":no_distro\r\n" in data and "wsl --install -d Ubuntu" in data


def _run_main_without_distro(monkeypatch, tmp_path, wsl_stdout: bytes):
    import tools.build_apk as ba

    log_path = tmp_path / "apk.log"
    monkeypatch.setattr(ba, "open_log", lambda name: (log_path, log_path.open("w", encoding="utf-8")))
    monkeypatch.setattr(ba, "is_windows", lambda: True)
    monkeypatch.setattr(ba, "has_wsl", lambda: True)
    monkeypatch.setattr(ba, "_NO_DISTRO", False)

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if list(cmd[:2]) != ["wsl", "-l"]:
            return real_run(cmd, *args, **kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout=wsl_stdout, stderr=b"")

    monkeypatch.setattr(ba.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["build_apk.py"])
    code = ba.main()
    return code, log_path.read_text(encoding="utf-8")


def test_build_apk_no_distro_writes_log_and_returns_3(monkeypatch, tmp_path, capsys):
    code, log = _run_main_without_distro(monkeypatch, tmp_path, b"")
    assert code == 3
    assert log.strip(), "build log must not be empty"
    assert "wsl -l -q" in log
    assert "[FAILED]" in log and "wsl --install -d Ubuntu" in log
    assert "result: failed" in log


def test_build_apk_only_docker_desktop_counts_as_no_distro(monkeypatch, tmp_path, capsys):
    code, log = _run_main_without_distro(monkeypatch, tmp_path, "docker-desktop\r\n".encode("utf-16-le"))
    assert code == 3
    assert "docker-desktop" in log
