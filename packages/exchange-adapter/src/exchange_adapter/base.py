from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from .types import (
    Balance,
    Kline,
    KlineInterval,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Orderbook,
    Position,
    PositionSide,
    Ticker,
)


class Exchange(ABC):
    """交易所适配器抽象基类。

    所有交易所实现都必须继承此类，提供统一的接口。
    分为三大类方法：
    - 行情数据（公开，无需鉴权）
    - 账户/订单（私有，需要 API Key）
    - 订单执行（私有，需要 API Key）
    """

    @abstractmethod
    async def close(self) -> None:
        """关闭底层连接（HTTP session 等），进程退出时调用。"""
        ...

    async def __aenter__(self) -> "Exchange":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """获取指定交易对的 Ticker 行情。"""
        ...

    @abstractmethod
    async def get_klines(
        self,
        symbol: str,
        interval: KlineInterval,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[Kline]:
        """获取 K 线数据。

        Args:
            symbol: 交易对，如 BTCUSDT
            interval: K线周期
            limit: 返回数量限制
            start_time: 起始时间（可选）
            end_time: 结束时间（可选）
        """
        ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Orderbook:
        """获取订单簿深度数据。

        Args:
            symbol: 交易对
            limit: 档位数量
        """
        ...

    @abstractmethod
    async def get_balances(self) -> list[Balance]:
        """获取账户余额。"""
        ...

    @abstractmethod
    async def get_positions(self, symbol: Optional[str] = None) -> list[Position]:
        """获取持仓列表。

        Args:
            symbol: 可选，指定交易对；不传返回所有持仓
        """
        ...

    @abstractmethod
    async def get_orders(
        self,
        symbol: str,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
    ) -> list[Order]:
        """获取订单列表。

        Args:
            symbol: 交易对
            status: 可选，按状态过滤
            limit: 返回数量限制
        """
        ...

    @abstractmethod
    async def get_order(self, symbol: str, order_id: str) -> Order:
        """获取单个订单详情。"""
        ...

    @abstractmethod
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
        """提交订单。

        Args:
            symbol: 交易对
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 限价单价格
            stop_price: 止损触发价
            take_profit_price: 止盈价
            stop_loss_price: 止损价
            client_order_id: 客户端自定义订单 ID
        """
        ...

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Order:
        """撤销订单。"""
        ...

    @abstractmethod
    async def cancel_all_orders(self, symbol: str) -> list[Order]:
        """撤销指定交易对的所有未成交订单。"""
        ...

    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int) -> None:
        """设置杠杆倍数。"""
        ...

    @abstractmethod
    async def set_margin_mode(self, symbol: str, margin_mode: str) -> None:
        """设置保证金模式（isolated / cross）。"""
        ...
