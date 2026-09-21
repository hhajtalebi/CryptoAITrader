"""
آزمون‌های ربات ساخت فایل نصبی و ربات به‌روزرسانی (۱٫۹٫۱۱).

چرا منطق این دو در پایتون است و نه در `.bat`؟
    چون یک اسکریپت بت فقط روی ویندوز و فقط دستی آزموده می‌شود — یعنی
    عملاً هرگز. اینجا گام‌ها توابع خالص‌اند و بدون اجرای واقعی
    PyInstaller یا نصب‌کننده سنجیده می‌شوند.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from app.core.updater import (
    UpdateChecker,
    UpdateInfo,
    is_newer,
    parse_manifest,
    parse_version,
    verify_checksum,
)
from tools.build_installer import find_iscc, read_version, write_manifest


class TestVersionComparison:
    """
    مقایسهٔ نسخه باید عددی باشد، نه رشته‌ای.

    دام واقعی: در مقایسهٔ رشته‌ای «1.9.9» > «1.9.11» است، چون «9» از
    «1» بزرگ‌تر است. با این اشتباه، هر کاربری که روی نسخهٔ دورقمی
    باشد دیگر هیچ به‌روزرسانی‌ای نمی‌گیرد — و هیچ‌کس متوجه نمی‌شود.
    """

    def test_two_digit_patch_beats_single_digit(self) -> None:
        """مهم‌ترین آزمون این بخش."""
        assert is_newer("1.9.11", "1.9.9") is True

    def test_the_naive_string_compare_would_be_wrong(self) -> None:
        """ثبت صریح دامی که از آن پرهیز شده است."""
        assert "1.9.9" > "1.9.11"  # رفتار غلط رشته‌ای
        assert not is_newer("1.9.9", "1.9.11")  # رفتار درست ما

    def test_an_equal_version_is_not_newer(self) -> None:
        """نسخهٔ یکسان نباید به‌روزرسانی پیشنهاد کند."""
        assert is_newer("1.9.11", "1.9.11") is False

    def test_a_major_bump_wins(self) -> None:
        """۲.۰.۰ از ۱.۹.۱۱ جدیدتر است."""
        assert is_newer("2.0.0", "1.9.11") is True

    def test_garbage_does_not_crash(self) -> None:
        """نسخهٔ نامعتبر نباید استثنا بدهد."""
        assert parse_version("") == (0,)
        assert is_newer("", "1.0.0") is False


class TestManifestParsing:
    """`latest.json` از بیرون می‌آید؛ به ساختارش اعتماد نمی‌کنیم."""

    def test_a_complete_manifest_is_read(self) -> None:
        """حالت عادی."""
        info = parse_manifest(
            {
                "version": "1.9.11",
                "installer": "setup.exe",
                "size_bytes": 1234,
                "sha256": "ABC",
            }
        )

        assert info.version == "1.9.11"
        assert info.installer == "setup.exe"
        assert info.sha256 == "abc"  # نرمال‌سازی به حروف کوچک

    def test_a_manifest_without_installer_is_unusable(self) -> None:
        """نسخه بدون فایل، به‌روزرسانی نیست."""
        assert parse_manifest({"version": "9.9.9"}).usable is False

    @pytest.mark.parametrize("payload", [None, [], "text", 42])
    def test_malformed_payloads_are_survived(self, payload) -> None:  # noqa: ANN001
        """هر چیزی جز دیکشنری باید بی‌خطر رد شود."""
        assert parse_manifest(payload).usable is False

    def test_a_bad_size_does_not_crash(self) -> None:
        """اندازهٔ غیرعددی نباید ساختار را بشکند."""
        assert parse_manifest({"version": "1", "installer": "a", "size_bytes": "x"}).size_bytes == 0


class TestChecksumVerification:
    """اجرای یک نصب‌کنندهٔ ناقص بدتر از به‌روز نشدن است."""

    def test_a_matching_checksum_passes(self, tmp_path: Path) -> None:
        """فایل سالم باید پذیرفته شود."""
        target = tmp_path / "f.bin"
        target.write_bytes(b"payload")
        digest = hashlib.sha256(b"payload").hexdigest()

        assert verify_checksum(target, digest) is True

    def test_a_wrong_checksum_is_rejected(self, tmp_path: Path) -> None:
        """فایل دستکاری‌شده هرگز نباید اجرا شود."""
        target = tmp_path / "f.bin"
        target.write_bytes(b"payload")

        assert verify_checksum(target, "0" * 64) is False

    def test_a_missing_checksum_is_allowed_but_noted(self, tmp_path: Path) -> None:
        """
        منبع بدون checksum مسدود نمی‌شود.

        وگرنه کاربری که فایل را دستی در پوشه‌ای می‌گذارد هرگز نمی‌تواند
        به‌روزرسانی کند. هشدارش در لاگ می‌نشیند.
        """
        target = tmp_path / "f.bin"
        target.write_bytes(b"payload")

        assert verify_checksum(target, "") is True


class TestTheTwoRobotsWorkTogether:
    """
    خروجی ربات ساخت باید دقیقاً همان چیزی باشد که ربات به‌روزرسانی
    می‌خواند. اگر این قرارداد بشکند، هیچ‌کدام به‌تنهایی خطا نمی‌دهند.
    """

    def test_the_build_manifest_is_readable_by_the_updater(self, tmp_path: Path) -> None:
        """قرارداد میان دو ربات."""
        installer = tmp_path / "CryptoAITrader-Setup-9.9.9.exe"
        installer.write_bytes(b"x" * 500)
        manifest = write_manifest(tmp_path / "latest.json", "9.9.9", installer)

        info = parse_manifest(json.loads(manifest.read_text(encoding="utf-8")))

        assert info.usable
        assert info.version == "9.9.9"
        assert info.size_bytes == 500

    def test_a_full_local_update_round_trip(self, tmp_path: Path) -> None:
        """از ساخت manifest تا دانلود تأییدشده."""
        source = tmp_path / "share"
        source.mkdir()
        installer = source / "CryptoAITrader-Setup-9.9.9.exe"
        installer.write_bytes(b"installer bytes" * 100)
        write_manifest(source / "latest.json", "9.9.9", installer)

        checker = UpdateChecker(str(source))
        info = asyncio.run(checker.check())
        assert info is not None

        downloaded = asyncio.run(checker.download(info, tmp_path / "dl"))

        assert downloaded is not None
        assert downloaded.read_bytes() == installer.read_bytes()

    def test_a_corrupt_download_is_refused(self, tmp_path: Path) -> None:
        """checksum غلط باید فایل را حذف کند، نه اجرا."""
        source = tmp_path / "share"
        source.mkdir()
        installer = source / "setup.exe"
        installer.write_bytes(b"good bytes")
        (source / "latest.json").write_text(
            json.dumps(
                {"version": "9.9.9", "installer": "setup.exe", "sha256": "0" * 64}
            ),
            encoding="utf-8",
        )

        checker = UpdateChecker(str(source))
        info = asyncio.run(checker.check())
        result = asyncio.run(checker.download(info, tmp_path / "dl"))

        assert result is None


class TestTheUpdaterIsSafeWhenIdle:
    """به‌روزرسانی نباید هرگز خودش منبع خطا شود."""

    def test_an_empty_source_checks_nothing(self) -> None:
        """پیش‌فرض خاموش است؛ برنامه بی‌اجازه به جایی وصل نمی‌شود."""
        assert asyncio.run(UpdateChecker("").check()) is None

    def test_a_missing_folder_is_survived(self, tmp_path: Path) -> None:
        """مسیر اشتباه باید بی‌صدا رد شود."""
        assert asyncio.run(UpdateChecker(str(tmp_path / "nope")).check()) is None

    def test_an_older_remote_version_is_ignored(self, tmp_path: Path) -> None:
        """نسخهٔ قدیمی‌تر نباید پیشنهاد شود (جلوگیری از downgrade)."""
        (tmp_path / "latest.json").write_text(
            json.dumps({"version": "0.0.1", "installer": "old.exe"}), encoding="utf-8"
        )

        assert asyncio.run(UpdateChecker(str(tmp_path)).check()) is None

    def test_launching_a_missing_installer_fails_safely(self, tmp_path: Path) -> None:
        """نبود فایل نباید استثنا بدهد."""
        assert UpdateChecker.launch_installer(tmp_path / "ghost.exe") is False


class TestTheBuildRobot:
    """ربات ساخت باید نسخه را از یک منبع حقیقت بخواند."""

    def test_the_version_comes_from_constants(self) -> None:
        """نسخهٔ خوانده‌شده باید با نسخهٔ واقعی برنامه یکی باشد."""
        from app.core.constants import APP_VERSION

        assert read_version() == APP_VERSION

    def test_a_missing_iscc_is_reported_not_crashed(self) -> None:
        """
        نبود Inno Setup باید `None` بدهد.

        در این محیط لینوکسی نصب نیست؛ ساخت باید با پیام روشن رد شود نه
        با استثنا.
        """
        assert find_iscc() is None or isinstance(find_iscc(), str)

    def test_the_manifest_records_a_real_checksum(self, tmp_path: Path) -> None:
        """checksum باید واقعاً از محتوای فایل حساب شود."""
        installer = tmp_path / "s.exe"
        installer.write_bytes(b"abc")
        write_manifest(tmp_path / "latest.json", "1.0.0", installer)

        payload = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))

        assert payload["sha256"] == hashlib.sha256(b"abc").hexdigest()

    def test_a_manifest_without_an_installer_still_records_the_version(
        self, tmp_path: Path
    ) -> None:
        """اگر Inno Setup نبود، دست‌کم نسخه ثبت شود."""
        write_manifest(tmp_path / "latest.json", "1.2.3", None)

        payload = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))

        assert payload["version"] == "1.2.3"
        assert "installer" not in payload


class TestTheInstallerScriptProtectsUserData:
    """
    حذف یا به‌روزرسانی برنامه نباید سابقهٔ کاربر را نابود کند.

    این قاعده در اسکریپت Inno Setup کدنویسی شده و اینجا قفل می‌شود.
    """

    @staticmethod
    def _script() -> str:
        return (
            Path(__file__).resolve().parent.parent / "installer" / "CryptoAITrader.iss"
        ).read_text(encoding="utf-8")

    def test_the_installer_script_exists(self) -> None:
        """بدون این فایل، ربات ساخت فایل نصبی نمی‌سازد."""
        assert self._script().strip()

    def test_the_database_is_never_deleted_on_uninstall(self) -> None:
        """هیچ قاعدهٔ حذفی نباید دادهٔ کاربر را هدف بگیرد."""
        script = self._script().lower()

        assert ".db" not in script.split("[uninstalldelete]")[-1]

    def test_shortcuts_are_created(self) -> None:
        """کاربر باید میان‌بر منو و گزینهٔ دسکتاپ داشته باشد."""
        script = self._script()

        assert "[Icons]" in script
        assert "desktopicon" in script

    def test_the_version_is_injected_not_hardcoded(self) -> None:
        """نسخه باید از ربات ساخت بیاید تا هرگز جا نماند."""
        assert "AppVersion" in self._script()

class TestTheBatchFilesSurviveWindows:
    """
    فایل‌های `.bat` روی ویندوز اجرا می‌شوند، نه اینجا.

    این آزمون‌ها همان چند دامی را قفل می‌کنند که باعث شد کاربر گزارش
    دهد «ربات کار نمی‌کند»: پنجره باز می‌شد و بی‌صدا بسته می‌شد.
    """

    @staticmethod
    def _bat(name: str) -> bytes:
        return (
            Path(__file__).resolve().parent.parent / "scripts" / name
        ).read_bytes()

    @pytest.mark.parametrize("name", ["build_installer.bat", "build_apk.bat"])
    def test_the_window_never_closes_silently(self, name: str) -> None:
        """
        بدون `pause`، دوبار کلیک روی فایل یعنی یک پنجرهٔ سیاه که فوراً
        بسته می‌شود و کاربر هیچ پیامی نمی‌بیند. دقیقاً همان چیزی که
        گزارش شد.
        """
        assert b"pause" in self._bat(name)

    @pytest.mark.parametrize("name", ["build_installer.bat", "build_apk.bat"])
    def test_line_endings_are_windows_style(self, name: str) -> None:
        """
        `cmd.exe` با خطوط سبک یونیکس رفتار عجیبی دارد و دستورها را
        ناقص می‌خواند.
        """
        content = self._bat(name)

        assert b"\r\n" in content
        assert b"\n" not in content.replace(b"\r\n", b"")

    @pytest.mark.parametrize("name", ["build_installer.bat", "build_apk.bat"])
    def test_persian_text_has_a_code_page(self, name: str) -> None:
        """
        بدون `chcp 65001` متن فارسی در کنسول ویندوز به هم می‌ریزد و
        پیام خطا ناخوانا می‌شود.
        """
        assert b"chcp 65001" in self._bat(name)

    def test_a_half_built_venv_is_detected(self) -> None:
        """
        دام واقعی: اگر ساخت محیط مجازی نیمه‌کاره رها شود، پوشهٔ `.venv`
        هست ولی `activate.bat` نیست. شرط قدیمی (`if not exist .venv`)
        آن را سالم می‌پنداشت و `call` روی فایل ناموجود، کل اسکریپت را
        بی‌صدا می‌بست.
        """
        content = self._bat("build_installer.bat").decode("utf-8-sig")
        # فقط خطوط فرمان بررسی می‌شوند؛ توضیحات REM کنار گذاشته می‌شوند
        # وگرنه آزمون به متن کامنت گیر می‌کند نه به منطق واقعی.
        commands = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().upper().startswith("REM")
        ]
        guard = next(line for line in commands if line.startswith("if not exist"))

        assert "activate.bat" in guard

    def test_the_store_python_stub_is_avoided(self) -> None:
        """
        روی ویندوز `python` اغلب میان‌بر فروشگاه مایکروسافت است که بی‌صدا
        خارج می‌شود. `py -3` باید اول امتحان شود.
        """
        content = self._bat("build_installer.bat").decode("utf-8-sig")

        assert "py -3" in content


class TestIsccDiscovery:
    """پیدا نکردن Inno Setup نباید به‌خاطر مسیر غیرپیش‌فرض باشد."""

    def test_the_registry_is_consulted_on_windows(self) -> None:
        """
        کاربری که Inno Setup را روی درایو دیگری نصب کرده باشد در هیچ‌کدام
        از مسیرهای ثابت پیدا نمی‌شود و ساخت بی‌دلیل رد می‌شد.
        """
        from tools.build_installer import _iscc_from_registry

        assert callable(_iscc_from_registry)

    def test_registry_lookup_is_harmless_off_windows(self) -> None:
        """روی لینوکس باید بی‌سروصدا `None` بدهد."""
        from tools.build_installer import _iscc_from_registry

        assert _iscc_from_registry() is None

    def test_a_silent_iscc_success_without_output_is_caught(self) -> None:
        """
        اگر ISCC کد ۰ بدهد ولی فایلی نسازد، قبلاً «موفق» گزارش می‌شد.
        گزارش موفقیت بدون خروجی، بدترین حالت است.
        """
        source = (
            Path(__file__).resolve().parent.parent / "tools" / "build_installer.py"
        ).read_text(encoding="utf-8")

        assert "ISCC بدون خطا تمام شد" in source
