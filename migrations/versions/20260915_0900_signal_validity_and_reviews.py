"""
پنجرهٔ اعتبار سیگنال و جدول بازبینی هوش مصنوعی.

نسخهٔ ۱.۹.۵ — پاسخ به دو گزارش کاربر:

۱) «باید بدانیم این سیگنال تا کی اعتبار دارد.» تا پیش از این، سیگنال
   هیچ تاریخ مصرفی نداشت و کاربر سیگنال دو‌ساعته را تازه می‌پنداشت.
   سه ستون به جدول سیگنال‌ها اضافه می‌شود.

۲) «سابقهٔ سیگنال باید تحلیل با هوش مصنوعی داشته باشد.» جدول تازه
   `signal_reviews` بازبینی *پس از* بسته‌شدن معامله را نگه می‌دارد —
   برخلاف `signal_analysis` که پیش‌بینیِ پیش از معامله است.

Revision ID: b7e4a1c8f209
Revises: a4f1c9d2b730
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4a1c8f209"
down_revision: str | None = "a4f1c9d2b730"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """افزودن ستون‌های اعتبار و ساخت جدول بازبینی."""
    # ستون‌ها nullable هستند تا سیگنال‌های موجود دست‌نخورده بمانند؛
    # داده‌های کاربر هرگز نباید در مهاجرت از بین برود.
    with op.batch_alter_table("signals") as batch:
        batch.add_column(
            sa.Column(
                "primary_timeframe",
                sa.String(length=10),
                nullable=False,
                server_default="",
            )
        )
        batch.add_column(sa.Column("enter_before", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("valid_until", sa.DateTime(), nullable=True))

    op.create_table(
        "signal_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=False),
        sa.Column("outcome_status", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("review_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("verdict", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("lesson", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("ai_provider", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("ai_model", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id"),
    )
    op.create_index("ix_signal_reviews_signal_id", "signal_reviews", ["signal_id"])
    op.create_index("ix_signal_reviews_lesson", "signal_reviews", ["lesson"])


def downgrade() -> None:
    """بازگشت به وضعیت پیشین."""
    op.drop_index("ix_signal_reviews_lesson", table_name="signal_reviews")
    op.drop_index("ix_signal_reviews_signal_id", table_name="signal_reviews")
    op.drop_table("signal_reviews")
    with op.batch_alter_table("signals") as batch:
        batch.drop_column("valid_until")
        batch.drop_column("enter_before")
        batch.drop_column("primary_timeframe")
