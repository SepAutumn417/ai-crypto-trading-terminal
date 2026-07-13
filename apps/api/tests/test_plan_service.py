from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import DecisionGateResult, PositionSizingResult, RiskCheck


@pytest.mark.asyncio
async def test_check_persists_results(client, db_session):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    await client.post(f"/api/trade-plans/{plan_id}/check")

    ps = await db_session.scalar(select(PositionSizingResult).where(PositionSizingResult.trade_plan_id == UUID(plan_id)))
    rc = await db_session.scalar(select(RiskCheck).where(RiskCheck.trade_plan_id == UUID(plan_id)))
    dg = await db_session.scalar(select(DecisionGateResult).where(DecisionGateResult.trade_plan_id == UUID(plan_id)))
    assert ps is not None
    assert rc is not None
    assert dg is not None
