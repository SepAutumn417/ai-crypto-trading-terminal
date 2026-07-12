from decimal import Decimal

from decision_gate.gate import decide
from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import RiskCheckResult


def _risk(status: RiskStatus) -> RiskCheckResult:
    return RiskCheckResult(
        status=status, risk_amount=Decimal("15"), notional_value=Decimal("1872"),
        required_margin=Decimal("187.2"), risk_reward_ratio=Decimal("2.8"),
        max_allowed_risk_percent=Decimal("3"), warnings=[], block_reasons=[],
        risk_config_version="risk-v1",
    )


def _ai(grade: str) -> dict:
    return {"grade": grade, "overall_score": Decimal("60"), "symbol": "BTCUSDT", "direction": "LONG"}


# ===== 原有测试（无 AI 评估时保持原行为）=====

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


# ===== AI 融合测试 =====

def test_ai_grade_f_blocks_allow():
    """AI F + 风控 ALLOW → BLOCK"""
    r = decide(_risk(RiskStatus.ALLOW), True, False, ai_evaluation=_ai("F"))
    assert r.result == DecisionGateStatus.BLOCK
    assert any("ai_fusion" in x for x in r.reasons)


def test_ai_grade_d_downgrades_allow_to_wait():
    """AI D + 风控 ALLOW → WAIT"""
    r = decide(_risk(RiskStatus.ALLOW), True, False, ai_evaluation=_ai("D"))
    assert r.result == DecisionGateStatus.WAIT
    assert any("ai_fusion" in x for x in r.reasons)


def test_ai_grade_a_keeps_allow_confirm():
    """AI A + 风控 ALLOW → ALLOW_CONFIRM"""
    r = decide(_risk(RiskStatus.ALLOW), True, False, ai_evaluation=_ai("A"))
    assert r.result == DecisionGateStatus.ALLOW_CONFIRM


def test_ai_grade_c_keeps_allow_confirm():
    """AI C + 风控 ALLOW → ALLOW_CONFIRM"""
    r = decide(_risk(RiskStatus.ALLOW), True, False, ai_evaluation=_ai("C"))
    assert r.result == DecisionGateStatus.ALLOW_CONFIRM


def test_ai_grade_f_with_warn_upgrades_to_block():
    """AI F + 风控 WARN → BLOCK"""
    r = decide(_risk(RiskStatus.WARN), True, False, ai_evaluation=_ai("F"))
    assert r.result == DecisionGateStatus.BLOCK


def test_ai_grade_a_with_warn_keeps_wait():
    """AI A + 风控 WARN → WAIT（AI 好评不覆盖风控警告）"""
    r = decide(_risk(RiskStatus.WARN), True, False, ai_evaluation=_ai("A"))
    assert r.result == DecisionGateStatus.WAIT


def test_ai_does_not_override_block():
    """AI A + 风控 BLOCK → BLOCK（AI 无法覆盖硬风控）"""
    r = decide(_risk(RiskStatus.BLOCK), True, False, ai_evaluation=_ai("A"))
    assert r.result == DecisionGateStatus.BLOCK


def test_ai_does_not_override_reduce_risk():
    """AI A + 风控 REDUCE_RISK → REDUCE_RISK"""
    r = decide(_risk(RiskStatus.REDUCE_RISK), True, False, ai_evaluation=_ai("A"))
    assert r.result == DecisionGateStatus.REDUCE_RISK


def test_ai_grade_b_keeps_allow_confirm():
    """AI B + 风控 ALLOW → ALLOW_CONFIRM"""
    r = decide(_risk(RiskStatus.ALLOW), True, False, ai_evaluation=_ai("B"))
    assert r.result == DecisionGateStatus.ALLOW_CONFIRM


def test_ai_grade_d_with_warn_upgrades_to_block():
    """AI D + 风控 WARN → BLOCK"""
    r = decide(_risk(RiskStatus.WARN), True, False, ai_evaluation=_ai("D"))
    assert r.result == DecisionGateStatus.BLOCK


def test_block_reasons_preserved_when_blocked():
    """风控 BLOCK 时 block_reasons 被保留在 reasons 中"""
    risk = RiskCheckResult(
        status=RiskStatus.BLOCK, risk_amount=Decimal("15"), notional_value=Decimal("1872"),
        required_margin=Decimal("187.2"), risk_reward_ratio=Decimal("2.8"),
        max_allowed_risk_percent=Decimal("3"), warnings=[],
        block_reasons=["max_leverage_exceeded", "daily_loss_limit"],
        risk_config_version="risk-v1",
    )
    r = decide(risk, True, False, ai_evaluation=_ai("A"))
    assert r.result == DecisionGateStatus.BLOCK
    assert "max_leverage_exceeded" in r.reasons
    assert "daily_loss_limit" in r.reasons
