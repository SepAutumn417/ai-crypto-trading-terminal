import pytest


@pytest.mark.asyncio
async def test_create_plan(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_check_plan_allows(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{plan_id}/check")
    body = resp.json()["data"]
    assert body["decision"]["result"] == "ALLOW_CONFIRM"
    assert body["plan"]["status"] == "READY_FOR_CONFIRMATION"
    assert body["sizing"]["risk_amount"] == "15"


@pytest.mark.asyncio
async def test_check_plan_blocks_no_stop(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": None,
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{plan_id}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "BLOCK"
    assert body["decision"]["result"] == "BLOCK"
    assert body["plan"]["status"] == "CHECKED"


@pytest.mark.asyncio
async def test_list_plans(client):
    await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    resp = await client.get("/api/trade-plans", params={"status": "DRAFT"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_get_plan_detail(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]
    resp = await client.get(f"/api/trade-plans/{plan_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["symbol"] == "BTCUSDT"