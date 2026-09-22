"""
افزودن جدول پیش‌بینی‌های موتور هوش پیش‌بینی.

نسخهٔ ۱.۱۱٫۰ — قانون حیاتی ۵: «پیش‌بینی باید ذخیره و بعداً با نتیجهٔ
واقعی مقایسه شود.» هر پیش‌بینی (نماد × افق) ثبت و پس از سپری شدن افق
با قیمت واقعی حل می‌شود تا دقت/کالیبراسیون صادقانه قابل اندازه‌گیری
باشد.

Revision ID: e5c9d1f7a320
Revises: d1a7b3e05c62
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e5c9d1f7a320"
down_revision: str | None = "d1a7b3e05c62"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """ساخت جدول پیش‌بینی‌ها."""
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("horizon", sa.String(length=10), nullable=False),
        sa.Column("horizon_minutes", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=12), nullable=False),
        sa.Column("probability", sa.Integer(), nullable=False),
        sa.Column("confidence_effective", sa.Integer(), server_default="0", nullable=False),
        sa.Column("p10", sa.Float(), server_default="0", nullable=False),
        sa.Column("p25", sa.Float(), server_default="0", nullable=False),
        sa.Column("p50", sa.Float(), server_default="0", nullable=False),
        sa.Column("p75", sa.Float(), server_default="0", nullable=False),
        sa.Column("p90", sa.Float(), server_default="0", nullable=False),
        sa.Column("last_price", sa.Float(), server_default="0", nullable=False),
        sa.Column("method", sa.String(length=12), server_default="empirical", nullable=False),
        sa.Column("regime", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("model_agreement", sa.Float(), server_default="0", nullable=False),
        sa.Column("models", sa.JSON(), nullable=False),
        sa.Column("contributors", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="open", nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("actual_price", sa.Float(), nullable=True),
        sa.Column("direction_correct", sa.Boolean(), nullable=True),
        sa.Column("range_correct", sa.Boolean(), nullable=True),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_symbol", "predictions", ["symbol"])
    op.create_index("ix_predictions_status", "predictions", ["status"])
    op.create_index(
        "ix_predictions_lookup", "predictions", ["symbol", "horizon", "status"]
    )
    op.create_index("ix_predictions_resolve", "predictions", ["status", "created_at"])


def downgrade() -> None:
    """حذف جدول پیش‌بینی‌ها."""
    op.drop_index("ix_predictions_resolve", table_name="predictions")
    op.drop_index("ix_predictions_lookup", table_name="predictions")
    op.drop_index("ix_predictions_status", table_name="predictions")
    op.drop_index("ix_predictions_symbol", table_name="predictions")
    op.drop_table("predictions")
