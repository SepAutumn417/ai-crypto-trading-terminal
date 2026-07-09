from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DecisionGateResult(Base):
    __tablename__ = "decision_gate_results"
    __table_args__ = (
        Index(
            "ix_decision_gate_latest",
            "trade_plan_id",
            unique=True,
            postgresql_where=text("is_latest = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    trade_plan_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trade_plans.id"), nullable=True
    )
    risk_check_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("risk_checks.id"), nullable=True
    )
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())