import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from exchange_adapter import BitgetExchange, KlineInterval, OrderSide, OrderType


@pytest.fixture
def exchange():
    return BitgetExchange()


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
    from unittest.mock import AsyncMock, MagicMock

    mock_resp = MagicMock()
    mock_resp.json = AsyncMock(return_value={"code": "40001", "msg": "Invalid symbol", "data": {}})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.request = MagicMock(return_value=mock_resp)
    exchange._session = mock_session

    with pytest.raises(ValueError, match="Bitget API error"):
        await exchange.get_ticker("INVALID")


@pytest.mark.asyncio
async def test_private_methods_not_implemented(exchange):
    with pytest.raises(NotImplementedError):
        await exchange.get_balances()
    with pytest.raises(NotImplementedError):
        await exchange.get_positions()
    with pytest.raises(NotImplementedError):
        await exchange.place_order("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, Decimal("0.01"))


@pytest.mark.asyncio
async def test_interval_mapping():
    from exchange_adapter.bitget_exchange import INTERVAL_MAP
    assert INTERVAL_MAP[KlineInterval.ONE_MINUTE] == "1m"
    assert INTERVAL_MAP[KlineInterval.ONE_HOUR] == "1H"
    assert INTERVAL_MAP[KlineInterval.ONE_DAY] == "1D"
    assert INTERVAL_MAP[KlineInterval.ONE_WEEK] == "1W"
