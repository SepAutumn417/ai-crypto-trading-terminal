"""add execution tracking fields to trade_plans

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-09 10:00:00.000000

补齐 trade_plans 表的 5 个执行追踪字段：
- exchange_order_id: 交易所返回的订单 ID
- client_order_id: 客户端幂等键
- filled_quantity: 已成交数量
- average_fill_price: 成交均价
- execution_error: 执行错误信息

这些字段在 ORM 模型中已定义，但迁移中缺失，导致 alembic upgrade head 后写入失败。
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trade_plans', sa.Column('exchange_order_id', sa.String(length=128), nullable=True))
    op.add_column('trade_plans', sa.Column('client_order_id', sa.String(length=128), nullable=True))
    op.add_column('trade_plans', sa.Column('filled_quantity', sa.Numeric(), nullable=True))
    op.add_column('trade_plans', sa.Column('average_fill_price', sa.Numeric(), nullable=True))
    op.add_column('trade_plans', sa.Column('execution_error', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('trade_plans', 'execution_error')
    op.drop_column('trade_plans', 'average_fill_price')
    op.drop_column('trade_plans', 'filled_quantity')
    op.drop_column('trade_plans', 'client_order_id')
    op.drop_column('trade_plans', 'exchange_order_id')
