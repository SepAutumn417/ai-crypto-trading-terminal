import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from exchange_adapter import BitgetExchange, KlineInterval, OrderSide, OrderType, OrderStatus


@pytest.fixture
def exchange():
    return BitgetExchange(
        api_key="test_key",
        api_secret="test_secret",
        passphrase="test_pass",
    )


def _mock_response(data):
    return {"code": "00000", "msg": "success", "data": data}


@pytest.mark.asyncio
async def test_get_ticker_parses_correctly(exchange):
    mock_data = {
        "symbol": "BTCUSDT",
        "lastPr": "65000.5",
        "markPrice": "65010.0",
        "indexPrice": "64990.0",
        "high24h": "66000",
        "low24h": "64000",
        "baseVolume": "1234.5",
        "changePercent": "2.5",
        "ts": "1700000000000",
    }
    exchange._request = AsyncMock(return_value=mock_data)

    ticker = await exchange.get_ticker("BTCUSDT")
    assert ticker.symbol == "BTCUSDT"
    assert ticker.last_price == Decimal("65000.5")
    assert ticker.mark_price == Decimal("65010.0")
    assert ticker.high_24h == Decimal("66000")
    assert ticker.low_24h == Decimal("64000")
    assert ticker.change_percent_24h == Decimal("2.5")
    assert ticker.timestamp == datetime.fromtimestamp(1700000000, tz=timezone.utc)


@pytest.mark.asyncio
async def test_get_klines_parses_correctly(exchange):
    mock_data = [
        ["1700000000000", "65000", "66000", "64000", "65500", "100.5", "6550000"],
        ["1700003600000", "65500", "67000", "65000", "66500", "200.3", "13300000"],
    ]
    exchange._request = AsyncMock(return_value=mock_data)

    klines = await exchange.get_klines("BTCUSDT", KlineInterval.ONE_HOUR, limit=2)
    assert len(klines) == 2
    k = klines[0]
    assert k.open == Decimal("65000")
    assert k.high == Decimal("66000")
    assert k.low == Decimal("64000")
    assert k.close == Decimal("65500")
    assert k.volume == Decimal("100.5")
    assert klines[0].timestamp < klines[1].timestamp


@pytest.mark.asyncio
async def test_get_orderbook_parses_correctly(exchange):
    mock_data = {
        "bids": [["64900.5", "1.5"], ["64900.0", "2.0"]],
        "asks": [["65000.0", "1.2"], ["65000.5", "0.8"]],
        "ts": "1700000000000",
    }
    exchange._request = AsyncMock(return_value=mock_data)

    ob = await exchange.get_orderbook("BTCUSDT", limit=2)
    assert ob.symbol == "BTCUSDT"
    assert len(ob.bids) == 2
    assert len(ob.asks) == 2
    assert ob.bids[0].price == Decimal("64900.5")
    assert ob.bids[0].quantity == Decimal("1.5")
    assert ob.asks[0].price == Decimal("65000.0")
    assert ob.asks[0].quantity == Decimal("1.2")


@pytest.mark.asyncio
async def test_request_error_handling(exchange):
    """验证 _request 方法对非 00000 错误码抛 ValueError。"""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "40001", "msg": "Invalid symbol", "data": {}})

    exchange._transport = httpx.MockTransport(handler)

    with pytest.raises(ValueError, match="Bitget API error"):
        await exchange.get_ticker("INVALID")

    await exchange.close()


@pytest.mark.asyncio
async def test_get_balances(exchange):
    mock_data = [
        {
            "marginCoin": "USDT",
            "available": "10000.5",
            "equity": "10500.0",
            "unrealizedPL": "500.0",
            "marginBalance": "10500.0",
        }
    ]
    exchange._request = AsyncMock(return_value=mock_data)

    balances = await exchange.get_balances()
    assert len(balances) == 1
    assert balances[0].asset == "USDT"
    assert balances[0].available == Decimal("10000.5")
    assert balances[0].total == Decimal("10500.0")
    assert balances[0].unrealized_pnl == Decimal("500.0")


