"""
کلاس پایه مخازن داده.

عملیات مشترک (افزودن، یافتن با شناسه، حذف، شمارش) اینجا یک بار نوشته شده
تا اصل DRY رعایت شود و مخازن فرزند فقط منطق اختصاصی خود را داشته باشند.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.database.models import Base
from app.database.session import DatabaseManager
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    مخزن عمومی برای عملیات پایه روی یک مدل.

    وابستگی DatabaseManager از بیرون تزریق می‌شود تا در تست بتوان پایگاه
    داده موقت جایگزین کرد.
    """

    model: type[ModelType]

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    @property
    def db(self) -> DatabaseManager:
        """دسترسی به مدیر پایگاه داده برای مخازن فرزند."""
        return self._db

    def add(self, entity: ModelType) -> ModelType:
        """افزودن یک رکورد جدید و بازگرداندن آن پس از Commit."""
        try:
            with self._db.session_scope() as session:
                session.add(entity)
                session.flush()
                session.refresh(entity)
                return entity
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Failed to add {self.model.__name__}") from exc

    def get_by_id(self, entity_id: int) -> ModelType | None:
        """یافتن یک رکورد بر اساس شناسه."""
        with self._db.session_scope() as session:
            return session.get(self.model, entity_id)

    def list_all(self, limit: int | None = None) -> list[ModelType]:
        """فهرست تمام رکوردها با محدودیت اختیاری تعداد."""
        with self._db.session_scope() as session:
            stmt = select(self.model)
            if limit is not None:
                stmt = stmt.limit(limit)
            return list(session.execute(stmt).scalars().all())

    def delete_by_id(self, entity_id: int) -> bool:
        """حذف یک رکورد؛ True یعنی رکورد وجود داشت و حذف شد."""
        with self._db.session_scope() as session:
            entity = session.get(self.model, entity_id)
            if entity is None:
                return False
            session.delete(entity)
            return True

    def count(self) -> int:
        """شمارش کل رکوردها."""
        with self._db.session_scope() as session:
            return int(session.execute(select(func.count()).select_from(self.model)).scalar() or 0)
