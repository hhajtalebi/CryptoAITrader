"""افزودن ستون آخرین قیمت به معاملات کاغذی.

بدون این ستون، سود/زیان معاملهٔ باز جایی برای ذخیره‌شدن نداشت و کاربر
تا لحظهٔ بستن معامله هیچ عددی نمی‌دید.

Revision ID: c8d5f2a91e44
Revises: b7e4a1c8f209
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c8d5f2a91e44"
down_revision: str | None = "b7e4a1c8f209"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """افزودن ستون با مقدار پیش‌فرض صفر برای ردیف‌های موجود."""
    with op.batch_alter_table("paper_trades") as batch:
        batch.add_column(
            sa.Column("last_price", sa.Float(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    """حذف ستون."""
    with op.batch_alter_table("paper_trades") as batch:
        batch.drop_column("last_price")
