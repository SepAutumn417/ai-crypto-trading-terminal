from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AIEvaluationResultModel(Base):
    """AI 评估结果落库表。

    每次 check_plan 时若触发 AI 评估，将结果写入此表，
    支持后续复盘分析 AI 评分与实际盈亏的相关性。
    """
    __tablename__ = "ai_evaluation_results"
    __table_args__ = (
        Index("ix_ai_eval_results_plan_id", "trade_plan_id"),
        Index("ix_ai_eval_results_symbol", "symbol"),
        Index("ix_ai_eval_results_grade", "grade"),
        Index("ix_ai_eval_results_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    trade_plan_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trade_plans.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    overall_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    grade: Mapped[str] = mapped_column(String(2), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    signals: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    conviction: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    interval: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_latest: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
