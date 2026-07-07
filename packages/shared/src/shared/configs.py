from decimal import Decimal
from pydantic import BaseModel

from shared.enums import MarginMode, OrderType


class RiskConfig(BaseModel):
    """风控配置（配置版本载荷）。

    ⚠️ 单位约定（v0.1.1）：
    - max_risk_percent / min_stop_distance_percent：百分数基（整数百分数）
        如 max_risk_percent=3 表示 3%；min_stop_distance_percent=0.3 表示 0.3%
    - daily_loss_limit_r：R 倍数（2 = 2R）
    - min_risk_reward_ratio / preferred_risk_reward_ratio：纯比率（如 1.5）

    注意：calculator 算出的 sizing.stop_distance_percent 是小数（0.008 = 0.8%），
    与 min_stop_distance_percent 不是同一单位。rules.py 比较时显式 * 100 换算。
    """

    max_risk_percent: Decimal
    max_leverage: Decimal
    min_risk_reward_ratio: Decimal
    preferred_risk_reward_ratio: Decimal
    min_stop_distance_percent: Decimal
    daily_loss_limit_r: Decimal
    max_consecutive_losses: int
    cooldown_minutes_after_loss: int
    max_notional_equity_ratio: Decimal = Decimal("20")


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
