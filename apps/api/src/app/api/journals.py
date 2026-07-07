from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.response import ApiResponse
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalUpdate,
    TradeJournalOut,
    TradeJournalListResponse,
    TradeJournalSummary,
)
from app.services.trade_journal_service import TradeJournalService

router = APIRouter(prefix="/api/journals", tags=["journals"])


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
        raise HTTPException(status_code=404, detail="Journal not found")
    return ApiResponse.ok(TradeJournalOut.model_validate(journal).model_dump()).model_dump()


@router.post("")
async def create_journal(
    data: TradeJournalCreate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    journal = await TradeJournalService.create(db, data)
    return ApiResponse.ok(TradeJournalOut.model_validate(journal).model_dump()).model_dump()


@router.put("/{journal_id}")
async def update_journal(
    journal_id: UUID,
    data: TradeJournalUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    journal = await TradeJournalService.update(db, journal_id, data)
    if not journal:
        raise HTTPException(status_code=404, detail="Journal not found")
    return ApiResponse.ok(TradeJournalOut.model_validate(journal).model_dump()).model_dump()


@router.delete("/{journal_id}")
async def delete_journal(
    journal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    success = await TradeJournalService.delete(db, journal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Journal not found")
    return ApiResponse.ok({"deleted": True}).model_dump()
