"""Authenticated, read-only exchange account endpoints."""
from fastapi import APIRouter, Depends, Query

from app.response import ApiResponse
from app.security import require_auth
from app.services.account_sync_service import get_account_snapshot

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/snapshot")
async def get_snapshot(
    symbol: str = Query(default="BTCUSDT", min_length=3, max_length=32),
    order_limit: int = Query(default=50, ge=1, le=100),
    _auth: str = Depends(require_auth),
) -> dict:
    """Return balances, positions and orders using only exchange read APIs."""
    return ApiResponse.ok(await get_account_snapshot(symbol.upper(), order_limit)).model_dump()
