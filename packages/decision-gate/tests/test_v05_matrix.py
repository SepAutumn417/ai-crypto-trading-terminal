"""v0.5 DecisionGate 矩阵测试 — AI recommendedAction × 风控结果融合。

对应 AI_GUARDRAILS §5.1 合并矩阵。
测试 decision_gate.gate._fuse_with_recommended_action 的 13 个有效组合：
- BLOCK + 任意 → BLOCK（AI 无法覆盖硬风控）
- REDUCE_RISK × 4 种 action
- WARN × 4 种 action
- ALLOW × 4 种 action

另测试向后兼容性：ai_evaluation=None 时按 grade 融合。
"""
from decimal import Decimal

import pytest

from decision_gate.gate import decide
from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import RiskCheckResult


def make_risk_result(status: RiskStatus) -> RiskCheckResult:
    return RiskCheckResult(
        status=status,
        risk_amount=Decimal("100"),
        notional_value=Decimal("1000"),
        required_margin=Decimal("100"),
        risk_reward_ratio=Decimal("2"),
        max_allowed_risk_percent=Decimal("1"),
        warnings=[],
        block_reasons=[],
    )


def make_ai_evaluation(action: str) -> dict:
    """构造带 recommended_action 的 ai_evaluation dict。"""
    return {"recommended_action": action}


# ===== BLOCK: AI 无法覆盖硬风控（4 种 action 均 → BLOCK）=====


@pytest.mark.parametrize(
    "action",
    ["WAIT", "ALLOW_CONFIRM", "REDUCE_RISK", "DO_NOT_TRADE"],
)
def test_block_overrides_any_ai_action(action):
    """BLOCK + 任意 AI action → BLOCK。"""
    r = decide(
        make_risk_result(RiskStatus.BLOCK), True, False,
        ai_evaluation=make_ai_evaluation(action),
    )
    assert r.result == DecisionGateStatus.BLOCK


# ===== REDUCE_RISK 矩阵 =====


def test_reduce_risk_with_do_not_trade_upgrades_to_block():
    """REDUCE_RISK + DO_NOT_TRADE → BLOCK。"""
    r = decide(
        make_risk_result(RiskStatus.REDUCE_RISK), True, False,
        ai_evaluation=make_ai_evaluation("DO_NOT_TRADE"),
    )
    assert r.result == DecisionGateStatus.BLOCK


def test_reduce_risk_with_wait_becomes_wait():
    """REDUCE_RISK + WAIT → WAIT。"""
    r = decide(
        make_risk_result(RiskStatus.REDUCE_RISK), True, False,
        ai_evaluation=make_ai_evaluation("WAIT"),
    )
    assert r.result == DecisionGateStatus.WAIT


def test_reduce_risk_with_allow_confirm_stays_reduce_risk():
    """REDUCE_RISK + ALLOW_CONFIRM → REDUCE_RISK。"""
    r = decide(
        make_risk_result(RiskStatus.REDUCE_RISK), True, False,
        ai_evaluation=make_ai_evaluation("ALLOW_CONFIRM"),
    )
    assert r.result == DecisionGateStatus.REDUCE_RISK


def test_reduce_risk_with_reduce_risk_stays_reduce_risk():
    """REDUCE_RISK + REDUCE_RISK → REDUCE_RISK。"""
    r = decide(
        make_risk_result(RiskStatus.REDUCE_RISK), True, False,
        ai_evaluation=make_ai_evaluation("REDUCE_RISK"),
    )
    assert r.result == DecisionGateStatus.REDUCE_RISK


# ===== WARN 矩阵 =====


def test_warn_with_do_not_trade_becomes_wait():
    """WARN + DO_NOT_TRADE → WAIT。"""
    r = decide(
        make_risk_result(RiskStatus.WARN), True, False,
        ai_evaluation=make_ai_evaluation("DO_NOT_TRADE"),
    )
    assert r.result == DecisionGateStatus.WAIT


