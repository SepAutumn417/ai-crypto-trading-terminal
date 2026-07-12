from decimal import Decimal

import pytest

from exchange_adapter import KlineInterval, MockExchange, OrderSide, OrderType


@pytest.fixture
def exchange():
    return MockExchange(base_price=Decimal("65000"))


@pytest.mark.asyncio
async def test_get_ticker(exchange):
    ticker = await exchange.get_ticker("BTCUSDT")
    assert ticker.symbol == "BTCUSDT"
    assert ticker.last_price > 0
    assert ticker.high_24h >= ticker.low_24h
    assert ticker.volume_24h > 0


@pytest.mark.asyncio
async def test_get_klines(exchange):
    klines = await exchange.get_klines("BTCUSDT", KlineInterval.ONE_HOUR, limit=50)
    assert len(klines) == 50
    for k in klines:
        assert k.open > 0
        assert k.high >= k.low
        assert k.close > 0
        assert k.volume >= 0


@pytest.mark.asyncio
async def test_get_orderbook(exchange):
    ob = await exchange.get_orderbook("BTCUSDT", limit=20)
    assert ob.symbol == "BTCUSDT"
    assert len(ob.bids) == 20
    assert len(ob.asks) == 20
    for i in range(1, 20):
        assert ob.bids[i].price < ob.bids[i-1].price
        assert ob.asks[i].price > ob.asks[i-1].price
    assert ob.bids[0].price < ob.asks[0].price


@pytest.mark.asyncio
async def test_get_balances(exchange):
    balances = await exchange.get_balances()
    assert len(balances) > 0
    usdt = next(b for b in balances if b.asset == "USDT")
    assert usdt.total >= usdt.available


@pytest.mark.asyncio
async def test_get_positions(exchange):
    positions = await exchange.get_positions("BTCUSDT")
    assert len(positions) == 1
    pos = positions[0]
    assert pos.symbol == "BTCUSDT"
    assert pos.quantity > 0
    assert pos.entry_price > 0


@pytest.mark.asyncio
async def test_place_and_get_order(exchange):
    order = await exchange.place_order(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        price=Decimal("64000"),
        client_order_id="test-001",
    )
    assert order.id.startswith("mock-")
    assert order.symbol == "BTCUSDT"
    assert order.side == OrderSide.BUY
    assert order.status.value == "new"

    fetched = await exchange.get_order("BTCUSDT", order.id)
    assert fetched.id == order.id


@pytest.mark.asyncio
async def test_cancel_order(exchange):
    order = await exchange.place_order(
        symbol="BTCUSDT",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.01"),
        price=Decimal("66000"),
    )
    canceled = await exchange.cancel_order("BTCUSDT", order.id)
    assert canceled.status.value == "canceled"


@pytest.mark.asyncio
async def test_cancel_all_orders(exchange):
    await exchange.place_order("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, Decimal("0.01"), Decimal("64000"))
    await exchange.place_order("BTCUSDT", OrderSide.SELL, OrderType.LIMIT, Decimal("0.01"), Decimal("66000"))
    canceled = await exchange.cancel_all_orders("BTCUSDT")
    assert len(canceled) == 2
    for o in canceled:
        assert o.status.value == "canceled"


@pytest.mark.asyncio
async def test_set_leverage(exchange):
    await exchange.set_leverage("BTCUSDT", 10)
    with pytest.raises(ValueError):
        await exchange.set_leverage("BTCUSDT", 200)


@pytest.mark.asyncio
async def test_set_margin_mode(exchange):
    await exchange.set_margin_mode("BTCUSDT", "isolated")
    await exchange.set_margin_mode("BTCUSDT", "cross")
    with pytest.raises(ValueError):
        await exchange.set_margin_mode("BTCUSDT", "invalid")


@pytest.mark.asyncio
async def test_get_orders_with_status_filter(exchange):
    await exchange.place_order("BTCUSDT", OrderSide.BUY, OrderType.LIMIT, Decimal("0.01"), Decimal("64000"))
    all_orders = await exchange.get_orders("BTCUSDT")
    assert len(all_orders) > 0
    new_orders = await exchange.get_orders("BTCUSDT", status=None)
    assert len(new_orders) == len(all_orders)
