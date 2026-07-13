from datetime import datetime, timezone
from decimal import Decimal

import pytest

from exchange_adapter import KlineInterval, MockExchange


@pytest.mark.asyncio
async def test_get_ticker(client):
    resp = await client.get("/api/market/ticker", params={"symbol": "BTCUSDT"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "BTCUSDT"
    assert "last_price" in data
    assert Decimal(data["last_price"]) > 0


@pytest.mark.asyncio
async def test_get_ticker_missing_symbol(client):
    resp = await client.get("/api/market/ticker")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_klines(client):
    resp = await client.get(
        "/api/market/klines",
        params={"symbol": "BTCUSDT", "interval": "1h", "limit": 10}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 10
    kline = data[0]
    assert "timestamp" in kline
    assert "open" in kline
    assert "high" in kline
    assert "low" in kline
    assert "close" in kline
    assert "volume" in kline


@pytest.mark.asyncio
async def test_get_klines_default_params(client):
    resp = await client.get("/api/market/klines", params={"symbol": "BTCUSDT"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 100


@pytest.mark.asyncio
async def test_get_klines_invalid_limit(client):
    resp = await client.get(
        "/api/market/klines",
        params={"symbol": "BTCUSDT", "limit": 0}
    )
    assert resp.status_code == 422

    resp = await client.get(
        "/api/market/klines",
        params={"symbol": "BTCUSDT", "limit": 1001}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_orderbook(client):
    resp = await client.get(
        "/api/market/orderbook",
        params={"symbol": "BTCUSDT", "limit": 5}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "BTCUSDT"
    assert isinstance(data["bids"], list)
    assert isinstance(data["asks"], list)
    assert len(data["bids"]) == 5
    assert len(data["asks"]) == 5
    bid = data["bids"][0]
    assert "price" in bid
    assert "quantity" in bid


@pytest.mark.asyncio
async def test_get_orderbook_default_limit(client):
    resp = await client.get("/api/market/orderbook", params={"symbol": "BTCUSDT"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["bids"]) == 20
    assert len(data["asks"]) == 20


@pytest.mark.asyncio
async def test_get_orderbook_invalid_limit(client):
    resp = await client.get(
        "/api/market/orderbook",
        params={"symbol": "BTCUSDT", "limit": 101}
    )
    assert resp.status_code == 422
