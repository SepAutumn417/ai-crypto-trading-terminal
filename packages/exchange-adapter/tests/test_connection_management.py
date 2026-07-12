"""PR-3: exchange-adapter 连接管理与重试 的单测。

TDD 纪律：先写测试看到失败，再写实现。

测试矩阵（6 条）：
1. test_close_is_idempotent — close() 调用两次不报错
2. test_retry_on_5xx — 503 → 重试后成功
3. test_no_retry_on_4xx — 400 业务错误 → 立即抛出，不重试
4. test_retry_on_network_error — httpx.ConnectError → 重试
5. test_connection_pool_config — httpx.AsyncClient 创建时带连接池 limits
6. test_aenter_aexit_context_manager — async with exchange as e 可用
"""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from exchange_adapter import BitgetExchange


def _make_exchange_with_transport(transport: httpx.MockTransport) -> BitgetExchange:
    """创建一个用 MockTransport 的 BitgetExchange，绕过真实网络。"""
    exchange = BitgetExchange(
        api_key="test_key",
        api_secret="test_secret",
        passphrase="test_pass",
    )
    exchange._transport = transport
    return exchange


@pytest.mark.asyncio
async def test_close_is_idempotent():
    """close() 调用两次不报错。"""
    exchange = BitgetExchange(api_key="k", api_secret="s", passphrase="p")
    await exchange.close()
    await exchange.close()
    assert exchange._client is None or exchange._client.is_closed


@pytest.mark.asyncio
async def test_retry_on_5xx():
    """503 → 重试 3 次后第 3 次成功返回数据。"""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503, json={"code": "50001", "msg": "service unavailable", "data": {}})
        return httpx.Response(200, json={"code": "00000", "msg": "success", "data": {"lastPr": "65000"}})

    transport = httpx.MockTransport(handler)
    exchange = _make_exchange_with_transport(transport)

    data = await exchange._request("GET", "/api/v2/mix/market/ticker", params={"symbol": "BTCUSDT", "productType": "usdt-futures"})
    assert call_count == 3
    assert data == {"lastPr": "65000"}

    await exchange.close()


@pytest.mark.asyncio
async def test_no_retry_on_4xx():
    """400 业务错误 → 立即抛出，不重试。"""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(400, json={"code": "40001", "msg": "Invalid symbol", "data": {}})

    transport = httpx.MockTransport(handler)
    exchange = _make_exchange_with_transport(transport)

    with pytest.raises(ValueError, match="Bitget API error"):
        await exchange._request("GET", "/api/v2/mix/market/ticker", params={"symbol": "INVALID", "productType": "usdt-futures"})

    assert call_count == 1, f"4xx should not retry, but got {call_count} calls"

    await exchange.close()


@pytest.mark.asyncio
async def test_retry_on_network_error():
    """httpx.ConnectError → 重试后成功。"""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("Connection refused")
        return httpx.Response(200, json={"code": "00000", "msg": "success", "data": {"lastPr": "65000"}})

    transport = httpx.MockTransport(handler)
    exchange = _make_exchange_with_transport(transport)

    data = await exchange._request("GET", "/api/v2/mix/market/ticker", params={"symbol": "BTCUSDT", "productType": "usdt-futures"})
    assert call_count == 3
    assert data == {"lastPr": "65000"}

    await exchange.close()


@pytest.mark.asyncio
async def test_connection_pool_config():
    """httpx.AsyncClient 创建时带连接池 limits（max_connections=20）。"""
    exchange = BitgetExchange(api_key="k", api_secret="s", passphrase="p")
    client = await exchange._get_client()
    assert client is not None
    assert isinstance(client, httpx.AsyncClient)
    assert exchange._limits.max_connections == 20
    assert exchange._limits.max_keepalive_connections == 20
    await exchange.close()


@pytest.mark.asyncio
async def test_aenter_aexit_context_manager():
    """async with exchange as e 可用，退出时自动 close。"""
    exchange = BitgetExchange(api_key="k", api_secret="s", passphrase="p")
    async with exchange as e:
        assert e is exchange
        client = await e._get_client()
        assert client is not None
    assert exchange._client is None or exchange._client.is_closed
