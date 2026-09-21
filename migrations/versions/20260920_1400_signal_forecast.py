"""افزودن ستون پیش‌بینی به جدول سیگنال‌ها.

بدون این ستون، پیش‌بینی تایم‌فریم بعدی فقط تا لحظهٔ بسته‌شدن پنجره
زنده می‌ماند و در سابقه از بین می‌رفت.

Revision ID: d1a7b3e05c62
Revises: c8d5f2a91e44
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d1a7b3e05c62"
down_revision: str | None = "c8d5f2a91e44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """افزودن ستون با فهرست خالی برای ردیف‌های موجود."""
    with op.batch_alter_table("signals") as batch:
        batch.add_column(
            sa.Column("forecast", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    """حذف ستون."""
    with op.batch_alter_table("signals") as batch:
        batch.drop_column("forecast")
