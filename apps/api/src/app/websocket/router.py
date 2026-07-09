"""WebSocket 路由 /api/ws。

协议：
1. 客户端连接时通过 query param ?token=xxx 传递鉴权 token（P1-9）
2. 服务端校验 Origin 头是否在 CORS 允许列表内（P1-10）
3. 客户端发送订阅消息：{"action": "subscribe", "channel": "system"}
4. 取消订阅：{"action": "unsubscribe", "channel": "ticker.BTCUSDT"}
5. 心跳：客户端发送 {"action": "ping"}，服务端返回 {"channel":"_meta","type":"pong"}
6. 服务端主动 ping（P1-11），客户端收到后应发送 {"action": "pong"} 更新存活时间
7. 服务端推送：{"channel":"system","type":"status_update","data":{...},"timestamp":"..."}

支持频道：system, ticker.{SYMBOL}, orderbook.{SYMBOL}, plans, journals, auto-plans
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import settings
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_CHANNELS = {"system", "plans", "journals", "auto-plans"}
VALID_PREFIXES = ("ticker.", "orderbook.")


def _is_valid_channel(channel: str) -> bool:
    if channel in VALID_CHANNELS:
        return True
    return any(channel.startswith(p) for p in VALID_PREFIXES)


def _is_origin_allowed(origin: str | None) -> bool:
    """P1-10: 校验 WebSocket 握手的 Origin 头。

    无 Origin（非浏览器客户端）或 Origin 在 CORS 允许列表内则通过。
    """
    if not origin:
        # 非浏览器客户端（如 Python websockets 库）无 Origin 头，允许通过
        # 生产环境如需严格校验可改为 return False
        return True
    # 允许 localhost 的各种端口（开发环境）
    parsed = urlparse(origin)
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1"):
        return True
    # 校验是否在 CORS 允许列表内
    return origin in settings.cors_origins


def _validate_token(token: str | None) -> bool:
    """P1-9: 校验 WebSocket 连接 token。

    v0.2 阶段无完整 auth 体系，使用简单 token 校验：
    - 如果 settings.ws_token 未设置，允许所有连接（开发模式）
    - 如果 settings.ws_token 已设置，要求 token 匹配
    """
    ws_token = getattr(settings, "ws_token", None)
    if not ws_token:
        # 开发模式：未配置 token 则允许所有连接
        return True
    return token == ws_token


@router.websocket("/api/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    # P1-10: Origin 校验
    origin = ws.headers.get("origin")
    if not _is_origin_allowed(origin):
        logger.warning("WS rejected: origin not allowed: %s", origin)
        await ws.close(code=4403, reason="Origin not allowed")
        return

    # P1-9: Token 鉴权
    if not _validate_token(token):
        logger.warning("WS rejected: invalid or missing token")
        await ws.close(code=4401, reason="Unauthorized")
        return

    client = await ws_manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_json()
            # 收到任何消息都更新 last_seen（P1-11 心跳超时检测）
            client.touch()
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

            if action == "pong":
                # 客户端响应服务端 ping，已通过 touch() 更新 last_seen
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
