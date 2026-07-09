import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from .base import Exchange
from .types import (
    Balance,
    Kline,
    KlineInterval,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Orderbook,
    OrderbookLevel,
    Position,
    PositionSide,
    Ticker,
)


class MockExchange(Exchange):
    """Mock 交易所实现，用于开发和测试。

    生成合理的模拟数据，不依赖真实网络。
    """

    def __init__(self, base_price: Decimal = Decimal("65000"), seed: int = 42):
        self._base_price = base_price
        self._rng = random.Random(seed)
        self._orders: dict[str, Order] = {}
        self._order_counter = 0

    async def close(self) -> None:
        """Mock 无网络连接，close 为 no-op。"""
        pass

    async def get_ticker(self, symbol: str) -> Ticker:
        price = self._base_price * Decimal(str(0.95 + self._rng.random() * 0.1))
        high = price * Decimal("1.02")
        low = price * Decimal("0.98")
        change = Decimal(str(self._rng.uniform(-0.05, 0.05)))
        volume = Decimal(str(self._rng.uniform(1000, 5000)))
        return Ticker(
            symbol=symbol,
            last_price=price,
            mark_price=price * Decimal("1.001"),
            index_price=price * Decimal("0.999"),
            high_24h=high,
            low_24h=low,
            volume_24h=volume,
            change_percent_24h=change * Decimal("100"),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_klines(
        self,
        symbol: str,
        interval: KlineInterval,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[Kline]:
        interval_seconds = {
            KlineInterval.ONE_MINUTE: 60,
            KlineInterval.FIVE_MINUTES: 300,
            KlineInterval.FIFTEEN_MINUTES: 900,
            KlineInterval.THIRTY_MINUTES: 1800,
            KlineInterval.ONE_HOUR: 3600,
            KlineInterval.FOUR_HOURS: 14400,
            KlineInterval.SIX_HOURS: 21600,
            KlineInterval.TWELVE_HOURS: 43200,
            KlineInterval.ONE_DAY: 86400,
            KlineInterval.ONE_WEEK: 604800,
        }
        secs = interval_seconds.get(interval, 3600)

        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(seconds=secs * limit)

        klines: list[Kline] = []
        current_price = self._base_price * Decimal("0.9")
        t = start_time
        while t <= end_time and len(klines) < limit:
            volatility = Decimal("0.005")
            change = Decimal(str(self._rng.uniform(-0.01, 0.01)))
            open_price = current_price
            close_price = open_price * (Decimal("1") + change)
            high = max(open_price, close_price) * (Decimal("1") + volatility)
            low = min(open_price, close_price) * (Decimal("1") - volatility)
            volume = Decimal(str(self._rng.uniform(10, 100)))

            klines.append(Kline(
                timestamp=t,
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=volume,
                quote_volume=volume * close_price,
            ))
            current_price = close_price
            t += timedelta(seconds=secs)

        return klines

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Orderbook:
        mid_price = self._base_price
        bids: list[OrderbookLevel] = []
        asks: list[OrderbookLevel] = []

        for i in range(limit):
            bid_price = mid_price * (Decimal("1") - Decimal("0.0001") * (i + 1))
            bid_qty = Decimal(str(self._rng.uniform(0.1, 5.0)))
            bids.append(OrderbookLevel(price=bid_price, quantity=bid_qty))

            ask_price = mid_price * (Decimal("1") + Decimal("0.0001") * (i + 1))
            ask_qty = Decimal(str(self._rng.uniform(0.1, 5.0)))
            asks.append(OrderbookLevel(price=ask_price, quantity=ask_qty))

        return Orderbook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_balances(self) -> list[Balance]:
        return [
            Balance(
                asset="USDT",
                available=Decimal("1500"),
                total=Decimal("2000"),
                unrealized_pnl=Decimal("-50"),
                margin_balance=Decimal("1950"),
                equity=Decimal("1950"),
            ),
        ]

    async def get_positions(self, symbol: Optional[str] = None) -> list[Position]:
        pos = Position(
            symbol=symbol or "BTCUSDT",
            side=PositionSide.LONG,
            quantity=Decimal("0.02"),
            entry_price=Decimal("62000"),
            mark_price=Decimal("65000"),
            unrealized_pnl=Decimal("60"),
            unrealized_pnl_percent=Decimal("4.84"),
            leverage=Decimal("10"),
            margin_type="isolated",
            liquidation_price=Decimal("56000"),
            margin=Decimal("124"),
            updated_at=datetime.now(timezone.utc),
        )
        return [pos]

    async def get_orders(
        self,
        symbol: str,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> list[Order]:
        orders = list(self._orders.values())
        if status:
            orders = [o for o in orders if o.status == status]
        return orders[:limit]

    async def get_order(self, symbol: str, order_id: str) -> Order:
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")
        return self._orders[order_id]

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        take_profit_price: Optional[Decimal] = None,
        stop_loss_price: Optional[Decimal] = None,
        client_order_id: Optional[str] = None,
    ) -> Order:
        self._order_counter += 1
        order_id = f"mock-{self._order_counter}"
        now = datetime.now(timezone.utc)
        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            type=order_type,
            status=OrderStatus.NEW,
            price=price,
            quantity=quantity,
            filled_quantity=Decimal("0"),
            average_fill_price=None,
            stop_price=stop_price,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            client_order_id=client_order_id,
            created_at=now,
            updated_at=now,
        )
        self._orders[order_id] = order
        return order

    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")
        order = self._orders[order_id]
        order.status = OrderStatus.CANCELED
        order.updated_at = datetime.now(timezone.utc)
        return order

    async def cancel_all_orders(self, symbol: str) -> list[Order]:
        canceled = []
        for order in self._orders.values():
            if order.symbol == symbol and order.status in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED):
                order.status = OrderStatus.CANCELED
                order.updated_at = datetime.now(timezone.utc)
                canceled.append(order)
        return canceled

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        if leverage < 1 or leverage > 125:
            raise ValueError(f"Invalid leverage: {leverage}")

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> None:
        # P1-1: 统一接受 cross/crossed/isolated 三种取值
        normalized = margin_mode.lower()
        if normalized not in ("isolated", "cross", "crossed"):
            raise ValueError(f"Invalid margin mode: {margin_mode}")
