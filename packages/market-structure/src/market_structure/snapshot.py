"""支撑/阻力区识别 + 禁交易区域。

将相近的 swing 点聚合成价格区间（zone）：
- 支撑区：多个 swing low 聚集
- 阻力区：多个 swing high 聚集
- 禁交易区：价格在支撑/阻力之间的中部区域（无明确方向时）

聚合方法：按价格排序，将价差小于 tolerance 的 swing 点合并为一个 zone。
zone 的强度 = 聚合的 swing 点数量。
"""
from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from typing import Any

from exchange_adapter import Kline

from .structure import detect_bos_choch
from .swing import detect_swings
from .types import (
    BosEvent,
    ChochEvent,
    MarketState,
    PriceZone,
    StructureSnapshot,
    SwingPoint,
    SwingType,
    TrendDirection,
)


def detect_zones(
    swings: list[SwingPoint],
    tolerance_pct: Decimal = Decimal("0.5"),  # 0.5% 以内的 swing 合并
) -> tuple[list[PriceZone], list[PriceZone]]:
    """识别支撑区和阻力区。

    Args:
        swings: 所有 swing 点
        tolerance_pct: 合并容差（百分比，基于价格）

    Returns:
        (support_zones, resistance_zones)
    """
    highs = [s for s in swings if s.type == SwingType.HIGH]
    lows = [s for s in swings if s.type == SwingType.LOW]

    resistance_zones = _cluster_swings(highs, tolerance_pct, "resistance")
    support_zones = _cluster_swings(lows, tolerance_pct, "support")

    return support_zones, resistance_zones


def _cluster_swings(
    swing_points: list[SwingPoint],
    tolerance_pct: Decimal,
    zone_type: str,
) -> list[PriceZone]:
    """将相近的 swing 点聚合成 PriceZone。"""
    if not swing_points:
        return []

    # 按价格排序
    sorted_swings = sorted(swing_points, key=lambda s: s.price)
    zones: list[PriceZone] = []
    current_cluster: list[SwingPoint] = [sorted_swings[0]]

    for i in range(1, len(sorted_swings)):
        sw = sorted_swings[i]
        prev_price = current_cluster[-1].price
        # 计算价差百分比
        diff_pct = (sw.price - prev_price) / prev_price * Decimal("100") if prev_price > 0 else Decimal("0")
        abs_diff_pct = abs(diff_pct)

        if abs_diff_pct <= tolerance_pct:
            current_cluster.append(sw)
        else:
            zones.append(_make_zone(current_cluster, zone_type))
            current_cluster = [sw]

    zones.append(_make_zone(current_cluster, zone_type))

    # 只返回 strength >= 1 的 zone（全部保留，单点 zone 也有参考价值）
    return zones


def _make_zone(cluster: list[SwingPoint], zone_type: str) -> PriceZone:
    """从 swing 点聚类创建 PriceZone。"""
    prices = [s.price for s in cluster]
    upper = max(prices)
    lower = min(prices)
    midpoint = (upper + lower) / Decimal("2")
    timestamps = [s.timestamp for s in cluster]

    return PriceZone(
        zone_type=zone_type,
        upper=upper,
        lower=lower,
        midpoint=midpoint,
        strength=len(cluster),
        swing_ids=[s.id for s in cluster],
        formed_at=min(timestamps),
        last_tested_at=max(timestamps),
    )


