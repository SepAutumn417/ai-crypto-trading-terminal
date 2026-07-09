"""市场结构识别模块 v0.3。

识别 Swing High/Low、趋势/震荡状态、BOS/CHOCH、支撑压力区，
输出结构快照供前端展示和后续候选计划生成使用。

核心流程：
    K线序列 → swing 检测 → BOS/CHOCH → 趋势/震荡判断 → 支撑压力区 → 结构快照

使用示例：
    from market_structure import analyze_structure
    from exchange_adapter import Kline

    snapshot = analyze_structure(klines, symbol="BTCUSDT", timeframe="1h")
    print(snapshot.market_state)  # TREND / RANGE
    print(snapshot.trend_direction)  # BULLISH / BEARISH / NEUTRAL
"""
from .snapshot import analyze_structure
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

__all__ = [
    "analyze_structure",
    "BosEvent",
    "ChochEvent",
    "MarketState",
    "PriceZone",
    "StructureSnapshot",
    "SwingPoint",
    "SwingType",
    "TrendDirection",
]
