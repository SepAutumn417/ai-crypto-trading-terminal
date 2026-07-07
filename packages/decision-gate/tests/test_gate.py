from decimal import Decimal
from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import RiskCheckResult
from decision_gate.gate import decide


def _risk(status: RiskStatus) -> RiskCheckResult:
    return RiskCheckResult(
        status=status, risk_amount=Decimal("15"), notional_value=Decimal("1872"),
        required_margin=Decimal("187.2"), risk_reward_ratio=Decimal("2.8"),
        max_allowed_risk_percent=Decimal("3"), warnings=[], block_reasons=[],
        risk_config_version="risk-v1",
    )


def test_allow_becomes_allow_confirm():
    assert decide(_risk(RiskStatus.ALLOW), True, False).result == DecisionGateStatus.ALLOW_CONFIRM


def test_reduce_risk_passes_through():
    assert decide(_risk(RiskStatus.REDUCE_RISK), True, False).result == DecisionGateStatus.REDUCE_RISK


def test_block_passes_through():
    assert decide(_risk(RiskStatus.BLOCK), True, False).result == DecisionGateStatus.BLOCK


def test_execution_disabled_blocks():
    r = decide(_risk(RiskStatus.ALLOW), False, False)
    assert r.result == DecisionGateStatus.BLOCK
    assert any("execution_disabled" in x for x in r.reasons)


def test_kill_switch_blocks():
    r = decide(_risk(RiskStatus.ALLOW), True, True)
    assert r.result == DecisionGateStatus.BLOCK
    assert any("kill_switch" in x for x in r.reasons)


def test_expired():
    assert decide(_risk(RiskStatus.ALLOW), True, False, plan_expired=True).result == DecisionGateStatus.EXPIRED


def test_warn_becomes_wait():
    assert decide(_risk(RiskStatus.WARN), True, False).result == DecisionGateStatus.WAIT