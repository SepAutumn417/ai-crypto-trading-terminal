"""PR-1: execute_plan 错误处理与幂等键 的单测。

TDD 纪律：先写测试看到失败，再写实现。

测试矩阵（5 条）：
1. test_execute_plan_happy_path — READY_FOR_CONFIRMATION → 成功下单，状态 SUBMITTED
2. test_execute_plan_idempotent_when_submitted — 第二次 execute（SUBMITTED 状态）→ 不调交易所，返回现状
3. test_execute_plan_retry_after_failure — FAILED 状态 execute → attempt 增 1，重新下新单
4. test_execute_plan_marks_failed_on_exchange_error — 交易所 5xx/业务错误 → plan.status=FAILED，execution_error 有内容，raise AppException
5. test_execute_plan_rejects_kill_switch — kill_switch=True → AppException，不调交易所
"""
import pytest
from decimal import Decimal
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import select

from app.exceptions import AppException
from app.models import TradePlan
from app.services import execution_service
from shared.enums import Direction, MarginMode, OpportunityGrade, PlanStatus


def _make_plan_kwargs(plan_id: UUID | None = None, **overrides) -> dict:
    base = {
        "exchange": "bitget",
        "symbol": "BTCUSDT",
        "direction": Direction.LONG.value,
        "entry_price": Decimal("62400"),
        "stop_loss_price": Decimal("61900"),
        "take_profit_prices": ["63800"],
        "leverage": Decimal("10"),
        "risk_percent": Decimal("1"),
        "opportunity_grade": OpportunityGrade.A.value,
        "equity": Decimal("1500"),
        "setup_type": None,
        "margin_mode": MarginMode.ISOLATED.value,
        "notes": None,
        "status": PlanStatus.READY_FOR_CONFIRMATION.value,
        "execution_attempts": 0,
    }
    base.update(overrides)
    if plan_id is not None:
        base["id"] = plan_id
    return base


@pytest.mark.asyncio
async def test_execute_plan_happy_path(client, db_session):
    """Happy path：READY_FOR_CONFIRMATION → 调交易所 → status=SUBMITTED，client_order_id 已写入。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    fake_order = MagicMock()
    fake_order.id = "bitget-12345"
    fake_order.status = MagicMock()
    fake_order.status.value = "new"
    fake_order.filled_quantity = Decimal("0")
    fake_order.average_fill_price = None

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(return_value=fake_order)

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.SUBMITTED.value
    assert body["exchange_order_id"] == "bitget-12345"
    assert body["client_order_id"].startswith(plan_id.hex[:16] + "-")
    assert body["client_order_id"].endswith("-1")
    assert body["execution_error"] is None


@pytest.mark.asyncio
async def test_execute_plan_idempotent_when_submitted(client, db_session):
    """幂等键：SUBMITTED 状态二次调用 → 不调交易所，直接返回现状。"""
    plan_id = uuid4()
    existing_client_order_id = f"{plan_id.hex[:16]}-1"
    plan = TradePlan(
        id=plan_id, **_make_plan_kwargs(
            plan_id=plan_id,
            status=PlanStatus.SUBMITTED.value,
            client_order_id=existing_client_order_id,
            exchange_order_id="bitget-99999",
            execution_attempts=1,
        ),
    )
    db_session.add(plan)
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=AssertionError("place_order should NOT be called for idempotent path"))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.SUBMITTED.value
    assert body["client_order_id"] == existing_client_order_id
    fake_exchange.place_order.assert_not_called()


@pytest.mark.asyncio
async def test_execute_plan_retry_after_failure(client, db_session):
    """失败重试：FAILED 状态 execute → attempt 增 1，client_order_id 变 -2，新单生成。"""
    plan_id = uuid4()
    old_client_order_id = f"{plan_id.hex[:16]}-1"
    plan = TradePlan(
        id=plan_id, **_make_plan_kwargs(
            plan_id=plan_id,
            status=PlanStatus.FAILED.value,
            client_order_id=old_client_order_id,
            execution_error="previous attempt: network timeout",
            execution_attempts=1,
        ),
    )
    db_session.add(plan)
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    fake_order = MagicMock()
    fake_order.id = "bitget-67890"
    fake_order.status = MagicMock()
    fake_order.status.value = "new"
    fake_order.filled_quantity = Decimal("0")
    fake_order.average_fill_price = None

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(return_value=fake_order)

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.SUBMITTED.value
    assert body["client_order_id"] == f"{plan_id.hex[:16]}-2"
    assert body["exchange_order_id"] == "bitget-67890"
    assert body["execution_error"] is None
    fake_exchange.place_order.assert_called_once()


@pytest.mark.asyncio
async def test_execute_plan_marks_failed_on_exchange_error(client, db_session):
    """交易所错误：place_order 抛异常 → plan.status=FAILED，execution_error 有内容，response 422。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=ValueError("Bitget API error: insufficient margin"))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body.get("code") == "SUBMISSION_FAILED"
    assert body.get("data", {}).get("error_code") == "EXCHANGE_REJECTED"
    assert body.get("data", {}).get("retryable") is False

    fresh_plan = await db_session.get(TradePlan, plan_id)
    assert fresh_plan.status == PlanStatus.FAILED.value
    assert fresh_plan.execution_error is not None
    assert "insufficient margin" in fresh_plan.execution_error
    assert fresh_plan.execution_error_code == "EXCHANGE_REJECTED"
    assert fresh_plan.execution_attempts == 1


@pytest.mark.asyncio
async def test_execute_plan_rejects_kill_switch(client, db_session):
    """Kill switch 拒绝：kill_switch=True → 422/409，plan 状态不变，交易所未调用。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": True})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=AssertionError("place_order must not be called when kill_switch is on"))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body.get("code") == "EXECUTION_DISABLED"
    assert "Kill Switch" in str(body)

    fresh_plan = await db_session.get(TradePlan, plan_id)
    assert fresh_plan.status == PlanStatus.READY_FOR_CONFIRMATION.value
    assert fresh_plan.execution_error is None
    fake_exchange.place_order.assert_not_called()