"""
مخزن تنظیمات کاربر.

مهم‌ترین مسئولیت این مخزن، رعایت قانون «عدم بازنویسی تنظیمات کاربر» است:
متد ensure_defaults فقط کلیدهای غایب را اضافه می‌کند و هرگز مقدار موجود
را تغییر نمی‌دهد.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.database.models import SettingRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)


class SettingsRepository(BaseRepository[SettingRecord]):
    """دسترسی به جدول settings به‌صورت کلید/مقدار."""

    model = SettingRecord

    def get(self, key: str, default: Any = None) -> Any:
        """
        خواندن مقدار یک تنظیم.

        مقدار در ستون JSON درون کلید "v" بسته‌بندی می‌شود تا انواع ساده
        (عدد، رشته، بولین) هم قابل ذخیره باشند.
        """
        with self._db.session_scope() as session:
            record = session.execute(
                select(SettingRecord).where(SettingRecord.key == key)
            ).scalar_one_or_none()
            if record is None or record.value is None:
                return default
            return record.value.get("v", default)

    def set(self, key: str, value: Any, *, category: str = "general", user_modified: bool = True) -> None:
        """
        نوشتن یا به‌روزرسانی یک تنظیم.

        user_modified=True یعنی این مقدار توسط کاربر تعیین شده و در اجراهای
        بعدی نباید با مقدار پیش‌فرض جایگزین شود.
        """
        with self._db.session_scope() as session:
            record = session.execute(
                select(SettingRecord).where(SettingRecord.key == key)
            ).scalar_one_or_none()
            if record is None:
                record = SettingRecord(
                    key=key,
                    value={"v": value},
                    category=category,
                    is_user_modified=user_modified,
                )
                session.add(record)
            else:
                record.value = {"v": value}
                if user_modified:
                    record.is_user_modified = True

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        """خواندن گروهی چند تنظیم در یک Query (بهینه‌تر از چند فراخوانی)."""
        with self._db.session_scope() as session:
            records = session.execute(
                select(SettingRecord).where(SettingRecord.key.in_(keys))
            ).scalars().all()
            return {r.key: (r.value or {}).get("v") for r in records}

    def get_all(self) -> dict[str, Any]:
        """خواندن تمام تنظیمات به‌صورت دیکشنری."""
        with self._db.session_scope() as session:
            records = session.execute(select(SettingRecord)).scalars().all()
            return {r.key: (r.value or {}).get("v") for r in records}

    def get_by_category(self, category: str) -> dict[str, Any]:
        """خواندن تنظیمات یک دسته مشخص (برای صفحه تنظیمات)."""
        with self._db.session_scope() as session:
            records = session.execute(
                select(SettingRecord).where(SettingRecord.category == category)
            ).scalars().all()
            return {r.key: (r.value or {}).get("v") for r in records}

    def exists(self, key: str) -> bool:
        """آیا این کلید در پایگاه داده وجود دارد؟"""
        with self._db.session_scope() as session:
            return (
                session.execute(select(SettingRecord.id).where(SettingRecord.key == key)).first()
                is not None
            )

    def ensure_defaults(self, defaults: dict[str, Any], categories: dict[str, list[str]] | None = None) -> int:
        """
        درج مقادیر پیش‌فرض فقط برای کلیدهای غایب.

        بازگشتی: تعداد کلیدهایی که واقعاً اضافه شدند.

        این متد قلب قانون «حفظ تنظیمات کاربر» است و در هر بار اجرای برنامه
        فراخوانی می‌شود، اما هیچ مقدار موجودی را دست نمی‌زند.
        """
        category_of: dict[str, str] = {}
        if categories:
            for category, keys in categories.items():
                for key in keys:
                    category_of[key] = category

        inserted = 0
        with self._db.session_scope() as session:
            existing = set(session.execute(select(SettingRecord.key)).scalars().all())
            for key, value in defaults.items():
                if key in existing:
                    continue  # مقدار کاربر یا مقدار قبلی حفظ می‌شود
                session.add(
                    SettingRecord(
                        key=key,
                        value={"v": value},
                        category=category_of.get(key, key.split(".", 1)[0]),
                        is_user_modified=False,
                    )
                )
                inserted += 1
        if inserted:
            logger.info("Inserted %d default settings (existing values untouched)", inserted)
        return inserted

    def reset_key(self, key: str, default_value: Any) -> None:
        """بازگرداندن یک تنظیم به مقدار پیش‌فرض (به درخواست صریح کاربر)."""
        self.set(key, default_value, user_modified=False)
