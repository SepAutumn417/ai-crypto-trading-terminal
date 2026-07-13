import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PlanNotRecheckableException
from app.models import (
    AIEvaluationResultModel,
)
from app.models import (
    DecisionGateResult as DecisionGateResultModel,
)
from app.models import (
    PositionSizingResult as PositionSizingResultModel,
)
from app.models import (
    RiskCheck as RiskCheckModel,
)
from app.models import (
    TradePlan as TradePlanModel,
)
from app.services.config_service import (
    get_account_risk_state,
    get_active_execution_config,
    get_active_opportunity_grade_config,
    get_active_risk_config,
    get_active_symbol_rules,
    get_ai_indicator_weights,
    get_symbol_rule,
    get_user_settings,
)
from app.services.plan_converter import (
    to_decision_out as _to_decision_out,
)
from app.services.plan_converter import (
    to_input as _to_input,
)
from app.services.plan_converter import (
    to_risk_out as _to_risk_out,
)
from app.services.plan_converter import (
    to_schema as _to_schema,
)
from app.services.plan_converter import (
    to_sizing_out as _to_sizing_out,
)
from decision_gate.gate import decide
from position_sizing.calculator import calculate as calculate_position
from risk_engine.checker import check as risk_check
from shared.enums import (
    DecisionGateStatus,
    Direction,
    MarginMode,
    OpportunityGrade,
    PlanStatus,
)
from shared.schemas import TradePlan as TradePlanSchema
from shared.schemas import TradePlanInput

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

    # P1-26: 获取真实的 exchange / db 连接状态，替代硬编码
    from app.services.execution_service import check_system_health
    exchange_connected, db_healthy = await check_system_health(db, symbol=model.symbol)

    risk = risk_check(
        sizing_result=sizing, risk_config=risk_config, execution_config=execution_config,
        opportunity_grade_config=grade_config, account_risk_state=account_state,
        plan=plan_input, execution_enabled=exec_enabled, kill_switch=kill_sw,
        exchange_connected=exchange_connected, db_healthy=db_healthy,
    )

    # v0.5 AI 评估：规则评分 + LLM 解释层
    ai_eval_dict: dict | None = None
    ai_model: AIEvaluationResultModel | None = None
    ai_comprehensive = None
    try:
        from ai_evaluator import AIInput, LLMClient, evaluate_with_llm
        from app.config import settings
        from app.services.execution_service import _get_exchange
        from exchange_adapter import KlineInterval

        exchange = _get_exchange()
        interval = KlineInterval.ONE_HOUR
        klines = await exchange.get_klines(model.symbol, interval, limit=100)
        weights = await get_ai_indicator_weights(db)

        # v0.5: 构建 LLM 客户端（仅在启用时）
        llm_client: LLMClient | None = None
        if settings.ai_evaluation_enabled and settings.llm_api_key:
            llm_client = LLMClient(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
            )

        # v0.5: 组装结构化输入
        ai_input = AIInput(
            marketStructure={
                "symbol": model.symbol,
                "direction": plan_input.direction.value,
                "entry_price": str(plan_input.entry_price),
            },
            candidatePlan={
                "setup_type": model.setup_type or "",
                "opportunity_grade": model.opportunity_grade or "",
                "leverage": str(model.leverage),
                "risk_percent": str(model.risk_percent),
                "stop_loss_price": str(model.stop_loss_price) if model.stop_loss_price else None,
                "take_profit_prices": [str(tp) for tp in (model.take_profit_prices or [])],
                "notes": model.notes or "",
            },
            riskResult={
                "status": risk.status.value,
                "risk_amount": str(risk.risk_amount),
                "notional_value": str(risk.notional_value),
                "risk_reward_ratio": str(risk.risk_reward_ratio),
                "warnings": risk.warnings,
                "block_reasons": risk.block_reasons,
            },
            systemMode="L4_CONFIRM_EXECUTION" if exec_enabled else "L4_DRY_RUN",
        )

        ai_comprehensive = await evaluate_with_llm(
            ai_input=ai_input,
            symbol=model.symbol,
            direction=plan_input.direction.value,
            entry_price=plan_input.entry_price,
            klines=klines,
            interval=interval,
            weights=weights or None,
            llm_client=llm_client,
        )

        ai_eval_dict = {
            "grade": ai_comprehensive.grade.value,
            "overall_score": float(ai_comprehensive.overall_score),
            "symbol": ai_comprehensive.symbol,
            "direction": ai_comprehensive.direction,
            "recommendation": ai_comprehensive.recommendation,
            "risk_level": ai_comprehensive.risk_level,
            "source": ai_comprehensive.source.value,
        }
        # v0.5: 若有 LLM 解释，传入 recommended_action 供 DecisionGate 使用
        if ai_comprehensive.explanation:
            ai_eval_dict["recommended_action"] = ai_comprehensive.explanation.recommendedAction.value
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
        if ai_eval_dict is not None and ai_comprehensive is not None:
            ai_model = AIEvaluationResultModel(
                id=uuid4(), trade_plan_id=plan_id,
                symbol=ai_comprehensive.symbol, direction=ai_comprehensive.direction,
                overall_score=ai_comprehensive.overall_score, grade=ai_comprehensive.grade.value,
                recommendation=ai_comprehensive.recommendation, risk_level=ai_comprehensive.risk_level,
                signals=[s.model_dump(mode="json") for s in ai_comprehensive.signals],
                summary=ai_comprehensive.explanation.summary if ai_comprehensive.explanation else "",
                conviction=ai_comprehensive.conviction,
                interval=interval.value,
                source=ai_comprehensive.source.value,
                recommended_action=ai_comprehensive.explanation.recommendedAction.value if ai_comprehensive.explanation else None,
                market_state_explanation=ai_comprehensive.explanation.marketStateExplanation if ai_comprehensive.explanation else "",
                plan_quality_explanation=ai_comprehensive.explanation.planQualityExplanation if ai_comprehensive.explanation else "",
                risk_explanation=ai_comprehensive.explanation.riskExplanation if ai_comprehensive.explanation else "",
                opportunity_grade_comment=ai_comprehensive.explanation.opportunityGradeComment if ai_comprehensive.explanation else "",
                warnings=ai_comprehensive.explanation.warnings if ai_comprehensive.explanation else [],
                upgrade_conditions=ai_comprehensive.explanation.upgradeConditions if ai_comprehensive.explanation else [],
                invalidation_conditions=ai_comprehensive.explanation.invalidationConditions if ai_comprehensive.explanation else [],
                emotional_risk_flags=ai_comprehensive.explanation.emotionalRiskFlags if ai_comprehensive.explanation else [],
            )
            db.add(ai_model)

        if decision.result == DecisionGateStatus.ALLOW_CONFIRM:
            model.status = PlanStatus.READY_FOR_CONFIRMATION.value
            # P0-3: 生成二次确认挑战（plan_hash + token + TTL）
            from app.services.confirmation_service import generate_confirmation
            generate_confirmation(model)
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
            "source": ai_model.source,
            "recommended_action": ai_model.recommended_action,
            "market_state_explanation": ai_model.market_state_explanation,
            "plan_quality_explanation": ai_model.plan_quality_explanation,
            "risk_explanation": ai_model.risk_explanation,
            "opportunity_grade_comment": ai_model.opportunity_grade_comment,
            "warnings": ai_model.warnings,
            "upgrade_conditions": ai_model.upgrade_conditions,
            "invalidation_conditions": ai_model.invalidation_conditions,
            "emotional_risk_flags": ai_model.emotional_risk_flags,
        }
    return result
