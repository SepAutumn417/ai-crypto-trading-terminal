"""WebSocket 连接管理器。

职责：
1. 维护活跃客户端连接（每个连接订阅多个频道）
2. 提供 broadcast(channel, payload) 给业务层在状态变更后触发推送
3. 后台任务定时推送 ticker（基于 Mock 数据，避免真实交易所压力）

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
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WSClient:
    """单个 WebSocket 客户端连接 + 订阅频道集合。"""

    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.subscriptions: set[str] = set()

    async def send_json(self, payload: dict[str, Any]) -> None:
        try:
            await self.ws.send_json(payload)
        except Exception:
            # 连接已关闭或发送失败，由 accept_loop 捕获并清理
            logger.debug("WSClient send failed", exc_info=True)
            raise


class ConnectionManager:
    """全局 WebSocket 连接管理器（单例）。

    线程安全：FastAPI 在事件循环中调用，所有方法均为 async / 协程内同步操作。
    """

    def __init__(self) -> None:
        self._clients: list[WSClient] = []
        self._ticker_task: asyncio.Task | None = None
        self._ticker_symbols: set[str] = set()

    # ---------- 连接生命周期 ----------

    async def connect(self, ws: WebSocket) -> WSClient:
        await ws.accept()
        client = WSClient(ws)
        self._clients.append(client)
        logger.info("WS client connected, total=%d", len(self._clients))
        # 发送连接确认
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
        # ticker 频道需要后台任务支持
        if channel.startswith("ticker."):
            self._ticker_symbols.add(channel[len("ticker."):])
            self._ensure_ticker_task()

    def unsubscribe(self, client: WSClient, channel: str) -> None:
        client.subscriptions.discard(channel)
        # 清理无人订阅的 ticker symbol
        if channel.startswith("ticker."):
            ticker_channel = channel  # 如 ticker.BTCUSDT
            if not any(ticker_channel in c.subscriptions for c in self._clients):
                symbol = channel[len("ticker."):]
                self._ticker_symbols.discard(symbol)

    # ---------- 广播 ----------

    async def broadcast(self, channel: str, msg_type: str, data: Any) -> None:
        """向所有订阅了 channel 的客户端推送消息。"""
        if not self._clients:
            return
        payload = {
            "channel": channel,
            "type": msg_type,
            "data": data,
            "timestamp": _now_iso(),
        }
        dead: list[WSClient] = []
        for client in self._clients:
            if channel in client.subscriptions:
                try:
                    await client.send_json(payload)
                except Exception:
                    dead.append(client)
        for c in dead:
            self.disconnect(c)

    # ---------- 后台 ticker 推送 ----------

    def _ensure_ticker_task(self) -> None:
        if self._ticker_task is None or self._ticker_task.done():
            self._ticker_task = asyncio.create_task(self._ticker_loop())

    async def _ticker_loop(self) -> None:
        """定时推送 ticker（Mock 模式下生成随机波动，避免真实交易所压力）。

        生产环境可替换为订阅交易所 WebSocket 推送。
        """
        logger.info("WS ticker loop started")
        # 基础价格表
        base_prices: dict[str, Decimal] = {
            "BTCUSDT": Decimal("65000"),
            "ETHUSDT": Decimal("3500"),
            "SOLUSDT": Decimal("150"),
            "BNBUSDT": Decimal("600"),
            "XRPUSDT": Decimal("0.62"),
        }
        try:
            while self._clients and self._ticker_symbols:
                for symbol in list(self._ticker_symbols):
                    base = base_prices.get(symbol, Decimal("100"))
                    # 模拟 ±0.5% 波动
                    delta = (Decimal(str(random.random())) - Decimal("0.5")) * base * Decimal("0.01")
                    price = base + delta
                    data = {
                        "symbol": symbol,
                        "last_price": str(price.quantize(Decimal("0.0001"))),
                        "mark_price": str((price + delta * Decimal("0.1")).quantize(Decimal("0.0001"))),
                        "timestamp": _now_iso(),
                    }
                    await self.broadcast(f"ticker.{symbol}", "ticker_update", data)
                await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            logger.info("WS ticker loop cancelled")
            raise
        except Exception:
            logger.exception("WS ticker loop error")
        finally:
            logger.info("WS ticker loop stopped")

    async def shutdown(self) -> None:
        if self._ticker_task is not None and not self._ticker_task.done():
            self._ticker_task.cancel()
            try:
                await self._ticker_task
            except asyncio.CancelledError:
                pass
            self._ticker_task = None
        # 关闭所有客户端连接
        for client in list(self._clients):
            try:
                await client.ws.close()
            except Exception:
                pass
        self._clients.clear()


# 全局单例
ws_manager = ConnectionManager()
