"""add execution_attempts and error metadata to trade_plans

Revision ID: b2c3d4e5f6a7
Revises: 9d7b8a3c2f1e
Create Date: 2026-07-08 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '9d7b8a3c2f1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trade_plans', sa.Column('execution_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('trade_plans', sa.Column('execution_error_code', sa.String(length=64), nullable=True))
    op.add_column('trade_plans', sa.Column('execution_retryable', sa.Boolean(), nullable=True))
    op.add_column('trade_plans', sa.Column('execution_retry_after_seconds', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('trade_plans', 'execution_retry_after_seconds')
    op.drop_column('trade_plans', 'execution_retryable')
    op.drop_column('trade_plans', 'execution_error_code')
    op.drop_column('trade_plans', 'execution_attempts')