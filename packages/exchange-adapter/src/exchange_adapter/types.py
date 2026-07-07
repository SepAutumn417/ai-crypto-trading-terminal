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
    quote_volume: Optional[Decimal] = None


class OrderbookLevel(BaseModel):
    price: Decimal
    quantity: Decimal


class Orderbook(BaseModel):
    symbol: str
    bids: list[OrderbookLevel]
    asks: list[OrderbookLevel]
    timestamp: Optional[datetime] = None


class Ticker(BaseModel):
    symbol: str
    last_price: Decimal
    mark_price: Optional[Decimal] = None
    index_price: Optional[Decimal] = None
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    change_percent_24h: Optional[Decimal] = None
    timestamp: Optional[datetime] = None


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
    price: Optional[Decimal] = None
    quantity: Decimal
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    stop_loss_price: Optional[Decimal] = None
    client_order_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Position(BaseModel):
    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_percent: Optional[Decimal] = None
    leverage: Decimal
    margin_type: str
    liquidation_price: Optional[Decimal] = None
    margin: Optional[Decimal] = None
    updated_at: Optional[datetime] = None


class Balance(BaseModel):
    asset: str
    available: Decimal
    total: Decimal
    unrealized_pnl: Optional[Decimal] = None
    margin_balance: Optional[Decimal] = None
    equity: Optional[Decimal] = None
