"""auto-plan-engine 单元测试。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from auto_plan_engine import (
    CandidateDirection,
    CandidatePlan,
    CandidateStatus,
    SetupType,
    can_transition,
    generate_candidates,
    get_allowed_transitions,
    grade_opportunity,
    is_promotable,
    is_terminal,
    transition,
)
from market_structure import (
    BosEvent,
    ChochEvent,
    MarketState,
    PriceZone,
    StructureSnapshot,
    SwingPoint,
    SwingType,
    TrendDirection,
)

# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------

def _make_support_zone(price: Decimal, strength: int = 2) -> PriceZone:
    """创建支撑区。"""
    return PriceZone(
        id=uuid4(),
        zone_type="support",
        upper=price * Decimal("1.005"),
        lower=price * Decimal("0.995"),
        midpoint=price,
        strength=strength,
        swing_ids=[uuid4() for _ in range(strength)],
    )


def _make_resistance_zone(price: Decimal, strength: int = 2) -> PriceZone:
    """创建阻力区。"""
    return PriceZone(
        id=uuid4(),
        zone_type="resistance",
        upper=price * Decimal("1.005"),
        lower=price * Decimal("0.995"),
        midpoint=price,
        strength=strength,
        swing_ids=[uuid4() for _ in range(strength)],
    )


def _make_no_trade_zone(price: Decimal) -> PriceZone:
    """创建禁交易区。"""
    return PriceZone(
        id=uuid4(),
        zone_type="no_trade",
        upper=price * Decimal("1.01"),
        lower=price * Decimal("0.99"),
        midpoint=price,
        strength=1,
    )


def _make_swing_high(price: Decimal, index: int = 0) -> SwingPoint:
    return SwingPoint(
        type=SwingType.HIGH, index=index, price=price,
        timestamp=datetime(2026, 1, 1), confirmed=True,
    )


def _make_swing_low(price: Decimal, index: int = 0) -> SwingPoint:
    return SwingPoint(
        type=SwingType.LOW, index=index, price=price,
        timestamp=datetime(2026, 1, 1), confirmed=True,
    )


def _make_snapshot(
    market_state: MarketState = MarketState.TREND,
    trend_direction: TrendDirection = TrendDirection.BULLISH,
    support_zones: list[PriceZone] | None = None,
    resistance_zones: list[PriceZone] | None = None,
    no_trade_zones: list[PriceZone] | None = None,
    bos_events: list[BosEvent] | None = None,
    choch_events: list[ChochEvent] | None = None,
    swing_highs: list[SwingPoint] | None = None,
    swing_lows: list[SwingPoint] | None = None,
    last_price: Decimal | None = None,
    volatility_state: str = "normal",
) -> StructureSnapshot:
    """创建结构快照测试数据。"""
    return StructureSnapshot(
        id=uuid4(),
        symbol="BTCUSDT",
        timeframe="1h",
        captured_at=datetime(2026, 1, 1, 12, 0, 0),
        kline_count=100,
        kline_start=datetime(2026, 1, 1),
        kline_end=datetime(2026, 1, 1, 12, 0, 0),
        market_state=market_state,
        trend_direction=trend_direction,
        swing_highs=swing_highs or [],
        swing_lows=swing_lows or [],
        bos_events=bos_events or [],
        choch_events=choch_events or [],
        support_zones=support_zones or [],
        resistance_zones=resistance_zones or [],
        no_trade_zones=no_trade_zones or [],
        volatility_state=volatility_state,
        last_price=last_price or Decimal("100000"),
    )


def _make_bullish_bos(price: Decimal = Decimal("102000")) -> BosEvent:
    return BosEvent(
        direction=TrendDirection.BULLISH,
        broken_swing_id=uuid4(),
        broken_price=price,
        break_index=50,
        break_timestamp=datetime(2026, 1, 1, 10, 0, 0),
        close_price=price * Decimal("1.01"),
    )


def _make_bearish_bos(price: Decimal = Decimal("98000")) -> BosEvent:
    return BosEvent(
        direction=TrendDirection.BEARISH,
        broken_swing_id=uuid4(),
        broken_price=price,
        break_index=50,
        break_timestamp=datetime(2026, 1, 1, 10, 0, 0),
        close_price=price * Decimal("0.99"),
    )


def _make_bullish_choch(price: Decimal = Decimal("99000")) -> ChochEvent:
    return ChochEvent(
        direction=TrendDirection.BULLISH,
        broken_swing_id=uuid4(),
        broken_price=price,
        break_index=45,
        break_timestamp=datetime(2026, 1, 1, 9, 0, 0),
        close_price=price * Decimal("1.01"),
    )


def _make_bearish_choch(price: Decimal = Decimal("101000")) -> ChochEvent:
    return ChochEvent(
        direction=TrendDirection.BEARISH,
        broken_swing_id=uuid4(),
        broken_price=price,
        break_index=45,
        break_timestamp=datetime(2026, 1, 1, 9, 0, 0),
        close_price=price * Decimal("0.99"),
    )


# ---------------------------------------------------------------------------
# 生成器测试
# ---------------------------------------------------------------------------

class TestGenerator:
    def test_empty_snapshot_returns_empty(self):
        """空快照（无支撑阻力区、无BOS/CHOCH）应返回空列表。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TRANSITION,
            trend_direction=TrendDirection.NEUTRAL,
        )
        candidates = generate_candidates(snapshot)
        assert candidates == []

    def test_uptrend_generates_pullback_long(self):
        """上升趋势应生成 TREND_PULLBACK_LONG。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
        )
        candidates = generate_candidates(snapshot)
        types = [c.setup_type for c in candidates]
        assert SetupType.TREND_PULLBACK_LONG in types

    def test_downtrend_generates_pullback_short(self):
        """下降趋势应生成 TREND_PULLBACK_SHORT。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BEARISH,
            support_zones=[_make_support_zone(Decimal("95000"))],
            resistance_zones=[_make_resistance_zone(Decimal("101000"))],
        )
        candidates = generate_candidates(snapshot)
        types = [c.setup_type for c in candidates]
        assert SetupType.TREND_PULLBACK_SHORT in types

    def test_range_generates_support_bounce_and_resistance_reject(self):
        """震荡市应生成 RANGE_SUPPORT_BOUNCE 和 RANGE_RESISTANCE_REJECT。"""
        snapshot = _make_snapshot(
            market_state=MarketState.RANGE,
            trend_direction=TrendDirection.NEUTRAL,
            support_zones=[_make_support_zone(Decimal("98000"))],
            resistance_zones=[_make_resistance_zone(Decimal("102000"))],
        )
        candidates = generate_candidates(snapshot)
        types = [c.setup_type for c in candidates]
        assert SetupType.RANGE_SUPPORT_BOUNCE in types
        assert SetupType.RANGE_RESISTANCE_REJECT in types

    def test_bullish_bos_generates_breakout_retest_long(self):
        """有 bullish BOS 应生成 BREAKOUT_RETEST_LONG。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("110000"))],
            bos_events=[_make_bullish_bos(Decimal("100000"))],
        )
        candidates = generate_candidates(snapshot)
        types = [c.setup_type for c in candidates]
        assert SetupType.BREAKOUT_RETEST_LONG in types

    def test_bearish_bos_generates_breakdown_retest_short(self):
        """有 bearish BOS 应生成 BREAKDOWN_RETEST_SHORT。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BEARISH,
            support_zones=[_make_support_zone(Decimal("90000"))],
            resistance_zones=[_make_resistance_zone(Decimal("100000"))],
            bos_events=[_make_bearish_bos(Decimal("100000"))],
        )
        candidates = generate_candidates(snapshot)
        types = [c.setup_type for c in candidates]
        assert SetupType.BREAKDOWN_RETEST_SHORT in types

    def test_choch_generates_false_break_reversal(self):
        """有 CHOCH 应生成 FALSE_BREAK_REVERSAL。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TRANSITION,
            trend_direction=TrendDirection.NEUTRAL,
            support_zones=[_make_support_zone(Decimal("95000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
            choch_events=[_make_bullish_choch(Decimal("100000"))],
        )
        candidates = generate_candidates(snapshot)
        types = [c.setup_type for c in candidates]
        assert SetupType.FALSE_BREAK_REVERSAL in types

    def test_candidates_have_risk_reward_ratio(self):
        """所有候选计划应有盈亏比。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
        )
        candidates = generate_candidates(snapshot)
        assert len(candidates) > 0
        for c in candidates:
            assert c.risk_reward_ratio is not None
            assert c.risk_reward_ratio > 0

    def test_candidates_sorted_by_grade(self):
        """候选计划应按评级降序排列（A > B > C）。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("110000"))],
            bos_events=[_make_bullish_bos(Decimal("100000"))],
            swing_highs=[_make_swing_high(Decimal("108000"))],
        )
        candidates = generate_candidates(snapshot)
        if len(candidates) >= 2:
            grade_order = {"A": 0, "B": 1, "C": 2, "BLOCKED": 3}
            for i in range(len(candidates) - 1):
                assert grade_order[candidates[i].opportunity_grade] <= grade_order[candidates[i + 1].opportunity_grade]

    def test_min_rr_filter(self):
        """低盈亏比的候选计划应被过滤。"""
        # 支撑和阻力非常接近，盈亏比会很低
        snapshot = _make_snapshot(
            market_state=MarketState.RANGE,
            trend_direction=TrendDirection.NEUTRAL,
            support_zones=[_make_support_zone(Decimal("100000"))],
            resistance_zones=[_make_resistance_zone(Decimal("100100"))],  # 仅差 0.1%
        )
        candidates = generate_candidates(snapshot, min_rr=Decimal("1.0"))
        # 盈亏比 < 1.0 的应被过滤
        for c in candidates:
            assert c.risk_reward_ratio >= Decimal("1.0")

    def test_candidate_has_structure_snapshot_id(self):
        """候选计划应关联结构快照 ID。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
        )
        candidates = generate_candidates(snapshot)
        assert len(candidates) > 0
        for c in candidates:
            assert c.structure_snapshot_id == snapshot.id

    def test_candidate_has_symbol_and_timeframe(self):
        """候选计划应继承 symbol 和 timeframe。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
        )
        candidates = generate_candidates(snapshot)
        assert len(candidates) > 0
        for c in candidates:
            assert c.symbol == "BTCUSDT"
            assert c.timeframe == "1h"

    def test_long_candidate_direction_is_long(self):
        """做多候选计划方向应为 long。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
        )
        candidates = generate_candidates(snapshot)
        long_candidates = [c for c in candidates if c.setup_type == SetupType.TREND_PULLBACK_LONG]
        assert len(long_candidates) == 1
        assert long_candidates[0].direction == CandidateDirection.LONG

    def test_short_candidate_direction_is_short(self):
        """做空候选计划方向应为 short。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BEARISH,
            support_zones=[_make_support_zone(Decimal("95000"))],
            resistance_zones=[_make_resistance_zone(Decimal("101000"))],
        )
        candidates = generate_candidates(snapshot)
        short_candidates = [c for c in candidates if c.setup_type == SetupType.TREND_PULLBACK_SHORT]
        assert len(short_candidates) == 1
        assert short_candidates[0].direction == CandidateDirection.SHORT


# ---------------------------------------------------------------------------
# 评级测试
# ---------------------------------------------------------------------------

class TestGrading:
    def test_no_trade_zone_returns_blocked(self):
        """入场价在禁交易区域内应返回 BLOCKED。"""
        snapshot = _make_snapshot(
            market_state=MarketState.RANGE,
            trend_direction=TrendDirection.NEUTRAL,
            support_zones=[_make_support_zone(Decimal("100000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
            no_trade_zones=[_make_no_trade_zone(Decimal("100000"))],
        )
        candidate = CandidatePlan(
            symbol="BTCUSDT",
            direction=CandidateDirection.LONG,
            setup_type=SetupType.RANGE_SUPPORT_BOUNCE,
            entry_zone_upper=Decimal("100500"),
            entry_zone_lower=Decimal("99500"),
            entry_price=Decimal("100000"),
            stop_loss_price=Decimal("99000"),
            take_profit_prices=[Decimal("105000")],
            risk_reward_ratio=Decimal("5.0"),
        )
        grade = grade_opportunity(candidate, snapshot)
        assert grade == "BLOCKED"

    def test_high_rr_trend_aligned_gets_good_grade(self):
        """高盈亏比+趋势一致应获得较高评级。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("110000"))],
            bos_events=[_make_bullish_bos(Decimal("100000"))],
        )
        candidate = CandidatePlan(
            symbol="BTCUSDT",
            direction=CandidateDirection.LONG,
            setup_type=SetupType.TREND_PULLBACK_LONG,
            entry_zone_upper=Decimal("99500"),
            entry_zone_lower=Decimal("98500"),
            entry_price=Decimal("99000"),
            stop_loss_price=Decimal("98000"),
            take_profit_prices=[Decimal("110000")],
            risk_reward_ratio=Decimal("11.0"),
        )
        grade = grade_opportunity(candidate, snapshot)
        assert grade in ("A", "B")

    def test_low_rr_gets_low_grade(self):
        """低盈亏比应获得较低评级。"""
        snapshot = _make_snapshot(
            market_state=MarketState.RANGE,
            trend_direction=TrendDirection.NEUTRAL,
        )
        candidate = CandidatePlan(
            symbol="BTCUSDT",
            direction=CandidateDirection.LONG,
            setup_type=SetupType.RANGE_SUPPORT_BOUNCE,
            entry_zone_upper=Decimal("100050"),
            entry_zone_lower=Decimal("99950"),
            entry_price=Decimal("100000"),
            stop_loss_price=Decimal("99900"),
            take_profit_prices=[Decimal("100100")],
            risk_reward_ratio=Decimal("1.0"),
        )
        grade = grade_opportunity(candidate, snapshot)
        assert grade in ("C", "BLOCKED")

    def test_grade_returns_valid_value(self):
        """评级结果必须是 A/B/C/BLOCKED 之一。"""
        snapshot = _make_snapshot()
        candidate = CandidatePlan(
            symbol="BTCUSDT",
            direction=CandidateDirection.LONG,
            setup_type=SetupType.FALSE_BREAK_REVERSAL,
            entry_zone_upper=Decimal("100500"),
            entry_zone_lower=Decimal("99500"),
            entry_price=Decimal("100000"),
            stop_loss_price=Decimal("99000"),
            take_profit_prices=[Decimal("102000")],
            risk_reward_ratio=Decimal("2.0"),
        )
        grade = grade_opportunity(candidate, snapshot)
        assert grade in ("A", "B", "C", "BLOCKED")


