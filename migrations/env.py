"""
پیکربندی زمان اجرای Alembic.

دو تفاوت مهم با قالب پیش‌فرض Alembic:
    ۱) نشانی پایگاه داده از `AppPaths` خوانده می‌شود، نه از alembic.ini —
       چون مسیر داده در ویندوز به %APPDATA% کاربر بستگی دارد.
    ۲) **پیش از هر مهاجرت، پشتیبان خودکار گرفته می‌شود** (بند ۳۶ سند
       پروژه). اگر پشتیبان‌گیری شکست بخورد، مهاجرت انجام نمی‌شود.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# افزودن ریشه پروژه به مسیر واردسازی
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.paths import app_paths  # noqa: E402
from app.database.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

#: فراداده مدل‌ها برای تشخیص خودکار تغییرات
target_metadata = Base.metadata

# نشانی واقعی پایگاه داده کاربر
app_paths.ensure()
config.set_main_option("sqlalchemy.url", app_paths.database_url)


def _backup_before_migration() -> None:
    """
    تهیه پشتیبان خودکار پیش از اجرای مهاجرت.

    اگر متغیر محیطی `CAT_SKIP_MIGRATION_BACKUP=1` تنظیم شده باشد (فقط برای
    تست)، این مرحله رد می‌شود.
    """
    import os

    if os.getenv("CAT_SKIP_MIGRATION_BACKUP") == "1":
        return
    if context.is_offline_mode():
        return
    try:
        from backup import BackupManager

        info = BackupManager(app_paths).create_pre_migration()
        if info is not None:
            print(f"[alembic] Automatic backup created: {info.path.name}")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Refusing to migrate without a backup: {exc.__class__.__name__}: {exc}"
        ) from exc


def run_migrations_offline() -> None:
    """اجرای مهاجرت در حالت آفلاین (تولید اسکریپت SQL)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """اجرای مهاجرت روی پایگاه داده واقعی."""
    _backup_before_migration()

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite برای ALTER TABLE محدودیت دارد؛ حالت دسته‌ای لازم است
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
