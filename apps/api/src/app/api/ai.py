import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_evaluator import AIEvaluationResult, AIInput, LLMClient, evaluate_trade, evaluate_with_llm
from app.config import settings
from app.db import get_db
from app.exceptions import AppException
from app.models import AIEvaluationResultModel, TradePlan
from app.response import ApiResponse
from app.security import require_auth
from app.services.config_service import get_ai_indicator_weights
from app.services.execution_service import _get_exchange
from exchange_adapter import KlineInterval
from shared.enums import Direction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _get_llm_client() -> LLMClient | None:
    """构建 LLM 客户端，未启用或未配置时返回 None。"""
    if not settings.ai_evaluation_enabled or not settings.llm_api_key:
        return None
    return LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


@router.get("/evaluate")
async def evaluate_opportunity(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    direction: Direction = Query(..., description="方向: LONG 或 SHORT"),
    entry_price: Decimal = Query(..., description="入场价格"),
    interval: KlineInterval = Query(default=KlineInterval.ONE_HOUR, description="K线周期"),
    limit: int = Query(default=100, ge=50, le=500, description="K线数量"),
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> ApiResponse[AIEvaluationResult]:
    try:
        exchange = _get_exchange()
        klines = await exchange.get_klines(symbol, interval, limit=limit)
    except Exception as e:
        logger.exception("指标评分：交易所连接失败 symbol=%s", symbol)
        raise AppException("EXCHANGE_UNAVAILABLE", f"交易所连接失败: {e}", 503) from e

    try:
        weights = await get_ai_indicator_weights(db)
        if weights:
            logger.info("指标评分使用配置权重: %s", weights)
        else:
            logger.info("指标评分未读取到配置权重，使用默认权重")

        result = evaluate_trade(symbol, direction.value, entry_price, klines, interval, weights=weights or None)
    except Exception as e:
        logger.exception("指标评分：评估计算失败 symbol=%s", symbol)
        raise AppException("AI_EVALUATION_FAILED", f"指标评分计算失败: {e}", 500) from e

    return ApiResponse.ok(result)


@router.post("/evaluate-plan/{plan_id}")
async def evaluate_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> dict:
    """v0.5: 对交易计划进行 AI 综合评估（规则评分 + LLM 解释）。"""
    plan = await db.get(TradePlan, plan_id)
    if plan is None:
        raise AppException("NOT_FOUND", f"交易计划 {plan_id} 不存在", 404)

    try:
        exchange = _get_exchange()
        interval = KlineInterval.ONE_HOUR
        klines = await exchange.get_klines(plan.symbol, interval, limit=100)
    except Exception as e:
        logger.exception("AI 评估：交易所连接失败 plan_id=%s", plan_id)
        raise AppException("EXCHANGE_UNAVAILABLE", f"交易所连接失败: {e}", 503) from e

    try:
        weights = await get_ai_indicator_weights(db)
        llm_client = _get_llm_client()

        ai_input = AIInput(
            marketStructure={
                "symbol": plan.symbol,
                "direction": plan.direction,
                "entry_price": str(plan.entry_price),
            },
            candidatePlan={
                "setup_type": plan.setup_type or "",
                "opportunity_grade": plan.opportunity_grade or "",
                "leverage": str(plan.leverage),
                "risk_percent": str(plan.risk_percent),
                "stop_loss_price": str(plan.stop_loss_price) if plan.stop_loss_price else None,
                "take_profit_prices": [str(tp) for tp in (plan.take_profit_prices or [])],
                "notes": plan.notes or "",
            },
            riskResult={},
            systemMode="L4_CONFIRM_EXECUTION",
        )

        comprehensive = await evaluate_with_llm(
            ai_input=ai_input,
            symbol=plan.symbol,
            direction=plan.direction,
            entry_price=plan.entry_price,
            klines=klines,
            interval=interval,
            weights=weights or None,
            llm_client=llm_client,
        )
    except Exception as e:
        logger.exception("AI 评估失败 plan_id=%s", plan_id)
        raise AppException("AI_EVALUATION_FAILED", f"AI 评估失败: {e}", 500) from e

    result = {
        "symbol": comprehensive.symbol,
        "direction": comprehensive.direction,
        "overall_score": str(comprehensive.overall_score),
        "grade": comprehensive.grade.value,
        "recommendation": comprehensive.recommendation,
        "risk_level": comprehensive.risk_level,
        "conviction": str(comprehensive.conviction),
        "source": comprehensive.source.value,
        "signals": [s.model_dump(mode="json") for s in comprehensive.signals],
    }
    if comprehensive.explanation:
        result["explanation"] = comprehensive.explanation.model_dump(mode="json")
    return ApiResponse.ok(result).model_dump()


@router.post("/review-trade/{journal_id}")
async def review_trade(
    journal_id: UUID,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> dict:
    """v0.5: 对已平仓交易进行 AI 复盘。"""
    from app.models import TradeJournal
    journal = await db.get(TradeJournal, journal_id)
    if journal is None:
        raise AppException("NOT_FOUND", f"交易日志 {journal_id} 不存在", 404)

    llm_client = _get_llm_client()
    if llm_client is None:
        return ApiResponse.ok({
            "summary": "LLM 未启用，无法生成 AI 复盘。请在 .env 中配置 AI_EVALUATION_ENABLED=true 和 LLM_API_KEY。",
            "source": "rule_based",
        }).model_dump()

    review_input = {
        "symbol": journal.symbol,
        "direction": journal.direction,
        "entry_price": str(journal.entry_price) if journal.entry_price else None,
        "exit_price": str(journal.exit_price) if journal.exit_price else None,
        "exit_reason": journal.exit_reason or "",
        "lessons_learned": journal.lessons_learned or "",
        "emotions": journal.emotions or "",
        "pnl": str(journal.pnl) if journal.pnl else None,
    }

    system_prompt = """你是一个专业的交易复盘助手。请基于以下交易记录生成复盘总结，回答：
1. 是否按计划执行
2. 是否存在情绪化交易
3. 止损是否合理
4. 经验教训总结

输出 JSON: {"summary": "...", "emotionalAnalysis": "...", "lessonSummary": "...", "improvementSuggestions": []}"""

    try:
        import json
        user_content = json.dumps(review_input, ensure_ascii=False, default=str)
        raw = await llm_client.chat_json(system_prompt, user_content)
        raw["source"] = "llm"
        return ApiResponse.ok(raw).model_dump()
    except Exception as e:
        logger.exception("AI 复盘失败 journal_id=%s", journal_id)
        raise AppException("AI_REVIEW_FAILED", f"AI 复盘失败: {e}", 500) from e
