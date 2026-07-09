from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PositionSizingResult(Base):
    __tablename__ = "position_sizing_results"
    __table_args__ = (
        Index(
            "ix_position_sizing_latest",
            "trade_plan_id",
            unique=True,
            postgresql_where=text("is_latest = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    trade_plan_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trade_plans.id"), nullable=True
    )
    equity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    risk_percent: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    risk_amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    stop_distance_percent: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    notional_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    raw_size: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    rounded_size: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    required_margin: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    leverage: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    estimated_fee: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    risk_reward_ratio: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    estimated_loss_at_stop: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    sizing_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())