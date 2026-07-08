"""add ai_evaluation_results table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-08 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_evaluation_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('trade_plan_id', sa.UUID(), nullable=True),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('direction', sa.String(length=8), nullable=False),
        sa.Column('overall_score', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('grade', sa.String(length=2), nullable=False),
        sa.Column('recommendation', sa.String(length=32), nullable=False),
        sa.Column('risk_level', sa.String(length=16), nullable=False),
        sa.Column('signals', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('summary', sa.String(length=1024), nullable=False),
        sa.Column('conviction', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('interval', sa.String(length=8), nullable=True),
        sa.Column('is_latest', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['trade_plan_id'], ['trade_plans.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_eval_results_plan_id', 'ai_evaluation_results', ['trade_plan_id'])
    op.create_index('ix_ai_eval_results_symbol', 'ai_evaluation_results', ['symbol'])
    op.create_index('ix_ai_eval_results_grade', 'ai_evaluation_results', ['grade'])
    op.create_index('ix_ai_eval_results_created_at', 'ai_evaluation_results', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_eval_results_created_at', table_name='ai_evaluation_results')
    op.drop_index('ix_ai_eval_results_grade', table_name='ai_evaluation_results')
    op.drop_index('ix_ai_eval_results_symbol', table_name='ai_evaluation_results')
    op.drop_index('ix_ai_eval_results_plan_id', table_name='ai_evaluation_results')
    op.drop_table('ai_evaluation_results')
