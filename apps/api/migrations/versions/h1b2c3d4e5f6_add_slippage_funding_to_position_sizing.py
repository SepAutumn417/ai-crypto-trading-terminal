"""add slippage and funding columns to position_sizing_results

Revision ID: h1b2c3d4e5f6
Revises: g0a1b2c3d4e5
Create Date: 2026-07-10 23:00:00.000000

P1-2: 将滑点和资金费率纳入最大损失约束。
- estimated_slippage: 滑点成本估算
- estimated_funding: 资金费率成本估算（假设持仓 8h）
两者均纳入 estimated_loss_at_stop = risk_amount + estimated_fee + estimated_slippage + estimated_funding
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = 'h1b2c3d4e5f6'
down_revision: str | None = 'g0a1b2c3d4e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'position_sizing_results',
        sa.Column('estimated_slippage', sa.Numeric(), nullable=False, server_default='0'),
    )
    op.add_column(
        'position_sizing_results',
        sa.Column('estimated_funding', sa.Numeric(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('position_sizing_results', 'estimated_funding')
    op.drop_column('position_sizing_results', 'estimated_slippage')
