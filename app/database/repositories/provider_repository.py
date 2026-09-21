"""
مخازن پیکربندی ارائه‌دهندگان (صرافی و هوش مصنوعی).

نکته امنیتی: هیچ‌کدام از این مخازن کلید یا رمز ذخیره نمی‌کنند؛ فقط پرچم
has_credentials را نگه می‌دارند و مقدار واقعی در Secret Store سیستم‌عامل است.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database.models import AIProviderRecord, ExchangeProviderRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)


class ExchangeProviderRepository(BaseRepository[ExchangeProviderRecord]):
    """پیکربندی صرافی‌های ثبت‌شده."""

    model = ExchangeProviderRecord

    def get_by_name(self, name: str) -> ExchangeProviderRecord | None:
        """یافتن پیکربندی یک صرافی بر اساس نام یکتا."""
        with self._db.session_scope() as session:
            return session.execute(
                select(ExchangeProviderRecord).where(ExchangeProviderRecord.name == name)
            ).scalar_one_or_none()

    def ensure_provider(self, name: str, defaults: dict[str, Any]) -> ExchangeProviderRecord:
        """
        ایجاد رکورد صرافی در صورت نبود (بدون بازنویسی تنظیمات کاربر).
        """
        with self._db.session_scope() as session:
            record = session.execute(
                select(ExchangeProviderRecord).where(ExchangeProviderRecord.name == name)
            ).scalar_one_or_none()
            if record is None:
                record = ExchangeProviderRecord(name=name, **defaults)
                session.add(record)
                session.flush()
                logger.info("Exchange provider registered: %s", name)
            session.refresh(record)
            return record

    def update_status(
        self, name: str, *, connected: bool = False, error: str = "", has_credentials: bool | None = None
    ) -> None:
        """به‌روزرسانی وضعیت اتصال یک صرافی."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(ExchangeProviderRecord).where(ExchangeProviderRecord.name == name)
            ).scalar_one_or_none()
            if record is None:
                return
            if connected:
                record.last_connected_at = datetime.now(timezone.utc).replace(tzinfo=None)
            record.last_error = error[:500]
            if has_credentials is not None:
                record.has_credentials = has_credentials

    def list_enabled(self) -> list[ExchangeProviderRecord]:
        """فهرست صرافی‌های فعال."""
        with self._db.session_scope() as session:
            return list(
                session.execute(
                    select(ExchangeProviderRecord).where(ExchangeProviderRecord.enabled.is_(True))
                ).scalars().all()
            )


class AIProviderRepository(BaseRepository[AIProviderRecord]):
    """پیکربندی ارائه‌دهندگان هوش مصنوعی و ترتیب اولویت آن‌ها."""

    model = AIProviderRecord

    def get_by_name(self, name: str) -> AIProviderRecord | None:
        """یافتن پیکربندی یک ارائه‌دهنده هوش مصنوعی."""
        with self._db.session_scope() as session:
            return session.execute(
                select(AIProviderRecord).where(AIProviderRecord.name == name)
            ).scalar_one_or_none()

    def ensure_provider(self, name: str, defaults: dict[str, Any]) -> AIProviderRecord:
        """ایجاد رکورد ارائه‌دهنده در صورت نبود (تنظیمات موجود دست‌نخورده)."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(AIProviderRecord).where(AIProviderRecord.name == name)
            ).scalar_one_or_none()
            if record is None:
                record = AIProviderRecord(name=name, **defaults)
                session.add(record)
                session.flush()
                logger.info("AI provider registered: %s", name)
            session.refresh(record)
            return record

    def list_by_priority(self, *, enabled_only: bool = True) -> list[AIProviderRecord]:
        """
        فهرست ارائه‌دهندگان مرتب بر اساس اولویت (عدد کمتر = اولویت بالاتر).

        این ترتیب، زنجیره Fallback هوش مصنوعی را تعیین می‌کند.
        """
        with self._db.session_scope() as session:
            stmt = select(AIProviderRecord)
            if enabled_only:
                stmt = stmt.where(AIProviderRecord.enabled.is_(True))
            stmt = stmt.order_by(AIProviderRecord.priority, AIProviderRecord.id)
            return list(session.execute(stmt).scalars().all())

    def update_config(self, name: str, **fields: Any) -> bool:
        """
        به‌روزرسانی پیکربندی یک ارائه‌دهنده.

        فقط فیلدهای مجاز پذیرفته می‌شوند تا ستون‌های سیستمی تغییر نکنند.
        """
        allowed = {
            "display_name", "provider_type", "base_url", "model", "temperature",
            "max_tokens", "timeout", "priority", "enabled", "requires_api_key",
            "has_credentials", "extra_config",
        }
        with self._db.session_scope() as session:
            record = session.execute(
                select(AIProviderRecord).where(AIProviderRecord.name == name)
            ).scalar_one_or_none()
            if record is None:
                return False
            for key, value in fields.items():
                if key in allowed:
                    setattr(record, key, value)
            return True

    def mark_used(self, name: str, *, error: str = "") -> None:
        """ثبت زمان آخرین استفاده یا آخرین خطای یک ارائه‌دهنده."""
        with self._db.session_scope() as session:
            record = session.execute(
                select(AIProviderRecord).where(AIProviderRecord.name == name)
            ).scalar_one_or_none()
            if record is None:
                return
            record.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
            record.last_error = error[:500]