def test_warn_with_wait_stays_wait():
    """WARN + WAIT → WAIT。"""
    r = decide(
        make_risk_result(RiskStatus.WARN), True, False,
        ai_evaluation=make_ai_evaluation("WAIT"),
    )
    assert r.result == DecisionGateStatus.WAIT


def test_warn_with_reduce_risk_becomes_wait():
    """WARN + REDUCE_RISK → WAIT。"""
    r = decide(
        make_risk_result(RiskStatus.WARN), True, False,
        ai_evaluation=make_ai_evaluation("REDUCE_RISK"),
    )
    assert r.result == DecisionGateStatus.WAIT


def test_warn_with_allow_confirm_becomes_wait():
    """WARN + ALLOW_CONFIRM → WAIT（风控警告时不能直接确认）。"""
    r = decide(
        make_risk_result(RiskStatus.WARN), True, False,
        ai_evaluation=make_ai_evaluation("ALLOW_CONFIRM"),
    )
    assert r.result == DecisionGateStatus.WAIT


# ===== ALLOW 矩阵 =====


def test_allow_with_do_not_trade_becomes_wait():
    """ALLOW + DO_NOT_TRADE → WAIT。"""
    r = decide(
        make_risk_result(RiskStatus.ALLOW), True, False,
        ai_evaluation=make_ai_evaluation("DO_NOT_TRADE"),
    )
    assert r.result == DecisionGateStatus.WAIT


def test_allow_with_wait_becomes_wait():
    """ALLOW + WAIT → WAIT。"""
    r = decide(
        make_risk_result(RiskStatus.ALLOW), True, False,
        ai_evaluation=make_ai_evaluation("WAIT"),
    )
    assert r.result == DecisionGateStatus.WAIT


def test_allow_with_reduce_risk_becomes_reduce_risk():
    """ALLOW + REDUCE_RISK → REDUCE_RISK。"""
    r = decide(
        make_risk_result(RiskStatus.ALLOW), True, False,
        ai_evaluation=make_ai_evaluation("REDUCE_RISK"),
    )
    assert r.result == DecisionGateStatus.REDUCE_RISK


def test_allow_with_allow_confirm_stays_allow_confirm():
    """ALLOW + ALLOW_CONFIRM → ALLOW_CONFIRM。"""
    r = decide(
        make_risk_result(RiskStatus.ALLOW), True, False,
        ai_evaluation=make_ai_evaluation("ALLOW_CONFIRM"),
    )
    assert r.result == DecisionGateStatus.ALLOW_CONFIRM


# ===== 向后兼容：ai_evaluation=None 时按 grade 融合 =====


def test_backward_compat_allow_becomes_allow_confirm():
    """ai_evaluation=None + ALLOW → ALLOW_CONFIRM（按 grade 融合，无 AI 评估）。"""
    r = decide(make_risk_result(RiskStatus.ALLOW), True, False, ai_evaluation=None)
    assert r.result == DecisionGateStatus.ALLOW_CONFIRM


def test_backward_compat_warn_becomes_wait():
    """ai_evaluation=None + WARN → WAIT。"""
    r = decide(make_risk_result(RiskStatus.WARN), True, False, ai_evaluation=None)
    assert r.result == DecisionGateStatus.WAIT


def test_backward_compat_reduce_risk_stays_reduce_risk():
    """ai_evaluation=None + REDUCE_RISK → REDUCE_RISK。"""
    r = decide(make_risk_result(RiskStatus.REDUCE_RISK), True, False, ai_evaluation=None)
    assert r.result == DecisionGateStatus.REDUCE_RISK


def test_backward_compat_block_stays_block():
    """ai_evaluation=None + BLOCK → BLOCK。"""
    r = decide(make_risk_result(RiskStatus.BLOCK), True, False, ai_evaluation=None)
    assert r.result == DecisionGateStatus.BLOCK
