import pytest


@pytest.mark.asyncio
async def test_calculate_position(client):
    resp = await client.post("/api/risk/calculate-position", json={
        "equity": "1500", "risk_percent": "1",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "fee_rate": "0.0005", "direction": "LONG", "symbol": "BTCUSDT",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk_amount"] == "15"
    assert data["rounded_size"] == "0.030"


@pytest.mark.asyncio
async def test_risk_check(client):
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post("/api/risk/check", json={
        "plan": {
            "symbol": "BTCUSDT", "direction": "LONG",
            "entry_price": "62400", "stop_loss_price": "61900",
            "take_profit_prices": ["63800"], "leverage": "10",
            "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
        },
        "sizing_result": {
            "equity": "1500", "risk_percent": "1", "risk_amount": "15",
            "entry_price": "62400", "stop_loss_price": "61900",
            "stop_distance_percent": "0.008012820512820512820512820512820512",
            "notional_value": "1872",
            "raw_size": "0.03", "rounded_size": "0.030",
            "required_margin": "187.2", "leverage": "10",
            "estimated_fee": "1.872", "risk_reward_ratio": "2.8",
            "estimated_loss_at_stop": "17.9952", "sizing_warnings": [],
            "estimated_slippage": "0.936", "estimated_funding": "0.1872",
        },
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ALLOW"