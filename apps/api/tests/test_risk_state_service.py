"""P1-1: 风控状态更新服务测试。

测试矩阵：
1. test_loss_updates_risk_state — 亏损平仓 → consecutive_losses +1, daily_loss_r 增加, cooldown 设置
2. test_win_resets_consecutive_losses — 盈利平仓 → consecutive_losses 重置为 0
3. test_daily_loss_limit_triggers_kill_switch — 日亏损超限 → 自动触发 Kill Switch
4. test_consecutive_loss_limit_triggers_kill_switch — 连续亏损超限 → 自动触发 Kill Switch
5. test_new_day_resets_daily_loss — 交易日切换 → daily_loss_r 重置
6. test_journal_close_via_api_updates_risk_state — 通过 API 平仓 → 风控状态更新
"""
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import (
    AccountRiskState,
    PositionSizingResult,
    TradeJournal,
    TradePlan,
    UserSettings,
)
from shared.enums import Direction, MarginMode, OpportunityGrade, PlanStatus


def _make_plan_kwargs(plan_id: UUID, **overrides) -> dict:
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
        "status": PlanStatus.FILLED.value,
    }
    base.update(overrides)
    if "id" not in base:
        base["id"] = plan_id
    return base


async def _create_filled_journal(
    db_session,
    plan_id: UUID,
    pnl: Decimal,
    risk_amount: Decimal = Decimal("15"),
) -> TradeJournal:
    """创建一个已平仓的 trade journal，带关联的 plan 和 sizing result。"""
    plan = TradePlan(**_make_plan_kwargs(plan_id))
    db_session.add(plan)
    # 先 flush 确保 plan 被插入，避免 PositionSizingResult 外键违反
    await db_session.flush()

    sizing = PositionSizingResult(
        trade_plan_id=plan_id,
        equity=Decimal("1500"),
        risk_percent=Decimal("1"),
        risk_amount=risk_amount,
        entry_price=Decimal("62400"),
        stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"),
        notional_value=Decimal("750"),
        raw_size=Decimal("0.512"),
        rounded_size=Decimal("0.5"),
        required_margin=Decimal("75"),
        leverage=Decimal("10"),
        estimated_fee=Decimal("0.75"),
        risk_reward_ratio=Decimal("2.8"),
        estimated_loss_at_stop=risk_amount,
        sizing_warnings=[],
        is_latest=True,
    )
    db_session.add(sizing)

    journal = TradeJournal(
        trade_plan_id=plan_id,
        exchange="bitget",
        symbol="BTCUSDT",
        direction=Direction.LONG.value,
        entry_price=Decimal("62400"),
        exit_price=Decimal("62000"),
        quantity=Decimal("0.5"),
        leverage=Decimal("10"),
        pnl=pnl,
        pnl_percent=Decimal("-1.5"),
        status="CLOSED",
        entry_at=datetime.now(UTC),
        exit_at=datetime.now(UTC),
    )
    db_session.add(journal)
    await db_session.commit()
    await db_session.refresh(journal)
    return journal


@pytest.mark.asyncio
async def test_loss_updates_risk_state(client, db_session):
    """P1-1: 亏损平仓 → consecutive_losses +1, daily_loss_r 增加, cooldown 设置。"""
    from app.services.risk_state_service import update_risk_state_on_close

    plan_id = uuid4()
    journal = await _create_filled_journal(db_session, plan_id, pnl=Decimal("-15"))

    await update_risk_state_on_close(db_session, journal)

    state = await db_session.get(AccountRiskState, 1)
    assert state.consecutive_losses == 1
    assert state.daily_loss_r == Decimal("1")  # -15/15 = -1R → |R| = 1
    assert state.cooldown_until is not None
    assert state.cooldown_until > datetime.now(UTC)


@pytest.mark.asyncio
async def test_win_resets_consecutive_losses(client, db_session):
    """P1-1: 盈利平仓 → consecutive_losses 重置为 0。"""
    from app.services.risk_state_service import update_risk_state_on_close

    # 先设置 consecutive_losses=1
    state = await db_session.get(AccountRiskState, 1)
    state.consecutive_losses = 1
    state.daily_loss_r = Decimal("0.5")
    await db_session.commit()

    plan_id = uuid4()
    journal = await _create_filled_journal(db_session, plan_id, pnl=Decimal("30"))

    await update_risk_state_on_close(db_session, journal)

    state = await db_session.get(AccountRiskState, 1)
    assert state.consecutive_losses == 0
    # daily_loss_r 不因盈利减少（仅亏损累加）
    assert state.daily_loss_r == Decimal("0.5")


