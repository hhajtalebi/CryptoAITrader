"""
افزودن جدول نتیجهٔ واقعی سیگنال‌ها.

نسخهٔ ۱.۹.۱ — مورد ۱.۵ نقشهٔ راه. تا پیش از این، سیگنال تولید می‌شد و
هیچ‌کس نمی‌دانست به هدف رسید یا حد ضرر خورد؛ این جدول واقعیت را ثبت
می‌کند.

Revision ID: a4f1c9d2b730
Revises: ce3e52be9145
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a4f1c9d2b730"
down_revision: str | None = "ce3e52be9145"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """ساخت جدول نتیجه‌ها."""
    op.create_table(
        "signal_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="PENDING", nullable=False),
        sa.Column("entry_price", sa.Float(), server_default="0", nullable=False),
        sa.Column("stop_loss", sa.Float(), server_default="0", nullable=False),
        sa.Column("take_profits", sa.JSON(), nullable=False),
        sa.Column("targets_hit", sa.Integer(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("primary_timeframe", sa.String(length=10), server_default="", nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("result_percent", sa.Float(), server_default="0", nullable=False),
        sa.Column("realized_r", sa.Float(), server_default="0", nullable=False),
        sa.Column("max_favorable_percent", sa.Float(), server_default="0", nullable=False),
        sa.Column("max_adverse_percent", sa.Float(), server_default="0", nullable=False),
        sa.Column("last_price", sa.Float(), server_default="0", nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("manual", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # یک سیگنال فقط یک نتیجه دارد؛ یکتایی در سطح پایگاه داده تضمین
    # می‌شود تا پیگیری موازی ردیف تکراری نسازد.
    op.create_index(
        "ix_signal_outcomes_signal_id", "signal_outcomes", ["signal_id"], unique=True
    )
    op.create_index("ix_signal_outcomes_symbol", "signal_outcomes", ["symbol"])
    op.create_index("ix_signal_outcomes_status", "signal_outcomes", ["status"])
    op.create_index("ix_outcomes_status", "signal_outcomes", ["status", "checked_at"])


def downgrade() -> None:
    """حذف جدول نتیجه‌ها."""
    op.drop_index("ix_outcomes_status", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_status", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_symbol", table_name="signal_outcomes")
    op.drop_index("ix_signal_outcomes_signal_id", table_name="signal_outcomes")
    op.drop_table("signal_outcomes")
