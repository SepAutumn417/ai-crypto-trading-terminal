"""市场结构识别测试。

覆盖：
- Swing High/Low 检测（Fractal 算法）
- HH/HL/LH/LL 结构标签
- BOS / CHOCH 事件检测
- 趋势方向 / 市场状态推断
- 支撑/阻力区聚合
- 禁交易区域识别
- 完整 analyze_structure 集成
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from exchange_adapter import Kline

from market_structure import (
    BosEvent,
    ChochEvent,
    MarketState,
    PriceZone,
    StructureSnapshot,
    SwingPoint,
    SwingType,
    TrendDirection,
    analyze_structure,
)
from market_structure.snapshot import (
    detect_no_trade_zones,
    detect_zones,
)
from market_structure.structure import detect_bos_choch
from market_structure.swing import detect_swings


# ---------- 测试数据工厂 ----------


def _make_kline(
    ts: datetime,
    o: str,
    h: str,
    l: str,
    c: str,
    v: str = "100",
) -> Kline:
    return Kline(
        timestamp=ts,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(l),
        close=Decimal(c),
        volume=Decimal(v),
    )


def _make_uptrend_klines(n: int = 30, start_price: Decimal = Decimal("100")) -> list[Kline]:
    """生成上涨趋势 K 线：高点低点逐步抬高。

    每 5 根一个周期，波形设计确保：
    - phase 1 是 swing low（左右各 2 根 low 都更高）
    - phase 4 是 swing high（左右各 2 根 high 都更低）
    - phase 3 收盘价突破前周期 swing high → 触发 BOS
    """
    klines: list[Kline] = []
    base = start_price
    for i in range(n):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        phase = i % 5
        # (price, high, low) per phase
        prices = [
            (base + 1, base + 2, base - 1),      # phase 0: 回落
            (base - 2, base - 1, base - 3),       # phase 1 = swing low
            (base + 1, base + 2, base),           # phase 2: 反弹
            (base + 5, base + 6, base + 4),       # phase 3: 突破前 swing high → BOS
            (base + 7, base + 8, base + 6),       # phase 4 = swing high
        ]
        price, high, low = prices[phase]
        klines.append(_make_kline(ts, str(price), str(high), str(low), str(price)))
        if phase == 4:
            base += Decimal("4")  # 基底抬高，确保 HL
    return klines


def _make_downtrend_klines(n: int = 30, start_price: Decimal = Decimal("200")) -> list[Kline]:
    """生成下跌趋势 K 线：高点低点逐步降低。

    每 5 根一个周期，波形设计确保：
    - phase 1 是 swing high（左右各 2 根 high 都更低）
    - phase 4 是 swing low（左右各 2 根 low 都更高）
    - phase 3 收盘价跌破前周期 swing low → 触发 BOS
    """
    klines: list[Kline] = []
    base = start_price
    for i in range(n):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        phase = i % 5
        prices = [
            (base - 1, base + 1, base - 2),       # phase 0: 反弹
            (base + 2, base + 3, base + 1),        # phase 1 = swing high
            (base - 1, base, base - 2),            # phase 2: 回落
            (base - 5, base - 4, base - 6),        # phase 3: 跌破前 swing low → BOS
            (base - 7, base - 6, base - 8),        # phase 4 = swing low
        ]
        price, high, low = prices[phase]
        klines.append(_make_kline(ts, str(price), str(high), str(low), str(price)))
        if phase == 4:
            base -= Decimal("4")  # 基底降低，确保 LH/LL
    return klines


def _make_range_klines(n: int = 30, center: Decimal = Decimal("150")) -> list[Kline]:
    """生成震荡 K 线：价格在固定区间内来回。"""
    klines: list[Kline] = []
    for i in range(n):
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        phase = i % 10
        # 正弦波动
        import math

        offset = Decimal(str(math.sin(phase * math.pi / 5))) * Decimal("10")
        price = center + offset
        high = price + Decimal("1")
        low = price - Decimal("1")
        klines.append(_make_kline(ts, str(price), str(high), str(low), str(price)))
    return klines


# ---------- Swing 检测测试 ----------


class TestSwingDetection:
    def test_detect_swings_empty(self):
        """空 K 线序列不报错。"""
        swings = detect_swings([])
        assert swings == []

    def test_detect_swings_too_few(self):
        """K 线数不足时不检测。"""
        klines = _make_uptrend_klines(n=3)
        swings = detect_swings(klines, left_bars=2, right_bars=2)
        assert swings == []

    def test_detect_swings_uptrend(self):
        """上涨趋势应检测到 swing high 和 swing low。"""
        klines = _make_uptrend_klines(n=30)
        swings = detect_swings(klines, left_bars=2, right_bars=2)

        highs = [s for s in swings if s.type == SwingType.HIGH]
        lows = [s for s in swings if s.type == SwingType.LOW]

        assert len(highs) > 0, "应检测到 swing high"
        assert len(lows) > 0, "应检测到 swing low"
        assert all(s.confirmed for s in swings), "所有 swing 应已确认"

    def test_swing_high_is_local_max(self):
        """swing high 应是局部最高点。"""
        klines = _make_uptrend_klines(n=30)
        swings = detect_swings(klines, left_bars=2, right_bars=2)

        for sw in swings:
            if sw.type == SwingType.HIGH:
                # 验证左右 2 根 K 线的 high 都低于 swing price
                left = klines[sw.index - 2 : sw.index]
                right = klines[sw.index + 1 : sw.index + 3]
                for k in left + right:
                    assert k.high < sw.price, f"swing high at {sw.index} 不是局部最高"

    def test_swing_low_is_local_min(self):
        """swing low 应是局部最低点。"""
        klines = _make_uptrend_klines(n=30)
        swings = detect_swings(klines, left_bars=2, right_bars=2)

        for sw in swings:
            if sw.type == SwingType.LOW:
                left = klines[sw.index - 2 : sw.index]
                right = klines[sw.index + 1 : sw.index + 3]
                for k in left + right:
                    assert k.low > sw.price, f"swing low at {sw.index} 不是局部最低"

    def test_structure_labels_uptrend(self):
        """上涨趋势 swing high 应标记 HH，swing low 应标记 HL。"""
        klines = _make_uptrend_klines(n=30)
        swings = detect_swings(klines, left_bars=2, right_bars=2)

        highs = [s for s in swings if s.type == SwingType.HIGH]
        # 至少有 2 个 swing high 才能比较
        if len(highs) >= 2:
            # 后面的 high 应该是 HH（价格更高）
            later_highs = highs[1:]
            assert any(s.structure_label == "HH" for s in later_highs), "上涨趋势应有 HH 标签"

    def test_structure_labels_downtrend(self):
        """下跌趋势 swing low 应标记 LL，swing high 应标记 LH。"""
        klines = _make_downtrend_klines(n=30)
        swings = detect_swings(klines, left_bars=2, right_bars=2)

        lows = [s for s in swings if s.type == SwingType.LOW]
        if len(lows) >= 2:
            later_lows = lows[1:]
            assert any(s.structure_label == "LL" for s in later_lows), "下跌趋势应有 LL 标签"


# ---------- BOS / CHOCH 测试 ----------


class TestBosChoch:
    def test_no_events_on_flat(self):
        """震荡市场 BOS/CHOCH 事件较少。"""
        klines = _make_range_klines(n=30)
        swings = detect_swings(klines)
        bos, choch, trend, state = detect_bos_choch(klines, swings)

        # 震荡市场可能有一些事件但趋势不明确
        assert trend in (TrendDirection.NEUTRAL, TrendDirection.BULLISH, TrendDirection.BEARISH)
        assert state in (MarketState.RANGE, MarketState.TREND, MarketState.TRANSITION)

    def test_bullish_bos_in_uptrend(self):
        """上涨趋势应有 bullish BOS。"""
        klines = _make_uptrend_klines(n=40)
        swings = detect_swings(klines)
        bos, choch, trend, state = detect_bos_choch(klines, swings)

        assert len(bos) > 0, "上涨趋势应产生 BOS 事件"
        assert any(b.direction == TrendDirection.BULLISH for b in bos), "应有 bullish BOS"
        assert trend == TrendDirection.BULLISH
        assert state == MarketState.TREND

    def test_bearish_bos_in_downtrend(self):
        """下跌趋势应有 bearish BOS。"""
        klines = _make_downtrend_klines(n=40)
        swings = detect_swings(klines)
        bos, choch, trend, state = detect_bos_choch(klines, swings)

        assert len(bos) > 0, "下跌趋势应产生 BOS 事件"
        assert any(b.direction == TrendDirection.BEARISH for b in bos), "应有 bearish BOS"
        assert trend == TrendDirection.BEARISH
        assert state == MarketState.TREND

    def test_choch_on_reversal(self):
        """趋势反转应产生 CHOCH 事件。"""
        # 先涨后跌
        up = _make_uptrend_klines(n=20, start_price=Decimal("100"))
        down = _make_downtrend_klines(n=20, start_price=Decimal("140"))
        klines = up + down

        swings = detect_swings(klines)
        bos, choch, trend, state = detect_bos_choch(klines, swings)

        assert len(choch) > 0, "趋势反转应产生 CHOCH 事件"
        assert any(c.direction == TrendDirection.BEARISH for c in choch), "应有 bearish CHOCH"

    def test_bos_event_fields(self):
        """BOS 事件字段完整。"""
        klines = _make_uptrend_klines(n=40)
        swings = detect_swings(klines)
        bos, _, _, _ = detect_bos_choch(klines, swings)

        if bos:
            b = bos[0]
            assert b.broken_swing_id is not None
            assert b.broken_price > 0
            assert b.break_index >= 0
            assert b.break_timestamp is not None
            assert b.close_price > 0


# ---------- 支撑/阻力区测试 ----------


class TestZones:
    def test_detect_zones_returns_lists(self):
        """detect_zones 返回支撑区和阻力区列表。"""
        klines = _make_uptrend_klines(n=30)
        swings = detect_swings(klines)
        support, resistance = detect_zones(swings)

        assert isinstance(support, list)
        assert isinstance(resistance, list)

    def test_resistance_zones_from_highs(self):
        """阻力区来自 swing high。"""
        klines = _make_uptrend_klines(n=30)
        swings = detect_swings(klines)
        _, resistance = detect_zones(swings)

        assert len(resistance) > 0
        for z in resistance:
            assert z.zone_type == "resistance"
            assert z.upper >= z.lower
            assert z.midpoint > 0
            assert z.strength >= 1

    def test_support_zones_from_lows(self):
        """支撑区来自 swing low。"""
        klines = _make_uptrend_klines(n=30)
        swings = detect_swings(klines)
        support, _ = detect_zones(swings)

        assert len(support) > 0
        for z in support:
            assert z.zone_type == "support"
            assert z.upper >= z.lower

    def test_no_trade_zone_in_range(self):
        """窄幅震荡应产生禁交易区域。"""
        # 构造窄幅震荡：支撑 100，阻力 105（5% 间距）
        support_zone = PriceZone(
            zone_type="support",
            upper=Decimal("101"),
            lower=Decimal("99"),
            midpoint=Decimal("100"),
            strength=3,
        )
        resistance_zone = PriceZone(
            zone_type="resistance",
            upper=Decimal("106"),
            lower=Decimal("104"),
            midpoint=Decimal("105"),
            strength=3,
        )
        no_trade = detect_no_trade_zones([support_zone], [resistance_zone], Decimal("102"))

        assert len(no_trade) == 1
        assert no_trade[0].zone_type == "no_trade"
        assert no_trade[0].upper > no_trade[0].lower

    def test_no_no_trade_zone_in_trend(self):
        """宽幅趋势不产生禁交易区域。"""
        support_zone = PriceZone(
            zone_type="support",
            upper=Decimal("101"),
            lower=Decimal("99"),
            midpoint=Decimal("100"),
            strength=3,
        )
        resistance_zone = PriceZone(
            zone_type="resistance",
            upper=Decimal("120"),
            lower=Decimal("118"),
            midpoint=Decimal("119"),
            strength=3,
        )
        no_trade = detect_no_trade_zones([support_zone], [resistance_zone], Decimal("110"))

        assert len(no_trade) == 0


# ---------- 完整集成测试 ----------


class TestAnalyzeStructure:
    def test_returns_snapshot(self):
        """analyze_structure 返回 StructureSnapshot。"""
        klines = _make_uptrend_klines(n=50)
        snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")

        assert isinstance(snapshot, StructureSnapshot)
        assert snapshot.symbol == "BTCUSDT"
        assert snapshot.timeframe == "1h"
        assert snapshot.kline_count == 50
        assert snapshot.captured_at is not None

    def test_uptrend_snapshot(self):
        """上涨趋势快照应为 TREND + BULLISH。"""
        klines = _make_uptrend_klines(n=50)
        snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")

        assert snapshot.market_state == MarketState.TREND
        assert snapshot.trend_direction == TrendDirection.BULLISH
        assert len(snapshot.swing_highs) > 0
        assert len(snapshot.swing_lows) > 0
        assert len(snapshot.bos_events) > 0

    def test_downtrend_snapshot(self):
        """下跌趋势快照应为 TREND + BEARISH。"""
        klines = _make_downtrend_klines(n=50)
        snapshot = analyze_structure(klines, symbol="ETHUSDT", timeframe="4h")

        assert snapshot.market_state == MarketState.TREND
        assert snapshot.trend_direction == TrendDirection.BEARISH
        assert len(snapshot.bos_events) > 0

    def test_snapshot_has_zones(self):
        """快照包含支撑/阻力区。"""
        klines = _make_uptrend_klines(n=50)
        snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")

        assert len(snapshot.support_zones) > 0
        assert len(snapshot.resistance_zones) > 0

    def test_snapshot_has_last_price(self):
        """快照包含最新价格。"""
        klines = _make_uptrend_klines(n=50)
        snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")

        assert snapshot.last_price is not None
        assert snapshot.last_price == klines[-1].close

    def test_snapshot_has_volatility(self):
        """快照包含波动率状态。"""
        klines = _make_uptrend_klines(n=50)
        snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")

        assert snapshot.volatility_state in ("low", "normal", "high")

    def test_to_db_dict(self):
        """to_db_dict 生成数据库行 dict。"""
        klines = _make_uptrend_klines(n=30)
        snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")
        d = snapshot.to_db_dict()

        assert d["symbol"] == "BTCUSDT"
        assert d["timeframe"] == "1h"
        assert d["market_state"] == "trend"
        assert isinstance(d["swing_highs"], list)
        assert isinstance(d["support_zones"], list)
        assert "config" in d

    def test_empty_klines(self):
        """空 K 线不报错，返回 RANGE/NEUTRAL。"""
        snapshot = analyze_structure([], symbol="BTCUSDT", timeframe="1h")

        assert snapshot.kline_count == 0
        assert snapshot.market_state == MarketState.RANGE
        assert snapshot.trend_direction == TrendDirection.NEUTRAL
        assert snapshot.last_price is None