@pytest.mark.asyncio
async def test_daily_loss_limit_triggers_kill_switch(client, db_session):
    """P1-1: 日亏损超限 → 自动触发 Kill Switch。"""
    from app.services.risk_state_service import update_risk_state_on_close

    # seed: daily_loss_limit_r=2, 设置已亏损 1.5R
    state = await db_session.get(AccountRiskState, 1)
    state.daily_loss_r = Decimal("1.5")
    state.consecutive_losses = 1
    await db_session.commit()

    # 亏损 1R → daily_loss_r 达到 2.5R > 2R limit
    plan_id = uuid4()
    journal = await _create_filled_journal(db_session, plan_id, pnl=Decimal("-15"))

    await update_risk_state_on_close(db_session, journal)

    # Kill Switch 应被激活
    settings = await db_session.get(UserSettings, 1)
    assert settings.kill_switch is True
    assert settings.execution_enabled is False


@pytest.mark.asyncio
async def test_consecutive_loss_limit_triggers_kill_switch(client, db_session):
    """P1-1: 连续亏损超限 → 自动触发 Kill Switch。"""
    from app.services.risk_state_service import update_risk_state_on_close

    # seed: max_consecutive_losses=2, 设置已有 1 次连续亏损
    state = await db_session.get(AccountRiskState, 1)
    state.consecutive_losses = 1
    state.daily_loss_r = Decimal("0")
    await db_session.commit()

    # 再亏损 → consecutive_losses=2 >= max=2
    plan_id = uuid4()
    journal = await _create_filled_journal(db_session, plan_id, pnl=Decimal("-15"))

    await update_risk_state_on_close(db_session, journal)

    settings = await db_session.get(UserSettings, 1)
    assert settings.kill_switch is True


@pytest.mark.asyncio
async def test_new_day_resets_daily_loss(client, db_session):
    """P1-1: 交易日切换 → daily_loss_r 和 consecutive_losses 重置。"""
    from app.services.risk_state_service import reset_daily_loss_if_new_day

    state = await db_session.get(AccountRiskState, 1)
    state.daily_loss_r = Decimal("1.5")
    state.consecutive_losses = 2
    state.last_trade_date = date.today() - timedelta(days=1)
    await db_session.commit()

    reset = await reset_daily_loss_if_new_day(db_session)

    assert reset is True
    state = await db_session.get(AccountRiskState, 1)
    assert state.daily_loss_r == Decimal("0")
    assert state.consecutive_losses == 0


@pytest.mark.asyncio
async def test_same_day_no_reset(client, db_session):
    """P1-1: 同一天不重置 daily_loss_r。"""
    from app.services.risk_state_service import reset_daily_loss_if_new_day

    state = await db_session.get(AccountRiskState, 1)
    state.daily_loss_r = Decimal("1.5")
    state.last_trade_date = date.today()
    await db_session.commit()

    reset = await reset_daily_loss_if_new_day(db_session)

    assert reset is False
    state = await db_session.get(AccountRiskState, 1)
    assert state.daily_loss_r == Decimal("1.5")


@pytest.mark.asyncio
async def test_journal_close_via_api_updates_risk_state(client, db_session):
    """P1-1: 通过 API 平仓 journal → 风控状态自动更新。"""
    # 先解除 kill_switch
    await client.post("/api/system/kill-switch", json={"enabled": False, "reason": "测试前置"})

    # 创建 journal
    create_resp = await client.post("/api/journals", json={
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": "65000.0",
        "quantity": "0.1",
        "leverage": "10",
    })
    journal_id = create_resp.json()["data"]["id"]

    # 平仓（亏损）
    resp = await client.put(f"/api/journals/{journal_id}", json={
        "exit_price": "64000.0",
        "pnl": "-50.0",
        "pnl_percent": "-0.77",
        "status": "CLOSED",
        "exit_reason": "Stop loss hit",
    })
    assert resp.status_code == 200

    # 验证风控状态更新
    state = await db_session.get(AccountRiskState, 1)
    # journal 没有 trade_plan_id，risk_amount=None，亏损按 1R 估算
    assert state.consecutive_losses == 1
    assert state.daily_loss_r == Decimal("1")
    assert state.cooldown_until is not None
