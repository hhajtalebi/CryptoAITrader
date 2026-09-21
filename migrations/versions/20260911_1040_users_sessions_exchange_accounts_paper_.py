"""افزودن جداول کاربران، نشست‌ها، حساب‌های صرافی و معاملات کاغذی

این مهاجرت فقط جدول اضافه می‌کند و هیچ جدول یا ستون موجودی را تغییر
نمی‌دهد؛ بنابراین داده و تنظیمات کاربران فعلی دست‌نخورده می‌ماند.

Revision ID: ce3e52be9145
Revises: 3100f692a8d0
Create Date: 2026-09-11 10:40:56.822794

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'ce3e52be9145'
down_revision: str | None = '3100f692a8d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """اعمال تغییرات این نسخه."""
    # جداول تازه نسخه ۱٫۵ — مدیریت کاربر و حساب صرافی
    op.create_table('users',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=60), nullable=False),
    sa.Column('email', sa.String(length=160), nullable=False),
    sa.Column('display_name', sa.String(length=80), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('password_salt', sa.String(length=64), nullable=False),
    sa.Column('password_iterations', sa.Integer(), nullable=False),
    sa.Column('password_algorithm', sa.String(length=30), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('preferences', sa.JSON(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('failed_attempts', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    op.create_table('exchange_accounts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('exchange', sa.String(length=50), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('secret_ref', sa.String(length=160), nullable=False),
    sa.Column('api_key_masked', sa.String(length=60), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('read_only', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('last_sync_at', sa.DateTime(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=False),
    sa.Column('balances', sa.JSON(), nullable=False),
    sa.Column('total_value_usdt', sa.Float(), nullable=False),
    sa.Column('permissions', sa.JSON(), nullable=False),
    sa.Column('extra_config', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'exchange', 'label', name='uq_exchange_account')
    )
    with op.batch_alter_table('exchange_accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_exchange_accounts_exchange'), ['exchange'], unique=False)
        batch_op.create_index('ix_exchange_accounts_user_exchange', ['user_id', 'exchange'], unique=False)
        batch_op.create_index(batch_op.f('ix_exchange_accounts_user_id'), ['user_id'], unique=False)

    op.create_table('user_sessions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=128), nullable=False),
    sa.Column('device_label', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_sessions_token_hash'), ['token_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_user_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('paper_trades',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('account_id', sa.Integer(), nullable=True),
    sa.Column('signal_id', sa.Integer(), nullable=True),
    sa.Column('symbol', sa.String(length=30), nullable=False),
    sa.Column('side', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('mode', sa.String(length=10), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('entry_price', sa.Float(), nullable=False),
    sa.Column('exit_price', sa.Float(), nullable=True),
    sa.Column('stop_loss', sa.Float(), nullable=True),
    sa.Column('take_profit', sa.Float(), nullable=True),
    sa.Column('leverage', sa.Float(), nullable=False),
    sa.Column('fee', sa.Float(), nullable=False),
    sa.Column('pnl', sa.Float(), nullable=False),
    sa.Column('pnl_percent', sa.Float(), nullable=False),
    sa.Column('opened_at', sa.DateTime(), nullable=False),
    sa.Column('closed_at', sa.DateTime(), nullable=True),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('extra', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['account_id'], ['exchange_accounts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['signal_id'], ['signals.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('paper_trades', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_paper_trades_opened_at'), ['opened_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_paper_trades_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_paper_trades_symbol'), ['symbol'], unique=False)
        batch_op.create_index(batch_op.f('ix_paper_trades_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_paper_trades_user_time', ['user_id', 'opened_at'], unique=False)




def downgrade() -> None:
    """بازگرداندن تغییرات این نسخه."""
    # جداول تازه نسخه ۱٫۵ — مدیریت کاربر و حساب صرافی
    with op.batch_alter_table('paper_trades', schema=None) as batch_op:
        batch_op.drop_index('ix_paper_trades_user_time')
        batch_op.drop_index(batch_op.f('ix_paper_trades_user_id'))
        batch_op.drop_index(batch_op.f('ix_paper_trades_symbol'))
        batch_op.drop_index(batch_op.f('ix_paper_trades_status'))
        batch_op.drop_index(batch_op.f('ix_paper_trades_opened_at'))

    op.drop_table('paper_trades')
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_sessions_token_hash'))

    op.drop_table('user_sessions')
    with op.batch_alter_table('exchange_accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_exchange_accounts_user_id'))
        batch_op.drop_index('ix_exchange_accounts_user_exchange')
        batch_op.drop_index(batch_op.f('ix_exchange_accounts_exchange'))

    op.drop_table('exchange_accounts')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))

    op.drop_table('users')

