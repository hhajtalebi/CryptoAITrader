"""
مخازن سیستمی: سابقه پشتیبان‌گیری و گزارش‌ها.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.database.models import BackupHistory, ReportRecord
from app.database.repositories.base import BaseRepository


class BackupHistoryRepository(BaseRepository[BackupHistory]):
    """ثبت و بازیابی سابقه نسخه‌های پشتیبان."""

    model = BackupHistory

    def record_backup(
        self, file_path: str, size_bytes: int, *, backup_type: str = "manual", note: str = ""
    ) -> int:
        """ثبت یک نسخه پشتیبان موفق."""
        with self._db.session_scope() as session:
            record = BackupHistory(
                file_path=file_path,
                size_bytes=size_bytes,
                backup_type=backup_type,
                status="success",
                note=note,
            )
            session.add(record)
            session.flush()
            return record.id

    def list_recent(self, limit: int = 20) -> list[BackupHistory]:
        """فهرست آخرین پشتیبان‌ها برای نمایش در تنظیمات."""
        with self._db.session_scope() as session:
            return list(
                session.execute(
                    select(BackupHistory).order_by(BackupHistory.created_at.desc()).limit(limit)
                ).scalars().all()
            )


class ReportRepository(BaseRepository[ReportRecord]):
    """ثبت سابقه گزارش‌های خروجی‌گرفته‌شده."""

    model = ReportRecord

    def record_report(
        self,
        *,
        title: str,
        report_type: str,
        export_format: str,
        file_path: str,
        row_count: int,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """ثبت یک گزارش تولیدشده."""
        with self._db.session_scope() as session:
            record = ReportRecord(
                title=title,
                report_type=report_type,
                export_format=export_format,
                file_path=file_path,
                row_count=row_count,
                filters=filters or {},
            )
            session.add(record)
            session.flush()
            return record.id

    def list_recent(self, limit: int = 50) -> list[ReportRecord]:
        """فهرست آخرین گزارش‌ها."""
        with self._db.session_scope() as session:
            return list(
                session.execute(
                    select(ReportRecord).order_by(ReportRecord.created_at.desc()).limit(limit)
                ).scalars().all()
            )
