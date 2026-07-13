"""add candidate_plans table

Revision ID: a7c8d9e0f1a2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-09 18:00:00

v0.4: 自动候选计划生成——存储 Auto Plan Engine 生成的候选交易计划。
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7c8d9e0f1a2'
down_revision: str | None = 'f6a7b8c9d0e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'candidate_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('structure_snapshot_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('market_structure_snapshots.id'), nullable=True),
        sa.Column('exchange', sa.String(32), nullable=False, server_default='bitget'),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('timeframe', sa.String(16), nullable=False, server_default='1h'),
        sa.Column('direction', sa.String(16), nullable=False),
        sa.Column('setup_type', sa.String(64), nullable=False),
        sa.Column('entry_zone', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('entry_price', sa.Numeric(20, 8), nullable=True),
        sa.Column('stop_loss_price', sa.Numeric(20, 8), nullable=False),
        sa.Column('take_profit_prices', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('risk_reward_ratio', sa.Numeric(10, 4), nullable=True),
        sa.Column('opportunity_grade', sa.String(16), nullable=False, server_default='C'),
        sa.Column('status', sa.String(32), nullable=False, server_default='DISCOVERED'),
        sa.Column('invalidation_reason', sa.Text, nullable=True),
        sa.Column('rationale', sa.Text, nullable=False, server_default=''),
        sa.Column('structure_signals', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('strategy_config_version', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_candidate_plans_status', 'candidate_plans', ['status', 'created_at'])
    op.create_index('ix_candidate_plans_symbol', 'candidate_plans', ['symbol', 'timeframe'])
    op.create_index('ix_candidate_plans_grade', 'candidate_plans', ['opportunity_grade'])


def downgrade() -> None:
    op.drop_index('ix_candidate_plans_grade', table_name='candidate_plans')
    op.drop_index('ix_candidate_plans_symbol', table_name='candidate_plans')
    op.drop_index('ix_candidate_plans_status', table_name='candidate_plans')
    op.drop_table('candidate_plans')
