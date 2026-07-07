import pytest


@pytest.mark.asyncio
async def test_evaluate_opportunity(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": "65000.0",
            "interval": "1h",
            "limit": 100,
        }
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["direction"] == "LONG"
    assert "overall_score" in data
    assert "grade" in data
    assert len(data["signals"]) == 5


@pytest.mark.asyncio
async def test_evaluate_opportunity_short(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "ETHUSDT",
            "direction": "SHORT",
            "entry_price": "3500.0",
        }
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "ETHUSDT"
    assert data["direction"] == "SHORT"


@pytest.mark.asyncio
async def test_evaluate_opportunity_invalid_direction(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "BTCUSDT",
            "direction": "INVALID",
            "entry_price": "65000.0",
        }
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_evaluate_opportunity_missing_params(client):
    resp = await client.get("/api/ai/evaluate")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_evaluate_opportunity_has_summary(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": "65000.0",
        }
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "summary" in data
    assert len(data["summary"]) > 0
    assert "recommendation" in data
    assert "risk_level" in data
    assert "conviction" in data
