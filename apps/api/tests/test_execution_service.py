"""P0-3/P0-4/P0-5: execute_plan 测试 — 二次确认 + 状态机 + 行锁 + Kill Switch 联动。

测试矩阵：
1. test_execute_plan_happy_path — CONFIRMED → 成功下单，状态 SUBMITTED，稳定 client_order_id
2. test_execute_plan_idempotent_when_submitted — SUBMITTED 状态二次调用 → 幂等返回
3. test_execute_plan_rejects_ready_for_confirmation — READY_FOR_CONFIRMATION → 拒绝（需先确认）
4. test_execute_plan_rejects_failed_state — FAILED 状态 → 拒绝（需重新 check_plan）
5. test_execute_plan_marks_failed_on_exchange_error — 交易所错误 → FAILED + execution_error
6. test_execute_plan_rejects_kill_switch — kill_switch=True → 拒绝
7. test_execute_plan_executing_state_triggers_reconciliation — EXECUTING → 对账恢复
"""
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.exceptions import AppException
from app.models import PositionSizingResult, TradePlan
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


def _make_confirmed_plan_kwargs(plan_id: UUID, **overrides) -> dict:
    """生成 CONFIRMED 状态的计划，包含有效的二次确认字段。"""
    base = _make_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.CONFIRMED.value,
        confirmation_token="test-confirmation-token",
        plan_hash="dummy-hash",  # 会被 _compute_plan_hash 覆盖
        confirmed_at=datetime.now(UTC),
        confirmation_expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )
    base.update(overrides)
    return base


async def _add_sizing_result(db_session, plan_id: UUID, rounded_size: str = "0.5") -> None:
    """为计划添加 PositionSizingResult（execute_plan 前置依赖）。"""
    sizing = PositionSizingResult(
        trade_plan_id=plan_id,
        equity=Decimal("1500"),
        risk_percent=Decimal("1"),
        risk_amount=Decimal("15"),
        entry_price=Decimal("62400"),
        stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"),
        notional_value=Decimal("750"),
        raw_size=Decimal("0.512"),
        rounded_size=Decimal(rounded_size),
        required_margin=Decimal("75"),
        leverage=Decimal("10"),
        estimated_fee=Decimal("0.75"),
        risk_reward_ratio=Decimal("2.8"),
        estimated_loss_at_stop=Decimal("15"),
        sizing_warnings=[],
        is_latest=True,
    )
    db_session.add(sizing)
    await db_session.commit()


def _stable_client_order_id(plan_id: UUID) -> str:
    """P0-4: 稳定幂等键 — 仅基于 plan_id。"""
    return f"plan-{plan_id.hex[:16]}"


