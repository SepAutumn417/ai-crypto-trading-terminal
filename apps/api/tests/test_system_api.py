import pytest
from sqlalchemy import select

from app.models import SystemEvent, UserSettings


@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["execution_enabled"] is False
    assert data["kill_switch"] is True


@pytest.mark.asyncio
async def test_toggle_kill_switch(client):
    resp = await client.post(
        "/api/system/kill-switch",
        json={"enabled": False, "reason": "测试解除"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["kill_switch"] is False

    resp = await client.get("/api/system/status")
    assert resp.json()["data"]["kill_switch"] is False


@pytest.mark.asyncio
async def test_toggle_execution_mode(client):
    # 先解除 kill switch
    await client.post(
        "/api/system/kill-switch",
        json={"enabled": False, "reason": "测试前置"},
    )
    resp = await client.post(
        "/api/system/execution-mode",
        json={"enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["execution_enabled"] is True

    resp = await client.get("/api/system/status")
    assert resp.json()["data"]["execution_enabled"] is True


# ========== P0-5: Kill Switch 修复测试 ==========


@pytest.mark.asyncio
async def test_p0_5_activate_kill_switch_forces_execution_mode_off(client):
    """P0-5: 激活 Kill Switch 时强制关闭 execution mode。"""
    # 先解除 kill switch 并开启 execution mode
    await client.post(
        "/api/system/kill-switch",
        json={"enabled": False, "reason": "前置解除"},
    )
    await client.post(
        "/api/system/execution-mode",
        json={"enabled": True},
    )

    # 激活 kill switch
    resp = await client.post(
        "/api/system/kill-switch",
        json={"enabled": True, "reason": "测试激活联动"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["kill_switch"] is True
    # P0-5 核心断言：execution_enabled 被强制关闭
    assert data["execution_enabled"] is False


@pytest.mark.asyncio
async def test_p0_5_execution_mode_rejected_when_kill_switch_active(client):
    """P0-5: Kill Switch 激活时拒绝开启 execution mode。"""
    # 默认 kill_switch=True（seed），尝试开启 execution mode
    resp = await client.post(
        "/api/system/execution-mode",
        json={"enabled": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "KILL_SWITCH_ACTIVE"


@pytest.mark.asyncio
async def test_p0_5_kill_switch_activation_records_audit_event(client, db_session):
    """P0-5: 激活 Kill Switch 时写入审计 SystemEvent，包含 reason 和 triggered_by。"""
    # 先解除 kill switch
    await client.post(
        "/api/system/kill-switch",
        json={"enabled": False, "reason": "前置解除"},
    )
    # 开启 execution mode（这样激活 kill switch 时才能测试强制关闭）
    await client.post(
        "/api/system/execution-mode",
        json={"enabled": True},
    )
    # 激活 kill switch
    await client.post(
        "/api/system/kill-switch",
        json={"enabled": True, "reason": "连续亏损超限测试"},
    )

    result = await db_session.execute(
        select(SystemEvent).where(SystemEvent.event_type == "kill_switch_activated")
        .order_by(SystemEvent.created_at.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert "连续亏损超限测试" in event.message
    assert event.payload["reason"] == "连续亏损超限测试"
    assert event.payload["triggered_by"] == "user"
    assert event.payload["previous_kill_switch"] is False
    assert event.payload["forced_execution_mode_off"] is True


@pytest.mark.asyncio
async def test_p0_5_kill_switch_deactivation_records_audit(client, db_session):
    """P0-5: 解除 Kill Switch 时写入审计事件。"""
    # 默认 kill_switch=True，直接解除
    resp = await client.post(
        "/api/system/kill-switch",
        json={"enabled": False, "reason": "手动恢复测试"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(SystemEvent).where(SystemEvent.event_type == "kill_switch_deactivated")
        .order_by(SystemEvent.created_at.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert "手动恢复测试" in event.message
    assert event.payload["reason"] == "手动恢复测试"
    assert event.payload["previous_kill_switch"] is True


@pytest.mark.asyncio
async def test_p0_5_kill_switch_service_activate_directly(db_session):
    """P0-5: 直接调用 kill_switch_service.activate_kill_switch 验证联动。"""
    from uuid import uuid4

    from app.services.kill_switch_service import activate_kill_switch, is_kill_switch_active

    # 先确保 kill_switch=False
    settings_model = await db_session.get(UserSettings, 1)
    settings_model.kill_switch = False
    settings_model.execution_enabled = True
    await db_session.commit()

    plan_id = uuid4()
    changed = await activate_kill_switch(
        db_session,
        reason="孤儿订单测试",
        triggered_by="execution_service",
        related_plan_id=plan_id,
        severity="critical",
    )

    assert changed is True

    # 验证 kill_switch 激活
    assert await is_kill_switch_active(db_session) is True

    # 验证 execution_enabled 被强制关闭
    await db_session.refresh(settings_model)
    assert settings_model.execution_enabled is False

    # 验证审计事件
    result = await db_session.execute(
        select(SystemEvent).where(SystemEvent.event_type == "kill_switch_activated")
        .order_by(SystemEvent.created_at.desc())
        .limit(1)
    )
    event = result.scalar_one()
    assert event.actor == "execution_service"
    assert event.severity == "critical"
    assert event.entity_id == plan_id
    assert event.payload["related_plan_id"] == str(plan_id)


@pytest.mark.asyncio
async def test_p0_5_kill_switch_service_deactivate(db_session):
    """P0-5: 直接调用 deactivate_kill_switch，不自动恢复 execution_enabled。"""
    from app.services.kill_switch_service import deactivate_kill_switch

    settings_model = await db_session.get(UserSettings, 1)
    settings_model.kill_switch = True
    settings_model.execution_enabled = False
    await db_session.commit()

    changed = await deactivate_kill_switch(db_session, reason="手动恢复", triggered_by="user")

    assert changed is True

    await db_session.refresh(settings_model)
    assert settings_model.kill_switch is False
    # execution_enabled 不自动恢复
    assert settings_model.execution_enabled is False


@pytest.mark.asyncio
async def test_p0_5_kill_switch_activate_idempotent(client, db_session):
    """P0-5: 重复激活返回 False（未发生状态变更）。"""
    from app.services.kill_switch_service import activate_kill_switch

    settings_model = await db_session.get(UserSettings, 1)
    settings_model.kill_switch = True
    settings_model.execution_enabled = False
    await db_session.commit()

    changed = await activate_kill_switch(db_session, reason="重复激活", triggered_by="system")
    assert changed is False
