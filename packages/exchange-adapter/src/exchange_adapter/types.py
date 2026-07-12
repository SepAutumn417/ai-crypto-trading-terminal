from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class KlineInterval(str, Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


class Kline(BaseModel):
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    quote_volume: Decimal | None = None


class OrderbookLevel(BaseModel):
    price: Decimal
    quantity: Decimal


class Orderbook(BaseModel):
    symbol: str
    bids: list[OrderbookLevel]
    asks: list[OrderbookLevel]
    timestamp: datetime | None = None


class Ticker(BaseModel):
    symbol: str
    last_price: Decimal
    mark_price: Decimal | None = None
    index_price: Decimal | None = None
    high_24h: Decimal | None = None
    low_24h: Decimal | None = None
    volume_24h: Decimal | None = None
    change_percent_24h: Decimal | None = None
    timestamp: datetime | None = None


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"


class OrderStatus(str, Enum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class Order(BaseModel):
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    status: OrderStatus
    price: Decimal | None = None
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Decimal | None = None
    stop_price: Decimal | None = None
    take_profit_price: Decimal | None = None
    stop_loss_price: Decimal | None = None
    client_order_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Position(BaseModel):
    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_percent: Decimal | None = None
    leverage: Decimal
    margin_type: str
    liquidation_price: Decimal | None = None
    margin: Decimal | None = None
    updated_at: datetime | None = None


class Balance(BaseModel):
    asset: str
    available: Decimal
    total: Decimal
    unrealized_pnl: Decimal | None = None
    margin_balance: Decimal | None = None
    equity: Decimal | None = None
