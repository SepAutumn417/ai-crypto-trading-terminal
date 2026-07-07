from uuid import uuid4

from fastapi import APIRouter, Depends
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


router = APIRouter(prefix="/api/system", tags=["system"])


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

    return ApiResponse.ok(UserSettingsOut(
        execution_enabled=settings.execution_enabled,
        kill_switch=settings.kill_switch,
        account_equity=settings.account_equity,
        mode=settings.mode,
    ).model_dump()).model_dump()
