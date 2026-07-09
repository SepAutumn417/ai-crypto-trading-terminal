from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_plan_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("candidate_plans.id"), nullable=True
    )
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    setup_type: Mapped[str] = mapped_column(String(64), nullable=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    stop_loss_price: Mapped[Decimal] = mapped_column(Numeric, nullable=True)
    take_profit_prices: Mapped[list] = mapped_column(JSONB, nullable=False)
    leverage: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    margin_mode: Mapped[str] = mapped_column(String(32), default="isolated")
    risk_percent: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    opportunity_grade: Mapped[str] = mapped_column(String(16), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    risk_config_version: Mapped[str] = mapped_column(String(64), nullable=True)
    strategy_config_version: Mapped[str] = mapped_column(String(64), nullable=True)
    user_trading_config_version: Mapped[str] = mapped_column(String(64), nullable=True)
    exchange_order_id: Mapped[str] = mapped_column(String(128), nullable=True)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=True)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric, nullable=True)
    average_fill_price: Mapped[Decimal] = mapped_column(Numeric, nullable=True)
    execution_error: Mapped[str] = mapped_column(Text, nullable=True)
    execution_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    execution_retryable: Mapped[bool] = mapped_column(Boolean, nullable=True)
    execution_retry_after_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())