def detect_no_trade_zones(
    support_zones: list[PriceZone],
    resistance_zones: list[PriceZone],
    last_price: Decimal | None,
    range_pct_threshold: Decimal = Decimal("8"),  # 支撑阻力间距 < 8% 视为窄幅震荡
) -> list[PriceZone]:
    """识别禁交易区域。

    当支撑区和阻力区之间的间距较小（窄幅震荡），
    且价格位于中部时，标记为 no_trade zone。

    Args:
        support_zones: 支撑区列表
        resistance_zones: 阻力区列表
        last_price: 最新价格
        range_pct_threshold: 判定为窄幅震荡的间距阈值（百分比）

    Returns:
        禁交易区域列表
    """
    if not support_zones or not resistance_zones or last_price is None:
        return []

    # 取最近的支撑和阻力
    nearest_support = min(support_zones, key=lambda z: abs(z.midpoint - last_price))
    nearest_resistance = min(resistance_zones, key=lambda z: abs(z.midpoint - last_price))

    # 计算支撑阻力间距
    range_pct = (nearest_resistance.midpoint - nearest_support.midpoint) / last_price * Decimal("100")
    if abs(range_pct) < range_pct_threshold:
        # 窄幅震荡 → 中部 1/3 区域为 no_trade
        zone_upper = nearest_support.midpoint + (nearest_resistance.midpoint - nearest_support.midpoint) * Decimal("2") / Decimal("3")
        zone_lower = nearest_support.midpoint + (nearest_resistance.midpoint - nearest_support.midpoint) * Decimal("1") / Decimal("3")
        return [
            PriceZone(
                zone_type="no_trade",
                upper=zone_upper,
                lower=zone_lower,
                midpoint=(zone_upper + zone_lower) / Decimal("2"),
                strength=2,
                swing_ids=[],
                formed_at=None,
                last_tested_at=None,
            )
        ]
    return []


def _compute_volatility(klines: list[Kline]) -> str:
    """计算波动率状态：基于最近 ATR（简化版）。"""
    if len(klines) < 14:
        return "normal"

    # 简化 ATR：最近 14 根 K 线的 (high - low) 平均值占收盘价百分比
    recent = klines[-14:]
    avg_range = sum(k.high - k.low for k in recent) / Decimal("14")
    last_close = recent[-1].close
    if last_close <= 0:
        return "normal"
    atr_pct = avg_range / last_close * Decimal("100")

    if atr_pct < Decimal("0.5"):
        return "low"
    elif atr_pct > Decimal("2"):
        return "high"
    return "normal"


def analyze_structure(
    klines: list[Kline],
    symbol: str,
    timeframe: str,
    swing_left: int = 2,
    swing_right: int = 2,
    zone_tolerance_pct: Decimal = Decimal("0.5"),
) -> StructureSnapshot:
    """市场结构识别主入口——完整分析流程。

    流程：K线 → swing 检测 → BOS/CHOCH → 趋势/震荡 → 支撑压力区 → 禁交易区 → 快照

    Args:
        klines: K 线序列（按时间升序）
        symbol: 交易对，如 "BTCUSDT"
        timeframe: 时间周期，如 "1h"
        swing_left: swing 检测左侧确认 K 线数
        swing_right: swing 检测右侧确认 K 线数
        zone_tolerance_pct: 支撑压力区聚合容差（百分比）

    Returns:
        StructureSnapshot 完整结构快照
    """
    from datetime import datetime, timezone

    # 1. Swing 检测
    swings = detect_swings(klines, left_bars=swing_left, right_bars=swing_right)
    swing_highs = [s for s in swings if s.type == SwingType.HIGH]
    swing_lows = [s for s in swings if s.type == SwingType.LOW]

    # 2. BOS / CHOCH 检测 + 趋势/状态
    bos_events, choch_events, trend_direction, market_state = detect_bos_choch(klines, swings)

    # 3. 支撑压力区
    support_zones, resistance_zones = detect_zones(swings, tolerance_pct=zone_tolerance_pct)

    # 4. 最新价格
    last_price = klines[-1].close if klines else None

    # 5. 禁交易区
    no_trade_zones = detect_no_trade_zones(support_zones, resistance_zones, last_price)

    # 6. 波动率
    volatility = _compute_volatility(klines)

    return StructureSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        captured_at=datetime.now(UTC),
        kline_count=len(klines),
        kline_start=klines[0].timestamp if klines else None,
        kline_end=klines[-1].timestamp if klines else None,
        market_state=market_state,
        trend_direction=trend_direction,
        swing_highs=swing_highs,
        swing_lows=swing_lows,
        bos_events=bos_events,
        choch_events=choch_events,
        support_zones=support_zones,
        resistance_zones=resistance_zones,
        no_trade_zones=no_trade_zones,
        volatility_state=volatility,
        last_price=last_price,
        config={
            "swing_left": swing_left,
            "swing_right": swing_right,
            "zone_tolerance_pct": str(zone_tolerance_pct),
        },
    )
