from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db import get_db
from app.exceptions import AppException
from app.models import ConfigVersionModel
from app.response import ApiResponse
from app.schemas.config import (
    ActiveConfigsOut, ConfigVersionOut, CreateConfigRequest,
)
from shared.enums import ConfigType


router = APIRouter(prefix="/api/configs", tags=["configs"])


def _to_out(model: ConfigVersionModel) -> ConfigVersionOut:
    return ConfigVersionOut(
        id=model.id,
        config_type=model.config_type,
        version_label=model.version_label,
        payload=model.payload,
        is_active=model.is_active,
        created_at=model.created_at,
        activated_at=model.activated_at,
    )


def _config_type_set() -> set[str]:
    return {ct.value for ct in ConfigType}


def _ensure_config_type(type: str) -> None:
    if type not in _config_type_set():
        raise AppException("INVALID_CONFIG_TYPE", f"未知配置类型: {type}", 400)


@router.get("/active")
async def get_active_configs(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(ConfigVersionModel).where(ConfigVersionModel.is_active == True)  # noqa: E712
    )
    active = {v.config_type: v for v in result.scalars().all()}
    return ApiResponse.ok(ActiveConfigsOut(
        risk=_to_out(active[ConfigType.RISK.value]) if ConfigType.RISK.value in active else None,
        execution=_to_out(active[ConfigType.EXECUTION.value]) if ConfigType.EXECUTION.value in active else None,
        opportunity_grade=_to_out(active[ConfigType.OPPORTUNITY_GRADE.value]) if ConfigType.OPPORTUNITY_GRADE.value in active else None,
        symbol_rules=_to_out(active[ConfigType.SYMBOL_RULES.value]) if ConfigType.SYMBOL_RULES.value in active else None,
    ).model_dump()).model_dump()


@router.get("")
async def list_configs(
    type: str = Query(..., description="配置类型: risk/execution/opportunity_grade/symbol_rules"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ensure_config_type(type)
    result = await db.execute(
        select(ConfigVersionModel)
        .where(ConfigVersionModel.config_type == type)
        .order_by(ConfigVersionModel.created_at.desc())
    )
    versions = [_to_out(v).model_dump() for v in result.scalars().all()]
    return ApiResponse.ok(versions).model_dump()


@router.post("")
async def create_config(
    body: CreateConfigRequest, db: AsyncSession = Depends(get_db),
) -> dict:
    _ensure_config_type(body.config_type)

    existing = await db.execute(
        select(ConfigVersionModel).where(
            ConfigVersionModel.config_type == body.config_type,
            ConfigVersionModel.version_label == body.version_label,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AppException(
            "DUPLICATE_LABEL",
            f"配置 {body.config_type}/{body.version_label} 已存在",
            409,
        )

    new_version = ConfigVersionModel(
        id=uuid4(),
        config_type=body.config_type,
        version_label=body.version_label,
        payload=body.payload,
        is_active=False,
        activated_at=None,
    )
    db.add(new_version)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(
            "DUPLICATE_LABEL",
            f"配置 {body.config_type}/{body.version_label} 已存在",
            409,
        )
    await db.refresh(new_version)
    return ApiResponse.ok(_to_out(new_version).model_dump()).model_dump()


@router.post("/{version_id}/activate")
async def activate_config(
    version_id: UUID, db: AsyncSession = Depends(get_db),
) -> dict:
    # 单事务内：先锁住目标行（行锁），再锁住同 config_type 的全部行，
    # 防止并发激活同类型不同版本导致竞态。
    result = await db.execute(
        select(ConfigVersionModel)
        .where(ConfigVersionModel.id == version_id)
        .with_for_update()
    )
    target = result.scalar_one_or_none()
    if target is None:
        raise AppException("CONFIG_NOT_FOUND", f"配置 {version_id} 不存在", 404)

    config_type = target.config_type

    # 锁住同 config_type 所有行，串行化并发激活
    await db.execute(
        select(ConfigVersionModel)
        .where(ConfigVersionModel.config_type == config_type)
        .with_for_update()
    )

    # 同事务内将其他 active 版本置为 inactive
    await db.execute(
        update(ConfigVersionModel)
        .where(
            ConfigVersionModel.config_type == config_type,
            ConfigVersionModel.id != version_id,
            ConfigVersionModel.is_active == True,  # noqa: E712
        )
        .values(is_active=False)
    )

    if not target.is_active:
        target.is_active = True
        target.activated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(
            "ACTIVATE_CONFLICT",
            "激活配置冲突，请稍后重试",
            409,
        )

    await db.refresh(target)
    return ApiResponse.ok(_to_out(target).model_dump()).model_dump()
