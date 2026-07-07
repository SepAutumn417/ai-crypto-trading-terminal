import pytest


@pytest.mark.asyncio
async def test_get_active_configs(client):
    resp = await client.get("/api/configs/active")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk"]["version_label"] == "risk-v1"
    assert data["symbol_rules"]["version_label"] == "symbol_rules-v1"


@pytest.mark.asyncio
async def test_list_configs(client):
    resp = await client.get("/api/configs", params={"type": "risk"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(v["config_type"] == "risk" for v in data)


@pytest.mark.asyncio
async def test_create_and_activate_config(client):
    resp = await client.post("/api/configs", json={
        "config_type": "risk",
        "version_label": "risk-v2",
        "payload": {"max_leverage": "5"},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    new_id = body["data"]["id"]

    resp = await client.post(f"/api/configs/{new_id}/activate")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True

    resp = await client.get("/api/configs/active")
    active = resp.json()["data"]
    assert active["risk"]["version_label"] == "risk-v2"
    assert active["risk"]["id"] == new_id

    resp = await client.get("/api/configs", params={"type": "risk"})
    versions = {v["version_label"]: v for v in resp.json()["data"]}
    assert versions["risk-v1"]["is_active"] is False
    assert versions["risk-v2"]["is_active"] is True


@pytest.mark.asyncio
async def test_duplicate_label_rejected(client):
    resp = await client.post("/api/configs", json={
        "config_type": "risk",
        "version_label": "risk-v1",
        "payload": {},
    })
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "DUPLICATE_LABEL"


@pytest.mark.asyncio
async def test_invalid_config_type(client):
    resp = await client.post("/api/configs", json={
        "config_type": "invalid",
        "version_label": "x",
        "payload": {},
    })
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CONFIG_TYPE"


@pytest.mark.asyncio
async def test_invalid_config_type_in_list(client):
    resp = await client.get("/api/configs", params={"type": "invalid"})
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CONFIG_TYPE"


@pytest.mark.asyncio
async def test_activate_missing_config(client):
    from uuid import uuid4
    resp = await client.post(f"/api/configs/{uuid4()}/activate")
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "CONFIG_NOT_FOUND"
