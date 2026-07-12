"""add v0.5 LLM explanation fields to ai_evaluation_results

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-10 10:30:00.000000

v0.5: 扩展 ai_evaluation_results 表，添加 LLM 解释层字段。
- source: 评估来源 (llm / rule_based)
- recommended_action: AI 推荐动作 (WAIT/ALLOW_CONFIRM/REDUCE_RISK/DO_NOT_TRADE)
- market_state_explanation: 市场状态解释
- plan_quality_explanation: 计划质量分析
- risk_explanation: 风险解释
- opportunity_grade_comment: 机会评级评论
- warnings: 警告列表 (JSONB)
- upgrade_conditions: 升级条件列表 (JSONB)
- invalidation_conditions: 失效条件列表 (JSONB)
- emotional_risk_flags: 情绪风险标记列表 (JSONB)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ai_evaluation_results', sa.Column('source', sa.String(16), nullable=False, server_default=sa.text("'rule_based'")))
    op.add_column('ai_evaluation_results', sa.Column('recommended_action', sa.String(20), nullable=True))
    op.add_column('ai_evaluation_results', sa.Column('market_state_explanation', sa.String(2048), nullable=False, server_default=sa.text("''")))
    op.add_column('ai_evaluation_results', sa.Column('plan_quality_explanation', sa.String(2048), nullable=False, server_default=sa.text("''")))
    op.add_column('ai_evaluation_results', sa.Column('risk_explanation', sa.String(2048), nullable=False, server_default=sa.text("''")))
    op.add_column('ai_evaluation_results', sa.Column('opportunity_grade_comment', sa.String(1024), nullable=False, server_default=sa.text("''")))
    op.add_column('ai_evaluation_results', sa.Column('warnings', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column('ai_evaluation_results', sa.Column('upgrade_conditions', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column('ai_evaluation_results', sa.Column('invalidation_conditions', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column('ai_evaluation_results', sa.Column('emotional_risk_flags', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")))

    # 为 existing 行补 server_default 到 signals/summary
    op.execute("UPDATE ai_evaluation_results SET signals = '[]'::jsonb WHERE signals IS NULL")
    op.execute("UPDATE ai_evaluation_results SET summary = '' WHERE summary IS NULL")

    op.alter_column('ai_evaluation_results', 'signals', server_default=sa.text("'[]'::jsonb"))
    op.alter_column('ai_evaluation_results', 'summary', server_default=sa.text("''"))


def downgrade() -> None:
    op.alter_column('ai_evaluation_results', 'summary', server_default=None)
    op.alter_column('ai_evaluation_results', 'signals', server_default=None)

    op.drop_column('ai_evaluation_results', 'emotional_risk_flags')
    op.drop_column('ai_evaluation_results', 'invalidation_conditions')
    op.drop_column('ai_evaluation_results', 'upgrade_conditions')
    op.drop_column('ai_evaluation_results', 'warnings')
    op.drop_column('ai_evaluation_results', 'opportunity_grade_comment')
    op.drop_column('ai_evaluation_results', 'risk_explanation')
    op.drop_column('ai_evaluation_results', 'plan_quality_explanation')
    op.drop_column('ai_evaluation_results', 'market_state_explanation')
    op.drop_column('ai_evaluation_results', 'recommended_action')
    op.drop_column('ai_evaluation_results', 'source')