@pytest.mark.asyncio
async def test_execute_plan_happy_path(client, db_session):
    """Happy path：CONFIRMED → 调交易所 → status=SUBMITTED，稳定 client_order_id。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_confirmed_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()
    # 生成正确的 plan_hash
    from app.services.confirmation_service import _compute_plan_hash
    plan.plan_hash = _compute_plan_hash(plan)
    await db_session.commit()

    await _add_sizing_result(db_session, plan_id)

    # P0-5: 先解除 Kill Switch，再开启 Execution Mode
    await client.post("/api/system/kill-switch", json={"enabled": False})
    await client.post("/api/system/execution-mode", json={"enabled": True})

    from exchange_adapter import OrderStatus as ExchangeOrderStatus

    fake_order = MagicMock()
    fake_order.id = "bitget-12345"
    fake_order.status = ExchangeOrderStatus.NEW
    fake_order.filled_quantity = Decimal("0")
    fake_order.average_fill_price = None

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(return_value=fake_order)
    fake_exchange.set_leverage = AsyncMock(return_value=None)

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.SUBMITTED.value
    assert body["exchange_order_id"] == "bitget-12345"
    # P0-4: 稳定 client_order_id，不带 attempt 后缀
    assert body["client_order_id"] == _stable_client_order_id(plan_id)
    assert body["execution_error"] is None


@pytest.mark.asyncio
async def test_execute_plan_idempotent_when_submitted(client, db_session):
    """幂等键：SUBMITTED 状态二次调用 → 不调交易所，直接返回现状。"""
    plan_id = uuid4()
    existing_client_order_id = _stable_client_order_id(plan_id)
    plan = TradePlan(**_make_confirmed_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.SUBMITTED.value,
        client_order_id=existing_client_order_id,
        exchange_order_id="bitget-99999",
        execution_attempts=1,
    ))
    db_session.add(plan)
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=AssertionError(
        "place_order should NOT be called for idempotent path"
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.SUBMITTED.value
    assert body["client_order_id"] == existing_client_order_id
    fake_exchange.place_order.assert_not_called()


@pytest.mark.asyncio
async def test_execute_plan_rejects_ready_for_confirmation(client, db_session):
    """P0-3: READY_FOR_CONFIRMATION 状态执行 → 拒绝（需先调用 /confirm）。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=AssertionError(
        "place_order should NOT be called for unconfirmed plan"
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["details"]["error_code"] == "NOT_CONFIRMED"
    fake_exchange.place_order.assert_not_called()


@pytest.mark.asyncio
async def test_execute_plan_rejects_failed_state(client, db_session):
    """P0-4: FAILED 状态执行 → 拒绝（需重新 check_plan 并确认）。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.FAILED.value,
        client_order_id=_stable_client_order_id(plan_id),
        execution_error="previous attempt: network timeout",
        execution_attempts=1,
    ))
    db_session.add(plan)
    await db_session.commit()

    # P0-5: 先解除 Kill Switch，再开启 Execution Mode
    await client.post("/api/system/kill-switch", json={"enabled": False})
    await client.post("/api/system/execution-mode", json={"enabled": True})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=AssertionError(
        "place_order should NOT be called for FAILED plan"
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["details"]["error_code"] == "RECHECK_REQUIRED"
    fake_exchange.place_order.assert_not_called()


@pytest.mark.asyncio
async def test_execute_plan_marks_failed_on_exchange_error(client, db_session):
    """交易所错误：place_order 抛异常 → plan.status=FAILED，execution_error 有内容。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_confirmed_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()
    from app.services.confirmation_service import _compute_plan_hash
    plan.plan_hash = _compute_plan_hash(plan)
    await db_session.commit()

    await _add_sizing_result(db_session, plan_id)

    # P0-5: 先解除 Kill Switch，再开启 Execution Mode
    await client.post("/api/system/kill-switch", json={"enabled": False})
    await client.post("/api/system/execution-mode", json={"enabled": True})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=ValueError(
        "Bitget API error: insufficient margin"
    ))
    fake_exchange.set_leverage = AsyncMock(return_value=None)

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "SUBMISSION_FAILED"
    assert body["error"]["details"]["error_code"] == "EXCHANGE_REJECTED"
    assert body["error"]["details"]["retryable"] is False

    # 强制过期以从数据库重新加载（API 用不同 session 提交了变更）
    db_session.expire_all()
    fresh_plan = await db_session.get(TradePlan, plan_id)
    assert fresh_plan.status == PlanStatus.FAILED.value
    assert fresh_plan.execution_error is not None
    assert "insufficient margin" in fresh_plan.execution_error
    assert fresh_plan.execution_error_code == "EXCHANGE_REJECTED"
    assert fresh_plan.execution_attempts == 1


