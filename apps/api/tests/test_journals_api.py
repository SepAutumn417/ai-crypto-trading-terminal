from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_create_journal(client):
    resp = await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": "65000.0",
        "quantity": "0.1",
        "leverage": "10",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["direction"] == "LONG"
    assert Decimal(data["entry_price"]) == Decimal("65000.0")
    assert data["status"] == "OPEN"


@pytest.mark.asyncio
async def test_get_journal(client):
    create_resp = await client.post("/api/journals", json={
        "symbol": "ETHUSDT",
        "direction": "SHORT",
        "entry_price": "3500.0",
        "quantity": "1.0",
        "leverage": "5",
    })
    journal_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/journals/{journal_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "ETHUSDT"
    assert data["direction"] == "SHORT"


@pytest.mark.asyncio
async def test_get_journal_not_found(client):
    resp = await client.get("/api/journals/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_journals(client):
    for i in range(3):
        await client.post("/api/journals", json={
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": str(65000 + i * 100),
            "quantity": "0.1",
            "leverage": "10",
        })

    resp = await client.get("/api/journals?page_size=2")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_list_journals_with_symbol_filter(client):
    await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": "65000.0",
        "quantity": "0.1",
        "leverage": "10",
    })
    await client.post("/api/journals", json={
        "symbol": "ETHUSDT",
        "direction": "SHORT",
        "entry_price": "3500.0",
        "quantity": "1.0",
        "leverage": "5",
    })

    resp = await client.get("/api/journals?symbol=BTCUSDT")
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_update_journal(client):
    create_resp = await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": "65000.0",
        "quantity": "0.1",
        "leverage": "10",
    })
    journal_id = create_resp.json()["data"]["id"]

    resp = await client.put(f"/api/journals/{journal_id}", json={
        "exit_price": "66000.0",
        "pnl": "100.0",
        "pnl_percent": "1.54",
        "status": "CLOSED",
        "exit_reason": "Take profit hit",
        "lessons_learned": "Good entry",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["exit_price"] == "66000.0"
    assert data["pnl"] == "100.0"
    assert data["status"] == "CLOSED"
    assert data["exit_reason"] == "Take profit hit"


@pytest.mark.asyncio
async def test_delete_journal(client):
    create_resp = await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": "65000.0",
        "quantity": "0.1",
        "leverage": "10",
    })
    journal_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/journals/{journal_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True

    resp = await client.get(f"/api/journals/{journal_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_summary(client):
    await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": "65000.0",
        "exit_price": "66000.0",
        "quantity": "0.1",
        "leverage": "10",
        "pnl": "100.0",
        "pnl_percent": "1.54",
        "status": "CLOSED",
    })
    await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "SHORT",
        "entry_price": "66000.0",
        "exit_price": "65500.0",
        "quantity": "0.1",
        "leverage": "10",
        "pnl": "50.0",
        "pnl_percent": "0.76",
        "status": "CLOSED",
    })
    await client.post("/api/journals", json={
        "symbol": "ETHUSDT",
        "direction": "LONG",
        "entry_price": "3500.0",
        "quantity": "1.0",
        "leverage": "5",
        "status": "OPEN",
    })

    resp = await client.get("/api/journals/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_trades"] == 2
    assert data["winning_trades"] == 2
    assert data["losing_trades"] == 0
    assert Decimal(data["total_pnl"]) == Decimal("150.0")
