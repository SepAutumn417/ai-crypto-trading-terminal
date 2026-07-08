from uuid import uuid4
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import SystemEvent, UserSettings
from app.response import ApiResponse
from app.schemas.system import (
    ExecutionModeRequest,
    KillSwitchRequest,
    SystemStatus,
    UserSettingsOut,
)
from app.websocket import ws_manager


router = APIRouter(prefix="/api/system", tags=["system"])


class UpdateEquityRequest(BaseModel):
    account_equity: Decimal | None = None
    mode: str | None = None


@router.get("/status")
async def get_status(db: AsyncSession = Depends(get_db)) -> dict:
    settings = await db.get(UserSettings, 1)
    if settings is None:
        return ApiResponse.ok(SystemStatus(
            execution_enabled=False,
            kill_switch=True,
            db_healthy=True,
            latest_event_type=None,
            latest_event_at=None,
        ).model_dump()).model_dump()

    latest = await db.execute(
        select(SystemEvent).order_by(desc(SystemEvent.created_at)).limit(1)
    )
    event = latest.scalar_one_or_none()

    return ApiResponse.ok(SystemStatus(
        execution_enabled=settings.execution_enabled,
        kill_switch=settings.kill_switch,
        db_healthy=True,
        latest_event_type=event.event_type if event else None,
        latest_event_at=event.created_at if event else None,
    ).model_dump()).model_dump()


@router.post("/kill-switch")
async def toggle_kill_switch(
    body: KillSwitchRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    settings = await db.get(UserSettings, 1)
    if settings is None:
        return ApiResponse.err(
            "USER_SETTINGS_NOT_FOUND", "user_settings 未初始化"
        ).model_dump()

    settings.kill_switch = body.enabled
    event = SystemEvent(
        id=uuid4(),
        event_type="kill_switch_toggled",
        severity="info",
        entity_type="user_settings",
        entity_id=None,
        actor="user",
        message=f"Kill Switch set to {body.enabled}",
        payload={"enabled": body.enabled},
    )
    db.add(event)
    await db.commit()

    await _broadcast_system_status(settings)

    return ApiResponse.ok(UserSettingsOut(
        execution_enabled=settings.execution_enabled,
        kill_switch=settings.kill_switch,
        account_equity=settings.account_equity,
        mode=settings.mode,
    ).model_dump()).model_dump()


@router.post("/execution-mode")
async def toggle_execution_mode(
    body: ExecutionModeRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    settings = await db.get(UserSettings, 1)
    if settings is None:
        return ApiResponse.err(
            "USER_SETTINGS_NOT_FOUND", "user_settings 未初始化"
        ).model_dump()

    settings.execution_enabled = body.enabled
    event = SystemEvent(
        id=uuid4(),
        event_type="execution_mode_toggled",
        severity="info",
        entity_type="user_settings",
        entity_id=None,
        actor="user",
        message=f"Execution Mode set to {body.enabled}",
        payload={"enabled": body.enabled},
    )
    db.add(event)
    await db.commit()

    await _broadcast_system_status(settings)

    return ApiResponse.ok(UserSettingsOut(
        execution_enabled=settings.execution_enabled,
        kill_switch=settings.kill_switch,
        account_equity=settings.account_equity,
        mode=settings.mode,
    ).model_dump()).model_dump()


@router.get("/user-settings")
async def get_user_settings_endpoint(db: AsyncSession = Depends(get_db)) -> dict:
    """返回 UserSettings（包含 account_equity / mode），供 EquityEditor 使用。"""
    settings = await db.get(UserSettings, 1)
    if settings is None:
        return ApiResponse.ok(UserSettingsOut(
            execution_enabled=False,
            kill_switch=True,
            account_equity=None,
            mode="training",
        ).model_dump()).model_dump()

    return ApiResponse.ok(UserSettingsOut(
        execution_enabled=settings.execution_enabled,
        kill_switch=settings.kill_switch,
        account_equity=settings.account_equity,
        mode=settings.mode,
    ).model_dump()).model_dump()


@router.put("/user-settings")
async def update_user_settings(
    body: UpdateEquityRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    """更新 account_equity / mode。其他字段（execution_enabled/kill_switch）走专用端点。"""
    settings = await db.get(UserSettings, 1)
    if settings is None:
        return ApiResponse.err(
            "USER_SETTINGS_NOT_FOUND", "user_settings 未初始化"
        ).model_dump()

    if body.account_equity is not None:
        settings.account_equity = body.account_equity
    if body.mode is not None:
        settings.mode = body.mode

    event = SystemEvent(
        id=uuid4(),
        event_type="user_settings_updated",
        severity="info",
        entity_type="user_settings",
        entity_id=None,
        actor="user",
        message=f"User settings updated: equity={body.account_equity}, mode={body.mode}",
        payload={
            "account_equity": str(body.account_equity) if body.account_equity is not None else None,
            "mode": body.mode,
        },
    )
    db.add(event)
    await db.commit()
    await db.refresh(settings)

    await _broadcast_system_status(settings)

    return ApiResponse.ok(UserSettingsOut(
        execution_enabled=settings.execution_enabled,
        kill_switch=settings.kill_switch,
        account_equity=settings.account_equity,
        mode=settings.mode,
    ).model_dump()).model_dump()


async def _broadcast_system_status(settings: UserSettings) -> None:
    """系统状态变更后推送 system 频道。失败不影响主流程。"""
    import logging
    log = logging.getLogger(__name__)
    try:
        await ws_manager.broadcast("system", "status_update", {
            "execution_enabled": settings.execution_enabled,
            "kill_switch": settings.kill_switch,
            "db_healthy": True,
        })
    except Exception:
        log.debug("broadcast system status failed", exc_info=True)
