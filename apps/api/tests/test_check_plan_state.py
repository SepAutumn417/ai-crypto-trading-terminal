"""PR-2: check_plan 状态前置检查 + is_latest 唯一索引 的单测。

TDD 纪律：先写测试看到失败，再写实现。

测试矩阵（3 条）：
1. test_check_plan_rejects_submitted_status — SUBMITTED 状态被 check → 409 PLAN_NOT_RECHECKABLE
2. test_check_plan_sets_is_latest — 二次 check 后新记录 is_latest=true，旧记录 is_latest=false
3. test_check_plan_rejects_filled_status — FILLED 状态被 check → 409
"""
import pytest
from decimal import Decimal
from uuid import uuid4, UUID

from sqlalchemy import select

from app.exceptions import AppException
from app.models import (
    DecisionGateResult as DecisionGateResultModel,
    PositionSizingResult as PositionSizingResultModel,
    RiskCheck as RiskCheckModel,
    TradePlan,
)
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
        "status": PlanStatus.DRAFT.value,
    }
    base.update(overrides)
    if plan_id is not None:
        base["id"] = plan_id
    return base


@pytest.mark.asyncio
async def test_check_plan_rejects_submitted_status(client, db_session):
    """SUBMITTED 状态被 check → 409 PLAN_NOT_RECHECKABLE。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.SUBMITTED.value,
    ))
    db_session.add(plan)
    await db_session.commit()

    resp = await client.post(f"/api/trade-plans/{plan_id}/check")

    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["error"]["code"] == "PLAN_NOT_RECHECKABLE"

    # plan 状态不变
    fresh = await db_session.get(TradePlan, plan_id)
    assert fresh.status == PlanStatus.SUBMITTED.value


@pytest.mark.asyncio
async def test_check_plan_rejects_filled_status(client, db_session):
    """FILLED 状态被 check → 409。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_plan_kwargs(
        plan_id=plan_id,
        status=PlanStatus.FILLED.value,
    ))
    db_session.add(plan)
    await db_session.commit()

    resp = await client.post(f"/api/trade-plans/{plan_id}/check")

    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["error"]["code"] == "PLAN_NOT_RECHECKABLE"


@pytest.mark.asyncio
async def test_check_plan_sets_is_latest(client, db_session):
    """二次 check 后新记录 is_latest=true，旧记录 is_latest=false。"""
    plan_id = uuid4()
    plan = TradePlan(**_make_plan_kwargs(plan_id=plan_id))
    db_session.add(plan)
    await db_session.commit()

    # 第一次 check
    resp1 = await client.post(f"/api/trade-plans/{plan_id}/check")
    assert resp1.status_code == 200, resp1.text

    # 查第一次 check 的 sizing 记录
    q = select(PositionSizingResultModel).where(
        PositionSizingResultModel.trade_plan_id == plan_id
    )
    result = await db_session.execute(q)
    first_sizing = result.scalars().first()
    assert first_sizing is not None
    assert first_sizing.is_latest is True

    # 把 plan 状态改回 DRAFT 以允许二次 check
    plan_db = await db_session.get(TradePlan, plan_id)
    plan_db.status = PlanStatus.DRAFT.value
    await db_session.commit()

    # 第二次 check
    resp2 = await client.post(f"/api/trade-plans/{plan_id}/check")
    assert resp2.status_code == 200, resp2.text

    # 刷新旧记录
    await db_session.refresh(first_sizing)
    assert first_sizing.is_latest is False, "旧记录 is_latest 应为 False"

    # 查新记录
    q2 = select(PositionSizingResultModel).where(
        PositionSizingResultModel.trade_plan_id == plan_id,
        PositionSizingResultModel.is_latest == True,  # noqa: E712
    )
    result2 = await db_session.execute(q2)
    latest_sizing = result2.scalars().first()
    assert latest_sizing is not None, "应有一条 is_latest=True 的新记录"
    assert latest_sizing.id != first_sizing.id