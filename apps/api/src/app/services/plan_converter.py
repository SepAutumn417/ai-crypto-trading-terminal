"""ORM ↔ Schema 转换器。

从 plan_service 提取，供 plan_service / execution_service 共享，
避免 execution_service 反向依赖 plan_service（导致循环 import 风险）。
"""
from decimal import Decimal

from app.models import (
    DecisionGateResult as DecisionGateResultModel,
    PositionSizingResult as PositionSizingResultModel,
    RiskCheck as RiskCheckModel,
    TradePlan as TradePlanModel,
)
from shared.enums import Direction, MarginMode, OpportunityGrade, PlanStatus
from shared.schemas import TradePlan as TradePlanSchema, TradePlanInput


def to_schema(m: TradePlanModel) -> TradePlanSchema:
    return TradePlanSchema(
        id=m.id, exchange=m.exchange, symbol=m.symbol,
        direction=Direction(m.direction), entry_price=m.entry_price,
        stop_loss_price=m.stop_loss_price,
        take_profit_prices=[Decimal(p) for p in (m.take_profit_prices or [])],
        leverage=m.leverage, margin_mode=MarginMode(m.margin_mode),
        risk_percent=m.risk_percent, opportunity_grade=OpportunityGrade(m.opportunity_grade),
        equity=m.equity, setup_type=m.setup_type, notes=m.notes,
        status=PlanStatus(m.status), risk_config_version=m.risk_config_version,
        strategy_config_version=m.strategy_config_version,
        user_trading_config_version=m.user_trading_config_version,
        exchange_order_id=m.exchange_order_id,
        client_order_id=m.client_order_id,
        filled_quantity=m.filled_quantity,
        average_fill_price=m.average_fill_price,
        execution_error=m.execution_error,
        execution_attempts=m.execution_attempts,
        execution_error_code=m.execution_error_code,
        execution_retryable=m.execution_retryable,
        execution_retry_after_seconds=m.execution_retry_after_seconds,
        created_at=m.created_at, updated_at=m.updated_at,
    )


def to_input(m: TradePlanModel) -> TradePlanInput:
    return TradePlanInput(
        exchange=m.exchange, symbol=m.symbol,
        direction=Direction(m.direction), entry_price=m.entry_price,
        stop_loss_price=m.stop_loss_price,
        take_profit_prices=[Decimal(p) for p in (m.take_profit_prices or [])],
        leverage=m.leverage, margin_mode=MarginMode(m.margin_mode),
        risk_percent=m.risk_percent,
        opportunity_grade=OpportunityGrade(m.opportunity_grade),
        equity=m.equity, setup_type=m.setup_type, notes=m.notes,
    )


def to_sizing_out(m: PositionSizingResultModel) -> dict:
    return {
        "id": str(m.id) if m.id else None,
        "trade_plan_id": str(m.trade_plan_id) if m.trade_plan_id else None,
        "equity": str(m.equity), "risk_percent": str(m.risk_percent),
        "risk_amount": str(m.risk_amount), "entry_price": str(m.entry_price),
        "stop_loss_price": str(m.stop_loss_price) if m.stop_loss_price is not None else None,
        "stop_distance_percent": str(m.stop_distance_percent),
        "notional_value": str(m.notional_value), "raw_size": str(m.raw_size),
        "rounded_size": str(m.rounded_size) if m.rounded_size is not None else None,
        "required_margin": str(m.required_margin), "leverage": str(m.leverage),
        "estimated_fee": str(m.estimated_fee),
        "risk_reward_ratio": str(m.risk_reward_ratio),
        "estimated_loss_at_stop": str(m.estimated_loss_at_stop),
        "sizing_warnings": m.sizing_warnings or [],
    }


def to_risk_out(m: RiskCheckModel) -> dict:
    return {
        "id": str(m.id) if m.id else None,
        "trade_plan_id": str(m.trade_plan_id) if m.trade_plan_id else None,
        "status": m.status, "risk_amount": str(m.risk_amount),
        "notional_value": str(m.notional_value), "required_margin": str(m.required_margin),
        "risk_reward_ratio": str(m.risk_reward_ratio),
        "max_allowed_risk_percent": str(m.max_allowed_risk_percent),
        "warnings": m.warnings or [], "block_reasons": m.block_reasons or [],
        "risk_config_version": m.risk_config_version,
    }


def to_decision_out(m: DecisionGateResultModel) -> dict:
    return {
        "id": str(m.id) if m.id else None,
        "trade_plan_id": str(m.trade_plan_id) if m.trade_plan_id else None,
        "risk_check_id": str(m.risk_check_id) if m.risk_check_id else None,
        "result": m.result, "reasons": m.reasons or [],
    }
