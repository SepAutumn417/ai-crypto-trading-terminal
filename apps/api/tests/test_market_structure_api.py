"""市场结构识别 API 测试 - v0.3 market structure 端点。"""
import pytest

from app.models import MarketStructureSnapshotModel


@pytest.mark.asyncio
async def test_get_market_structure(client):
    """获取市场结构快照。"""
    resp = await client.get("/api/market/structure", params={
        "symbol": "BTCUSDT", "interval": "1h", "limit": 200,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["timeframe"] == "1h"
    assert "market_state" in data
    assert "trend_direction" in data
    assert isinstance(data["swing_highs"], list)
    assert isinstance(data["swing_lows"], list)
    assert isinstance(data["bos_events"], list)
    assert isinstance(data["choch_events"], list)
    assert isinstance(data["support_zones"], list)
    assert isinstance(data["resistance_zones"], list)
    assert isinstance(data["no_trade_zones"], list)
    assert "volatility_state" in data
    assert "kline_count" in data
    assert data["kline_count"] == 200


@pytest.mark.asyncio
async def test_get_market_structure_missing_symbol(client):
    """缺少 symbol → 422。"""
    resp = await client.get("/api/market/structure")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_market_structure_invalid_limit(client):
    """limit 超范围 → 422。"""
    resp = await client.get("/api/market/structure", params={"symbol": "BTCUSDT", "limit": 10})
    assert resp.status_code == 422

    resp = await client.get("/api/market/structure", params={"symbol": "BTCUSDT", "limit": 2000})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_market_structure_invalid_swing(client):
    """swing_left / swing_right 超范围 → 422。"""
    resp = await client.get("/api/market/structure", params={
        "symbol": "BTCUSDT", "swing_left": 0,
    })
    assert resp.status_code == 422

    resp = await client.get("/api/market/structure", params={
        "symbol": "BTCUSDT", "swing_right": 20,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_market_structure_default_params(client):
    """默认参数请求。"""
    resp = await client.get("/api/market/structure", params={"symbol": "BTCUSDT"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["timeframe"] == "1h"
    assert data["kline_count"] == 200


@pytest.mark.asyncio
async def test_get_market_structure_custom_swing(client):
    """自定义 swing 参数。"""
    resp = await client.get("/api/market/structure", params={
        "symbol": "BTCUSDT", "swing_left": 3, "swing_right": 3,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["kline_count"] == 200


@pytest.mark.asyncio
async def test_get_market_structure_persists_snapshot(client, db_session):
    """结构快照持久化到数据库。"""
    resp = await client.get("/api/market/structure", params={"symbol": "BTCUSDT"})
    assert resp.status_code == 200
    snapshot_id = resp.json()["data"]["id"]

    model = await db_session.get(MarketStructureSnapshotModel, snapshot_id)
    assert model is not None
    assert model.symbol == "BTCUSDT"
    assert model.timeframe == "1h"
    assert model.market_state is not None
    assert model.trend_direction is not None
    assert isinstance(model.swing_highs, list)
    assert isinstance(model.swing_lows, list)
    assert model.kline_count == 200


@pytest.mark.asyncio
async def test_get_market_structure_different_interval(client):
    """不同 K 线周期。"""
    resp = await client.get("/api/market/structure", params={
        "symbol": "BTCUSDT", "interval": "15m", "limit": 100,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["timeframe"] == "15m"
    assert data["kline_count"] == 100


@pytest.mark.asyncio
async def test_get_market_structure_snapshot_has_zones(client):
    """结构快照包含支撑/阻力/禁交易区域。"""
    resp = await client.get("/api/market/structure", params={
        "symbol": "BTCUSDT", "limit": 500,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    # 至少应该有支撑或阻力区域之一
    has_support = len(data["support_zones"]) > 0
    has_resistance = len(data["resistance_zones"]) > 0
    assert has_support or has_resistance, "应有支撑或阻力区域"
