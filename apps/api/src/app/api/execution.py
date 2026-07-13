from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.response import ApiResponse
from app.security import require_auth
from app.services.dry_run_service import create_preview, run_dry_run

router = APIRouter(prefix="/api/execution", tags=["execution"])


@router.post("/plans/{plan_id}/preview")
async def preview_order(plan_id: UUID, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)) -> dict:
    return ApiResponse.ok(await create_preview(db, plan_id)).model_dump()


@router.post("/intents/{intent_id}/dry-run")
async def dry_run(intent_id: UUID, db: AsyncSession = Depends(get_db), _auth: str = Depends(require_auth)) -> dict:
    return ApiResponse.ok(await run_dry_run(db, intent_id)).model_dump()
