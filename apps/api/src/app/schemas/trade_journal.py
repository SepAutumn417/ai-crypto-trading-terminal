from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TradeJournalCreate(BaseModel):
    trade_plan_id: UUID | None = None
    exchange: str = "bitget"
    symbol: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal | None = None
    quantity: Decimal
    leverage: Decimal = Decimal("1")
    pnl: Decimal | None = None
    pnl_percent: Decimal | None = None
    setup_type: str | None = None
    entry_reason: str | None = None
    exit_reason: str | None = None
    lessons_learned: str | None = None
    emotions: str | None = None
    status: str = "OPEN"
    entry_at: datetime | None = None
    exit_at: datetime | None = None


class TradeJournalUpdate(BaseModel):
    exit_price: Decimal | None = None
    pnl: Decimal | None = None
    pnl_percent: Decimal | None = None
    exit_reason: str | None = None
    lessons_learned: str | None = None
    emotions: str | None = None
    status: str | None = None
    exit_at: datetime | None = None


class TradeJournalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trade_plan_id: UUID | None
    exchange: str
    symbol: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    leverage: Decimal
    pnl: Decimal | None
    pnl_percent: Decimal | None
    setup_type: str | None
    entry_reason: str | None
    exit_reason: str | None
    lessons_learned: str | None
    emotions: str | None
    status: str
    entry_at: datetime | None
    exit_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TradeJournalListResponse(BaseModel):
    items: list[TradeJournalOut]
    total: int
    page: int
    page_size: int


class TradeJournalSummary(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal | None
    total_pnl: Decimal
    avg_pnl: Decimal | None
    best_trade: Decimal | None
    worst_trade: Decimal | None
