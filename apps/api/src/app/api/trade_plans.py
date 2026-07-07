from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db import get_db
from app.response import ApiResponse
from app.schemas.trade_plan import (
    CheckResult, TradePlanCreate, TradePlanOut,
)
from app.services import plan_service
from shared.schemas import TradePlanInput


router = APIRouter(prefix="/api/trade-plans", tags=["trade-plans"])


@router.post("")
async def create_plan(body: TradePlanCreate, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        plan_input = TradePlanInput(
            exchange=body.exchange, symbol=body.symbol,
            direction=body.direction, entry_price=body.entry_price,
            stop_loss_price=body.stop_loss_price,
            take_profit_prices=body.take_profit_prices,
            leverage=body.leverage, risk_percent=body.risk_percent,
            opportunity_grade=body.opportunity_grade, equity=body.equity,
            setup_type=body.setup_type, margin_mode=body.margin_mode, notes=body.notes,
        )
    except Exception as e:
        return ApiResponse.err("INVALID_INPUT", str(e)).model_dump()

    plan = await plan_service.create_plan(db, plan_input)
    return ApiResponse.ok(TradePlanOut(**plan.model_dump(mode="json")).model_dump(mode="json")).model_dump()


@router.post("/{plan_id}/check")
async def check_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        result = await plan_service.check_plan(db, plan_id)
    except LookupError as e:
        return ApiResponse.err("PLAN_NOT_FOUND", str(e)).model_dump()
    except ValueError as e:
        return ApiResponse.err("PLAN_STATUS_ERROR", str(e)).model_dump()

    payload = {
        "plan": result["plan"].model_dump(mode="json"),
        "sizing": result["sizing"],
        "risk": result["risk"],
        "decision": result["decision"],
    }
    return ApiResponse.ok(payload).model_dump()


@router.get("")
async def list_plans(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plans = await plan_service.list_plans(db, status=status)
    return ApiResponse.ok([p.model_dump(mode="json") for p in plans]).model_dump()


@router.get("/{plan_id}")
async def get_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        plan = await plan_service.get_plan(db, plan_id)
    except LookupError as e:
        return ApiResponse.err("PLAN_NOT_FOUND", str(e)).model_dump()
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()