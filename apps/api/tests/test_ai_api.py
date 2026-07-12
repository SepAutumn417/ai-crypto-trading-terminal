from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_evaluate_opportunity(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": "65000.0",
            "interval": "1h",
            "limit": 100,
        }
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["direction"] == "LONG"
    assert "overall_score" in data
    assert "grade" in data
    assert len(data["signals"]) == 5


@pytest.mark.asyncio
async def test_evaluate_opportunity_short(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "ETHUSDT",
            "direction": "SHORT",
            "entry_price": "3500.0",
        }
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "ETHUSDT"
    assert data["direction"] == "SHORT"


@pytest.mark.asyncio
async def test_evaluate_opportunity_invalid_direction(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "BTCUSDT",
            "direction": "INVALID",
            "entry_price": "65000.0",
        }
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_evaluate_opportunity_missing_params(client):
    resp = await client.get("/api/ai/evaluate")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_evaluate_opportunity_has_summary(client):
    resp = await client.get(
        "/api/ai/evaluate",
        params={
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": "65000.0",
        }
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "summary" in data
    assert len(data["summary"]) > 0
    assert "recommendation" in data
    assert "risk_level" in data
    assert "conviction" in data


# ===== v0.5: evaluate-plan 端点 =====


@pytest.mark.asyncio
async def test_evaluate_plan_not_found(client):
    """评估不存在的交易计划 → 404。"""
    resp = await client.post(f"/api/ai/evaluate-plan/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_evaluate_plan_success(client):
    """评估已存在的交易计划 → 200 + 评估结果。"""
    create_resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    assert create_resp.status_code == 200
    plan_id = create_resp.json()["data"]["id"]

    resp = await client.post(f"/api/ai/evaluate-plan/{plan_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["symbol"] == "BTCUSDT"
    assert data["direction"] == "LONG"
    assert "overall_score" in data
    assert "grade" in data
    # LLM 默认未启用，降级为 rule_based
    assert data["source"] == "rule_based"
    assert len(data["signals"]) == 5


# ===== v0.5: review-trade 端点 =====


@pytest.mark.asyncio
async def test_review_trade_not_found(client):
    """复盘不存在的交易日志 → 404。"""
    resp = await client.post(f"/api/ai/review-trade/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_review_trade_llm_disabled(client):
    """LLM 未启用时复盘返回提示信息。"""
    create_resp = await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": "65000.0",
        "quantity": "0.1",
        "leverage": "10",
    })
    assert create_resp.status_code == 200
    journal_id = create_resp.json()["data"]["id"]

    resp = await client.post(f"/api/ai/review-trade/{journal_id}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "LLM 未启用" in data["summary"]
    assert data["source"] == "rule_based"
