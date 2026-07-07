from datetime import datetime, timedelta, timezone
from decimal import Decimal

from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import (
    Direction, MarginMode, OpportunityGrade, OrderType, RiskStatus,
)
from shared.schemas import PositionSizingResult, TradePlanInput

from risk_engine.checker import check


def _risk_config(**kw):
    defaults = dict(
        max_risk_percent=Decimal("3"), max_leverage=Decimal("10"),
        min_risk_reward_ratio=Decimal("1.5"), preferred_risk_reward_ratio=Decimal("2.0"),
        min_stop_distance_percent=Decimal("0.3"),  # 0.3%（百分数基）
        daily_loss_limit_r=Decimal("2"),
        max_consecutive_losses=2, cooldown_minutes_after_loss=30,
    )
    defaults.update(kw)
    return RiskConfig(**defaults)


def _exec_config():
    return ExecutionConfig(
        enabled=True, mode="dry_run", margin_mode=MarginMode.ISOLATED,
        allowed_order_types=[OrderType.LIMIT], require_stop_loss=True,
        require_user_confirmation=True, require_second_confirmation=True,
    )


def _grade_config():
    return OpportunityGradeConfig(
        a_max_risk_percent=Decimal("3"), b_max_risk_percent=Decimal("1.5"),
        c_max_risk_percent=Decimal("0"), blocked_max_risk_percent=Decimal("0"),
    )


def _account(**kw):
    return AccountRiskState(**{**dict(
        daily_loss_r=Decimal("0"), consecutive_losses=0,
        cooldown_until=None, last_trade_date=None,
    ), **kw})


def _sizing(**kw):
    return PositionSizingResult(**{**dict(
        equity=Decimal("1500"), risk_percent=Decimal("1"), risk_amount=Decimal("15"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"), notional_value=Decimal("1872"),
        raw_size=Decimal("0.03"), rounded_size=Decimal("0.030"),
        required_margin=Decimal("187.2"), leverage=Decimal("10"),
        estimated_fee=Decimal("0.936"), risk_reward_ratio=Decimal("2.8"),
        estimated_loss_at_stop=Decimal("15.936"), sizing_warnings=[],
    ), **kw})


def _plan(**kw):
    return TradePlanInput(**{**dict(
        symbol="BTCUSDT", direction=Direction.LONG,
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        risk_percent=Decimal("1"), opportunity_grade=OpportunityGrade.A,
        equity=Decimal("1500"),
    ), **kw})


def _run(plan=None, sizing=None, account=None, kill_switch=False, db_healthy=True):
    return check(
        sizing_result=sizing or _sizing(),
        risk_config=_risk_config(), execution_config=_exec_config(),
        opportunity_grade_config=_grade_config(),
        account_risk_state=account or _account(),
        plan=plan or _plan(),
        execution_enabled=True, kill_switch=kill_switch,
        exchange_connected=False, db_healthy=db_healthy,
    )


def test_no_stop_loss_blocks():
    r = _run(plan=_plan(stop_loss_price=None), sizing=_sizing(stop_loss_price=None, stop_distance_percent=Decimal("0")))
    assert r.status == RiskStatus.BLOCK
    assert any("no_stop_loss" in x for x in r.block_reasons)


def test_excessive_leverage_blocks():
    r = _run(plan=_plan(leverage=Decimal("20")), sizing=_sizing(leverage=Decimal("20")))
    assert r.status == RiskStatus.BLOCK


def test_low_rr_blocks():
    r = _run(sizing=_sizing(risk_reward_ratio=Decimal("1.0")))
    assert r.status == RiskStatus.BLOCK


def test_daily_loss_limit_blocks():
    r = _run(account=_account(daily_loss_r=Decimal("2")))
    assert r.status == RiskStatus.BLOCK


def test_consecutive_losses_blocks():
    r = _run(account=_account(consecutive_losses=2))
    assert r.status == RiskStatus.BLOCK


def test_cooldown_blocks():
    future = datetime.now(timezone.utc) + timedelta(minutes=20)
    r = _run(account=_account(cooldown_until=future))
    assert r.status == RiskStatus.BLOCK


def test_kill_switch_blocks():
    r = _run(kill_switch=True)
    assert r.status == RiskStatus.BLOCK


def test_blocked_grade_blocks():
    r = _run(plan=_plan(opportunity_grade=OpportunityGrade.BLOCKED))
    assert r.status == RiskStatus.BLOCK


def test_c_grade_blocks():
    r = _run(plan=_plan(opportunity_grade=OpportunityGrade.C))
    assert r.status == RiskStatus.BLOCK


def test_db_unhealthy_blocks():
    r = _run(db_healthy=False)
    assert r.status == RiskStatus.BLOCK


def test_excessive_risk_percent_blocks():
    r = _run(plan=_plan(risk_percent=Decimal("5")), sizing=_sizing(risk_percent=Decimal("5")))
    assert r.status == RiskStatus.BLOCK


def test_below_min_size_blocks():
    r = _run(sizing=_sizing(rounded_size=None, sizing_warnings=["below_min_size: ..."]))
    assert r.status == RiskStatus.BLOCK


def test_min_stop_distance_unit_is_percent_basis():
    """守恒测试：min_stop_distance_percent 是百分数基（如 0.3 表示 0.3%），与
    sizing.stop_distance_percent 小数（0.008 = 0.8%）进行 *100 单位换算后比较。

    修复前：代码用 stop_dist_pct=0.008 *100=0.8 与 min=0.3 比较 → 永远不会触发 block。
    修复后：单位换算正确，止损距离 < 0.3% 应 BLOCK。
    """
    # 止损距离 0.05% < 0.3% → 应 BLOCK
    r = _run(
        plan=_plan(stop_loss_price=Decimal("62399.68")),
        sizing=_sizing(stop_loss_price=Decimal("62399.68"), stop_distance_percent=Decimal("0.0005")),
    )
    assert r.status == RiskStatus.BLOCK
    assert any("stop_distance_too_small" in x for x in r.block_reasons)


def test_min_stop_distance_above_threshold_does_not_block():
    """止损距离（0.8%）大于阈值（0.3%）时不应被 BLOCK。"""
    # stop_distance_percent=0.008 = 0.8% > 0.3%
    r = _run(sizing=_sizing(stop_distance_percent=Decimal("0.008")))
    assert not any("stop_distance_too_small" in x for x in r.block_reasons)


def test_notional_equity_ratio_exceeded_blocks():
    """名义价值/权益比超过上限时应 BLOCK。"""
    # notional=35000, equity=1500 → ratio≈23.3 > 20 → BLOCK
    r = _run(
        sizing=_sizing(
            notional_value=Decimal("35000"),
            equity=Decimal("1500"),
        ),
    )
    assert r.status == RiskStatus.BLOCK
    assert any("notional_equity_ratio_exceeded" in x for x in r.block_reasons)


def test_notional_equity_ratio_below_threshold_does_not_block():
    """名义价值/权益比在阈值内时不应因该规则 BLOCK。"""
    # notional=1872, equity=1500 → ratio≈1.25 < 20
    r = _run()
    assert not any("notional_equity_ratio_exceeded" in x for x in r.block_reasons)
