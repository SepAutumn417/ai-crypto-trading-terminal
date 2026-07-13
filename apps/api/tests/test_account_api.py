from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import account_sync_service
from exchange_adapter import Balance, Order, OrderSide, OrderStatus, OrderType, Position, PositionSide


@pytest.mark.asyncio
async def test_account_snapshot_returns_read_only_exchange_data(client):
    fake_exchange = MagicMock()
    fake_exchange.get_balances = AsyncMock(return_value=[Balance(
        asset="USDT", available=Decimal("1200"), total=Decimal("1500"), equity=Decimal("1490"),
    )])
    fake_exchange.get_positions = AsyncMock(return_value=[Position(
        symbol="BTCUSDT", side=PositionSide.LONG, quantity=Decimal("0.01"),
        entry_price=Decimal("62000"), leverage=Decimal("5"), margin_type="isolated",
    )])
    fake_exchange.get_orders = AsyncMock(return_value=[Order(
        id="order-1", symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.LIMIT,
        status=OrderStatus.NEW, price=Decimal("62000"), quantity=Decimal("0.01"),
    )])

    with patch.object(account_sync_service, "_get_exchange", return_value=fake_exchange):
        response = await client.get("/api/account/snapshot", params={"symbol": "btcusdt", "order_limit": 10})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["balances"][0]["equity"] == "1490"
    assert data["positions"][0]["side"] == "long"
    assert data["orders"][0]["status"] == "new"
    fake_exchange.get_orders.assert_awaited_once_with(symbol="BTCUSDT", limit=10)
    assert "place_order" not in fake_exchange._mock_children


@pytest.mark.asyncio
async def test_account_snapshot_reports_sync_failure(client):
    fake_exchange = MagicMock()
    fake_exchange.get_balances = AsyncMock(side_effect=ConnectionError("network down"))
    fake_exchange.get_positions = AsyncMock(return_value=[])
    fake_exchange.get_orders = AsyncMock(return_value=[])

    with patch.object(account_sync_service, "_get_exchange", return_value=fake_exchange):
        response = await client.get("/api/account/snapshot")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ACCOUNT_SYNC_FAILED"
