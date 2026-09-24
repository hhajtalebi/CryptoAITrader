"""
مدیریت پشتیبان‌گیری و بازیابی.

چرا وجود دارد؟
    از دست رفتن سابقه سیگنال‌ها و تنظیمات کاربر غیرقابل جبران است. این
    ماژول تضمین می‌کند:
        • پیش از هر مهاجرت پایگاه داده، پشتیبان خودکار گرفته شود
        • بازیابی هرگز داده فعلی را بدون نسخه ایمنی از بین نبرد
        • فایل پشتیبان قابل حمل باشد (یک فایل ZIP شامل پایگاه داده و تنظیمات)

ساختار فایل پشتیبان:
    backup_YYYYMMDD_HHMMSS.zip
    ├── crypto_ai_trader.db     پایگاه داده کامل
    ├── settings.json           تنظیمات (در صورت وجود)
    └── manifest.json           فراداده: نسخه برنامه، زمان، اندازه، جمع کنترلی

نکته امنیتی:
    فایل رمزهای محرمانه (`.secret_store.bin`) و کلیدهای Keyring **هرگز**
    در پشتیبان قرار نمی‌گیرند؛ انتقال آن‌ها میان دستگاه‌ها ناامن است و
    کاربر باید کلیدهای خارج از DB را دوباره وارد کند. در مقابل، انبار
    رمزنگاری‌شدهٔ داخل DB برای بازیابی بدون اتلاف نگه داشته می‌شود و
    manifest آن را صریحاً حساس علامت می‌زند؛ backup را عمومی نکنید.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.constants import APP_VERSION
from app.core.paths import AppPaths, app_paths
from app.exceptions import BackupError
from app.logging import get_logger

logger = get_logger(__name__)

MANIFEST_NAME = "manifest.json"
DATABASE_ENTRY = "crypto_ai_trader.db"
SETTINGS_ENTRY = "settings.json"


@dataclass(slots=True)
class BackupInfo:
    """اطلاعات یک فایل پشتیبان."""

    path: Path
    created_at: datetime
    size_bytes: int
    app_version: str = ""
    backup_type: str = "manual"
    note: str = ""
    valid: bool = True
    error: str = ""

    @property
    def size_mb(self) -> float:
        """اندازه بر حسب مگابایت، برای نمایش در رابط کاربری."""
        return round(self.size_bytes / (1024 * 1024), 3)

    def to_dict(self) -> dict[str, Any]:
        """تبدیل برای نمایش در جدول تنظیمات."""
        return {
            "file_name": self.path.name,
            "path": str(self.path),
            "created_at": self.created_at.isoformat(),
            "size_mb": self.size_mb,
            "app_version": self.app_version,
            "backup_type": self.backup_type,
            "note": self.note,
            "valid": self.valid,
            "error": self.error,
        }


class BackupManager:
    """
    سازنده و بازگرداننده نسخه‌های پشتیبان.

    نمونه‌سازی:
        manager = BackupManager()
        info = manager.create(backup_type="manual", note="پیش از تغییر تنظیمات")
    """

    def __init__(self, paths: AppPaths | None = None, *, max_backups: int = 20) -> None:
        self._paths = paths or app_paths
        self._max_backups = max(1, int(max_backups))

    # ------------------------------------------------------------------
    # ساخت پشتیبان
    # ------------------------------------------------------------------
    def create(self, *, backup_type: str = "manual", note: str = "") -> BackupInfo:
        """
        ساخت یک نسخه پشتیبان کامل.

        از `sqlite3.backup` استفاده می‌شود، نه کپی ساده فایل: کپی فایل در
        حین نوشتن برنامه می‌تواند پایگاه داده خراب تولید کند، ولی این روش
        یک تصویر منسجم (Consistent Snapshot) می‌سازد.
        """
        self._paths.ensure()
        database_file = self._paths.database_file
        if not database_file.exists():
            raise BackupError(
                "Database file does not exist yet; nothing to back up",
                details={"path": str(database_file)},
            )

        timestamp = datetime.now(UTC)
        # نام فایل باید یکتا باشد: چند پشتیبان در یک ثانیه (مثلاً پشتیبان
        # ایمنی درست پیش از بازیابی) نباید یکدیگر را بازنویسی کنند.
        target = self._unique_target(timestamp)
        temp_db = self._paths.backups_dir / f".tmp_{target.stem}.db"
        try:
            self._snapshot_database(database_file, temp_db)
            checksum = self._sha256(temp_db)
            # خود snapshot بررسی شود، نه تنظیم جاری برنامه: ممکن است
            # backend عوض شده باشد ولی رکورد رمزنگاری‌شده هنوز در DB باشد.
            encrypted_secrets = self._has_encrypted_secrets(temp_db)
            settings_data = (
                self._paths.settings_file.read_bytes()
                if self._paths.settings_file.exists() else None
            )

            manifest = {
                "app_version": APP_VERSION,
                "created_at": timestamp.isoformat(),
                "backup_type": backup_type,
                "note": note,
                "database_sha256": checksum,
                "database_size": temp_db.stat().st_size,
                # settings.json قدیمی schema تضمین‌شده‌ای ندارد؛ اگر
                # همراه بسته باشد، نبود راز را بی‌بررسی ادعا نمی‌کنیم.
                "contains_secrets": encrypted_secrets or settings_data is not None,
                "contains_encrypted_db_secrets": encrypted_secrets,
                "contains_uninspected_settings": settings_data is not None,
            }

            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(temp_db, DATABASE_ENTRY)
                if settings_data is not None:
                    archive.writestr(SETTINGS_ENTRY, settings_data)
                archive.writestr(MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2))
        except BackupError:
            raise
        except Exception as exc:  # noqa: BLE001
            if target.exists():
                target.unlink(missing_ok=True)
            raise BackupError(
                f"Failed to create backup: {exc.__class__.__name__}", details={"error": str(exc)}
            ) from exc
        finally:
            temp_db.unlink(missing_ok=True)

        size = target.stat().st_size
        logger.info("Backup created: %s (%.2f MB)", target.name, size / 1024 / 1024)
        self._prune()
        return BackupInfo(
            path=target,
            created_at=timestamp,
            size_bytes=size,
            app_version=APP_VERSION,
            backup_type=backup_type,
            note=note,
        )

    def create_pre_migration(self, note: str = "") -> BackupInfo | None:
        """
        پشتیبان خودکار پیش از مهاجرت پایگاه داده.

        اگر پایگاه داده هنوز ساخته نشده باشد (اولین اجرا)، None برمی‌گردد
        و مهاجرت بدون مانع ادامه می‌یابد.
        """
        if not self._paths.database_file.exists():
            logger.info("No database yet; skipping pre-migration backup")
            return None
        return self.create(
            backup_type="pre_migration", note=note or "Automatic backup before database migration"
        )

    # ------------------------------------------------------------------
    # فهرست و بررسی
    # ------------------------------------------------------------------
    def list_backups(self) -> list[BackupInfo]:
        """
        فهرست نسخه‌های پشتیبان موجود، از جدید به قدیم.

        فایل‌های خراب حذف نمی‌شوند بلکه با `valid=False` علامت می‌خورند تا
        کاربر خودش تصمیم بگیرد.
        """
        if not self._paths.backups_dir.exists():
            return []

        items: list[BackupInfo] = []
        for path in sorted(
            self._paths.backups_dir.glob("backup_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                manifest = self.read_manifest(path)
                items.append(
                    BackupInfo(
                        path=path,
                        created_at=datetime.fromisoformat(manifest["created_at"]),
                        size_bytes=path.stat().st_size,
                        app_version=manifest.get("app_version", ""),
                        backup_type=manifest.get("backup_type", "manual"),
                        note=manifest.get("note", ""),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                items.append(
                    BackupInfo(
                        path=path,
                        created_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
                        size_bytes=path.stat().st_size,
                        valid=False,
                        error=f"{exc.__class__.__name__}",
                    )
                )
        return items

    @staticmethod
    def read_manifest(archive_path: Path) -> dict[str, Any]:
        """خواندن فراداده یک فایل پشتیبان."""
        with zipfile.ZipFile(archive_path) as archive:
            if MANIFEST_NAME not in archive.namelist():
                raise BackupError("Backup file has no manifest", details={"file": archive_path.name})
            return json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))

    def verify(self, archive_path: Path) -> tuple[bool, str]:
        """
        بررسی سلامت یک فایل پشتیبان پیش از بازیابی.

        سه بررسی: سالم بودن ZIP، وجود پایگاه داده، و تطابق جمع کنترلی.
        """
        try:
            with zipfile.ZipFile(archive_path) as archive:
                if archive.testzip() is not None:
                    return False, "Archive is corrupted"
                names = archive.namelist()
                if DATABASE_ENTRY not in names:
                    return False, "Archive does not contain a database"
                manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
                expected = manifest.get("database_sha256", "")
                if expected:
                    digest = hashlib.sha256(archive.read(DATABASE_ENTRY)).hexdigest()
                    if digest != expected:
                        return False, "Database checksum mismatch"
            return True, "Backup is valid"
        except Exception as exc:  # noqa: BLE001
            return False, f"{exc.__class__.__name__}: {exc}"

    # ------------------------------------------------------------------
    # بازیابی
    # ------------------------------------------------------------------
    def restore(self, archive_path: Path, *, restore_settings: bool = True) -> BackupInfo:
        """
        بازگرداندن یک نسخه پشتیبان.

        **پیش از جایگزینی، از وضعیت فعلی یک پشتیبان ایمنی گرفته می‌شود** تا
        اگر کاربر اشتباهی نسخه نادرستی را بازگرداند، راه برگشت داشته باشد.

        هشدار: برنامه باید پیش از فراخوانی این متد، اتصال پایگاه داده را
        بسته باشد (در ویندوز فایل باز قابل جایگزینی نیست).
        """
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise BackupError("Backup file not found", details={"path": str(archive_path)})

        valid, message = self.verify(archive_path)
        if not valid:
            raise BackupError(f"Refusing to restore an invalid backup: {message}",
                              details={"file": archive_path.name})

        self._paths.ensure()
        safety: BackupInfo | None = None
        if self._paths.database_file.exists():
            safety = self.create(backup_type="pre_restore", note="Safety backup taken before restore")

        try:
            with zipfile.ZipFile(archive_path) as archive:
                temp_db = self._paths.data_dir / ".restore_tmp.db"
                with archive.open(DATABASE_ENTRY) as source, temp_db.open("wb") as target:
                    shutil.copyfileobj(source, target)

                # بررسی نهایی: آیا فایل بازیابی‌شده واقعاً پایگاه داده معتبری است؟
                self._assert_valid_sqlite(temp_db)
                # حیاتی: پایگاه داده در حالت WAL کار می‌کند. اگر فقط فایل
                # اصلی جایگزین شود ولی فایل‌های جانبی -wal و -shm بمانند،
                # تراکنش‌های قدیمی دوباره روی داده بازیابی‌شده اعمال شده و
                # بازیابی عملاً بی‌اثر می‌شود.
                self._remove_wal_sidecars()
                temp_db.replace(self._paths.database_file)
                self._remove_wal_sidecars()

                if restore_settings and SETTINGS_ENTRY in archive.namelist():
                    with archive.open(SETTINGS_ENTRY) as source, self._paths.settings_file.open("wb") as target:
                        shutil.copyfileobj(source, target)
        except BackupError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BackupError(
                f"Restore failed: {exc.__class__.__name__}",
                details={"error": str(exc), "safety_backup": str(safety.path) if safety else ""},
            ) from exc

        manifest = self.read_manifest(archive_path)
        logger.info("Backup restored from %s (created %s)", archive_path.name, manifest.get("created_at"))
        return BackupInfo(
            path=archive_path,
            created_at=datetime.fromisoformat(manifest["created_at"]),
            size_bytes=archive_path.stat().st_size,
            app_version=manifest.get("app_version", ""),
            backup_type=manifest.get("backup_type", "manual"),
            note=manifest.get("note", ""),
        )

    def delete(self, archive_path: Path) -> None:
        """حذف یک نسخه پشتیبان."""
        Path(archive_path).unlink(missing_ok=True)
        logger.info("Backup deleted: %s", Path(archive_path).name)

    # ------------------------------------------------------------------
    # کمکی‌ها
    # ------------------------------------------------------------------
    def _remove_wal_sidecars(self) -> None:
        """
        حذف فایل‌های جانبی WAL پایگاه داده.

        این فایل‌ها (`-wal` و `-shm`) حاوی تراکنش‌های تأییدنشده یا
        ادغام‌نشده‌اند و پس از جایگزینی فایل اصلی، دیگر معتبر نیستند.
        """
        database = self._paths.database_file
        for suffix in ("-wal", "-shm"):
            sidecar = database.with_name(database.name + suffix)
            if sidecar.exists():
                sidecar.unlink(missing_ok=True)
                logger.debug("Removed stale WAL sidecar: %s", sidecar.name)

    def _unique_target(self, timestamp: datetime) -> Path:
        """
        ساخت مسیر یکتا برای فایل پشتیبان.

        اگر نام پایه از قبل وجود داشته باشد، پسوند شماره‌دار اضافه می‌شود
        تا هیچ پشتیبانی بازنویسی نشود.
        """
        base = f"backup_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        candidate = self._paths.backups_dir / f"{base}.zip"
        counter = 1
        while candidate.exists():
            candidate = self._paths.backups_dir / f"{base}_{counter:02d}.zip"
            counter += 1
        return candidate

    @staticmethod
    def _snapshot_database(source: Path, target: Path) -> None:
        """
        ساخت تصویر منسجم از پایگاه داده با API رسمی SQLite.
        """
        source_conn = sqlite3.connect(source)
        target_conn = sqlite3.connect(target)
        try:
            # ادغام WAL تا تصویر شامل آخرین تراکنش‌های تأییدشده باشد
            try:
                source_conn.execute("PRAGMA wal_checkpoint(FULL)")
            except sqlite3.DatabaseError:
                pass  # اگر پایگاه داده در حالت WAL نباشد، اهمیتی ندارد
            with target_conn:
                source_conn.backup(target_conn)
        finally:
            source_conn.close()
            target_conn.close()

    @staticmethod
    def _has_encrypted_secrets(path: Path) -> bool:
        """
        تشخیص محافظه‌کارانهٔ رکورد انبار راز در snapshot، بدون رمزگشایی.

        حتی رکورد خالی/ناخوانا حساس فرض می‌شود. DB پیش از اولین migration
        ممکن است settings نداشته باشد؛ خطای خواندن واقعی باید ساخت backup
        را متوقف کند، نه اینکه با برچسب «بدون راز» پنهان شود.
        """
        from app.security.db_backend import SECRETS_SETTING_KEY

        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'"
            ).fetchone()
            if exists is None:
                return False
            return connection.execute(
                'SELECT 1 FROM settings WHERE "key" = ? LIMIT 1', (SECRETS_SETTING_KEY,)
            ).fetchone() is not None
        finally:
            connection.close()

    @staticmethod
    def _assert_valid_sqlite(path: Path) -> None:
        """اطمینان از اینکه فایل بازیابی‌شده یک پایگاه داده سالم است."""
        connection = sqlite3.connect(path)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise BackupError("Restored database failed the integrity check")
        finally:
            connection.close()

    @staticmethod
    def _sha256(path: Path) -> str:
        """محاسبه جمع کنترلی فایل به‌صورت تکه‌ای (برای فایل‌های بزرگ)."""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _prune(self) -> None:
        """
        حذف پشتیبان‌های قدیمی مازاد.

        پشتیبان‌های `pre_restore` هرگز خودکار حذف نمی‌شوند چون آخرین راه
        نجات کاربر هستند.
        """
        backups = [b for b in self.list_backups() if b.backup_type != "pre_restore"]
        if len(backups) <= self._max_backups:
            return
        for old in backups[self._max_backups :]:
            old.path.unlink(missing_ok=True)
            logger.info("Pruned old backup: %s", old.path.name)
