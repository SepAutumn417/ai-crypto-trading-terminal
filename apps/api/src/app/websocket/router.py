"""WebSocket 路由 /api/ws。

协议：
1. 客户端连接后发送订阅消息：{"action": "subscribe", "channel": "system"}
2. 取消订阅：{"action": "unsubscribe", "channel": "ticker.BTCUSDT"}
3. 心跳：客户端发送 {"action": "ping"}，服务端返回 {"channel":"_meta","type":"pong"}
4. 服务端推送：{"channel":"system","type":"status_update","data":{...},"timestamp":"..."}

支持频道：system, ticker.{SYMBOL}, orderbook.{SYMBOL}, plans, journals
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_CHANNELS = {"system", "plans", "journals"}
VALID_PREFIXES = ("ticker.", "orderbook.")


def _is_valid_channel(channel: str) -> bool:
    if channel in VALID_CHANNELS:
        return True
    return any(channel.startswith(p) for p in VALID_PREFIXES)


@router.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    client = await ws_manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_json()
            action = msg.get("action")
            channel = msg.get("channel", "")

            if action == "ping":
                await client.send_json({
                    "channel": "_meta",
                    "type": "pong",
                    "data": None,
                    "timestamp": "",
                })
                continue

            if not _is_valid_channel(channel):
                await client.send_json({
                    "channel": "_meta",
                    "type": "error",
                    "data": {"error": f"invalid channel: {channel}"},
                    "timestamp": "",
                })
                continue

            if action == "subscribe":
                ws_manager.subscribe(client, channel)
                await client.send_json({
                    "channel": "_meta",
                    "type": "subscribed",
                    "data": {"channel": channel},
                    "timestamp": "",
                })
            elif action == "unsubscribe":
                ws_manager.unsubscribe(client, channel)
                await client.send_json({
                    "channel": "_meta",
                    "type": "unsubscribed",
                    "data": {"channel": channel},
                    "timestamp": "",
                })
            else:
                await client.send_json({
                    "channel": "_meta",
                    "type": "error",
                    "data": {"error": f"unknown action: {action}"},
                    "timestamp": "",
                })
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception:
        logger.exception("WebSocket endpoint error")
    finally:
        ws_manager.disconnect(client)
