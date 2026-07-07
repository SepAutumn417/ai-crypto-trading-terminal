from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_plan_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    setup_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    take_profit_prices: Mapped[list] = mapped_column(JSONB, nullable=False)
    leverage: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    margin_mode: Mapped[str] = mapped_column(String(32), default="isolated")
    risk_percent: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    opportunity_grade: Mapped[str] = mapped_column(String(16), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_trading_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())