# ---------------------------------------------------------------------------
# 状态机测试
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_discovered_to_watching(self):
        assert can_transition(CandidateStatus.DISCOVERED, CandidateStatus.WATCHING)
        assert transition(CandidateStatus.DISCOVERED, CandidateStatus.WATCHING) == CandidateStatus.WATCHING

    def test_watching_to_ready(self):
        assert can_transition(CandidateStatus.WATCHING, CandidateStatus.READY)
        assert transition(CandidateStatus.WATCHING, CandidateStatus.READY) == CandidateStatus.READY

    def test_ready_to_risk_checked(self):
        assert can_transition(CandidateStatus.READY, CandidateStatus.RISK_CHECKED)

    def test_risk_checked_to_ai_evaluated(self):
        assert can_transition(CandidateStatus.RISK_CHECKED, CandidateStatus.AI_EVALUATED)

    def test_ai_evaluated_to_allow_confirm(self):
        assert can_transition(CandidateStatus.AI_EVALUATED, CandidateStatus.ALLOW_CONFIRM)

    def test_ai_evaluated_to_block(self):
        assert can_transition(CandidateStatus.AI_EVALUATED, CandidateStatus.BLOCK)

    def test_ai_evaluated_to_wait(self):
        assert can_transition(CandidateStatus.AI_EVALUATED, CandidateStatus.WAIT)

    def test_wait_back_to_ready(self):
        assert can_transition(CandidateStatus.WAIT, CandidateStatus.READY)

    def test_any_to_expired(self):
        """大多数状态都可以转到 EXPIRED。"""
        for status in [
            CandidateStatus.DISCOVERED,
            CandidateStatus.WATCHING,
            CandidateStatus.READY,
            CandidateStatus.RISK_CHECKED,
            CandidateStatus.AI_EVALUATED,
            CandidateStatus.ALLOW_CONFIRM,
            CandidateStatus.WAIT,
        ]:
            assert can_transition(status, CandidateStatus.EXPIRED), f"{status} should transition to EXPIRED"

    def test_illegal_transition_raises(self):
        """非法转换应抛出 ValueError。"""
        with pytest.raises(ValueError, match="非法状态转换"):
            transition(CandidateStatus.DISCOVERED, CandidateStatus.ALLOW_CONFIRM)

    def test_block_is_terminal(self):
        """BLOCK 是终态，不能转出。"""
        assert is_terminal(CandidateStatus.BLOCK)
        assert not can_transition(CandidateStatus.BLOCK, CandidateStatus.READY)

    def test_expired_is_terminal(self):
        """EXPIRED 是终态。"""
        assert is_terminal(CandidateStatus.EXPIRED)
        assert not can_transition(CandidateStatus.EXPIRED, CandidateStatus.READY)

    def test_allow_confirm_is_not_terminal(self):
        """ALLOW_CONFIRM 不是终态（可以过期）。"""
        assert not is_terminal(CandidateStatus.ALLOW_CONFIRM)

    def test_ready_is_promotable(self):
        assert is_promotable(CandidateStatus.READY)

    def test_allow_confirm_is_promotable(self):
        assert is_promotable(CandidateStatus.ALLOW_CONFIRM)

    def test_discovered_not_promotable(self):
        assert not is_promotable(CandidateStatus.DISCOVERED)

    def test_watching_not_promotable(self):
        assert not is_promotable(CandidateStatus.WATCHING)

    def test_wait_not_promotable(self):
        assert not is_promotable(CandidateStatus.WAIT)

    def test_block_not_promotable(self):
        assert not is_promotable(CandidateStatus.BLOCK)

    def test_expired_not_promotable(self):
        assert not is_promotable(CandidateStatus.EXPIRED)

    def test_get_allowed_transitions_returns_set(self):
        """get_allowed_transitions 应返回合法后续状态集合。"""
        allowed = get_allowed_transitions(CandidateStatus.DISCOVERED)
        assert CandidateStatus.WATCHING in allowed
        assert CandidateStatus.EXPIRED in allowed
        assert CandidateStatus.READY not in allowed

    def test_get_allowed_transitions_terminal_is_empty(self):
        """终态的合法后续状态为空。"""
        assert get_allowed_transitions(CandidateStatus.BLOCK) == set()
        assert get_allowed_transitions(CandidateStatus.EXPIRED) == set()


