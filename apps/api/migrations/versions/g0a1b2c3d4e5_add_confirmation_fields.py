"""add confirmation fields to trade_plans

Revision ID: g0a1b2c3d4e5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-10 22:00:00.000000

P0-3: 添加服务端二次确认字段到 trade_plans 表：
- confirmation_token: 一次性确认 token
- plan_hash: 计划内容 SHA256 哈希（检测执行前内容是否被篡改）
- confirmed_at: 确认时间
- confirmation_expires_at: 确认过期时间
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'g0a1b2c3d4e5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trade_plans', sa.Column('confirmation_token', sa.String(length=64), nullable=True))
    op.add_column('trade_plans', sa.Column('plan_hash', sa.String(length=128), nullable=True))
    op.add_column('trade_plans', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('trade_plans', sa.Column('confirmation_expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('trade_plans', 'confirmation_expires_at')
    op.drop_column('trade_plans', 'confirmed_at')
    op.drop_column('trade_plans', 'plan_hash')
    op.drop_column('trade_plans', 'confirmation_token')
