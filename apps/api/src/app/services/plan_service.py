from uuid import UUID, uuid4
from decimal import Decimal
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PlanNotRecheckableException
from app.models import (
    AIEvaluationResultModel,
    DecisionGateResult as DecisionGateResultModel,
    PositionSizingResult as PositionSizingResultModel,
    RiskCheck as RiskCheckModel,
    TradePlan as TradePlanModel,
)
from app.services.config_service import (
    get_account_risk_state, get_active_execution_config,
    get_active_opportunity_grade_config, get_active_risk_config,
    get_active_symbol_rules, get_ai_indicator_weights, get_symbol_rule, get_user_settings,
)
from app.services.plan_converter import (
    to_schema as _to_schema, to_input as _to_input,
    to_sizing_out as _to_sizing_out, to_risk_out as _to_risk_out,
    to_decision_out as _to_decision_out,
)
from shared.enums import (
    DecisionGateStatus, Direction, MarginMode, OpportunityGrade, PlanStatus,
)
from shared.schemas import TradePlanInput, TradePlan as TradePlanSchema
from decision_gate.gate import decide
from position_sizing.calculator import calculate as calculate_position
from risk_engine.checker import check as risk_check

logger = logging.getLogger(__name__)


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
        raise PlanNotRecheckableException(str(plan_id), model.status)

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

    # AI 评估：拉取 K 线并调用 ai_evaluator，结果落库并参与决策门融合
    ai_eval_dict: dict | None = None
    ai_model: AIEvaluationResultModel | None = None
    try:
        from app.services.execution_service import _get_exchange
        from ai_evaluator import evaluate_trade
        from exchange_adapter import KlineInterval

        exchange = _get_exchange()
        interval = KlineInterval.ONE_HOUR
        klines = await exchange.get_klines(model.symbol, interval, limit=100)
        weights = await get_ai_indicator_weights(db)
        ai_result = evaluate_trade(
            symbol=model.symbol,
            direction=plan_input.direction.value,
            entry_price=plan_input.entry_price,
            klines=klines,
            interval=interval,
            weights=weights or None,
        )
        ai_eval_dict = {
            "grade": ai_result.grade.value,
            "overall_score": float(ai_result.overall_score),
            "symbol": ai_result.symbol,
            "direction": ai_result.direction,
            "recommendation": ai_result.recommendation,
            "risk_level": ai_result.risk_level,
        }
    except Exception as e:
        logger.warning("AI 评估失败，跳过融合（plan_id=%s）: %s", plan_id, e)

    decision = decide(
        risk_result=risk, execution_enabled=exec_enabled, kill_switch=kill_sw,
        ai_evaluation=ai_eval_dict,
    )

    async with db.begin_nested():
        # 翻转旧记录 is_latest → false
        await db.execute(
            update(PositionSizingResultModel)
            .where(
                PositionSizingResultModel.trade_plan_id == plan_id,
                PositionSizingResultModel.is_latest == True,  # noqa: E712
            )
            .values(is_latest=False)
        )
        await db.execute(
            update(RiskCheckModel)
            .where(
                RiskCheckModel.trade_plan_id == plan_id,
                RiskCheckModel.is_latest == True,  # noqa: E712
            )
            .values(is_latest=False)
        )
        await db.execute(
            update(DecisionGateResultModel)
            .where(
                DecisionGateResultModel.trade_plan_id == plan_id,
                DecisionGateResultModel.is_latest == True,  # noqa: E712
            )
            .values(is_latest=False)
        )
        if ai_eval_dict is not None:
            await db.execute(
                update(AIEvaluationResultModel)
                .where(
                    AIEvaluationResultModel.trade_plan_id == plan_id,
                    AIEvaluationResultModel.is_latest == True,  # noqa: E712
                )
                .values(is_latest=False)
            )

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

        # AI 评估结果落库
        if ai_eval_dict is not None:
            ai_model = AIEvaluationResultModel(
                id=uuid4(), trade_plan_id=plan_id,
                symbol=ai_result.symbol, direction=ai_result.direction,
                overall_score=ai_result.overall_score, grade=ai_result.grade.value,
                recommendation=ai_result.recommendation, risk_level=ai_result.risk_level,
                signals=[s.model_dump(mode="json") for s in ai_result.signals],
                summary=ai_result.summary, conviction=ai_result.conviction,
                interval=interval.value,
            )
            db.add(ai_model)

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
    if ai_model is not None:
        await db.refresh(ai_model)

    result = {
        "plan": _to_schema(model),
        "sizing": _to_sizing_out(sizing_model),
        "risk": _to_risk_out(risk_model),
        "decision": _to_decision_out(decision_model),
    }
    if ai_model is not None:
        result["ai_evaluation"] = {
            "id": str(ai_model.id),
            "grade": ai_model.grade,
            "overall_score": str(ai_model.overall_score),
            "recommendation": ai_model.recommendation,
            "risk_level": ai_model.risk_level,
            "summary": ai_model.summary,
            "conviction": str(ai_model.conviction),
            "signals": ai_model.signals,
        }
    return result