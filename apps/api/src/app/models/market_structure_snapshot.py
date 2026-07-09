"""市场结构快照 ORM 模型。

对应 market_structure_snapshots 表，存储每次结构识别的结果。
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MarketStructureSnapshotModel(Base):
    """市场结构快照——每次 analyze_structure 的结果落库。

    用于历史回溯和前端展示。
    """
    __tablename__ = "market_structure_snapshots"
    __table_args__ = (
        Index("ix_structure_snapshots_symbol_tf", "symbol", "timeframe"),
        Index("ix_structure_snapshots_captured_at", "captured_at"),
        Index("ix_structure_snapshots_market_state", "market_state"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # 市场状态
    market_state: Mapped[str] = mapped_column(String(32), nullable=False)  # trend / range / transition
    trend_direction: Mapped[str] = mapped_column(String(32), nullable=False)  # bullish / bearish / neutral

    # 结构元素（JSONB）
    swing_highs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    swing_lows: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    bos_events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    choch_events: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    support_zones: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    resistance_zones: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    no_trade_zones: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # 波动率
    volatility_state: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")

    # 最新价格
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    # 分析输入信息
    kline_count: Mapped[int] = mapped_column(nullable=False, default=0)
    kline_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kline_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 算法参数
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
