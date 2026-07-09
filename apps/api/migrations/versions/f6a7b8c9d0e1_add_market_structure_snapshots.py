"""add market_structure_snapshots table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-09 16:00:00

v0.3: 市场结构识别——存储每次 analyze_structure 的结果快照。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'market_structure_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('symbol', sa.String(32), nullable=False),
        sa.Column('timeframe', sa.String(16), nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('market_state', sa.String(32), nullable=False),
        sa.Column('trend_direction', sa.String(32), nullable=False),
        sa.Column('swing_highs', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('swing_lows', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('bos_events', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('choch_events', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('support_zones', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('resistance_zones', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('no_trade_zones', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('volatility_state', sa.String(16), nullable=False, server_default='normal'),
        sa.Column('last_price', sa.Numeric(20, 8), nullable=True),
        sa.Column('kline_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('kline_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('kline_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('config', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_structure_snapshots_symbol_tf', 'market_structure_snapshots', ['symbol', 'timeframe'])
    op.create_index('ix_structure_snapshots_captured_at', 'market_structure_snapshots', ['captured_at'])
    op.create_index('ix_structure_snapshots_market_state', 'market_structure_snapshots', ['market_state'])


def downgrade() -> None:
    op.drop_index('ix_structure_snapshots_market_state', table_name='market_structure_snapshots')
    op.drop_index('ix_structure_snapshots_captured_at', table_name='market_structure_snapshots')
    op.drop_index('ix_structure_snapshots_symbol_tf', table_name='market_structure_snapshots')
    op.drop_table('market_structure_snapshots')
