"""市场结构识别核心类型定义。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SwingType(str, Enum):
    """Swing 点类型。"""

    HIGH = "high"
    LOW = "low"


class MarketState(str, Enum):
    """市场状态：趋势 / 震荡。"""

    TREND = "trend"
    RANGE = "range"
    TRANSITION = "transition"  # 结构转换中（CHOCH 刚发生但未确认 BOS）


class TrendDirection(str, Enum):
    """趋势方向。"""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class SwingPoint(BaseModel):
    """单个 Swing High / Low。

    index: K 线在输入序列中的位置（0-based）
    price: swing 价格（high 或 low）
    timestamp: K 线时间戳
    confirmed: 是否被后续 N 根 K 线确认（Fractal 确认）
    """

    id: UUID = Field(default_factory=uuid4)
    type: SwingType
    index: int
    price: Decimal
    timestamp: datetime
    confirmed: bool = False
    # 结构序列标签：HH (Higher High) / HL (Higher Low) / LH (Lower High) / LL (Lower Low)
    structure_label: str | None = None


class BosEvent(BaseModel):
    """Break of Structure 事件。

    价格突破前一个 swing high（ bullish BOS）或 swing low（bearish BOS），
    表示趋势延续。
    """

    id: UUID = Field(default_factory=uuid4)
    direction: TrendDirection  # BULLISH=突破 swing high, BEARISH=突破 swing low
    broken_swing_id: UUID  # 被突破的 swing point id
    broken_price: Decimal  # 被突破的 swing 价格
    break_index: int  # 突破发生的 K 线位置
    break_timestamp: datetime
    close_price: Decimal  # 突破 K 线收盘价


class ChochEvent(BaseModel):
    """Change of Character 事件。

    趋势反转的早期信号：价格突破反向的 swing 点。
    例如上涨趋势中价格跌破最近 swing low → bearish CHOCH。
    """

    id: UUID = Field(default_factory=uuid4)
    direction: TrendDirection  # 反转后的方向
    broken_swing_id: UUID
    broken_price: Decimal
    break_index: int
    break_timestamp: datetime
    close_price: Decimal


class PriceZone(BaseModel):
    """支撑/阻力价格区间。

    多个 swing 点聚集形成的区域，价格在该区域有较高概率出现反应。
    """

    id: UUID = Field(default_factory=uuid4)
    zone_type: str  # "support" / "resistance" / "no_trade"
    upper: Decimal
    lower: Decimal
    midpoint: Decimal
    strength: int = 1  # 形成该区域的 swing 点数量，越多越强
    swing_ids: list[UUID] = Field(default_factory=list)
    # 首次形成 / 最后触碰时间
    formed_at: datetime | None = None
    last_tested_at: datetime | None = None


class StructureSnapshot(BaseModel):
    """市场结构快照——一次完整分析的输出。

    包含 swing 点序列、BOS/CHOCH 事件、支撑压力区、市场状态等。
    用于持久化到 market_structure_snapshots 表和前端展示。
    """

    id: UUID = Field(default_factory=uuid4)
    symbol: str
    timeframe: str
    captured_at: datetime
    # 分析输入信息
    kline_count: int
    kline_start: datetime | None = None
    kline_end: datetime | None = None
    # 市场状态
    market_state: MarketState
    trend_direction: TrendDirection
    # 结构元素
    swing_highs: list[SwingPoint] = Field(default_factory=list)
    swing_lows: list[SwingPoint] = Field(default_factory=list)
    bos_events: list[BosEvent] = Field(default_factory=list)
    choch_events: list[ChochEvent] = Field(default_factory=list)
    support_zones: list[PriceZone] = Field(default_factory=list)
    resistance_zones: list[PriceZone] = Field(default_factory=list)
    no_trade_zones: list[PriceZone] = Field(default_factory=list)
    # 波动率状态
    volatility_state: str = "normal"  # low / normal / high
    # 最近价格
    last_price: Decimal | None = None
    # 算法参数（用于追溯）
    config: dict[str, Any] = Field(default_factory=dict)

    def to_db_dict(self) -> dict[str, Any]:
        """转换为数据库行 dict（JSONB 字段用 JSON 字符串）。"""
        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "captured_at": self.captured_at,
            "market_state": self.market_state.value,
            "trend_direction": self.trend_direction.value,
            "swing_highs": [s.model_dump(mode="json") for s in self.swing_highs],
            "swing_lows": [s.model_dump(mode="json") for s in self.swing_lows],
            "bos_events": [e.model_dump(mode="json") for e in self.bos_events],
            "choch_events": [e.model_dump(mode="json") for e in self.choch_events],
            "support_zones": [z.model_dump(mode="json") for z in self.support_zones],
            "resistance_zones": [z.model_dump(mode="json") for z in self.resistance_zones],
            "no_trade_zones": [z.model_dump(mode="json") for z in self.no_trade_zones],
            "volatility_state": self.volatility_state,
            "last_price": str(self.last_price) if self.last_price else None,
            "kline_count": self.kline_count,
            "kline_start": self.kline_start.isoformat() if self.kline_start else None,
            "kline_end": self.kline_end.isoformat() if self.kline_end else None,
            "config": self.config,
        }
