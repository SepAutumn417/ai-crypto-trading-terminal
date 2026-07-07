from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from shared.enums import (
    DecisionGateStatus, Direction, MarginMode, OpportunityGrade, PlanStatus, RiskStatus,
)


class TradePlanCreate(BaseModel):
    exchange: str = "bitget"
    symbol: str
    direction: Direction
    entry_price: Decimal
    stop_loss_price: Decimal | None = None
    take_profit_prices: list[Decimal] = Field(default_factory=list)
    leverage: Decimal
    risk_percent: Decimal
    opportunity_grade: OpportunityGrade
    equity: Decimal
    setup_type: str | None = None
    margin_mode: MarginMode = MarginMode.ISOLATED
    notes: str | None = None


class TradePlanOut(BaseModel):
    id: UUID
    exchange: str
    symbol: str
    direction: Direction
    entry_price: Decimal
    stop_loss_price: Decimal | None
    take_profit_prices: list[Decimal]
    leverage: Decimal
    margin_mode: MarginMode
    risk_percent: Decimal
    opportunity_grade: OpportunityGrade
    equity: Decimal
    setup_type: str | None
    notes: str | None
    status: PlanStatus
    risk_config_version: str | None
    strategy_config_version: str | None
    user_trading_config_version: str | None
    exchange_order_id: str | None = None
    client_order_id: str | None = None
    filled_quantity: Decimal | None = None
    average_fill_price: Decimal | None = None
    execution_error: str | None = None
    created_at: datetime
    updated_at: datetime


class PositionSizingOut(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    equity: Decimal
    risk_percent: Decimal
    risk_amount: Decimal
    entry_price: Decimal
    stop_loss_price: Decimal | None = None
    stop_distance_percent: Decimal
    notional_value: Decimal
    raw_size: Decimal
    rounded_size: Decimal | None = None
    required_margin: Decimal
    leverage: Decimal
    estimated_fee: Decimal
    risk_reward_ratio: Decimal
    estimated_loss_at_stop: Decimal
    sizing_warnings: list[str] = Field(default_factory=list)


class RiskCheckOut(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    status: RiskStatus
    risk_amount: Decimal
    notional_value: Decimal
    required_margin: Decimal
    risk_reward_ratio: Decimal
    max_allowed_risk_percent: Decimal
    warnings: list[str] = Field(default_factory=list)
    block_reasons: list[str] = Field(default_factory=list)
    risk_config_version: str | None = None


class DecisionGateOut(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    risk_check_id: UUID | None = None
    result: DecisionGateStatus
    reasons: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    plan: TradePlanOut
    sizing: PositionSizingOut
    risk: RiskCheckOut
    decision: DecisionGateOut


class CalculatePositionRequest(BaseModel):
    equity: Decimal
    risk_percent: Decimal
    entry_price: Decimal
    stop_loss_price: Decimal | None = None
    take_profit_prices: list[Decimal] = Field(default_factory=list)
    leverage: Decimal
    fee_rate: Decimal
    direction: Direction
    symbol: str


class RiskCheckRequest(BaseModel):
    plan: TradePlanCreate
    sizing_result: PositionSizingOut