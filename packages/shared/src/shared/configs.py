from decimal import Decimal
from pydantic import BaseModel

from shared.enums import MarginMode, OrderType


class RiskConfig(BaseModel):
    max_risk_percent: Decimal
    max_leverage: Decimal
    min_risk_reward_ratio: Decimal
    preferred_risk_reward_ratio: Decimal
    min_stop_distance_percent: Decimal
    daily_loss_limit_r: Decimal
    max_consecutive_losses: int
    cooldown_minutes_after_loss: int


class ExecutionConfig(BaseModel):
    enabled: bool
    mode: str
    margin_mode: MarginMode
    allowed_order_types: list[OrderType]
    require_stop_loss: bool
    require_user_confirmation: bool
    require_second_confirmation: bool


class OpportunityGradeConfig(BaseModel):
    a_max_risk_percent: Decimal
    b_max_risk_percent: Decimal
    c_max_risk_percent: Decimal
    blocked_max_risk_percent: Decimal


class SymbolRule(BaseModel):
    size_step: Decimal
    price_step: Decimal
    min_size: Decimal
    min_notional: Decimal
    max_leverage: Decimal
    fee_rate: Decimal


class SymbolRules(BaseModel):
    rules: dict[str, SymbolRule]

    def get(self, symbol: str) -> SymbolRule | None:
        return self.rules.get(symbol)
