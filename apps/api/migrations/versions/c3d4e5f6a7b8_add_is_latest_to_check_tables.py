"""add is_latest to risk_checks, decision_gate_results, position_sizing_results

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-08 19:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('risk_checks', sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('decision_gate_results', sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('position_sizing_results', sa.Column('is_latest', sa.Boolean(), nullable=False, server_default='true'))

    op.create_index('ix_risk_checks_is_latest', 'risk_checks', ['trade_plan_id', 'is_latest'])
    op.create_index('ix_decision_gate_results_is_latest', 'decision_gate_results', ['trade_plan_id', 'is_latest'])
    op.create_index('ix_position_sizing_results_is_latest', 'position_sizing_results', ['trade_plan_id', 'is_latest'])


def downgrade() -> None:
    op.drop_index('ix_position_sizing_results_is_latest', table_name='position_sizing_results')
    op.drop_index('ix_decision_gate_results_is_latest', table_name='decision_gate_results')
    op.drop_index('ix_risk_checks_is_latest', table_name='risk_checks')

    op.drop_column('position_sizing_results', 'is_latest')
    op.drop_column('decision_gate_results', 'is_latest')
    op.drop_column('risk_checks', 'is_latest')