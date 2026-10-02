"""
نسخهٔ ۲.۵.۹ — ساخت APK روی WSLِ بدون توزیع لینوکس.

گزارش کاربر: «Windows Subsystem for Linux has no installed distributions»
با حروفی که NUL میانشان بود (W i n d o w s …)؛ `wsl --status` با این حال
موفق برمی‌گشت و ربات بدون راهنمای درست شکست می‌خورد.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.build_apk as build_apk
from tools.build_common import run_streaming

ROOT = Path(__file__).resolve().parent.parent
NO_DISTRO = "Windows Subsystem for Linux has no installed distributions."


class TestDecode:
    def test_utf16_output_is_decoded(self) -> None:
        raw = NO_DISTRO.encode("utf-16-le")
        assert build_apk.decode_wsl_output(raw) == NO_DISTRO

    def test_utf16_with_bom(self) -> None:
        assert build_apk.decode_wsl_output("\ufeffUbuntu\r\n".encode("utf-16-le")).strip() == "Ubuntu"

    def test_utf8_output_is_kept(self) -> None:
        assert build_apk.decode_wsl_output(b"Ubuntu\ndocker-desktop\n") == "Ubuntu\ndocker-desktop\n"

    def test_str_nuls_are_stripped(self) -> None:
        assert build_apk.decode_wsl_output("W\x00i\x00n\x00") == "Win"


class TestDistros:
    def test_usable_prefers_ubuntu_and_drops_docker(self) -> None:
        names = ["docker-desktop", "Debian", "Ubuntu-22.04", "docker-desktop-data"]
        assert build_apk.usable_distros(names) == ["Ubuntu-22.04", "Debian"]

    def test_only_docker_is_unusable(self) -> None:
        assert build_apk.usable_distros(["docker-desktop", "docker-desktop-data"]) == []

    def test_list_parses_utf16(self, monkeypatch) -> None:
        output = "Ubuntu\r\ndocker-desktop\r\n".encode("utf-16-le")
        monkeypatch.setattr(
            build_apk.subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=0, stdout=output, stderr=b""),
        )
        assert build_apk.list_wsl_distros() == ["Ubuntu", "docker-desktop"]

    def test_list_empty_when_wsl_fails(self, monkeypatch) -> None:
        monkeypatch.setattr(
            build_apk.subprocess, "run",
            lambda *a, **k: SimpleNamespace(returncode=1, stdout=NO_DISTRO.encode("utf-16-le"), stderr=b""),
        )
        assert build_apk.list_wsl_distros() == []

    def test_list_empty_when_wsl_missing(self, monkeypatch) -> None:
        def boom(*_a, **_k):
            raise FileNotFoundError("wsl")

        monkeypatch.setattr(build_apk.subprocess, "run", boom)
        assert build_apk.list_wsl_distros() == []


class TestCheckEnvironment:
    def _report(self):
        return build_apk.ApkReport()

    def test_no_distro_gives_install_guidance(self, monkeypatch) -> None:
        monkeypatch.setattr(build_apk, "is_windows", lambda: True)
        monkeypatch.setattr(build_apk, "has_wsl", lambda: True)
        monkeypatch.setattr(build_apk, "list_wsl_distros", lambda: ["docker-desktop"])
        report = self._report()
        assert build_apk.check_environment(report) is False
        detail = report.steps[-1].detail
        assert build_apk.INSTALL_UBUNTU_COMMAND in detail
        assert "docker-desktop" in detail

    def test_distro_is_selected_and_used(self, monkeypatch) -> None:
        monkeypatch.setattr(build_apk, "is_windows", lambda: True)
        monkeypatch.setattr(build_apk, "has_wsl", lambda: True)
        monkeypatch.setattr(build_apk, "list_wsl_distros", lambda: ["docker-desktop", "Ubuntu"])
        monkeypatch.setattr(build_apk, "WSL_DISTRO", "")
        report = self._report()
        assert build_apk.check_environment(report) is True
        assert build_apk.WSL_DISTRO == "Ubuntu"
        assert build_apk.shell_command("echo hi") == ["wsl", "-d", "Ubuntu", "bash", "-lc", "echo hi"]

    def test_default_command_unchanged_without_distro(self, monkeypatch) -> None:
        monkeypatch.setattr(build_apk, "is_windows", lambda: True)
        monkeypatch.setattr(build_apk, "WSL_DISTRO", "")
        assert build_apk.shell_command("x") == ["wsl", "bash", "-lc", "x"]


def test_run_streaming_strips_nuls(capsys) -> None:
    code = (
        "import sys; sys.stdout.write('W\\x00i\\x00n\\x00\\n'); sys.stdout.flush()"
    )
    rc, tail = run_streaming([sys.executable, "-c", code], echo=False)
    assert rc == 0
    assert tail[-1] == "Win"


def test_bat_detects_missing_distro_and_offers_install() -> None:
    raw = (ROOT / "scripts" / "build_apk.bat").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM breaks the first cmd line"
    assert b"\n" not in raw.replace(b"\r\n", b""), "batch file must be CRLF only"
    text = raw.decode("utf-8")
    assert "wsl -e true" in text
    assert "goto :no_distro" in text
    assert "\r\n:no_distro\r\n" in text and "\r\n:no_distro_manual\r\n" in text
    assert "choice /c YN" in text
    assert text.index(":no_distro\r\n") < text.index("\r\n:fail\r\n")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
def test_shell_command_on_linux_is_plain_bash() -> None:
    assert build_apk.shell_command("true")[0] == "bash"
    assert subprocess.run(build_apk.shell_command("true"), check=False).returncode == 0
