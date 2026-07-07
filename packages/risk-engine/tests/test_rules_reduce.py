from decimal import Decimal
from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import (
    Direction, MarginMode, OpportunityGrade, OrderType, RiskStatus,
)
from shared.schemas import PositionSizingResult, TradePlanInput
from risk_engine.checker import check


def _cfgs():
    return (
        RiskConfig(
            max_risk_percent=Decimal("3"), max_leverage=Decimal("10"),
            min_risk_reward_ratio=Decimal("1.5"), preferred_risk_reward_ratio=Decimal("2.0"),
            min_stop_distance_percent=Decimal("0.3"),  # 0.3%（百分数基）
            daily_loss_limit_r=Decimal("2"),
            max_consecutive_losses=2, cooldown_minutes_after_loss=30,
        ),
        ExecutionConfig(
            enabled=True, mode="dry_run", margin_mode=MarginMode.ISOLATED,
            allowed_order_types=[OrderType.LIMIT], require_stop_loss=True,
            require_user_confirmation=True, require_second_confirmation=True,
        ),
        OpportunityGradeConfig(
            a_max_risk_percent=Decimal("3"), b_max_risk_percent=Decimal("1.5"),
            c_max_risk_percent=Decimal("0"), blocked_max_risk_percent=Decimal("0"),
        ),
    )


def _sizing():
    return PositionSizingResult(
        equity=Decimal("1500"), risk_percent=Decimal("1"), risk_amount=Decimal("15"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"), notional_value=Decimal("1872"),
        raw_size=Decimal("0.03"), rounded_size=Decimal("0.030"),
        required_margin=Decimal("187.2"), leverage=Decimal("10"),
        estimated_fee=Decimal("0.936"), risk_reward_ratio=Decimal("2.8"),
        estimated_loss_at_stop=Decimal("15.936"), sizing_warnings=[],
    )


def _plan(grade=OpportunityGrade.A):
    return TradePlanInput(
        symbol="BTCUSDT", direction=Direction.LONG,
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        risk_percent=Decimal("1"), opportunity_grade=grade, equity=Decimal("1500"),
    )


def test_grade_b_reduces_risk():
    rc, ec, gc = _cfgs()
    r = check(
        sizing_result=_sizing(), risk_config=rc, execution_config=ec,
        opportunity_grade_config=gc, account_risk_state=AccountRiskState(),
        plan=_plan(grade=OpportunityGrade.B), execution_enabled=True,
        kill_switch=False, exchange_connected=False, db_healthy=True,
    )
    assert r.status == RiskStatus.REDUCE_RISK
    assert r.max_allowed_risk_percent == Decimal("1.5")


def test_grade_a_allows():
    rc, ec, gc = _cfgs()
    r = check(
        sizing_result=_sizing(), risk_config=rc, execution_config=ec,
        opportunity_grade_config=gc, account_risk_state=AccountRiskState(),
        plan=_plan(grade=OpportunityGrade.A), execution_enabled=True,
        kill_switch=False, exchange_connected=False, db_healthy=True,
    )
    assert r.status == RiskStatus.ALLOW
    assert r.max_allowed_risk_percent == Decimal("3")


def test_recent_loss_warns():
    rc, ec, gc = _cfgs()
    r = check(
        sizing_result=_sizing(), risk_config=rc, execution_config=ec,
        opportunity_grade_config=gc,
        account_risk_state=AccountRiskState(consecutive_losses=1),
        plan=_plan(grade=OpportunityGrade.A), execution_enabled=True,
        kill_switch=False, exchange_connected=False, db_healthy=True,
    )
    assert r.status == RiskStatus.ALLOW
    assert any("recent_loss" in w or "consecutive" in w for w in r.warnings)
