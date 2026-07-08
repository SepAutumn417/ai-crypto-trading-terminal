from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DecisionGateResult as DecisionGateResultModel,
    PositionSizingResult as PositionSizingResultModel,
    RiskCheck as RiskCheckModel,
    TradePlan as TradePlanModel,
)
from app.services.config_service import (
    get_account_risk_state, get_active_execution_config,
    get_active_opportunity_grade_config, get_active_risk_config,
    get_active_symbol_rules, get_symbol_rule, get_user_settings,
)
from shared.enums import (
    DecisionGateStatus, Direction, MarginMode, OpportunityGrade, PlanStatus,
)
from shared.schemas import TradePlanInput, TradePlan as TradePlanSchema
from decision_gate.gate import decide
from position_sizing.calculator import calculate as calculate_position
from risk_engine.checker import check as risk_check


async def create_plan(db: AsyncSession, plan_input: TradePlanInput) -> TradePlanSchema:
    model = TradePlanModel(
        id=uuid4(),
        exchange=plan_input.exchange,
        symbol=plan_input.symbol,
        direction=plan_input.direction.value,
        entry_price=plan_input.entry_price,
        stop_loss_price=plan_input.stop_loss_price,
        take_profit_prices=[str(p) for p in plan_input.take_profit_prices],
        leverage=plan_input.leverage,
        margin_mode=plan_input.margin_mode.value,
        risk_percent=plan_input.risk_percent,
        opportunity_grade=plan_input.opportunity_grade.value,
        equity=plan_input.equity,
        setup_type=plan_input.setup_type,
        notes=plan_input.notes,
        status=PlanStatus.DRAFT.value,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _to_schema(model)


async def get_plan(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")
    return _to_schema(model)


async def list_plans(db: AsyncSession, status: str | None = None) -> list[TradePlanSchema]:
    q = select(TradePlanModel)
    if status is not None:
        q = q.where(TradePlanModel.status == status)
    q = q.order_by(TradePlanModel.created_at.desc())
    result = await db.execute(q)
    return [_to_schema(m) for m in result.scalars().all()]


async def check_plan(db: AsyncSession, plan_id: UUID) -> dict:
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")
    if model.status not in (PlanStatus.DRAFT.value, PlanStatus.CHECKED.value):
        raise ValueError(f"Plan status {model.status} 不允许 check")

    plan_input = _to_input(model)

    risk_config, risk_ver = await get_active_risk_config(db)
    execution_config, _ = await get_active_execution_config(db)
    grade_config, grade_ver = await get_active_opportunity_grade_config(db)
    symbol_rule = await get_symbol_rule(db, model.symbol)
    account_state = await get_account_risk_state(db)
    user_settings = await get_user_settings(db)

    exec_enabled = user_settings.execution_enabled if user_settings else False
    kill_sw = user_settings.kill_switch if user_settings else True

    sizing = calculate_position(
        equity=plan_input.equity, risk_percent=plan_input.risk_percent,
        entry_price=plan_input.entry_price, stop_loss_price=plan_input.stop_loss_price,
        take_profit_prices=plan_input.take_profit_prices, leverage=plan_input.leverage,
        fee_rate=symbol_rule.fee_rate, direction=plan_input.direction,
        symbol_rules=symbol_rule,
    )

    risk = risk_check(
        sizing_result=sizing, risk_config=risk_config, execution_config=execution_config,
        opportunity_grade_config=grade_config, account_risk_state=account_state,
        plan=plan_input, execution_enabled=exec_enabled, kill_switch=kill_sw,
        exchange_connected=False, db_healthy=True,
    )

    decision = decide(
        risk_result=risk, execution_enabled=exec_enabled, kill_switch=kill_sw,
    )

    async with db.begin_nested():
        sizing_model = PositionSizingResultModel(
            id=uuid4(), trade_plan_id=plan_id,
            equity=sizing.equity, risk_percent=sizing.risk_percent, risk_amount=sizing.risk_amount,
            entry_price=sizing.entry_price, stop_loss_price=sizing.stop_loss_price,
            stop_distance_percent=sizing.stop_distance_percent, notional_value=sizing.notional_value,
            raw_size=sizing.raw_size, rounded_size=sizing.rounded_size,
            required_margin=sizing.required_margin, leverage=sizing.leverage,
            estimated_fee=sizing.estimated_fee, risk_reward_ratio=sizing.risk_reward_ratio,
            estimated_loss_at_stop=sizing.estimated_loss_at_stop, sizing_warnings=sizing.sizing_warnings,
        )
        risk_model = RiskCheckModel(
            id=uuid4(), trade_plan_id=plan_id, status=risk.status.value,
            risk_amount=risk.risk_amount, notional_value=risk.notional_value,
            required_margin=risk.required_margin, risk_reward_ratio=risk.risk_reward_ratio,
            max_allowed_risk_percent=risk.max_allowed_risk_percent,
            warnings=risk.warnings, block_reasons=risk.block_reasons,
            risk_config_version=risk_ver,
        )
        decision_model = DecisionGateResultModel(
            id=uuid4(), trade_plan_id=plan_id, risk_check_id=risk_model.id,
            result=decision.result.value, reasons=decision.reasons,
        )
        db.add_all([sizing_model, risk_model])
        await db.flush()
        db.add(decision_model)

        if decision.result == DecisionGateStatus.ALLOW_CONFIRM:
            model.status = PlanStatus.READY_FOR_CONFIRMATION.value
        else:
            model.status = PlanStatus.CHECKED.value

        model.risk_config_version = risk_ver
        model.strategy_config_version = grade_ver

    await db.commit()
    await db.refresh(model)
    await db.refresh(sizing_model)
    await db.refresh(risk_model)
    await db.refresh(decision_model)

    return {
        "plan": _to_schema(model),
        "sizing": _to_sizing_out(sizing_model),
        "risk": _to_risk_out(risk_model),
        "decision": _to_decision_out(decision_model),
    }


def _to_schema(m: TradePlanModel) -> TradePlanSchema:
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


def _to_input(m: TradePlanModel) -> TradePlanInput:
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


def _to_sizing_out(m: PositionSizingResultModel) -> dict:
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


def _to_risk_out(m: RiskCheckModel) -> dict:
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


def _to_decision_out(m: DecisionGateResultModel) -> dict:
    return {
        "id": str(m.id) if m.id else None,
        "trade_plan_id": str(m.trade_plan_id) if m.trade_plan_id else None,
        "risk_check_id": str(m.risk_check_id) if m.risk_check_id else None,
        "result": m.result, "reasons": m.reasons or [],
    }