from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.response import ApiResponse
from app.schemas.trade_plan import (
    CalculatePositionRequest, RiskCheckRequest,
)
from app.services.config_service import (
    get_active_execution_config, get_active_opportunity_grade_config,
    get_active_risk_config, get_account_risk_state, get_symbol_rule, get_user_settings,
)
from position_sizing.calculator import calculate as calculate_position
from risk_engine.checker import check as risk_check
from shared.schemas import (
    PositionSizingResult as PositionSizingSchema,
    TradePlanInput,
)


router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.post("/calculate-position")
async def calculate_position_endpoint(
    body: CalculatePositionRequest, db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        rule = await get_symbol_rule(db, body.symbol)
    except ValueError as e:
        return ApiResponse.err("SYMBOL_NOT_FOUND", str(e)).model_dump()

    result = calculate_position(
        equity=body.equity, risk_percent=body.risk_percent,
        entry_price=body.entry_price, stop_loss_price=body.stop_loss_price,
        take_profit_prices=body.take_profit_prices, leverage=body.leverage,
        fee_rate=body.fee_rate, direction=body.direction, symbol_rules=rule,
    )
    return ApiResponse.ok({
        "equity": str(result.equity), "risk_percent": str(result.risk_percent),
        "risk_amount": str(result.risk_amount), "entry_price": str(result.entry_price),
        "stop_loss_price": str(result.stop_loss_price) if result.stop_loss_price is not None else None,
        "stop_distance_percent": str(result.stop_distance_percent),
        "notional_value": str(result.notional_value), "raw_size": str(result.raw_size),
        "rounded_size": str(result.rounded_size) if result.rounded_size is not None else None,
        "required_margin": str(result.required_margin), "leverage": str(result.leverage),
        "estimated_fee": str(result.estimated_fee),
        "risk_reward_ratio": str(result.risk_reward_ratio),
        "estimated_loss_at_stop": str(result.estimated_loss_at_stop),
        "sizing_warnings": result.sizing_warnings,
    }).model_dump()


@router.post("/check")
async def risk_check_endpoint(
    body: RiskCheckRequest, db: AsyncSession = Depends(get_db),
) -> dict:
    plan_input = TradePlanInput(
        exchange=body.plan.exchange, symbol=body.plan.symbol,
        direction=body.plan.direction, entry_price=body.plan.entry_price,
        stop_loss_price=body.plan.stop_loss_price,
        take_profit_prices=body.plan.take_profit_prices,
        leverage=body.plan.leverage, risk_percent=body.plan.risk_percent,
        opportunity_grade=body.plan.opportunity_grade, equity=body.plan.equity,
        setup_type=body.plan.setup_type, margin_mode=body.plan.margin_mode, notes=body.plan.notes,
    )

    sizing = PositionSizingSchema.model_validate(body.sizing_result.model_dump())

    risk_config, risk_ver = await get_active_risk_config(db)
    execution_config, _ = await get_active_execution_config(db)
    grade_config, _ = await get_active_opportunity_grade_config(db)
    account_state = await get_account_risk_state(db)
    user_settings = await get_user_settings(db)

    exec_enabled = user_settings.execution_enabled if user_settings else False
    kill_sw = user_settings.kill_switch if user_settings else True

    risk = risk_check(
        sizing_result=sizing, risk_config=risk_config, execution_config=execution_config,
        opportunity_grade_config=grade_config, account_risk_state=account_state,
        plan=plan_input, execution_enabled=exec_enabled, kill_switch=kill_sw,
        exchange_connected=False, db_healthy=True,
    )

    return ApiResponse.ok({
        "status": risk.status.value,
        "risk_amount": str(risk.risk_amount),
        "notional_value": str(risk.notional_value),
        "required_margin": str(risk.required_margin),
        "risk_reward_ratio": str(risk.risk_reward_ratio),
        "max_allowed_risk_percent": str(risk.max_allowed_risk_percent),
        "warnings": risk.warnings, "block_reasons": risk.block_reasons,
        "risk_config_version": risk_ver,
    }).model_dump()