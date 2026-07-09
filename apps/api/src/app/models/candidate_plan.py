"""候选交易计划 ORM 模型。

对应 candidate_plans 表，存储 Auto Plan Engine 自动生成的候选交易计划。
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CandidatePlanModel(Base):
    """候选交易计划——由 Auto Plan Engine 自动生成。

    经风控预检查和 AI 评估后，可 promote 为正式 TradePlan。
    状态机：DISCOVERED → WATCHING → READY → RISK_CHECKED → AI_EVALUATED
           → ALLOW_CONFIRM / WAIT / BLOCK / EXPIRED
    """
    __tablename__ = "candidate_plans"
    __table_args__ = (
        Index("ix_candidate_plans_status", "status", "created_at"),
        Index("ix_candidate_plans_symbol", "symbol", "timeframe"),
        Index("ix_candidate_plans_grade", "opportunity_grade"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    structure_snapshot_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("market_structure_snapshots.id"), nullable=True
    )
    exchange: Mapped[str] = mapped_column(String(32), nullable=False, default="bitget")
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False, default="1h")
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # long / short
    setup_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # 入场区域（JSONB: {upper, lower}）
    entry_zone: Mapped[dict] = mapped_column(JSONB, nullable=False)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_loss_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    take_profit_prices: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risk_reward_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    # 机会评级
    opportunity_grade: Mapped[str] = mapped_column(String(16), nullable=False, default="C")

    # 状态机
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED")
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 生成依据
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    structure_signals: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # 配置版本
    strategy_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
