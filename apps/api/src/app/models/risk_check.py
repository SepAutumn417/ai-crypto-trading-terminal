from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RiskCheck(Base):
    __tablename__ = "risk_checks"
    __table_args__ = (
        Index(
            "ix_risk_checks_latest",
            "trade_plan_id",
            unique=True,
            postgresql_where=text("is_latest = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    trade_plan_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trade_plans.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_amount: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    notional_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    required_margin: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    risk_reward_ratio: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    max_allowed_risk_percent: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    block_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risk_config_version: Mapped[str] = mapped_column(String(64), nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
