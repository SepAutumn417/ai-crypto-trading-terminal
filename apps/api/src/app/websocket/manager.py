"""WebSocket 连接管理器。

职责：
1. 维护活跃客户端连接（每个连接订阅多个频道）
2. 提供 broadcast(channel, payload) 给业务层在状态变更后触发推送
3. 后台任务定时推送 ticker（Mock 模式 / Exchange 模式，通过 TickerProvider 抽象切换）
4. 服务端主动心跳（P1-11），检测半开 TCP 连接并清理

频道命名约定：
- system: 系统状态变更（kill_switch / execution_mode）
- ticker.{SYMBOL}: 行情推送
- orderbook.{SYMBOL}: 订单簿更新
- plans: 交易计划状态变更
- journals: 交易日志变更

消息格式（JSON）：
{
  "channel": "system",
  "type": "status_update",
  "data": {...},
  "timestamp": "2026-07-08T12:00:00+00:00"
}
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# P1-16: TickerProvider 抽象，支持 Mock / Exchange 两种实现切换
class TickerProvider(Protocol):
    """行情数据提供者接口。"""

    async def get_ticker_data(self, symbol: str) -> dict[str, Any]:
        """返回 ticker 数据 dict，包含 symbol/last_price/mark_price/timestamp。"""
        ...


class MockTickerProvider:
    """Mock 行情提供者，生成随机波动数据。"""

    def __init__(self) -> None:
        self._base_prices: dict[str, Decimal] = {
            "BTCUSDT": Decimal("65000"),
            "ETHUSDT": Decimal("3500"),
            "SOLUSDT": Decimal("150"),
            "BNBUSDT": Decimal("600"),
            "XRPUSDT": Decimal("0.62"),
        }

    async def get_ticker_data(self, symbol: str) -> dict[str, Any]:
        base = self._base_prices.get(symbol, Decimal("100"))
        delta = (Decimal(str(random.random())) - Decimal("0.5")) * base * Decimal("0.01")
        price = base + delta
        return {
            "symbol": symbol,
            "last_price": str(price.quantize(Decimal("0.0001"))),
            "mark_price": str((price + delta * Decimal("0.1")).quantize(Decimal("0.0001"))),
            "timestamp": _now_iso(),
        }


class WSClient:
    """单个 WebSocket 客户端连接 + 订阅频道集合。"""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.subscriptions: set[str] = set()
        self.last_seen: float = asyncio.get_event_loop().time()

    def touch(self) -> None:
        self.last_seen = asyncio.get_event_loop().time()

    async def send_json(self, payload: dict[str, Any]) -> None:
        try:
            await self.ws.send_json(payload)
        except Exception:
            logger.debug("WSClient send failed", exc_info=True)
            raise


class ConnectionManager:
    """全局 WebSocket 连接管理器（单例）。

    线程安全：FastAPI 在事件循环中调用，所有方法均为 async / 协程内同步操作。
    """

    HEARTBEAT_INTERVAL = 30.0  # P1-11: 心跳间隔
    CLIENT_TIMEOUT = 90.0  # P1-11: 客户端超时（3 次心跳周期无响应）

    def __init__(self, ticker_provider: TickerProvider | None = None) -> None:
        self._clients: list[WSClient] = []
        self._ticker_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._ticker_symbols: set[str] = set()
        # P1-16: 通过依赖注入切换 Mock / Exchange 行情源
        self._ticker_provider: TickerProvider = ticker_provider or MockTickerProvider()

    # ---------- 连接生命周期 ----------

    async def connect(self, ws: WebSocket) -> WSClient:
        await ws.accept()
        client = WSClient(ws)
        self._clients.append(client)
        logger.info("WS client connected, total=%d", len(self._clients))
        self._ensure_heartbeat_task()
        await client.send_json({
            "channel": "_meta",
            "type": "connected",
            "data": {"message": "WebSocket connected"},
            "timestamp": _now_iso(),
        })
        return client

    def disconnect(self, client: WSClient) -> None:
        if client in self._clients:
            self._clients.remove(client)
        logger.info("WS client disconnected, total=%d", len(self._clients))

    # ---------- 订阅管理 ----------

    def subscribe(self, client: WSClient, channel: str) -> None:
        client.subscriptions.add(channel)
        if channel.startswith("ticker."):
            self._ticker_symbols.add(channel[len("ticker."):])
            self._ensure_ticker_task()

    def unsubscribe(self, client: WSClient, channel: str) -> None:
        client.subscriptions.discard(channel)
        if channel.startswith("ticker."):
            ticker_channel = channel
            if not any(ticker_channel in c.subscriptions for c in self._clients):
                symbol = channel[len("ticker."):]
                self._ticker_symbols.discard(symbol)

    # ---------- 广播 ----------

    async def broadcast(self, channel: str, msg_type: str, data: Any) -> None:
        """向所有订阅了 channel 的客户端推送消息。

        P1-12: 使用 list() 快照迭代，避免 await 期间 disconnect 修改 _clients 导致跳过
        P1-13: 使用 asyncio.gather 并行发送，避免慢客户端阻塞其他订阅者
        """
        if not self._clients:
            return
        payload = {
            "channel": channel,
            "type": msg_type,
            "data": data,
            "timestamp": _now_iso(),
        }
        # P1-12: 快照迭代，避免并发修改
        subscribers = [c for c in list(self._clients) if channel in c.subscriptions]
        if not subscribers:
            return
        # P1-13: 并行发送，return_exceptions 避免单个失败影响其他
        results = await asyncio.gather(
            *[c.send_json(payload) for c in subscribers],
            return_exceptions=True,
        )
        # 清理失败的客户端
        for client, result in zip(subscribers, results):
            if isinstance(result, Exception):
                self.disconnect(client)

    # ---------- 后台 ticker 推送 ----------

    def _ensure_ticker_task(self) -> None:
        if self._ticker_task is None or self._ticker_task.done():
            self._ticker_task = asyncio.create_task(self._ticker_loop())

    async def _ticker_loop(self) -> None:
        """定时推送 ticker，使用 TickerProvider 抽象支持 Mock / Exchange 切换。"""
        logger.info("WS ticker loop started, provider=%s", type(self._ticker_provider).__name__)
        try:
            while self._clients and self._ticker_symbols:
                for symbol in list(self._ticker_symbols):
                    try:
                        data = await self._ticker_provider.get_ticker_data(symbol)
                        await self.broadcast(f"ticker.{symbol}", "ticker_update", data)
                    except Exception:
                        logger.debug("ticker provider failed for %s", symbol, exc_info=True)
                await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            logger.info("WS ticker loop cancelled")
            raise
        except Exception:
            logger.exception("WS ticker loop error")
        finally:
            logger.info("WS ticker loop stopped")

    # ---------- P1-11: 服务端心跳 ----------

    def _ensure_heartbeat_task(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        """定时向所有客户端发送 ping，超时未响应的客户端被清理。"""
        logger.info("WS heartbeat loop started")
        try:
            while self._clients:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                now = asyncio.get_event_loop().time()
                # 检查超时客户端
                timed_out = [c for c in list(self._clients) if now - c.last_seen > self.CLIENT_TIMEOUT]
                for c in timed_out:
                    logger.info("WS client timed out (no heartbeat response), disconnecting")
                    try:
                        await c.ws.close(code=1001, reason="heartbeat timeout")
                    except Exception:
                        pass
                    self.disconnect(c)
                # 向存活客户端发送 ping
                alive = [c for c in list(self._clients) if c not in timed_out]
                if alive:
                    ping_payload = {
                        "channel": "_meta",
                        "type": "ping",
                        "data": None,
                        "timestamp": _now_iso(),
                    }
                    results = await asyncio.gather(
                        *[c.send_json(ping_payload) for c in alive],
                        return_exceptions=True,
                    )
                    for client, result in zip(alive, results):
                        if isinstance(result, Exception):
                            self.disconnect(client)
        except asyncio.CancelledError:
            logger.info("WS heartbeat loop cancelled")
            raise
        except Exception:
            logger.exception("WS heartbeat loop error")
        finally:
            logger.info("WS heartbeat loop stopped")

    async def shutdown(self) -> None:
        for task in (self._ticker_task, self._heartbeat_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._ticker_task = None
        self._heartbeat_task = None
        for client in list(self._clients):
            try:
                await client.ws.close()
            except Exception:
                pass
        self._clients.clear()


# 全局单例
ws_manager = ConnectionManager()
