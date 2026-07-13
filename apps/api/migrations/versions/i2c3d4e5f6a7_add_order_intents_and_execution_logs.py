"""add v0.6 order intents and execution logs

Revision ID: i2c3d4e5f6a7
Revises: h1b2c3d4e5f6
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i2c3d4e5f6a7"
down_revision: str | None = "h1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trade_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trade_plans.id"), nullable=False),
        sa.Column("client_order_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("margin_mode", sa.String(length=32), nullable=False),
        sa.Column("entry_price", sa.Numeric(), nullable=False),
        sa.Column("stop_loss_price", sa.Numeric(), nullable=True),
        sa.Column("take_profit_prices", postgresql.JSONB(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column("leverage", sa.Numeric(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_intent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_intents.id"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("execution_logs")
    op.drop_table("order_intents")
