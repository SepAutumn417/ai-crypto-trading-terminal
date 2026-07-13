from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OrderIntent(Base):
    __tablename__ = "order_intents"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    trade_plan_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("trade_plans.id"), nullable=False)
    client_order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False, default="limit")
    margin_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    take_profit_prices: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    quantity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    leverage: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PREVIEWED")
    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
