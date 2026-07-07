import pytest


@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["execution_enabled"] is False
    assert data["kill_switch"] is True


@pytest.mark.asyncio
async def test_toggle_kill_switch(client):
    resp = await client.post("/api/system/kill-switch", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["kill_switch"] is False

    resp = await client.get("/api/system/status")
    assert resp.json()["data"]["kill_switch"] is False


@pytest.mark.asyncio
async def test_toggle_execution_mode(client):
    resp = await client.post("/api/system/execution-mode", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["execution_enabled"] is True

    resp = await client.get("/api/system/status")
    assert resp.json()["data"]["execution_enabled"] is True
