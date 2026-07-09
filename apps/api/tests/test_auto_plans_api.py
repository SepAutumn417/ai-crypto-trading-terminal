"""候选计划 API 测试 - v0.4 auto_plans 端点。"""
import pytest
from uuid import uuid4


@pytest.mark.asyncio
async def test_scan_candidates(client):
    """扫描标的生成候选计划。"""
    resp = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["symbol"] == "BTCUSDT"
    assert "market_state" in data
    assert "trend_direction" in data
    assert isinstance(data["candidates"], list)
    assert data["total"] == len(data["candidates"])
    assert "skipped_duplicates" in data


@pytest.mark.asyncio
async def test_scan_candidates_with_params(client):
    """带参数扫描。"""
    resp = await client.post("/api/auto-plans/scan", params={
        "symbol": "BTCUSDT", "interval": "1h", "limit": 200,
        "swing_left": 2, "swing_right": 2,
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_scan_candidates_missing_symbol(client):
    """缺少 symbol 参数 → 422。"""
    resp = await client.post("/api/auto-plans/scan")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scan_candidates_invalid_limit(client):
    """limit 超范围 → 422。"""
    resp = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT", "limit": 10})
    assert resp.status_code == 422

    resp = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT", "limit": 2000})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_candidates_empty(client):
    """无候选计划时返回空列表。"""
    resp = await client.get("/api/auto-plans")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_candidates_after_scan(client):
    """扫描后查询候选计划列表。"""
    await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    resp = await client.get("/api/auto-plans")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) > 0
    assert data["total"] == len(data["items"])
    assert data["page"] == 1
    assert data["page_size"] == 50


@pytest.mark.asyncio
async def test_list_candidates_with_filters(client):
    """按状态和标的过滤。"""
    await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    resp = await client.get("/api/auto-plans", params={"status": "READY", "symbol": "BTCUSDT"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    for item in data["items"]:
        assert item["status"] == "READY"
        assert item["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_list_candidates_pagination(client):
    """分页查询。"""
    await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    resp = await client.get("/api/auto-plans", params={"page": 1, "page_size": 5})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) <= 5


@pytest.mark.asyncio
async def test_get_candidate(client):
    """查询单个候选计划。"""
    scan_resp = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    candidates = scan_resp.json()["data"]["candidates"]
    assert len(candidates) > 0
    candidate_id = candidates[0]["id"]

    resp = await client.get(f"/api/auto-plans/{candidate_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == candidate_id
    assert data["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_get_candidate_not_found(client):
    """查询不存在的候选计划。"""
    resp = await client.get(f"/api/auto-plans/{uuid4()}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_promote_candidate(client):
    """提升候选计划为正式交易计划。"""
    scan_resp = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    candidates = scan_resp.json()["data"]["candidates"]
    # 找到有入场价的候选
    promotable = [c for c in candidates if c["entry_price"] is not None]
    if not promotable:
        pytest.skip("MockExchange 未生成有入场价的候选计划")
    candidate_id = promotable[0]["id"]

    resp = await client.post(f"/api/auto-plans/{candidate_id}/promote", json={
        "leverage": "10",
        "risk_percent": "1",
        "equity": "1500",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["candidate_id"] == candidate_id
    assert "trade_plan_id" in data
    assert data["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_promote_candidate_not_found(client):
    """提升不存在的候选计划。"""
    resp = await client.post(f"/api/auto-plans/{uuid4()}/promote", json={
        "leverage": "10",
        "risk_percent": "1",
        "equity": "1500",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_promote_candidate_idempotent(client):
    """重复提升同一候选计划 → ALREADY_PROMOTED。"""
    scan_resp = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    candidates = scan_resp.json()["data"]["candidates"]
    promotable = [c for c in candidates if c["entry_price"] is not None]
    if not promotable:
        pytest.skip("MockExchange 未生成有入场价的候选计划")
    candidate_id = promotable[0]["id"]

    # 第一次提升
    resp1 = await client.post(f"/api/auto-plans/{candidate_id}/promote", json={
        "leverage": "10", "risk_percent": "1", "equity": "1500",
    })
    assert resp1.json()["success"] is True

    # 第二次提升 → 幂等拒绝
    resp2 = await client.post(f"/api/auto-plans/{candidate_id}/promote", json={
        "leverage": "10", "risk_percent": "1", "equity": "1500",
    })
    body = resp2.json()
    assert body["success"] is False
    assert body["error"]["code"] == "ALREADY_PROMOTED"


@pytest.mark.asyncio
async def test_promote_invalid_leverage(client):
    """无效杠杆 → 422。"""
    scan_resp = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    candidates = scan_resp.json()["data"]["candidates"]
    if not candidates:
        pytest.skip("MockExchange 未生成候选计划")
    candidate_id = candidates[0]["id"]

    resp = await client.post(f"/api/auto-plans/{candidate_id}/promote", json={
        "leverage": "0",  # 低于最小值 1
        "risk_percent": "1",
        "equity": "1500",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scan_dedup(client, db_session):
    """重复扫描同标的不产生重复候选（1小时内）。"""
    resp1 = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    first_count = resp1.json()["data"]["total"]

    resp2 = await client.post("/api/auto-plans/scan", params={"symbol": "BTCUSDT"})
    second_data = resp2.json()["data"]
    # 第二次扫描应跳过已存在的同 setup_type+direction 的候选
    assert second_data["skipped_duplicates"] >= first_count or second_data["total"] == 0