# ---------------------------------------------------------------------------
# 集成测试
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_pipeline_generates_valid_candidates(self):
        """完整流程：趋势+BOS+支撑阻力 → 生成候选 → 有评级 → 有盈亏比。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("95000"))],
            resistance_zones=[_make_resistance_zone(Decimal("110000"))],
            bos_events=[_make_bullish_bos(Decimal("100000"))],
            swing_highs=[_make_swing_high(Decimal("105000"))],
            swing_lows=[_make_swing_low(Decimal("94000"))],
        )
        candidates = generate_candidates(snapshot)
        assert len(candidates) >= 2  # 至少有回踩做多 + 突破回踩做多

        for c in candidates:
            assert c.risk_reward_ratio is not None
            assert c.risk_reward_ratio > 0
            assert c.opportunity_grade in ("A", "B", "C", "BLOCKED")
            assert c.entry_price is not None
            assert c.stop_loss_price > 0
            assert len(c.take_profit_prices) > 0
            assert c.rationale != ""
            assert c.structure_snapshot_id == snapshot.id

    def test_candidate_to_db_dict(self):
        """to_db_dict 应返回正确的字典结构。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("99000"))],
            resistance_zones=[_make_resistance_zone(Decimal("105000"))],
        )
        candidates = generate_candidates(snapshot)
        assert len(candidates) > 0
        db_dict = candidates[0].to_db_dict()
        assert "id" in db_dict
        assert "symbol" in db_dict
        assert "direction" in db_dict
        assert "setup_type" in db_dict
        assert "entry_zone" in db_dict
        assert "stop_loss_price" in db_dict
        assert "take_profit_prices" in db_dict
        assert "opportunity_grade" in db_dict
        assert "status" in db_dict
        assert db_dict["symbol"] == "BTCUSDT"

    def test_no_candidates_for_transition_state_without_events(self):
        """TRANSITION 状态无 BOS/CHOCH 事件时应返回空列表。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TRANSITION,
            trend_direction=TrendDirection.NEUTRAL,
        )
        candidates = generate_candidates(snapshot)
        assert candidates == []

    def test_multiple_setup_types_generated(self):
        """复杂场景应生成多种 setupType。"""
        snapshot = _make_snapshot(
            market_state=MarketState.TREND,
            trend_direction=TrendDirection.BULLISH,
            support_zones=[_make_support_zone(Decimal("95000"))],
            resistance_zones=[_make_resistance_zone(Decimal("110000"))],
            bos_events=[_make_bullish_bos(Decimal("100000"))],
            choch_events=[_make_bearish_choch(Decimal("101000"))],
            swing_highs=[_make_swing_high(Decimal("105000")), _make_swing_high(Decimal("108000"))],
            swing_lows=[_make_swing_low(Decimal("94000"))],
        )
        candidates = generate_candidates(snapshot)
        types = {c.setup_type for c in candidates}
        # 应该有多种类型
        assert len(types) >= 2
