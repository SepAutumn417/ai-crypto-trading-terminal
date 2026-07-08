from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
import hmac
import hashlib
import base64
import json
import logging

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

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
    pass


logger = logging.getLogger(__name__)


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


_MAX_CONNECTIONS = 20
_MAX_RETRIES = 3


class BitgetExchange(Exchange):
    """Bitget USDT-M 合约交易所适配器。

    公开行情接口无需 API Key；私有接口需要 api_key + api_secret + passphrase。
    使用 httpx.AsyncClient 连接池 + tenacity 重试。
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
        self._client: Optional[httpx.AsyncClient] = None
        self._transport: Optional[httpx.MockTransport] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_connections=_MAX_CONNECTIONS, max_keepalive_connections=_MAX_CONNECTIONS)
            kwargs: dict = {"limits": limits, "timeout": httpx.Timeout(30.0)}
            if self._transport is not None:
                kwargs["transport"] = self._transport
            self._client = httpx.AsyncClient(**kwargs)
            self._limits = limits
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _sign(self, timestamp: str, method: str, path: str, body: Optional[str] = None) -> str:
        if not self.api_secret:
            raise ValueError("API secret is required for private endpoints")
        message = f"{timestamp}{method.upper()}{path}{body or ''}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')

    @retry(
        stop=stop_after_attempt(_MAX_RETRIES),
        wait=wait_exponential(min=0.5, max=3),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        is_private: bool = False,
    ) -> dict:
        url = f"{self.base_url}{path}"

        headers = {"Content-Type": "application/json"}

        if is_private:
            if not self.api_key or not self.passphrase:
                raise ValueError("API key and passphrase are required for private endpoints")

            timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
            body_str = json.dumps(body, separators=(',', ':')) if body else ""
            query_string = ""
            if params:
                query_string = "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))

            sign_path = path + query_string
            signature = await self._sign(timestamp, method, sign_path, body_str if body else None)

            headers.update({
                "ACCESS-KEY": self.api_key,
                "ACCESS-SIGN": signature,
                "ACCESS-TIMESTAMP": timestamp,
                "ACCESS-PASSPHRASE": self.passphrase,
                "locale": "en-US",
            })

        client = await self._get_client()
        resp = await client.request(method, url, params=params, json=body, headers=headers)

        if resp.status_code >= 500:
            raise httpx.RemoteProtocolError(f"Bitget server error: {resp.status_code}")

        data = resp.json()
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
        data = await self._request(
            "GET", "/api/v2/mix/account/accounts",
            params={"productType": "usdt-futures"},
            is_private=True,
        )
        balances: list[Balance] = []
        if isinstance(data, list):
            for item in data:
                balances.append(Balance(
                    asset=item.get("marginCoin", "USDT"),
                    available=Decimal(str(item.get("available", "0"))),
                    total=Decimal(str(item.get("equity", "0"))),
                    unrealized_pnl=Decimal(str(item.get("unrealizedPL", "0"))) if item.get("unrealizedPL") else None,
                    margin_balance=Decimal(str(item.get("marginBalance", "0"))) if item.get("marginBalance") else None,
                    equity=Decimal(str(item.get("equity", "0"))) if item.get("equity") else None,
                ))
        return balances

    async def get_positions(self, symbol: Optional[str] = None) -> list[Position]:
        params = {"productType": "usdt-futures"}
        if symbol:
            params["symbol"] = symbol
        data = await self._request(
            "GET", "/api/v2/mix/position/all-position",
            params=params,
            is_private=True,
        )
        positions: list[Position] = []
        if isinstance(data, list):
            for item in data:
                hold_side = item.get("holdSide", "")
                side = PositionSide.LONG if hold_side == "long" else PositionSide.SHORT
                positions.append(Position(
                    symbol=item.get("symbol", ""),
                    side=side,
                    quantity=Decimal(str(item.get("total", "0"))),
                    entry_price=Decimal(str(item.get("averageOpenPrice", "0"))),
                    mark_price=Decimal(str(item.get("markPrice", "0"))) if item.get("markPrice") else None,
                    unrealized_pnl=Decimal(str(item.get("unrealizedPL", "0"))) if item.get("unrealizedPL") else None,
                    unrealized_pnl_percent=Decimal(str(item.get("unrealizedPLR", "0"))) if item.get("unrealizedPLR") else None,
                    leverage=Decimal(str(item.get("leverage", "1"))),
                    margin_type=item.get("marginMode", "isolated"),
                    liquidation_price=Decimal(str(item.get("liquidationPrice", "0"))) if item.get("liquidationPrice") else None,
                    margin=Decimal(str(item.get("margin", "0"))) if item.get("margin") else None,
                    updated_at=datetime.fromtimestamp(int(item.get("uTime", "0")) / 1000, tz=timezone.utc) if item.get("uTime") else None,
                ))
        return positions

    async def get_orders(
        self,
        symbol: str,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> list[Order]:
        if status == OrderStatus.FILLED:
            endpoint = "/api/v2/mix/order/history-orders"
        elif status in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED):
            endpoint = "/api/v2/mix/order/current"
        else:
            endpoint = "/api/v2/mix/order/history-orders"

        params = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "pageSize": str(limit),
        }
        data = await self._request("GET", endpoint, params=params, is_private=True)

        order_list = data.get("orderList", []) if isinstance(data, dict) else []
        orders: list[Order] = []
        for item in order_list:
            orders.append(self._parse_order(item))
        return orders

    async def get_order(self, symbol: str, order_id: str) -> Order:
        data = await self._request(
            "GET", "/api/v2/mix/order/detail",
            params={"symbol": symbol, "orderId": order_id, "productType": "usdt-futures"},
            is_private=True,
        )
        return self._parse_order(data)

    def _parse_order(self, item: dict) -> Order:
        state = item.get("state", "")
        status_map = {
            "filled": OrderStatus.FILLED,
            "live": OrderStatus.NEW,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "canceled": OrderStatus.CANCELED,
            "rejected": OrderStatus.REJECTED,
        }
        status = status_map.get(state, OrderStatus.NEW)

        side = OrderSide.BUY if item.get("side", "") == "buy" else OrderSide.SELL
        order_type_map = {
            "limit": OrderType.LIMIT,
            "market": OrderType.MARKET,
            "stop": OrderType.STOP,
        }
        order_type = order_type_map.get(item.get("orderType", "limit"), OrderType.LIMIT)

        return Order(
            id=item.get("orderId", ""),
            symbol=item.get("symbol", ""),
            side=side,
            type=order_type,
            status=status,
            price=Decimal(str(item.get("price", "0"))) if item.get("price") else None,
            quantity=Decimal(str(item.get("size", "0"))),
            filled_quantity=Decimal(str(item.get("baseVolume", "0"))) if item.get("baseVolume") else Decimal("0"),
            average_fill_price=Decimal(str(item.get("priceAvg", "0"))) if item.get("priceAvg") else None,
            stop_price=Decimal(str(item.get("stopPrice", "0"))) if item.get("stopPrice") else None,
            client_order_id=item.get("clientOid") or None,
            created_at=datetime.fromtimestamp(int(item.get("cTime", "0")) / 1000, tz=timezone.utc) if item.get("cTime") else None,
            updated_at=datetime.fromtimestamp(int(item.get("uTime", "0")) / 1000, tz=timezone.utc) if item.get("uTime") else None,
        )

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
        body: dict = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "side": side.value,
            "orderType": order_type.value,
            "size": str(quantity),
        }

        if price is not None:
            body["price"] = str(price)

        if client_order_id:
            body["clientOid"] = client_order_id

        if stop_price is not None:
            body["stopPrice"] = str(stop_price)

        preset_take_stop = {}
        if take_profit_price is not None:
            preset_take_stop["takeProfitPrice"] = str(take_profit_price)
        if stop_loss_price is not None:
            preset_take_stop["stopLossPrice"] = str(stop_loss_price)
        if preset_take_stop:
            body["presetTakeProfitStopLoss"] = preset_take_stop

        data = await self._request(
            "POST", "/api/v2/mix/order/place-order",
            body=body,
            is_private=True,
        )

        order_id = data.get("orderId") or client_order_id or ""
        if order_id:
            try:
                return await self.get_order(symbol, order_id)
            except Exception:
                pass

        return Order(
            id=order_id,
            symbol=symbol,
            side=side,
            type=order_type,
            status=OrderStatus.NEW,
            price=price,
            quantity=quantity,
            client_order_id=client_order_id,
        )

    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        body = {
            "symbol": symbol,
            "orderId": order_id,
            "productType": "usdt-futures",
        }
        data = await self._request(
            "POST", "/api/v2/mix/order/cancel-order",
            body=body,
            is_private=True,
        )
        return Order(
            id=data.get("orderId", order_id),
            symbol=symbol,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            status=OrderStatus.CANCELED,
            quantity=Decimal("0"),
        )

    async def cancel_all_orders(self, symbol: str) -> list[Order]:
        body = {
            "symbol": symbol,
            "productType": "usdt-futures",
        }
        data = await self._request(
            "POST", "/api/v2/mix/order/cancel-all",
            body=body,
            is_private=True,
        )
        canceled_ids = data.get("orderIds", []) if isinstance(data, dict) else []
        return [
            Order(
                id=oid,
                symbol=symbol,
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                status=OrderStatus.CANCELED,
                quantity=Decimal("0"),
            )
            for oid in canceled_ids
        ]

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        body = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "leverage": str(leverage),
            "marginCoin": "USDT",
        }
        await self._request(
            "POST", "/api/v2/mix/account/set-leverage",
            body=body,
            is_private=True,
        )

    async def set_margin_mode(self, symbol: str, margin_mode: str) -> None:
        body = {
            "symbol": symbol,
            "productType": "usdt-futures",
            "marginMode": margin_mode,
        }
        await self._request(
            "POST", "/api/v2/mix/account/set-margin-mode",
            body=body,
            is_private=True,
        )