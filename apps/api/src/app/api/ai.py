from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException
from exchange_adapter import KlineInterval, MockExchange

from app.response import ApiResponse
from ai_evaluator import evaluate_trade, AIEvaluationResult

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/evaluate")
async def evaluate_opportunity(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    direction: str = Query(..., description="方向: LONG 或 SHORT"),
    entry_price: Decimal = Query(..., description="入场价格"),
    interval: KlineInterval = Query(default=KlineInterval.ONE_HOUR, description="K线周期"),
    limit: int = Query(default=100, ge=50, le=500, description="K线数量"),
) -> dict:
    if direction not in ("LONG", "SHORT"):
        raise HTTPException(status_code=400, detail="direction must be LONG or SHORT")

    exchange = MockExchange()
    klines = await exchange.get_klines(symbol, interval, limit=limit)

    result = evaluate_trade(symbol, direction, entry_price, klines, interval)

    return ApiResponse.ok(result.model_dump()).model_dump()
