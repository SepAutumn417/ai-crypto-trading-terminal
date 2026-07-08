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
from app.services import plan_service, execution_service
from app.websocket import ws_manager
from shared.schemas import TradePlanInput


router = APIRouter(prefix="/api/trade-plans", tags=["trade-plans"])


async def _broadcast_plan(msg_type: str, plan_id: str | None = None) -> None:
    """推送 plans 频道，失败不影响主流程。"""
    import logging
    log = logging.getLogger(__name__)
    try:
        await ws_manager.broadcast("plans", msg_type, {"plan_id": plan_id} if plan_id else {})
    except Exception:
        log.debug("broadcast plans failed", exc_info=True)


@router.post("")
async def create_plan(body: TradePlanCreate, db: AsyncSession = Depends(get_db)) -> dict:
    plan_input = TradePlanInput(
        exchange=body.exchange, symbol=body.symbol,
        direction=body.direction, entry_price=body.entry_price,
        stop_loss_price=body.stop_loss_price,
        take_profit_prices=body.take_profit_prices,
        leverage=body.leverage, risk_percent=body.risk_percent,
        opportunity_grade=body.opportunity_grade, equity=body.equity,
        setup_type=body.setup_type, margin_mode=body.margin_mode, notes=body.notes,
    )
    plan = await plan_service.create_plan(db, plan_input)
    await _broadcast_plan("plan_created", str(plan.id))
    return ApiResponse.ok(TradePlanOut(**plan.model_dump(mode="json")).model_dump(mode="json")).model_dump()


@router.post("/{plan_id}/check")
async def check_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    result = await plan_service.check_plan(db, plan_id)
    await _broadcast_plan("plan_checked", str(plan_id))
    payload = {
        "plan": result["plan"].model_dump(mode="json"),
        "sizing": result["sizing"],
        "risk": result["risk"],
        "decision": result["decision"],
    }
    return ApiResponse.ok(payload).model_dump()


@router.post("/{plan_id}/execute")
async def execute_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    plan = await execution_service.execute_plan(db, plan_id)
    await _broadcast_plan("plan_executed", str(plan_id))
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()


@router.post("/{plan_id}/sync")
async def sync_order_status(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    plan = await execution_service.sync_order_status(db, plan_id)
    await _broadcast_plan("plan_synced", str(plan_id))
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()


@router.post("/{plan_id}/cancel")
async def cancel_plan_order(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    plan = await execution_service.cancel_plan_order(db, plan_id)
    await _broadcast_plan("plan_cancelled", str(plan_id))
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()


@router.get("")
async def list_plans(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plans = await plan_service.list_plans(db, status=status)
    return ApiResponse.ok([p.model_dump(mode="json") for p in plans]).model_dump()


@router.get("/{plan_id}")
async def get_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    plan = await plan_service.get_plan(db, plan_id)
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()