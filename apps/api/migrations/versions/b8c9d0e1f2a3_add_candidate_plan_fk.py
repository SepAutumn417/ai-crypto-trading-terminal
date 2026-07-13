"""add candidate_plan_id foreign key to trade_plans

Revision ID: b8c9d0e1f2a3
Revises: a7c8d9e0f1a2
Create Date: 2026-07-09 19:00:00

P1-6: 为 trade_plans.candidate_plan_id 添加外键约束，引用 candidate_plans.id。
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: str | None = 'a7c8d9e0f1a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # P1-6: 添加外键约束（candidate_plan_id → candidate_plans.id）
    op.create_foreign_key(
        'fk_trade_plans_candidate_plan_id',
        'trade_plans',
        'candidate_plans',
        ['candidate_plan_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_trade_plans_candidate_plan_id', 'trade_plans', type_='foreignkey')
