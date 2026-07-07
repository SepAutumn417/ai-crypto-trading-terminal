from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

from shared.enums import (
    DecisionGateStatus, Direction, MarginMode,
    OpportunityGrade, PlanStatus, RiskStatus,
)


class TradePlanInput(BaseModel):
    exchange: str = "bitget"
    symbol: str
    direction: Direction
    entry_price: Decimal
    stop_loss_price: Decimal | None = None
    take_profit_prices: list[Decimal]
    leverage: Decimal
    risk_percent: Decimal
    opportunity_grade: OpportunityGrade
    equity: Decimal
    setup_type: str | None = None
    margin_mode: MarginMode = MarginMode.ISOLATED
    notes: str | None = None


class TradePlan(BaseModel):
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
    risk_config_version: str | None = None
    strategy_config_version: str | None = None
    user_trading_config_version: str | None = None
    exchange_order_id: str | None = None
    client_order_id: str | None = None
    filled_quantity: Decimal | None = None
    average_fill_price: Decimal | None = None
    execution_error: str | None = None
    created_at: datetime
    updated_at: datetime


class PositionSizingResult(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    equity: Decimal
    risk_percent: Decimal
    risk_amount: Decimal
    entry_price: Decimal
    stop_loss_price: Decimal | None
    stop_distance_percent: Decimal
    notional_value: Decimal
    raw_size: Decimal
    rounded_size: Decimal | None
    required_margin: Decimal
    leverage: Decimal
    estimated_fee: Decimal
    risk_reward_ratio: Decimal
    estimated_loss_at_stop: Decimal
    sizing_warnings: list[str] = Field(default_factory=list)


class RiskCheckResult(BaseModel):
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


class DecisionGateResult(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    risk_check_id: UUID | None = None
    result: DecisionGateStatus
    reasons: list[str] = Field(default_factory=list)
