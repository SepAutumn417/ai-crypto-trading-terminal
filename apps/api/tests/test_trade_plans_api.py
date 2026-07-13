import pytest


@pytest.mark.asyncio
async def test_create_plan(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_check_plan_allows(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    # P0-5: 先解除 Kill Switch，再开启 Execution Mode
    await client.post("/api/system/kill-switch", json={"enabled": False})
    await client.post("/api/system/execution-mode", json={"enabled": True})

    # Mock AI 评估返回 A 级，避免 MockExchange 正弦波数据导致 D 级降级为 WAIT
    from decimal import Decimal
    from unittest.mock import AsyncMock, MagicMock, patch

    from ai_evaluator.types import EvaluationGrade
    fake_ai = MagicMock()
    fake_ai.grade = EvaluationGrade.A
    fake_ai.overall_score = Decimal("80")
    fake_ai.symbol = "BTCUSDT"
    fake_ai.direction = "LONG"
    fake_ai.recommendation = "强烈推荐"
    fake_ai.risk_level = "低"
    fake_ai.signals = []
    fake_ai.summary = "mock"
    fake_ai.conviction = Decimal("80")
    fake_ai.source.value = "rule_based"
    fake_ai.explanation = None

    with patch("ai_evaluator.evaluate_with_llm", new=AsyncMock(return_value=fake_ai)):
        resp = await client.post(f"/api/trade-plans/{plan_id}/check")

    body = resp.json()["data"]
    assert body["decision"]["result"] == "ALLOW_CONFIRM"
    assert body["plan"]["status"] == "READY_FOR_CONFIRMATION"
    assert body["sizing"]["risk_amount"] == "15"
    assert body["confirmation"]["token"]
    assert body["confirmation"]["expires_at"]

    confirm = await client.post(
        f"/api/trade-plans/{plan_id}/confirm",
        json={"token": body["confirmation"]["token"]},
    )
    assert confirm.status_code == 200
    assert confirm.json()["data"]["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_check_plan_blocks_no_stop(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": None,
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{plan_id}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "BLOCK"
    assert body["decision"]["result"] == "BLOCK"
    assert body["plan"]["status"] == "CHECKED"


@pytest.mark.asyncio
async def test_list_plans(client):
    await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    resp = await client.get("/api/trade-plans", params={"status": "DRAFT"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_get_plan_detail(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]
    resp = await client.get(f"/api/trade-plans/{plan_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["symbol"] == "BTCUSDT"
