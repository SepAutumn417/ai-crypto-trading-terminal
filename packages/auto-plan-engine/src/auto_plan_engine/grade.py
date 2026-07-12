"""机会评级逻辑。

根据结构信号强度、BOS/CHOCH 质量、波动率、盈亏比等维度
对候选计划进行 A/B/C/BLOCKED 评级。

评级规则（参考 RISK_RULES.md §8）：
- A: 结构清晰、趋势明确、盈亏比优秀 → 可直接进入确认
- B: 结构一般、有不确定因素 → 降低风险，观察或小风险确认
- C: 结构较弱、信号不充分 → 仅观察
- BLOCKED: 禁交易区域或风控禁止
"""
from __future__ import annotations

from decimal import Decimal

from market_structure import MarketState, StructureSnapshot, TrendDirection

from .types import CandidateDirection, CandidatePlan, SetupType

# 评级阈值
MIN_RR_FOR_A = Decimal("2.0")   # A 级最低盈亏比
MIN_RR_FOR_B = Decimal("1.5")   # B 级最低盈亏比
MIN_RR_FOR_C = Decimal("1.0")   # C 级最低盈亏比


def grade_opportunity(
    candidate: CandidatePlan,
    snapshot: StructureSnapshot,
) -> str:
    """对候选计划进行机会评级。

    返回 'A' / 'B' / 'C' / 'BLOCKED'。

    评级维度：
    1. 禁交易区域检查（BLOCKED 一票否决）
    2. 趋势一致性：计划方向与市场趋势一致加分
    3. BOS/CHOCH 信号质量：近期事件数量和方向
    4. 波动率状态：极端波动降级
    5. 盈亏比：RR 越高评级越高
    6. setup_type 可靠性：不同形态有不同基础分
    """
    # 1. 禁交易区域检查
    if _is_in_no_trade_zone(candidate, snapshot):
        return "BLOCKED"

    score = 0  # 基础分 0-100

    # 2. 趋势一致性（+20 / -10）
    trend_bonus = _trend_consistency_score(candidate, snapshot)
    score += trend_bonus

    # 3. BOS/CHOCH 信号质量（+0~25）
    score += _structure_event_score(candidate, snapshot)

    # 4. 波动率状态（-10~0）
    score += _volatility_score(snapshot)

    # 5. 盈亏比（+0~30）
    score += _risk_reward_score(candidate)

    # 6. setup_type 基础分（+10~20）
    score += _setup_type_base_score(candidate.setup_type)

    # 综合评级
    return _score_to_grade(score, candidate)


def _is_in_no_trade_zone(candidate: CandidatePlan, snapshot: StructureSnapshot) -> bool:
    """检查入场价是否在禁交易区域内。"""
    if not snapshot.no_trade_zones:
        return False
    entry = candidate.entry_price
    if entry is None:
        entry = (candidate.entry_zone_upper + candidate.entry_zone_lower) / 2
    for zone in snapshot.no_trade_zones:
        if zone.lower <= entry <= zone.upper:
            return True
    return False


def _trend_consistency_score(
    candidate: CandidatePlan,
    snapshot: StructureSnapshot,
) -> int:
    """趋势一致性评分。

    计划方向与市场趋势一致 +20，不一致 -10，中性 0。
    """
    if snapshot.market_state != MarketState.TREND:
        return 0  # 震荡市不适用趋势一致性

    if snapshot.trend_direction == TrendDirection.BULLISH:
        return 20 if candidate.direction == CandidateDirection.LONG else -10
    elif snapshot.trend_direction == TrendDirection.BEARISH:
        return 20 if candidate.direction == CandidateDirection.SHORT else -10
    return 0


def _structure_event_score(
    candidate: CandidatePlan,
    snapshot: StructureSnapshot,
) -> int:
    """BOS/CHOCH 信号质量评分（0-25）。

    近期有同方向 BOS 加分，有 CHOCH 反转信号加分（如果计划方向与 CHOCH 一致）。
    """
    score = 0

    # 同方向 BOS 事件（趋势延续信号）
    for bos in snapshot.bos_events[-3:]:  # 最近 3 个 BOS
        if candidate.direction == CandidateDirection.LONG and bos.direction == TrendDirection.BULLISH:
            score += 8
        elif candidate.direction == CandidateDirection.SHORT and bos.direction == TrendDirection.BEARISH:
            score += 8

    # CHOCH 反转信号（如果计划方向与 CHOCH 方向一致）
    for choch in snapshot.choch_events[-2:]:  # 最近 2 个 CHOCH
        if candidate.direction == CandidateDirection.LONG and choch.direction == TrendDirection.BULLISH:
            score += 9
        elif candidate.direction == CandidateDirection.SHORT and choch.direction == TrendDirection.BEARISH:
            score += 9

    return min(score, 25)


def _volatility_score(snapshot: StructureSnapshot) -> int:
    """波动率评分。

    高波动降 10 分，低波动降 5 分（机会不足），正常 0。
    """
    if snapshot.volatility_state == "high":
        return -10
    elif snapshot.volatility_state == "low":
        return -5
    return 0


def _risk_reward_score(candidate: CandidatePlan) -> int:
    """盈亏比评分（0-30）。

    RR >= 3.0 → 30
    RR >= 2.0 → 25
    RR >= 1.5 → 18
    RR >= 1.0 → 10
    RR < 1.0  → 0
    """
    rr = candidate.risk_reward_ratio
    if rr is None:
        return 0
    if rr >= Decimal("3.0"):
        return 30
    elif rr >= Decimal("2.0"):
        return 25
    elif rr >= Decimal("1.5"):
        return 18
    elif rr >= Decimal("1.0"):
        return 10
    return 0


def _setup_type_base_score(setup_type: SetupType) -> int:
    """不同 setupType 的基础可靠性分（10-20）。

    趋势回踩和突破回踩类更可靠（20），震荡类次之（15），假突破类风险较高（10）。
    """
    high_reliability = {
        SetupType.TREND_PULLBACK_LONG,
        SetupType.TREND_PULLBACK_SHORT,
        SetupType.BREAKOUT_RETEST_LONG,
        SetupType.BREAKDOWN_RETEST_SHORT,
    }
    medium_reliability = {
        SetupType.RANGE_SUPPORT_BOUNCE,
        SetupType.RANGE_RESISTANCE_REJECT,
    }

    if setup_type in high_reliability:
        return 20
    elif setup_type in medium_reliability:
        return 15
    return 10  # FALSE_BREAK_REVERSAL


def _score_to_grade(score: int, candidate: CandidatePlan) -> str:
    """将综合评分转换为评级。

    score >= 75 → A
    score >= 55 → B
    score >= 35 → C
    score < 35  → BLOCKED（信号太弱）
    """
    if score >= 75:
        return "A"
    elif score >= 55:
        return "B"
    elif score >= 35:
        return "C"
    return "BLOCKED"
