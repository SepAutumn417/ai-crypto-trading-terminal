from enum import Enum
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.response import ApiResponse
from app.schemas.trade_plan import (
    CheckResult,
    TradePlanCreate,
    TradePlanOut,
)
from app.security import require_auth
from app.services import execution_service, plan_service
from app.services.confirmation_service import confirm_plan
from app.websocket import ws_manager
from shared.schemas import TradePlanInput


class PlanStatusFilter(str, Enum):
    DRAFT = "DRAFT"
    CHECKED = "CHECKED"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    EXECUTING = "EXECUTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class ConfirmRequest(BaseModel):
    """P0-3: 二次确认请求体。"""
    token: str
    passphrase: str | None = None


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
async def create_plan(body: TradePlanCreate, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)) -> dict:
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
async def check_plan(plan_id: UUID, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)) -> dict:
    result = await plan_service.check_plan(db, plan_id)
    await _broadcast_plan("plan_checked", str(plan_id))
    payload = {
        "plan": result["plan"].model_dump(mode="json"),
        "sizing": result["sizing"],
        "risk": result["risk"],
        "decision": result["decision"],
    }
    return ApiResponse.ok(payload).model_dump()


@router.post("/{plan_id}/confirm")
async def confirm_plan_endpoint(
    plan_id: UUID, body: ConfirmRequest, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)
) -> dict:
    """P0-3: 服务端二次确认端点。

    验证 confirmation_token 和口令，将计划状态从 READY_FOR_CONFIRMATION 变为 CONFIRMED。
    只有 CONFIRMED 状态的计划才能执行 execute_plan。
    """
    await confirm_plan(db, plan_id, body.token, body.passphrase)
    await _broadcast_plan("plan_confirmed", str(plan_id))
    return ApiResponse.ok({"plan_id": str(plan_id), "status": "CONFIRMED"}).model_dump()


@router.post("/{plan_id}/execute")
async def execute_plan(plan_id: UUID, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)) -> dict:
    plan = await execution_service.execute_plan(db, plan_id)
    await _broadcast_plan("plan_executed", str(plan_id))
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()


@router.post("/{plan_id}/sync")
async def sync_order_status(plan_id: UUID, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)) -> dict:
    plan = await execution_service.sync_order_status(db, plan_id)
    await _broadcast_plan("plan_synced", str(plan_id))
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()


@router.post("/{plan_id}/cancel")
async def cancel_plan_order(plan_id: UUID, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)) -> dict:
    plan = await execution_service.cancel_plan_order(db, plan_id)
    await _broadcast_plan("plan_cancelled", str(plan_id))
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()


@router.get("")
async def list_plans(
    status: PlanStatusFilter | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plans = await plan_service.list_plans(db, status=status.value if status else None)
    return ApiResponse.ok([p.model_dump(mode="json") for p in plans]).model_dump()


@router.get("/{plan_id}")
async def get_plan(plan_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    plan = await plan_service.get_plan(db, plan_id)
    return ApiResponse.ok(plan.model_dump(mode="json")).model_dump()