@pytest.mark.asyncio
async def test_get_positions(exchange):
    mock_data = [
        {
            "symbol": "BTCUSDT",
            "holdSide": "long",
            "total": "0.1",
            "averageOpenPrice": "65000.0",
            "markPrice": "65500.0",
            "unrealizedPL": "50.0",
            "unrealizedPLR": "0.077",
            "leverage": "10",
            "marginMode": "isolated",
            "liquidationPrice": "60000.0",
            "margin": "650.0",
            "uTime": "1700000000000",
        }
    ]
    exchange._request = AsyncMock(return_value=mock_data)

    positions = await exchange.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BTCUSDT"
    assert positions[0].quantity == Decimal("0.1")
    assert positions[0].entry_price == Decimal("65000.0")
    assert positions[0].leverage == Decimal("10")


@pytest.mark.asyncio
async def test_get_orders(exchange):
    mock_data = {
        "orderList": [
            {
                "orderId": "12345",
                "symbol": "BTCUSDT",
                "side": "buy",
                "orderType": "limit",
                "state": "filled",
                "price": "65000.0",
                "size": "0.1",
                "baseVolume": "0.1",
                "priceAvg": "65000.0",
                "cTime": "1700000000000",
                "uTime": "1700003600000",
            }
        ]
    }
    exchange._request = AsyncMock(return_value=mock_data)

    orders = await exchange.get_orders("BTCUSDT", status=OrderStatus.FILLED)
    assert len(orders) == 1
    assert orders[0].id == "12345"
    assert orders[0].status == OrderStatus.FILLED
    assert orders[0].side == OrderSide.BUY


@pytest.mark.asyncio
async def test_place_order(exchange):
    place_response = {"orderId": "67890"}
    order_detail = {
        "orderId": "67890",
        "symbol": "BTCUSDT",
        "side": "buy",
        "orderType": "limit",
        "state": "live",
        "price": "65000.0",
        "size": "0.01",
        "baseVolume": "0",
        "cTime": "1700000000000",
        "uTime": "1700000000000",
    }

    call_count = 0

    async def mock_request(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return place_response
        return order_detail

    exchange._request = mock_request

    order = await exchange.place_order(
        "BTCUSDT",
        OrderSide.BUY,
        OrderType.LIMIT,
        Decimal("0.01"),
        price=Decimal("65000.0"),
    )
    assert order.id == "67890"
    assert order.side == OrderSide.BUY
    assert order.type == OrderType.LIMIT
    assert order.status == OrderStatus.NEW


@pytest.mark.asyncio
async def test_cancel_order(exchange):
    mock_data = {"orderId": "67890"}
    exchange._request = AsyncMock(return_value=mock_data)

    order = await exchange.cancel_order("BTCUSDT", "67890")
    assert order.id == "67890"
    assert order.status == OrderStatus.CANCELED


@pytest.mark.asyncio
async def test_cancel_all_orders(exchange):
    mock_data = {"orderIds": ["111", "222", "333"]}
    exchange._request = AsyncMock(return_value=mock_data)

    orders = await exchange.cancel_all_orders("BTCUSDT")
    assert len(orders) == 3
    assert all(o.status == OrderStatus.CANCELED for o in orders)


@pytest.mark.asyncio
async def test_set_leverage(exchange):
    exchange._request = AsyncMock(return_value={})
    await exchange.set_leverage("BTCUSDT", 10)
    exchange._request.assert_called_once()


@pytest.mark.asyncio
async def test_set_margin_mode(exchange):
    exchange._request = AsyncMock(return_value={})
    await exchange.set_margin_mode("BTCUSDT", "isolated")
    exchange._request.assert_called_once()


@pytest.mark.asyncio
async def test_interval_mapping():
    from exchange_adapter.bitget_exchange import INTERVAL_MAP
    assert INTERVAL_MAP[KlineInterval.ONE_MINUTE] == "1m"
    assert INTERVAL_MAP[KlineInterval.ONE_HOUR] == "1H"
    assert INTERVAL_MAP[KlineInterval.ONE_DAY] == "1D"
    assert INTERVAL_MAP[KlineInterval.ONE_WEEK] == "1W"


@pytest.mark.asyncio
async def test_sign_generates_valid_signature(exchange):
    timestamp = "1700000000000"
    signature = await exchange._sign(timestamp, "GET", "/api/v2/mix/account/accounts")
    assert isinstance(signature, str)
    assert len(signature) > 0


@pytest.mark.asyncio
async def test_private_requires_credentials():
    exchange_no_key = BitgetExchange()
    with pytest.raises(ValueError, match="API key and passphrase"):
        await exchange_no_key.get_balances()
