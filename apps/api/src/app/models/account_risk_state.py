from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AccountRiskState(Base):
    __tablename__ = "account_risk_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    daily_loss_r: Mapped[Decimal] = mapped_column(Numeric, nullable=False, default=0)
    consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
