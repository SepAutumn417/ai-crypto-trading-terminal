from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

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

if TYPE_CHECKING:
    import aiohttp


INTERVAL_MAP = {
    KlineInterval.ONE_MINUTE: "1m",
    KlineInterval.FIVE_MINUTES: "5m",
    KlineInterval.FIFTEEN_MINUTES: "15m",
    KlineInterval.THIRTY_MINUTES: "30m",
    KlineInterval.ONE_HOUR: "1H",
    KlineInterval.FOUR_HOURS: "4H",
    KlineInterval.SIX_HOURS: "6H",
    KlineInterval.TWELVE_HOURS: "12H",
    KlineInterval.ONE_DAY: "1D",
    KlineInterval.ONE_WEEK: "1W",
}


class BitgetExchange(Exchange):
    """Bitget USDT-M 合约交易所适配器。

    公开行情接口无需 API Key；私有接口需要 api_key + api_secret + passphrase。
    """

    BASE_URL = "https://api.bitget.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.base_url = base_url or self.BASE_URL
        self._session = None

    async def _get_session(self) -> "aiohttp.ClientSession":
        if self._session is None:
            try:
                import aiohttp
            except ImportError:
                raise ImportError("aiohttp is required for BitgetExchange. Install it with: pip install aiohttp")
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, path: str, params: Optional[dict] = None, body: Optional[dict] = None) -> dict:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        async with session.request(method, url, params=params, json=body) as resp:
            data = await resp.json()
            if data.get("code") != "00000":
                raise ValueError(f"Bitget API error: {data.get('msg', data)}")
            return data.get("data", {})

    async def get_ticker(self, symbol: str) -> Ticker:
        data = await self._request("GET", "/api/v2/mix/market/ticker", params={"symbol": symbol, "productType": "usdt-futures"})
        return Ticker(
            symbol=symbol,
            last_price=Decimal(str(data["lastPr"])),
            mark_price=Decimal(str(data["markPrice"])) if data.get("markPrice") else None,
            index_price=Decimal(str(data["indexPrice"])) if data.get("indexPrice") else None,
            high_24h=Decimal(str(data["high24h"])) if data.get("high24h") else None,
            low_24h=Decimal(str(data["low24h"])) if data.get("low24h") else None,
            volume_24h=Decimal(str(data["baseVolume"])) if data.get("baseVolume") else None,
            change_percent_24h=Decimal(str(data["changePercent"])) if data.get("changePercent") else None,
            timestamp=datetime.fromtimestamp(int(data["ts"]) / 1000, tz=timezone.utc) if data.get("ts") else None,
        )

    async def get_klines(
        self,
        symbol: str,
        interval: KlineInterval,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[Kline]:
        params = {
            "symbol": symbol,
            "granularity": INTERVAL_MAP.get(interval, "1H"),
            "limit": str(limit),
            "productType": "usdt-futures",
        }
        if start_time:
            params["startTime"] = str(int(start_time.timestamp() * 1000))
        if end_time:
            params["endTime"] = str(int(end_time.timestamp() * 1000))

        data = await self._request("GET", "/api/v2/mix/market/candles", params=params)
        klines: list[Kline] = []
        for item in data:
            ts_ms = int(item[0])
            klines.append(Kline(
                timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                volume=Decimal(str(item[5])) if len(item) > 5 else Decimal("0"),
                quote_volume=Decimal(str(item[6])) if len(item) > 6 else None,
            ))
        klines.sort(key=lambda k: k.timestamp)
        return klines

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Orderbook:
        data = await self._request(
            "GET", "/api/v2/mix/market/merge-depth",
            params={"symbol": symbol, "limit": str(limit), "precision": "scale0", "productType": "usdt-futures"},
        )
        bids = [OrderbookLevel(price=Decimal(b[0]), quantity=Decimal(b[1])) for b in data.get("bids", [])]
        asks = [OrderbookLevel(price=Decimal(a[0]), quantity=Decimal(a[1])) for a in data.get("asks", [])]
        return Orderbook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.fromtimestamp(int(data["ts"]) / 1000, tz=timezone.utc) if data.get("ts") else None,
        )

    async def get_balances(self) -> list[Balance]:
        raise NotImplementedError("Bitget private API requires API key authentication")

    async def get_positions(self, symbol: Optional[str] = None) -> list[Position]:
        raise NotImplementedError("Bitget private API requires API key authentication")

    async def get_orders(
        self,
        symbol: str,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> list[Order]:
        raise NotImplementedError("Bitget private API requires API key authentication")

    async def get_order(self, symbol: str, order_id: str) -> Order:
        raise NotImplementedError("Bitget private API requires API key authentication")

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
        raise NotImplementedError("Bitget private API requires API key authentication")

    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        raise NotImplementedError("Bitget private API requires API key authentication")

    async def cancel_all_orders(self, symbol: str) -> list[Order]:
        raise NotImplementedError("Bitget private API requires API key authentication")

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        raise NotImplementedError("Bitget private API requires API key authentication")

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> None:
        raise NotImplementedError("Bitget private API requires API key authentication")
