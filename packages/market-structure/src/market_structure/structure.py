"""BOS (Break of Structure) / CHOCH (Change of Character) 检测。

核心概念（Smart Money Concepts）：
- BOS：价格突破同向 swing 点，表示趋势延续。
  - 上涨趋势中价格突破前一个 swing high → bullish BOS（趋势延续）
  - 下跌趋势中价格跌破前一个 swing low → bearish BOS（趋势延续）
- CHOCH：价格突破反向 swing 点，表示趋势可能反转。
  - 上涨趋势中价格跌破最近 swing low → bearish CHOCH（反转信号）
  - 下跌趋势中价格突破最近 swing high → bullish CHOCH（反转信号）

判定规则：遍历 K 线序列，检查收盘价是否突破最近的 swing high/low。
突破以收盘价为准（避免影线假突破）。
"""
from __future__ import annotations

from decimal import Decimal

from exchange_adapter import Kline

from .types import (
    BosEvent,
    ChochEvent,
    MarketState,
    SwingPoint,
    SwingType,
    TrendDirection,
)


def detect_bos_choch(
    klines: list[Kline],
    swings: list[SwingPoint],
) -> tuple[list[BosEvent], list[ChochEvent], TrendDirection, MarketState]:
    """检测 BOS / CHOCH 事件，并推断趋势方向和市场状态。

    Args:
        klines: K 线序列（升序）
        swings: 已检测的 swing 点列表

    Returns:
        (bos_events, choch_events, trend_direction, market_state)
    """
    if not swings or len(klines) < 2:
        return [], [], TrendDirection.NEUTRAL, MarketState.RANGE

    bos_events: list[BosEvent] = []
    choch_events: list[ChochEvent] = []

    # 维护"尚未被突破"的最近 swing high / low
    current_trend = TrendDirection.NEUTRAL
    last_swing_high: SwingPoint | None = None
    last_swing_low: SwingPoint | None = None

    # 按 K 线位置遍历，遇到 swing 点时更新 last_swing，遇到突破时记录事件
    swing_by_index: dict[int, SwingPoint] = {s.index: s for s in swings}

    for i, k in enumerate(klines):
        # 先检查是否有 swing 点在此位置（用收盘前的高/低与 swing 价对比）
        # 注意：swing 的确认需要 right_bars 根 K 线，所以突破检测从第一个 swing 之后开始
        if i in swing_by_index:
            sw = swing_by_index[i]
            if sw.type == SwingType.HIGH:
                last_swing_high = sw
            else:
                last_swing_low = sw
            continue

        # 检查收盘价是否突破 last_swing_high（bullish）或 last_swing_low（bearish）
        close = k.close

        if last_swing_high is not None and close > last_swing_high.price:
            # 突破 swing high
            if current_trend == TrendDirection.BEARISH:
                # 下跌趋势中突破 swing high → CHOCH（看涨反转）
                choch_events.append(
                    ChochEvent(
                        direction=TrendDirection.BULLISH,
                        broken_swing_id=last_swing_high.id,
                        broken_price=last_swing_high.price,
                        break_index=i,
                        break_timestamp=k.timestamp,
                        close_price=close,
                    )
                )
                current_trend = TrendDirection.BULLISH
            elif current_trend in (TrendDirection.BULLISH, TrendDirection.NEUTRAL):
                # 上涨趋势或中性 → BOS（看涨延续）
                bos_events.append(
                    BosEvent(
                        direction=TrendDirection.BULLISH,
                        broken_swing_id=last_swing_high.id,
                        broken_price=last_swing_high.price,
                        break_index=i,
                        break_timestamp=k.timestamp,
                        close_price=close,
                    )
                )
                current_trend = TrendDirection.BULLISH
            # 标记已突破，避免重复触发
            last_swing_high = None

        if last_swing_low is not None and close < last_swing_low.price:
            # 跌破 swing low
            if current_trend == TrendDirection.BULLISH:
                # 上涨趋势中跌破 swing low → CHOCH（看跌反转）
                choch_events.append(
                    ChochEvent(
                        direction=TrendDirection.BEARISH,
                        broken_swing_id=last_swing_low.id,
                        broken_price=last_swing_low.price,
                        break_index=i,
                        break_timestamp=k.timestamp,
                        close_price=close,
                    )
                )
                current_trend = TrendDirection.BEARISH
            elif current_trend in (TrendDirection.BEARISH, TrendDirection.NEUTRAL):
                # 下跌趋势或中性 → BOS（看跌延续）
                bos_events.append(
                    BosEvent(
                        direction=TrendDirection.BEARISH,
                        broken_swing_id=last_swing_low.id,
                        broken_price=last_swing_low.price,
                        break_index=i,
                        break_timestamp=k.timestamp,
                        close_price=close,
                    )
                )
                current_trend = TrendDirection.BEARISH
            last_swing_low = None

    # 推断市场状态
    market_state = _infer_market_state(bos_events, choch_events)

    return bos_events, choch_events, current_trend, market_state


def _infer_market_state(
    bos_events: list[BosEvent],
    choch_events: list[ChochEvent],
) -> MarketState:
    """根据 BOS/CHOCH 事件推断市场状态。

    - 有 BOS 无 CHOCH → TREND（趋势明确）
    - 最近事件是 CHOCH 且之后无 BOS → TRANSITION（转换中）
    - 无 BOS 无 CHOCH → RANGE（震荡）
    """
    if not bos_events and not choch_events:
        return MarketState.RANGE

    if not choch_events:
        return MarketState.TREND

    # 比较最后一个 BOS 和最后一个 CHOCH 的时间
    last_bos_idx = bos_events[-1].break_index if bos_events else -1
    last_choch_idx = choch_events[-1].break_index

    if last_bos_idx > last_choch_idx:
        # BOS 在 CHOCH 之后 → CHOCH 被确认，进入趋势
        return MarketState.TREND
    else:
        # CHOCH 在最后 → 转换中
        return MarketState.TRANSITION
