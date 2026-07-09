"""候选计划生成器。

根据市场结构快照自动生成候选交易计划。
支持 7 种 setupType（对应 AUTOMATION_DESIGN.md §3）。

核心入口：
    generate_candidates(snapshot) -> list[CandidatePlan]
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from market_structure import (
    BosEvent,
    ChochEvent,
    MarketState,
    PriceZone,
    StructureSnapshot,
    SwingPoint,
    TrendDirection,
)

from .grade import grade_opportunity
from .types import CandidateDirection, CandidatePlan, SetupType

# 止损缓冲比例（入场区外扩）
STOP_BUFFER_PCT = Decimal("0.005")  # 0.5%
# 入场区域宽度（基于价格的百分比）
ENTRY_ZONE_WIDTH_PCT = Decimal("0.01")  # 1%


def generate_candidates(
    snapshot: StructureSnapshot,
    min_rr: Decimal = Decimal("1.0"),
) -> list[CandidatePlan]:
    """根据结构快照生成候选交易计划列表。

    参数：
        snapshot: 市场结构快照
        min_rr: 最低盈亏比过滤阈值，低于此值的候选计划不返回

    返回：
        候选计划列表，按机会评级降序排列。
    """
    candidates: list[CandidatePlan] = []

    # 1. 趋势回踩类
    candidates.extend(_gen_trend_pullback_long(snapshot))
    candidates.extend(_gen_trend_pullback_short(snapshot))

    # 2. 震荡区间类
    candidates.extend(_gen_range_support_bounce(snapshot))
    candidates.extend(_gen_range_resistance_reject(snapshot))

    # 3. 突破回踩类
    candidates.extend(_gen_breakout_retest_long(snapshot))
    candidates.extend(_gen_breakdown_retest_short(snapshot))

    # 4. 假突破反转类
    candidates.extend(_gen_false_break_reversal(snapshot))

    # 计算盈亏比、评级，过滤
    valid_candidates = []
    for c in candidates:
        c.risk_reward_ratio = _calc_rr(c)
        if c.risk_reward_ratio is None:
            c.invalidation_reason = "无法计算盈亏比（缺少止盈或止损）"
            continue
        if c.risk_reward_ratio < min_rr:
            c.invalidation_reason = f"盈亏比 {c.risk_reward_ratio} 低于阈值 {min_rr}"
            continue
        c.opportunity_grade = grade_opportunity(c, snapshot)
        if c.opportunity_grade == "BLOCKED":
            c.invalidation_reason = "机会评级为 BLOCKED"
        valid_candidates.append(c)

    # 按评级排序：A > B > C
    grade_order = {"A": 0, "B": 1, "C": 2, "BLOCKED": 3}
    valid_candidates.sort(key=lambda c: (grade_order.get(c.opportunity_grade, 9), -(c.risk_reward_ratio or Decimal("0"))))

    return valid_candidates


# ---------------------------------------------------------------------------
# 各 setupType 生成逻辑
# ---------------------------------------------------------------------------

def _gen_trend_pullback_long(snapshot: StructureSnapshot) -> list[CandidatePlan]:
    """上升趋势回踩做多。

    条件：market_state=TREND, trend_direction=BULLISH
    入场区：最近支撑区
    止损：支撑区下方
    目标：最近阻力区或前高
    """
    if snapshot.market_state != MarketState.TREND:
        return []
    if snapshot.trend_direction != TrendDirection.BULLISH:
        return []
    if not snapshot.support_zones:
        return []

    zone = snapshot.support_zones[-1]  # 最近的支撑区
    entry_lower = zone.lower
    entry_upper = zone.upper
    entry_price = (entry_lower + entry_upper) / 2
    stop_loss = entry_lower * (Decimal("1") - STOP_BUFFER_PCT)

    # 目标：阻力区或最近的 swing high
    targets = _get_targets_upward(snapshot, entry_price)

    return [_make_candidate(
        snapshot, SetupType.TREND_PULLBACK_LONG, CandidateDirection.LONG,
        entry_lower, entry_upper, entry_price, stop_loss, targets,
        rationale=f"上升趋势回踩支撑区 {zone.lower}-{zone.upper}，等待企稳做多",
        structure_signals={"support_zone": str(zone.midpoint), "trend": "bullish"},
    )]


def _gen_trend_pullback_short(snapshot: StructureSnapshot) -> list[CandidatePlan]:
    """下降趋势反抽做空。

    条件：market_state=TREND, trend_direction=BEARISH
    入场区：最近阻力区
    止损：阻力区上方
    目标：最近支撑区或前低
    """
    if snapshot.market_state != MarketState.TREND:
        return []
    if snapshot.trend_direction != TrendDirection.BEARISH:
        return []
    if not snapshot.resistance_zones:
        return []

    zone = snapshot.resistance_zones[-1]
    entry_lower = zone.lower
    entry_upper = zone.upper
    entry_price = (entry_lower + entry_upper) / 2
    stop_loss = entry_upper * (Decimal("1") + STOP_BUFFER_PCT)

    targets = _get_targets_downward(snapshot, entry_price)

    return [_make_candidate(
        snapshot, SetupType.TREND_PULLBACK_SHORT, CandidateDirection.SHORT,
        entry_lower, entry_upper, entry_price, stop_loss, targets,
        rationale=f"下降趋势反抽阻力区 {zone.lower}-{zone.upper}，等待受阻做空",
        structure_signals={"resistance_zone": str(zone.midpoint), "trend": "bearish"},
    )]


def _gen_range_support_bounce(snapshot: StructureSnapshot) -> list[CandidatePlan]:
    """震荡支撑反弹做多。

    条件：market_state=RANGE
    入场区：支撑区
    止损：支撑区下方
    目标：阻力区
    """
    if snapshot.market_state != MarketState.RANGE:
        return []
    if not snapshot.support_zones or not snapshot.resistance_zones:
        return []

    zone = snapshot.support_zones[-1]
    entry_lower = zone.lower
    entry_upper = zone.upper
    entry_price = (entry_lower + entry_upper) / 2
    stop_loss = entry_lower * (Decimal("1") - STOP_BUFFER_PCT)

    # 目标：阻力区中点
    resistance = snapshot.resistance_zones[-1]
    targets = [resistance.midpoint]

    return [_make_candidate(
        snapshot, SetupType.RANGE_SUPPORT_BOUNCE, CandidateDirection.LONG,
        entry_lower, entry_upper, entry_price, stop_loss, targets,
        rationale=f"震荡区间支撑反弹，支撑 {zone.lower}-{zone.upper} → 阻力 {resistance.lower}-{resistance.upper}",
        structure_signals={"support_zone": str(zone.midpoint), "resistance_zone": str(resistance.midpoint)},
    )]


def _gen_range_resistance_reject(snapshot: StructureSnapshot) -> list[CandidatePlan]:
    """震荡阻力回落做空。

    条件：market_state=RANGE
    入场区：阻力区
    止损：阻力区上方
    目标：支撑区
    """
    if snapshot.market_state != MarketState.RANGE:
        return []
    if not snapshot.support_zones or not snapshot.resistance_zones:
        return []

    zone = snapshot.resistance_zones[-1]
    entry_lower = zone.lower
    entry_upper = zone.upper
    entry_price = (entry_lower + entry_upper) / 2
    stop_loss = entry_upper * (Decimal("1") + STOP_BUFFER_PCT)

    support = snapshot.support_zones[-1]
    targets = [support.midpoint]

    return [_make_candidate(
        snapshot, SetupType.RANGE_RESISTANCE_REJECT, CandidateDirection.SHORT,
        entry_lower, entry_upper, entry_price, stop_loss, targets,
        rationale=f"震荡区间阻力回落，阻力 {zone.lower}-{zone.upper} → 支撑 {support.lower}-{support.upper}",
        structure_signals={"resistance_zone": str(zone.midpoint), "support_zone": str(support.midpoint)},
    )]


def _gen_breakout_retest_long(snapshot: StructureSnapshot) -> list[CandidatePlan]:
    """突破后回踩确认做多。

    条件：有 bullish BOS 事件
    入场区：BOS 突破点附近
    止损：突破点下方
    目标：下一个阻力区
    """
    bullish_bos = [b for b in snapshot.bos_events if b.direction == TrendDirection.BULLISH]
    if not bullish_bos:
        return []

    bos = bullish_bos[-1]  # 最近的 bullish BOS
    break_price = bos.broken_price
    entry_lower = break_price * (Decimal("1") - ENTRY_ZONE_WIDTH_PCT / 2)
    entry_upper = break_price * (Decimal("1") + ENTRY_ZONE_WIDTH_PCT / 2)
    entry_price = break_price
    stop_loss = break_price * (Decimal("1") - STOP_BUFFER_PCT)

    targets = _get_targets_upward(snapshot, entry_price)
    if not targets:
        # 如果没有上方目标，用盈亏比 2:1 计算
        risk = entry_price - stop_loss
        targets = [entry_price + risk * Decimal("2")]

    return [_make_candidate(
        snapshot, SetupType.BREAKOUT_RETEST_LONG, CandidateDirection.LONG,
        entry_lower, entry_upper, entry_price, stop_loss, targets,
        rationale=f"Bullish BOS 突破 {break_price}，回踩确认做多",
        structure_signals={"bos_price": str(break_price), "bos_index": bos.break_index},
    )]


def _gen_breakdown_retest_short(snapshot: StructureSnapshot) -> list[CandidatePlan]:
    """跌破后反抽确认做空。

    条件：有 bearish BOS 事件
    入场区：BOS 突破点附近
    止损：突破点上方
    目标：下一个支撑区
    """
    bearish_bos = [b for b in snapshot.bos_events if b.direction == TrendDirection.BEARISH]
    if not bearish_bos:
        return []

    bos = bearish_bos[-1]
    break_price = bos.broken_price
    entry_lower = break_price * (Decimal("1") - ENTRY_ZONE_WIDTH_PCT / 2)
    entry_upper = break_price * (Decimal("1") + ENTRY_ZONE_WIDTH_PCT / 2)
    entry_price = break_price
    stop_loss = break_price * (Decimal("1") + STOP_BUFFER_PCT)

    targets = _get_targets_downward(snapshot, entry_price)
    if not targets:
        risk = stop_loss - entry_price
        targets = [entry_price - risk * Decimal("2")]

    return [_make_candidate(
        snapshot, SetupType.BREAKDOWN_RETEST_SHORT, CandidateDirection.SHORT,
        entry_lower, entry_upper, entry_price, stop_loss, targets,
        rationale=f"Bearish BOS 跌破 {break_price}，反抽确认做空",
        structure_signals={"bos_price": str(break_price), "bos_index": bos.break_index},
    )]


def _gen_false_break_reversal(snapshot: StructureSnapshot) -> list[CandidatePlan]:
    """假突破反向。

    条件：有 CHOCH 事件
    入场区：CHOCH 突破点附近
    止损：CHOCH 突破点另一侧
    目标：反向支撑/阻力区
    """
    if not snapshot.choch_events:
        return []

    choch = snapshot.choch_events[-1]
    break_price = choch.broken_price

    if choch.direction == TrendDirection.BULLISH:
        # 看涨反转：之前是下跌趋势，CHOCH 向上突破
        direction = CandidateDirection.LONG
        entry_lower = break_price * (Decimal("1") - ENTRY_ZONE_WIDTH_PCT / 2)
        entry_upper = break_price * (Decimal("1") + ENTRY_ZONE_WIDTH_PCT / 2)
        entry_price = break_price
        stop_loss = break_price * (Decimal("1") - STOP_BUFFER_PCT)
        targets = _get_targets_upward(snapshot, entry_price)
        if not targets:
            risk = entry_price - stop_loss
            targets = [entry_price + risk * Decimal("2")]
        rationale = f"Bullish CHOCH 反转 {break_price}，假突破后做多"
    else:
        # 看跌反转
        direction = CandidateDirection.SHORT
        entry_lower = break_price * (Decimal("1") - ENTRY_ZONE_WIDTH_PCT / 2)
        entry_upper = break_price * (Decimal("1") + ENTRY_ZONE_WIDTH_PCT / 2)
        entry_price = break_price
        stop_loss = break_price * (Decimal("1") + STOP_BUFFER_PCT)
        targets = _get_targets_downward(snapshot, entry_price)
        if not targets:
            risk = stop_loss - entry_price
            targets = [entry_price - risk * Decimal("2")]
        rationale = f"Bearish CHOCH 反转 {break_price}，假突破后做空"

    return [_make_candidate(
        snapshot, SetupType.FALSE_BREAK_REVERSAL, direction,
        entry_lower, entry_upper, entry_price, stop_loss, targets,
        rationale=rationale,
        structure_signals={"choch_price": str(break_price), "choch_direction": choch.direction.value},
    )]


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_targets_upward(snapshot: StructureSnapshot, entry_price: Decimal) -> list[Decimal]:
    """获取上方目标价（阻力区或 swing high）。"""
    targets: list[Decimal] = []
    # 阻力区
    for zone in snapshot.resistance_zones:
        if zone.midpoint > entry_price:
            targets.append(zone.midpoint)
    # swing high
    for sw in snapshot.swing_highs:
        if sw.price > entry_price:
            targets.append(sw.price)
    # 去重排序，取前 2 个
    targets = sorted(set(targets))
    return targets[:2]


def _get_targets_downward(snapshot: StructureSnapshot, entry_price: Decimal) -> list[Decimal]:
    """获取下方目标价（支撑区或 swing low）。"""
    targets: list[Decimal] = []
    for zone in snapshot.support_zones:
        if zone.midpoint < entry_price:
            targets.append(zone.midpoint)
    for sw in snapshot.swing_lows:
        if sw.price < entry_price:
            targets.append(sw.price)
    targets = sorted(set(targets), reverse=True)
    return targets[:2]


def _calc_rr(candidate: CandidatePlan) -> Decimal | None:
    """计算盈亏比。

    risk = |entry - stop|
    reward = |target - entry|（取第一个目标）
    RR = reward / risk
    """
    entry = candidate.entry_price
    if entry is None:
        return None
    if not candidate.take_profit_prices:
        return None
    stop = candidate.stop_loss_price
    target = candidate.take_profit_prices[0]

    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return None
    return reward / risk


def _make_candidate(
    snapshot: StructureSnapshot,
    setup_type: SetupType,
    direction: CandidateDirection,
    entry_lower: Decimal,
    entry_upper: Decimal,
    entry_price: Decimal,
    stop_loss: Decimal,
    targets: list[Decimal],
    rationale: str,
    structure_signals: dict[str, Any],
) -> CandidatePlan:
    """创建候选计划实例。"""
    return CandidatePlan(
        structure_snapshot_id=snapshot.id,
        exchange="bitget",
        symbol=snapshot.symbol,
        timeframe=snapshot.timeframe,
        direction=direction,
        setup_type=setup_type,
        entry_zone_upper=entry_upper,
        entry_zone_lower=entry_lower,
        entry_price=entry_price,
        stop_loss_price=stop_loss,
        take_profit_prices=targets,
        rationale=rationale,
        structure_signals=structure_signals,
    )
