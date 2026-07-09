"""候选计划状态机。

状态流转（AUTOMATION_DESIGN.md §4）：

    DISCOVERED → WATCHING → READY → RISK_CHECKED → AI_EVALUATED
                → ALLOW_CONFIRM / WAIT / BLOCK / EXPIRED

合法转换规则：
    DISCOVERED  → WATCHING, EXPIRED
    WATCHING    → READY, WAIT, EXPIRED
    READY       → RISK_CHECKED, WAIT, EXPIRED
    RISK_CHECKED → AI_EVALUATED, BLOCK, WAIT, EXPIRED
    AI_EVALUATED → ALLOW_CONFIRM, WAIT, BLOCK, EXPIRED
    ALLOW_CONFIRM → (终态，等待用户 promote 或 EXPIRED)
    WAIT        → READY (重新进入), EXPIRED
    BLOCK       → (终态)
    EXPIRED     → (终态)
"""
from __future__ import annotations

from .types import CandidateStatus

# 合法的状态转换映射
_TRANSITIONS: dict[CandidateStatus, set[CandidateStatus]] = {
    CandidateStatus.DISCOVERED: {
        CandidateStatus.WATCHING,
        CandidateStatus.EXPIRED,
    },
    CandidateStatus.WATCHING: {
        CandidateStatus.READY,
        CandidateStatus.WAIT,
        CandidateStatus.EXPIRED,
    },
    CandidateStatus.READY: {
        CandidateStatus.RISK_CHECKED,
        CandidateStatus.WAIT,
        CandidateStatus.EXPIRED,
    },
    CandidateStatus.RISK_CHECKED: {
        CandidateStatus.AI_EVALUATED,
        CandidateStatus.BLOCK,
        CandidateStatus.WAIT,
        CandidateStatus.EXPIRED,
    },
    CandidateStatus.AI_EVALUATED: {
        CandidateStatus.ALLOW_CONFIRM,
        CandidateStatus.WAIT,
        CandidateStatus.BLOCK,
        CandidateStatus.EXPIRED,
    },
    CandidateStatus.ALLOW_CONFIRM: {
        CandidateStatus.EXPIRED,  # 等待太久过期
    },
    CandidateStatus.WAIT: {
        CandidateStatus.READY,    # 条件重新满足
        CandidateStatus.EXPIRED,
    },
    CandidateStatus.BLOCK: set(),      # 终态
    CandidateStatus.EXPIRED: set(),    # 终态
}

# 终态集合
TERMINAL_STATUSES = frozenset({CandidateStatus.BLOCK, CandidateStatus.EXPIRED})

# 可 promote 的状态（对应 AUTOMATION_DESIGN.md §9）
PROMOTABLE_STATUSES = frozenset({
    CandidateStatus.READY,
    CandidateStatus.RISK_CHECKED,
    CandidateStatus.AI_EVALUATED,
    CandidateStatus.ALLOW_CONFIRM,
})


def can_transition(current: CandidateStatus, target: CandidateStatus) -> bool:
    """检查状态转换是否合法。"""
    return target in _TRANSITIONS.get(current, set())


def transition(current: CandidateStatus, target: CandidateStatus) -> CandidateStatus:
    """执行状态转换。

    如果转换不合法，抛出 ValueError。
    """
    if not can_transition(current, target):
        raise ValueError(
            f"非法状态转换：{current.value} → {target.value}。"
            f"合法目标状态：{[s.value for s in _TRANSITIONS.get(current, set())]}"
        )
    return target


def is_terminal(status: CandidateStatus) -> bool:
    """检查是否为终态。"""
    return status in TERMINAL_STATUSES


def is_promotable(status: CandidateStatus) -> bool:
    """检查候选计划是否可 promote 为正式交易计划。"""
    return status in PROMOTABLE_STATUSES


def get_allowed_transitions(status: CandidateStatus) -> set[CandidateStatus]:
    """获取当前状态的合法后续状态集合。"""
    return _TRANSITIONS.get(status, set()).copy()