@pytest.mark.asyncio
async def test_execute_plan_rejects_kill_switch(client, db_session):
    """Kill switch 拒绝：kill_switch=True → 409，plan 状态不变，交易所未调用。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_confirmed_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()
    from app.services.confirmation_service import _compute_plan_hash
    plan.plan_hash = _compute_plan_hash(plan)
    await db_session.commit()

    await _add_sizing_result(db_session, plan_id)

    # 先解除 kill switch，开启 execution mode，然后重新激活 kill switch
    await client.post("/api/system/kill-switch", json={"enabled": False})
    await client.post("/api/system/execution-mode", json={"enabled": True})
    # 重新激活 kill switch → execution_enabled 被强制关闭
    await client.post("/api/system/kill-switch", json={"enabled": True, "reason": "测试 Kill Switch 阻断"})

    fake_exchange = MagicMock()
    fake_exchange.place_order = AsyncMock(side_effect=AssertionError(
        "place_order must not be called when kill_switch is on"
    ))

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "EXECUTION_DISABLED"
    assert "Kill Switch" in body["error"]["message"] or "交易执行未启用" in body["error"]["message"]

    fresh_plan = await db_session.get(TradePlan, plan_id)
    # Plan 状态仍为 CONFIRMED（未执行）
    assert fresh_plan.status == PlanStatus.CONFIRMED.value
    assert fresh_plan.execution_error is None
    fake_exchange.place_order.assert_not_called()


@pytest.mark.asyncio
async def test_execute_plan_executing_state_triggers_reconciliation(client, db_session):
    """P0-4: EXECUTING 状态 → 触发对账恢复，按 client_order_id 查询交易所。"""
    plan_id = uuid4()
    client_order_id = _stable_client_order_id(plan_id)
    plan = TradePlan(**_make_confirmed_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.EXECUTING.value,
        client_order_id=client_order_id,
        execution_attempts=1,
    ))
    db_session.add(plan)
    await db_session.commit()

    # 对账恢复：交易所找到订单（已成交）
    from exchange_adapter import OrderStatus as ExchangeOrderStatus

    fake_order = MagicMock()
    fake_order.id = "bitget-recovered-001"
    fake_order.status = ExchangeOrderStatus.FILLED
    fake_order.filled_quantity = Decimal("0.5")
    fake_order.average_fill_price = Decimal("62500")

    fake_exchange = MagicMock()
    fake_exchange.get_order = AsyncMock(side_effect=Exception("no exchange_order_id"))
    fake_exchange.get_order_by_client_id = AsyncMock(return_value=fake_order)

    with patch.object(execution_service, "_get_exchange", return_value=fake_exchange):
        resp = await client.post(f"/api/trade-plans/{plan_id}/execute")

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == PlanStatus.FILLED.value
    assert body["exchange_order_id"] == "bitget-recovered-001"
    assert body["filled_quantity"] == "0.5"
    fake_exchange.get_order_by_client_id.assert_called_once_with("BTCUSDT", client_order_id)


# ========================================================================
# P1-27: sync_order_status / cancel_plan_order 测试矩阵
# ========================================================================


def _make_submitted_plan_kwargs(plan_id: UUID | None = None, **overrides) -> dict:
    """生成已提交（SUBMITTED）状态的 plan，带 exchange_order_id。"""
    base = _make_confirmed_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.SUBMITTED.value,
        client_order_id=_stable_client_order_id(plan_id) if plan_id else "plan-test",
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
    from exchange_adapter import OrderStatus as ExchangeOrderStatus

    order = MagicMock()
    order.id = "bitget-order-001"
    # 使用真正的 ExchangeOrderStatus 枚举值，避免 mapping 查找失败返回 UNKNOWN
    order.status = ExchangeOrderStatus(status_value)
    order.filled_quantity = Decimal(filled_quantity)
    order.average_fill_price = Decimal(average_fill_price) if average_fill_price else None
    return order


@pytest.mark.asyncio
async def test_sync_order_status_filled(client, db_session):
    """sync 正常成交：SUBMITTED → FILLED，filled_quantity/average_fill_price 更新，自动创建 journal。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_submitted_plan_kwargs(plan_id=plan_id))
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
    assert body["status"] == PlanStatus.FILLED.value, f"resp={resp.text}"
    assert body["filled_quantity"] == "0.5"
    assert body["average_fill_price"] == "62500"
    fake_exchange.get_order.assert_called_once()


@pytest.mark.asyncio
async def test_sync_order_status_partially_filled(client, db_session):
    """sync 部分成交：SUBMITTED → PARTIALLY_FILLED。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_submitted_plan_kwargs(plan_id=plan_id))
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
    plan = TradePlan(**_make_submitted_plan_kwargs(plan_id=plan_id))
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
    plan = TradePlan(**_make_submitted_plan_kwargs(plan_id=plan_id))
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
    plan = TradePlan(**_make_submitted_plan_kwargs(plan_id=plan_id))
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
    plan = TradePlan(**_make_submitted_plan_kwargs(plan_id=plan_id))
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
    plan = TradePlan(**_make_submitted_plan_kwargs(
        plan_id=plan_id, status=PlanStatus.FILLED.value,
    ))
    db_session.add(plan)
    await db_session.commit()

    fake_exchange = MagicMock()
    fake_exchange.cancel_order = AsyncMock(side_effect=AssertionError(
        "cancel_order should NOT be called for FILLED plan"
    ))

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
    plan = TradePlan(**_make_submitted_plan_kwargs(plan_id=plan_id))
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
