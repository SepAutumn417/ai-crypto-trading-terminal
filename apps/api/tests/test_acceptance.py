"""v0.1 验收测试 - 对齐设计稿 §7"""
import pytest
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select

from app.models import (
    AccountRiskState as AccountRiskStateModel,
    DecisionGateResult, PositionSizingResult, RiskCheck, SystemEvent,
)


# ===== §7.1 创建交易计划 + 输入入场/止损/止盈 + 计算风险/止损距离/名义仓位/保证金/盈亏比 =====

@pytest.mark.asyncio
async def test_acceptance_create_plan_with_sizing(client):
    """创建计划 + 跑检查 + 验证 sizing 结果落库"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "DRAFT"

    # 启用 execution + 关闭 kill_switch
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    plan_id = resp.json()["data"]["id"]
    resp = await client.post(f"/api/trade-plans/{plan_id}/check")
    body = resp.json()["data"]
    sizing = body["sizing"]
    # 风险金额 / 止损距离 / 名义仓位 / 保证金 / 盈亏比
    assert sizing["risk_amount"] == "15"
    assert Decimal(sizing["stop_distance_percent"]) > 0
    assert Decimal(sizing["notional_value"]) > 0
    assert Decimal(sizing["required_margin"]) > 0
    assert Decimal(sizing["risk_reward_ratio"]) > 0


# ===== §7.2 输出风控结论 + 保存计划 =====

@pytest.mark.asyncio
async def test_acceptance_risk_decision_and_persist(client, db_session):
    """风控结论 + 落库 3 个结果表"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    await client.post(f"/api/trade-plans/{plan_id}/check")

    ps = await db_session.scalar(select(PositionSizingResult).where(PositionSizingResult.trade_plan_id == UUID(plan_id)))
    rc = await db_session.scalar(select(RiskCheck).where(RiskCheck.trade_plan_id == UUID(plan_id)))
    dg = await db_session.scalar(select(DecisionGateResult).where(DecisionGateResult.trade_plan_id == UUID(plan_id)))
    assert ps is not None and ps.risk_amount == Decimal("15")
    assert rc is not None and rc.status == "ALLOW"
    assert dg is not None and dg.result == "ALLOW_CONFIRM"


# ===== §7.3 13 条硬阻断规则（精选关键覆盖） =====

@pytest.mark.asyncio
async def test_acceptance_no_stop_loss_blocks(client):
    """无止损 → BLOCK"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": None,
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "BLOCK"
    assert any("no_stop_loss" in r for r in body["risk"]["block_reasons"])


@pytest.mark.asyncio
async def test_acceptance_excessive_leverage_blocks(client):
    """超杠杆 → BLOCK"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "20",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "BLOCK"


@pytest.mark.asyncio
async def test_acceptance_daily_loss_limit_blocks(client, db_session):
    """当日亏损限制 → BLOCK（直接改 DB account_risk_state 模拟）"""
    # 先创建一个会通过的计划
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]

    # 修改 account_risk_state 模拟"已亏损 2R"
    state = await db_session.get(AccountRiskStateModel, 1)
    state.daily_loss_r = Decimal("2")
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "BLOCK"
    assert any("daily_loss" in r for r in body["risk"]["block_reasons"])


@pytest.mark.asyncio
async def test_acceptance_kill_switch_blocks(client):
    """Kill Switch ON → BLOCK"""
    # 默认 kill_switch=True（seed 后）
    # 不要 toggle 到 false
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    # kill_switch 保持 ON（默认）

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    body = resp.json()["data"]
    assert body["decision"]["result"] == "BLOCK"


@pytest.mark.asyncio
async def test_acceptance_execution_disabled_blocks(client):
    """Execution Mode OFF → decision-gate BLOCK"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    # execution_mode 保持 OFF（默认）
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    body = resp.json()["data"]
    assert body["decision"]["result"] == "BLOCK"
    assert any("execution_disabled" in r for r in body["decision"]["reasons"])


# ===== §7.4 精度圆整 =====

@pytest.mark.asyncio
async def test_acceptance_precision_rounding(client):
    """rounded_size 精度圆整符合 size_step"""
    resp = await client.post("/api/risk/calculate-position", json={
        "equity": "1500", "risk_percent": "1",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "fee_rate": "0.0005", "direction": "LONG", "symbol": "BTCUSDT",
    })
    data = resp.json()["data"]
    assert data["rounded_size"] == "0.030"  # BTCUSDT size_step = 0.001


# ===== §7.5 机会等级 A/B/C/BLOCKED 映射 =====

@pytest.mark.asyncio
async def test_acceptance_grade_b_reduces_risk(client):
    """B 级 → REDUCE_RISK"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "B", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "REDUCE_RISK"


@pytest.mark.asyncio
async def test_acceptance_grade_c_blocks(client):
    """C 级 → BLOCK"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "C", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "BLOCK"


# ===== §7.6 配置版本激活后生效 =====

@pytest.mark.asyncio
async def test_acceptance_config_activation_takes_effect(client):
    """创建 risk-v2 + 激活 → active_configs 返回新版本"""
    resp = await client.post("/api/configs", json={
        "config_type": "risk", "version_label": "risk-v2-test",
        "payload": {
            "max_risk_percent": "1",
            "max_leverage": "5",
            "min_risk_reward_ratio": "2",
            "preferred_risk_reward_ratio": "3",
            "min_stop_distance_percent": "0.5",
            "daily_loss_limit_r": "1",
            "max_consecutive_losses": 1,
            "cooldown_minutes_after_loss": 60,
        },
    })
    new_id = resp.json()["data"]["id"]

    resp = await client.post(f"/api/configs/{new_id}/activate")
    assert resp.json()["data"]["is_active"] is True

    resp = await client.get("/api/configs/active")
    assert resp.json()["data"]["risk"]["version_label"] == "risk-v2-test"
    assert resp.json()["data"]["risk"]["payload"]["max_leverage"] == "5"


# ===== §7.7 system_events 记录 =====

@pytest.mark.asyncio
async def test_acceptance_system_events_recorded(client, db_session):
    """切换 Kill Switch 应产生 system_event"""
    await client.post("/api/system/kill-switch", json={"enabled": False})
    result = await db_session.execute(select(SystemEvent).order_by(SystemEvent.created_at.desc()))
    latest = result.scalar_one_or_none()
    assert latest is not None
    assert latest.event_type == "kill_switch_toggled"


# ===== §7.8 decision-gate 5 种状态 =====

@pytest.mark.asyncio
async def test_acceptance_decision_gate_status_allow_confirm(client):
    """所有绿灯 → ALLOW_CONFIRM"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    assert resp.json()["data"]["decision"]["result"] == "ALLOW_CONFIRM"


@pytest.mark.asyncio
async def test_acceptance_decision_gate_status_reduce_risk(client):
    """B 级 + 绿灯 → REDUCE_RISK"""
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "B", "equity": "1500",
    })
    pid = resp.json()["data"]["id"]
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{pid}/check")
    assert resp.json()["data"]["decision"]["result"] == "REDUCE_RISK"
