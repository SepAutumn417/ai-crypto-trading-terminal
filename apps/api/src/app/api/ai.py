import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from exchange_adapter import KlineInterval
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.exceptions import AppException
from app.response import ApiResponse
from app.services.config_service import get_ai_indicator_weights
from app.services.execution_service import _get_exchange
from ai_evaluator import evaluate_trade, AIEvaluationResult
from shared.enums import Direction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/evaluate")
async def evaluate_opportunity(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    direction: Direction = Query(..., description="方向: LONG 或 SHORT"),
    entry_price: Decimal = Query(..., description="入场价格"),
    interval: KlineInterval = Query(default=KlineInterval.ONE_HOUR, description="K线周期"),
    limit: int = Query(default=100, ge=50, le=500, description="K线数量"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[AIEvaluationResult]:
    # P1-19: 包裹 try/except，交易所异常返回 503 而非 500
    try:
        exchange = _get_exchange()
        klines = await exchange.get_klines(symbol, interval, limit=limit)
    except Exception as e:
        logger.exception("AI 评估：交易所连接失败 symbol=%s", symbol)
        raise AppException("EXCHANGE_UNAVAILABLE", f"交易所连接失败: {e}", 503) from e

    try:
        weights = await get_ai_indicator_weights(db)
        if weights:
            logger.info("AI 评估使用配置权重: %s", weights)
        else:
            logger.info("AI 评估未读取到配置权重，使用默认权重")

        result = evaluate_trade(symbol, direction.value, entry_price, klines, interval, weights=weights or None)
    except Exception as e:
        logger.exception("AI 评估：评估计算失败 symbol=%s", symbol)
        raise AppException("AI_EVALUATION_FAILED", f"AI 评估计算失败: {e}", 500) from e

    return ApiResponse.ok(result)
