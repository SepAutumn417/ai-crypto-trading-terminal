from shared.enums import (
    ConfigType, DecisionGateStatus, Direction, MarginMode,
    OpportunityGrade, PlanStatus, RiskStatus,
)


def test_direction_values():
    assert Direction.LONG.value == "LONG"
    assert Direction.SHORT.value == "SHORT"


def test_opportunity_grade_values():
    assert OpportunityGrade.A.value == "A"
    assert OpportunityGrade.BLOCKED.value == "BLOCKED"


def test_risk_status_values():
    assert RiskStatus.ALLOW.value == "ALLOW"
    assert RiskStatus.REDUCE_RISK.value == "REDUCE_RISK"
    assert RiskStatus.BLOCK.value == "BLOCK"


def test_decision_gate_status_values():
    assert DecisionGateStatus.ALLOW_CONFIRM.value == "ALLOW_CONFIRM"
    assert DecisionGateStatus.EXPIRED.value == "EXPIRED"


def test_plan_status_values():
    assert PlanStatus.DRAFT.value == "DRAFT"
    assert PlanStatus.READY_FOR_CONFIRMATION.value == "READY_FOR_CONFIRMATION"


def test_config_type_values():
    assert ConfigType.RISK.value == "risk"
    assert ConfigType.SYMBOL_RULES.value == "symbol_rules"
