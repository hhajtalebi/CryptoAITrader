"""
مدیریت اتصال و نشست پایگاه داده.

چرا وجود دارد؟
    ساخت Engine و Session باید یکجا و با تنظیمات درست SQLite انجام شود:
    فعال‌سازی WAL برای همزمانی بهتر، فعال‌سازی Foreign Keys (که در SQLite
    به‌صورت پیش‌فرض خاموش است) و مدیریت صحیح چرخه عمر نشست.

ارتباط با ماژول‌های دیگر:
    Bootstrap این کلاس را می‌سازد و به Repositoryها تزریق می‌کند
    (Dependency Injection). هیچ ماژولی نباید Engine جداگانه بسازد.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect

from app.database.models import Base
from app.exceptions import DatabaseError
from app.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    نگهدارنده Engine و کارخانه نشست‌ها.

    استفاده معمول:
        db = DatabaseManager(url)
        db.create_all()
        with db.session_scope() as session:
            ...
    """

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        self.database_url = database_url
        self._engine: Engine = self._create_engine(echo=echo)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)
        logger.debug("DatabaseManager initialized for %s", self._safe_url())

    # ------------------------------------------------------------------
    # ساخت و پیکربندی
    # ------------------------------------------------------------------
    def _create_engine(self, *, echo: bool) -> Engine:
        """
        ساخت Engine با تنظیمات بهینه SQLite.

        check_same_thread=False لازم است چون رابط گرافیکی و کارهای پس‌زمینه
        ممکن است از Threadهای متفاوت به پایگاه داده دسترسی بگیرند؛ همزمانی
        نوشتن با WAL و Timeout مدیریت می‌شود.
        """
        try:
            engine = create_engine(
                self.database_url,
                echo=echo,
                future=True,
                connect_args={"check_same_thread": False, "timeout": 20},
            )
        except SQLAlchemyError as exc:
            raise DatabaseError("Failed to create database engine") from exc

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            """اعمال PRAGMAهای لازم روی هر اتصال جدید SQLite."""
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA busy_timeout=10000")
            finally:
                cursor.close()

        return engine

    def _safe_url(self) -> str:
        """نمایش نشانی پایگاه داده بدون افشای اطلاعات حساس احتمالی."""
        if "://" in self.database_url:
            scheme, _, rest = self.database_url.partition("://")
            return f"{scheme}://{Path(rest).name}" if rest else scheme
        return self.database_url

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    @property
    def engine(self) -> Engine:
        """دسترسی مستقیم به Engine (برای Alembic و پشتیبان‌گیری)."""
        return self._engine

    def create_all(self) -> None:
        """
        ساخت تمام جداول در صورت نبود.

        این عملیات ایمن است و جدول موجود را تغییر نمی‌دهد؛ تغییرات ساختاری
        از طریق Alembic انجام می‌شود.
        """
        try:
            Base.metadata.create_all(self._engine)
            self._add_missing_columns()
            logger.info("Database schema ensured (%d tables)", len(Base.metadata.tables))
        except SQLAlchemyError as exc:
            raise DatabaseError("Failed to create database schema") from exc

    def _add_missing_columns(self) -> None:
        """
        افزودن ستون‌های تازه به جدول‌های از پیش موجود.

        چرا لازم است: `create_all` جدول نبوده را می‌سازد ولی جدول موجود را
        **دست نمی‌زند**. پس هر ستون تازه‌ای که به مدل‌ها اضافه شود، روی
        پایگاه دادهٔ کاربرانِ فعلی وجود نخواهد داشت و برنامه با خطای
        «no such column» از کار می‌افتد — دقیقاً همان اتفاقی که با افزودن
        `paper_trades.last_price` رخ داد.

        این کار فقط **افزودنی** است: هیچ ستونی حذف یا تغییر نمی‌کند و هیچ
        داده‌ای بازنویسی نمی‌شود. قاعدهٔ همیشگی پروژه این است که دادهٔ
        کاربر هرگز پاک نشود.
        """
        if not self._engine.url.get_backend_name().startswith("sqlite"):
            # سایر پایگاه‌های داده مسیر رسمی Alembic را دارند.
            return

        inspector = inspect(self._engine)
        try:
            existing_tables = set(inspector.get_table_names())
        except SQLAlchemyError:
            logger.warning("Could not inspect the database schema", exc_info=True)
            return

        added = 0
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                # ستون با کلید اصلی یا یکتا را نمی‌شود بی‌خطر اضافه کرد؛
                # آن مورد نیاز به مهاجرت واقعی دارد.
                if column.primary_key or column.unique:
                    logger.warning(
                        "Column %s.%s needs a real migration; skipping",
                        table.name,
                        column.name,
                    )
                    continue
                try:
                    ddl = self._column_ddl(column)
                except Exception:  # noqa: BLE001 - نوع ناشناخته نباید برنامه را ببندد
                    logger.warning(
                        "Cannot build DDL for %s.%s", table.name, column.name, exc_info=True
                    )
                    continue
                statement = f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'
                try:
                    with self._engine.begin() as connection:
                        connection.execute(text(statement))
                except SQLAlchemyError:
                    logger.warning("Failed to add %s.%s", table.name, column.name, exc_info=True)
                    continue
                added += 1
                logger.info("Added missing column %s.%s", table.name, column.name)

        if added:
            logger.info("Schema reconciliation added %d column(s)", added)

    @staticmethod
    def _column_ddl(column: Any) -> str:
        """
        ساخت عبارت DDL یک ستون برای SQLite.

        ستون تازه روی جدولِ پر باید یا `NULL` بپذیرد یا مقدار پیش‌فرض
        داشته باشد، وگرنه SQLite عملیات را رد می‌کند.
        """
        column_type = column.type.compile(dialect=sqlite_dialect())
        parts = [f'"{column.name}"', column_type]

        default = None
        if column.server_default is not None:
            default = str(column.server_default.arg)
        elif column.default is not None and not column.default.is_callable:
            value = column.default.arg
            if isinstance(value, bool):
                default = "1" if value else "0"
            elif isinstance(value, (int, float)):
                default = str(value)
            elif isinstance(value, str):
                escaped = value.replace("'", "''")
                default = f"'{escaped}'"

        if not column.nullable:
            if default is None:
                # مقدار خنثی بر پایهٔ نوع، تا ستون NOT NULL قابل افزودن باشد.
                affinity = column_type.upper()
                if any(token in affinity for token in ("INT", "FLOAT", "REAL", "NUMERIC", "DECIMAL")):
                    default = "0"
                elif "BOOL" in affinity:
                    default = "0"
                elif "JSON" in affinity:
                    default = "'{}'"
                else:
                    default = "''"
            parts.append("NOT NULL")

        if default is not None:
            parts.append(f"DEFAULT {default}")
        return " ".join(parts)

    def create_session(self) -> Session:
        """ساخت یک نشست جدید که مدیریت آن بر عهده فراخوان است."""
        return self._session_factory()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """
        مدیریت خودکار نشست: Commit در موفقیت و Rollback در خطا.

        این روش از نشتی نشست (Session Leak) جلوگیری می‌کند.
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error("Database transaction failed: %s", exc.__class__.__name__)
            raise DatabaseError("Database transaction failed") from exc
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def check_connection(self) -> bool:
        """بررسی سلامت اتصال؛ برای نمایش وضعیت در داشبورد استفاده می‌شود."""
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.error("Database health check failed: %s", exc.__class__.__name__)
            return False

    def get_database_size(self) -> int:
        """اندازه فایل پایگاه داده بر حسب بایت (۰ اگر فایل نباشد)."""
        if not self.database_url.startswith("sqlite:///"):
            return 0
        path = Path(self.database_url.replace("sqlite:///", "", 1))
        return path.stat().st_size if path.exists() else 0

    def vacuum(self) -> None:
        """
        فشرده‌سازی فایل پایگاه داده و آزادسازی فضای بلااستفاده.

        پس از حذف حجم زیادی از کندل‌های قدیمی مفید است.
        """
        try:
            with self._engine.connect() as connection:
                connection.execute(text("VACUUM"))
                connection.commit()
            logger.info("Database vacuum completed")
        except SQLAlchemyError as exc:
            logger.error("Vacuum failed: %s", exc.__class__.__name__)

    def dispose(self) -> None:
        """بستن تمام اتصال‌های باز هنگام خروج از برنامه."""
        self._engine.dispose()
        logger.debug("Database engine disposed")


_database_manager: DatabaseManager | None = None


def get_database_manager(database_url: str | None = None, *, echo: bool = False) -> DatabaseManager:
    """
    دریافت نمونه مشترک DatabaseManager.

    اولین فراخوانی باید نشانی پایگاه داده را تعیین کند؛ فراخوانی‌های بعدی
    همان نمونه را برمی‌گردانند تا چند Engine موازی ساخته نشود.
    """
    global _database_manager  # noqa: PLW0603 - Singleton کنترل‌شده
    if _database_manager is None:
        if database_url is None:
            from app.config.settings import get_app_settings  # noqa: PLC0415 - جلوگیری از Import دوری

            database_url = get_app_settings().effective_database_url
        _database_manager = DatabaseManager(database_url, echo=echo)
    return _database_manager


def reset_database_manager() -> None:
    """بازنشانی نمونه مشترک (فقط برای تست‌ها)."""
    global _database_manager  # noqa: PLW0603
    if _database_manager is not None:
        _database_manager.dispose()
    _database_manager = None
