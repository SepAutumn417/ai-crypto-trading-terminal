"""add is_latest partial unique indexes to check tables

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-10 09:00:00.000000

P2-1/P2-2: 将三表 (risk_checks, decision_gate_results, position_sizing_results) 的
非唯一复合索引替换为部分唯一索引 (WHERE is_latest = true)，
确保每个 trade_plan 只有一条 latest 记录。
同时为 ai_evaluation_results 添加 is_latest server_default 和部分唯一索引。
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c9d0e1f2a3b4'
down_revision: str | None = 'b8c9d0e1f2a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 删除旧的非唯一复合索引
    op.drop_index('ix_risk_checks_is_latest', table_name='risk_checks')
    op.drop_index('ix_decision_gate_results_is_latest', table_name='decision_gate_results')
    op.drop_index('ix_position_sizing_results_is_latest', table_name='position_sizing_results')

    # 2. 创建部分唯一索引 (WHERE is_latest = true)
    op.create_index(
        'ix_risk_checks_latest',
        'risk_checks',
        ['trade_plan_id'],
        unique=True,
        postgresql_where=sa.text('is_latest = true'),
    )
    op.create_index(
        'ix_decision_gate_latest',
        'decision_gate_results',
        ['trade_plan_id'],
        unique=True,
        postgresql_where=sa.text('is_latest = true'),
    )
    op.create_index(
        'ix_position_sizing_latest',
        'position_sizing_results',
        ['trade_plan_id'],
        unique=True,
        postgresql_where=sa.text('is_latest = true'),
    )

    # 3. ai_evaluation_results: 添加 server_default + 部分唯一索引
    op.alter_column(
        'ai_evaluation_results',
        'is_latest',
        server_default=sa.text('true'),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    op.create_index(
        'ix_ai_eval_results_latest',
        'ai_evaluation_results',
        ['trade_plan_id'],
        unique=True,
        postgresql_where=sa.text('is_latest = true'),
    )


def downgrade() -> None:
    # 撤销 ai_evaluation_results 的部分唯一索引和 server_default
    op.drop_index('ix_ai_eval_results_latest', table_name='ai_evaluation_results')
    op.alter_column(
        'ai_evaluation_results',
        'is_latest',
        server_default=None,
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )

    # 撤销三表的部分唯一索引
    op.drop_index('ix_position_sizing_latest', table_name='position_sizing_results')
    op.drop_index('ix_decision_gate_latest', table_name='decision_gate_results')
    op.drop_index('ix_risk_checks_latest', table_name='risk_checks')

    # 恢复旧的非唯一复合索引
    op.create_index('ix_position_sizing_results_is_latest', 'position_sizing_results', ['trade_plan_id', 'is_latest'])
    op.create_index('ix_decision_gate_results_is_latest', 'decision_gate_results', ['trade_plan_id', 'is_latest'])
    op.create_index('ix_risk_checks_is_latest', 'risk_checks', ['trade_plan_id', 'is_latest'])
