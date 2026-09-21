"""آزمون پشتیبان‌گیری و بازیابی."""

from __future__ import annotations

import pytest

from app.config.settings_service import SettingsService
from app.core.paths import AppPaths
from app.database.repositories import SettingsRepository
from app.database.session import DatabaseManager
from app.exceptions import BackupError
from backup import BackupManager


@pytest.fixture()
def prepared(temp_paths: AppPaths):
    """پایگاه داده آماده با یک تنظیم شناخته‌شده."""
    database = DatabaseManager(temp_paths.database_url)
    database.create_all()
    settings = SettingsService(SettingsRepository(database))
    settings.initialize_defaults()
    settings.set("risk.max_leverage", 7)
    return temp_paths, database, settings


def test_backup_creates_valid_archive(prepared) -> None:
    """پشتیبان ساخته‌شده باید معتبر باشد."""
    paths, _, _ = prepared
    manager = BackupManager(paths)
    info = manager.create(note="test")
    assert info.path.exists()
    valid, message = manager.verify(info.path)
    assert valid, message


def test_manifest_records_metadata(prepared) -> None:
    """فراداده باید نسخه برنامه و جمع کنترلی داشته باشد."""
    paths, _, _ = prepared
    manager = BackupManager(paths)
    info = manager.create(note="metadata test")
    manifest = manager.read_manifest(info.path)
    assert manifest["app_version"]
    assert manifest["database_sha256"]
    assert manifest["contains_secrets"] is False


def test_secrets_are_never_included(prepared) -> None:
    """
    فایل رمزهای محرمانه هرگز نباید داخل پشتیبان برود.
    """
    import zipfile

    paths, _, _ = prepared
    paths.secret_store_file.write_bytes(b"super-secret")
    manager = BackupManager(paths)
    info = manager.create()
    with zipfile.ZipFile(info.path) as archive:
        names = archive.namelist()
    assert not any("secret" in name for name in names)


def test_restore_recovers_previous_value(prepared) -> None:
    """بازیابی باید مقدار قبلی را دقیقاً برگرداند."""
    paths, database, settings = prepared
    manager = BackupManager(paths)
    info = manager.create(note="leverage 7")

    settings.set("risk.max_leverage", 99)
    database.engine.dispose()

    manager.restore(info.path)
    reopened = SettingsService(SettingsRepository(DatabaseManager(paths.database_url)))
    assert reopened.get("risk.max_leverage") == 7


def test_restore_creates_safety_backup(prepared) -> None:
    """پیش از بازیابی باید یک نسخه ایمنی ساخته شود."""
    paths, database, _ = prepared
    manager = BackupManager(paths)
    info = manager.create()
    database.engine.dispose()
    manager.restore(info.path)
    assert any(b.backup_type == "pre_restore" for b in manager.list_backups())


def test_backups_in_same_second_do_not_overwrite(prepared) -> None:
    """چند پشتیبان در یک ثانیه باید نام یکتا بگیرند."""
    paths, _, _ = prepared
    manager = BackupManager(paths)
    first = manager.create(note="one")
    second = manager.create(note="two")
    assert first.path != second.path
    assert first.path.exists() and second.path.exists()


def test_corrupt_archive_is_refused(prepared) -> None:
    """بازیابی از فایل خراب باید رد شود."""
    paths, _, _ = prepared
    manager = BackupManager(paths)
    corrupt = paths.backups_dir / "backup_20200101_000000.zip"
    corrupt.write_bytes(b"this is not a zip file")

    valid, _ = manager.verify(corrupt)
    assert not valid
    with pytest.raises(BackupError):
        manager.restore(corrupt)


def test_corrupt_archive_is_listed_as_invalid(prepared) -> None:
    """فایل خراب باید در فهرست با علامت نامعتبر دیده شود، نه اینکه حذف گردد."""
    paths, _, _ = prepared
    manager = BackupManager(paths)
    (paths.backups_dir / "backup_20200101_000000.zip").write_bytes(b"broken")
    invalid = [b for b in manager.list_backups() if not b.valid]
    assert len(invalid) == 1


def test_pre_migration_backup_skipped_without_database(temp_paths: AppPaths) -> None:
    """اگر هنوز پایگاه داده‌ای نیست، مهاجرت نباید مسدود شود."""
    manager = BackupManager(temp_paths)
    assert manager.create_pre_migration() is None
