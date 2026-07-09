"""自动候选计划引擎 v0.4。

根据市场结构快照自动生成候选交易计划，支持 7 种 setupType：
- 趋势回踩（TREND_PULLBACK_LONG/SHORT）
- 震荡反弹/回落（RANGE_SUPPORT_BOUNCE / RANGE_RESISTANCE_REJECT）
- 突破回踩（BREAKOUT_RETEST_LONG / BREAKDOWN_RETEST_SHORT）
- 假突破反转（FALSE_BREAK_REVERSAL）

核心流程：
    StructureSnapshot → generate_candidates() → 候选计划列表
    → grade_opportunity() → 机会评级（A/B/C/BLOCKED）
    → 状态机流转 → promote 为正式 TradePlan

使用示例：
    from auto_plan_engine import generate_candidates
    from market_structure import analyze_structure
    from exchange_adapter import Kline

    snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")
    candidates = generate_candidates(snapshot)
    for c in candidates:
        print(c.setup_type, c.opportunity_grade, c.risk_reward_ratio)
"""
from .generator import generate_candidates
from .grade import grade_opportunity
from .state import (
    PROMOTABLE_STATUSES,
    TERMINAL_STATUSES,
    can_transition,
    get_allowed_transitions,
    is_promotable,
    is_terminal,
    transition,
)
from .types import (
    CandidateDirection,
    CandidatePlan,
    CandidateStatus,
    SetupType,
)

__all__ = [
    "generate_candidates",
    "grade_opportunity",
    "can_transition",
    "transition",
    "is_terminal",
    "is_promotable",
    "get_allowed_transitions",
    "PROMOTABLE_STATUSES",
    "TERMINAL_STATUSES",
    "CandidateDirection",
    "CandidatePlan",
    "CandidateStatus",
    "SetupType",
]
