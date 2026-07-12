from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.exceptions import AppException
from app.response import ApiResponse
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalListResponse,
    TradeJournalOut,
    TradeJournalSummary,
    TradeJournalUpdate,
)
from app.security import require_auth
from app.services.trade_journal_service import TradeJournalService
from app.websocket import ws_manager

router = APIRouter(prefix="/api/journals", tags=["journals"])


async def _broadcast_journal(msg_type: str, journal_id: str | None = None) -> None:
    """推送 journals 频道，失败不影响主流程。"""
    import logging
    log = logging.getLogger(__name__)
    try:
        await ws_manager.broadcast("journals", msg_type, {"journal_id": journal_id} if journal_id else {})
    except Exception:
        log.debug("broadcast journals failed", exc_info=True)


@router.get("")
async def list_journals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await TradeJournalService.list(db, page, page_size, symbol, status)
    data = TradeJournalListResponse(
        items=[TradeJournalOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return ApiResponse.ok(data.model_dump()).model_dump()


@router.get("/summary")
async def get_journal_summary(
    symbol: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    summary = await TradeJournalService.get_summary(db, symbol)
    return ApiResponse.ok(summary.model_dump()).model_dump()


@router.get("/{journal_id}")
async def get_journal(
    journal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    journal = await TradeJournalService.get_by_id(db, journal_id)
    if not journal:
        raise AppException("JOURNAL_NOT_FOUND", "Journal not found", 404)
    return ApiResponse.ok(TradeJournalOut.model_validate(journal).model_dump()).model_dump()


@router.post("")
async def create_journal(
    data: TradeJournalCreate,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> dict:
    journal = await TradeJournalService.create(db, data)
    await _broadcast_journal("journal_created", str(journal.id))
    return ApiResponse.ok(TradeJournalOut.model_validate(journal).model_dump()).model_dump()


@router.put("/{journal_id}")
async def update_journal(
    journal_id: UUID,
    data: TradeJournalUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> dict:
    journal = await TradeJournalService.update(db, journal_id, data)
    if not journal:
        raise AppException("JOURNAL_NOT_FOUND", "Journal not found", 404)
    await _broadcast_journal("journal_updated", str(journal_id))
    return ApiResponse.ok(TradeJournalOut.model_validate(journal).model_dump()).model_dump()


@router.delete("/{journal_id}")
async def delete_journal(
    journal_id: UUID,
    db: AsyncSession = Depends(get_db),
    _auth: str = Depends(require_auth),
) -> dict:
    success = await TradeJournalService.delete(db, journal_id)
    if not success:
        raise AppException("JOURNAL_NOT_FOUND", "Journal not found", 404)
    await _broadcast_journal("journal_deleted", str(journal_id))
    return ApiResponse.ok({"deleted": True}).model_dump()
