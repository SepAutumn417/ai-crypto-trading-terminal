"""add trade_journals table

Revision ID: 9d7b8a3c2f1e
Revises: e465fb3ecf35
Create Date: 2026-07-08 12:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '9d7b8a3c2f1e'
down_revision: str | None = 'e465fb3ecf35'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('trade_journals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('trade_plan_id', sa.UUID(), nullable=True),
    sa.Column('exchange', sa.String(length=32), nullable=False),
    sa.Column('symbol', sa.String(length=32), nullable=False),
    sa.Column('direction', sa.String(length=16), nullable=False),
    sa.Column('entry_price', sa.Numeric(), nullable=False),
    sa.Column('exit_price', sa.Numeric(), nullable=True),
    sa.Column('quantity', sa.Numeric(), nullable=False),
    sa.Column('leverage', sa.Numeric(), nullable=False),
    sa.Column('pnl', sa.Numeric(), nullable=True),
    sa.Column('pnl_percent', sa.Numeric(), nullable=True),
    sa.Column('setup_type', sa.String(length=64), nullable=True),
    sa.Column('entry_reason', sa.Text(), nullable=True),
    sa.Column('exit_reason', sa.Text(), nullable=True),
    sa.Column('lessons_learned', sa.Text(), nullable=True),
    sa.Column('emotions', sa.String(length=128), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('entry_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('exit_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trade_journals_symbol', 'trade_journals', ['symbol'])
    op.create_index('ix_trade_journals_status', 'trade_journals', ['status'])
    op.create_index('ix_trade_journals_created_at', 'trade_journals', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_trade_journals_created_at', table_name='trade_journals')
    op.drop_index('ix_trade_journals_status', table_name='trade_journals')
    op.drop_index('ix_trade_journals_symbol', table_name='trade_journals')
    op.drop_table('trade_journals')
