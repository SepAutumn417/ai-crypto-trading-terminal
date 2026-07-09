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
    # ApiResponse 格式：{success, data, error: {code, message, details}, request_id}
    assert body["success"] is False
    assert body["error"]["code"] == "SUBMISSION_FAILED"
    assert body["error"]["details"]["error_code"] == "EXCHANGE_REJECTED"
    assert body["error"]["details"]["retryable"] is False

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
    # ApiResponse 格式：{success, data, error: {code, message, details}, request_id}
    assert body["success"] is False
    assert body["error"]["code"] == "EXECUTION_DISABLED"
    assert "Kill Switch" in body["error"]["message"]

    fresh_plan = await db_session.get(TradePlan, plan_id)
    assert fresh_plan.status == PlanStatus.READY_FOR_CONFIRMATION.value
    assert fresh_plan.execution_error is None
    fake_exchange.place_order.assert_not_called()


# ========================================================================
# P1-27: sync_order_status / cancel_plan_order 测试矩阵
# ========================================================================


def _make_submitted_plan_kwargs(plan_id: UUID | None = None, **overrides) -> dict:
    """生成已提交（SUBMITTED）状态的 plan，带 exchange_order_id。"""
    base = _make_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.SUBMITTED.value,
        client_order_id=f"{plan_id.hex[:16]}-1" if plan_id else "test-1",
        exchange_order_id="bitget-order-001",
        execution_attempts=1,
    )
    base.update(overrides)
    return base


def _make_fake_order(
    status_value: str = "filled",
    filled_quantity: str = "0.5",
    average_fill_price: str | None = "62500",
) -> MagicMock:
    """构造 exchange.get_order 返回的 Order mock。"""
    order = MagicMock()
    order.id = "bitget-order-001"
    order.status = MagicMock()
    order.status.value = status_value
    order.filled_quantity = Decimal(filled_quantity)
    order.average_fill_price = Decimal(average_fill_price) if average_fill_price else None
    return order


@pytest.mark.asyncio
async def test_sync_order_status_filled(client, db_session):
    """sync 正常成交：SUBMITTED → FILLED，filled_quantity/average_fill_price 更新，自动创建 journal。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.get_order = AsyncMock(return_value=_make_fake_order(
        status_value="filled", filled_quantity="0.5", average_fill_price="62500",
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/sync")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.FILLED.value
    assert body["filled_quantity"] == "0.5"
    assert body["average_fill_price"] == "62500"
    fake_exchange.get_order.assert_called_once()


@pytest.mark.asyncio
async def test_sync_order_status_partially_filled(client, db_session):
    """sync 部分成交：SUBMITTED → PARTIALLY_FILLED。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.get_order = AsyncMock(return_value=_make_fake_order(
        status_value="partially_filled", filled_quantity="0.2", average_fill_price="62450",
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/sync")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.PARTIALLY_FILLED.value
    assert body["filled_quantity"] == "0.2"


@pytest.mark.asyncio
async def test_sync_order_still_pending(client, db_session):
    """sync 订单仍挂：SUBMITTED → SUBMITTED（状态不变，filled_quantity=0）。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.get_order = AsyncMock(return_value=_make_fake_order(
        status_value="new", filled_quantity="0", average_fill_price=None,
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/sync")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.SUBMITTED.value


@pytest.mark.asyncio
async def test_sync_order_rejected(client, db_session):
    """sync 订单被拒：SUBMITTED → FAILED（REJECTED 映射到 FAILED）。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.get_order = AsyncMock(return_value=_make_fake_order(
        status_value="rejected", filled_quantity="0", average_fill_price=None,
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/sync")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.FAILED.value


@pytest.mark.asyncio
async def test_sync_exchange_error(client, db_session):
    """sync 交易所异常：get_order 抛异常 → 422，plan 记录 execution_error。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.get_order = AsyncMock(side_effect=ValueError("Bitget API error: connection timeout"))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/sync")

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SUBMISSION_FAILED"
    assert body["error"]["details"]["error_code"] == "EXCHANGE_NETWORK_ERROR"
    assert body["error"]["details"]["retryable"] is True


@pytest.mark.asyncio
async def test_cancel_order_success(client, db_session):
    """cancel 正常：SUBMITTED → CANCELLED。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.cancel_order = AsyncMock(return_value=None)

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/cancel")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.CANCELLED.value
    fake_exchange.cancel_order.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_invalid_state_filled(client, db_session):
    """cancel 状态不允许：FILLED 状态取消 → 422 报错。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(
        plan_id=plan_id, status=PlanStatus.FILLED.value,
    ))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.cancel_order = AsyncMock(side_effect=AssertionError("cancel_order should NOT be called for FILLED plan"))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/cancel")

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SUBMISSION_FAILED"
    assert body["error"]["details"]["error_code"] == "INVALID_STATE_FOR_CANCEL"
    fake_exchange.cancel_order.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_exchange_error(client, db_session):
    """cancel 交易所异常：cancel_order 抛异常 → 422，plan 记录 execution_error。"""
    plan_id = uuid4()
    plan = TradePlan(id=plan_id, **_make_submitted_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.cancel_order = AsyncMock(side_effect=ValueError("Bitget API error: order not found"))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/cancel")

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SUBMISSION_FAILED"
    assert body["error"]["details"]["error_code"] == "EXCHANGE_REJECTED"
    assert body["error"]["details"]["retryable"] is False