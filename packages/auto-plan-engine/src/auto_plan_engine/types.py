"""自动候选计划引擎核心类型定义。"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SetupType(str, Enum):
    """候选计划类型——对应 AUTOMATION_DESIGN.md §3。"""

    TREND_PULLBACK_LONG = "TREND_PULLBACK_LONG"        # 上升趋势回踩做多
    TREND_PULLBACK_SHORT = "TREND_PULLBACK_SHORT"       # 下降趋势反抽做空
    RANGE_SUPPORT_BOUNCE = "RANGE_SUPPORT_BOUNCE"       # 震荡支撑反弹
    RANGE_RESISTANCE_REJECT = "RANGE_RESISTANCE_REJECT" # 震荡阻力回落
    BREAKOUT_RETEST_LONG = "BREAKOUT_RETEST_LONG"       # 突破后回踩确认做多
    BREAKDOWN_RETEST_SHORT = "BREAKDOWN_RETEST_SHORT"   # 跌破后反抽确认做空
    FALSE_BREAK_REVERSAL = "FALSE_BREAK_REVERSAL"       # 假突破反向


class CandidateStatus(str, Enum):
    """候选计划状态机——对应 AUTOMATION_DESIGN.md §4。

    流转：DISCOVERED → WATCHING → READY → RISK_CHECKED → AI_EVALUATED
          → ALLOW_CONFIRM / WAIT / BLOCK / EXPIRED
    """

    DISCOVERED = "DISCOVERED"       # 系统发现潜在机会
    WATCHING = "WATCHING"           # 进入观察，等待触发
    READY = "READY"                 # 入场条件接近满足
    RISK_CHECKED = "RISK_CHECKED"   # 已完成风控预检查
    AI_EVALUATED = "AI_EVALUATED"   # 已完成 AI 评估
    ALLOW_CONFIRM = "ALLOW_CONFIRM" # 允许用户确认执行
    WAIT = "WAIT"                   # 条件不足，继续等待
    BLOCK = "BLOCK"                 # 风控禁止
    EXPIRED = "EXPIRED"             # 计划失效


class CandidateDirection(str, Enum):
    """候选计划方向。"""

    LONG = "long"
    SHORT = "short"


class CandidatePlan(BaseModel):
    """候选交易计划。

    由 Auto Plan Engine 根据结构快照自动生成，
    经风控预检查和 AI 评估后可 promote 为正式 TradePlan。

    对应数据库表 candidate_plans。
    """

    id: UUID = Field(default_factory=uuid4)
    structure_snapshot_id: UUID | None = None
    exchange: str = "bitget"
    symbol: str
    timeframe: str = "1h"
    direction: CandidateDirection
    setup_type: SetupType
    # 入场区域（价格区间）
    entry_zone_upper: Decimal
    entry_zone_lower: Decimal
    entry_price: Decimal | None = None  # 建议入场价（区间中点或触发价）
    stop_loss_price: Decimal
    take_profit_prices: list[Decimal] = Field(default_factory=list)
    risk_reward_ratio: Decimal | None = None
    # 机会评级：A / B / C / BLOCKED
    opportunity_grade: str = "C"
    # 状态机
    status: CandidateStatus = CandidateStatus.DISCOVERED
    invalidation_reason: str | None = None
    # 生成依据
    rationale: str = ""  # 生成此候选计划的理由摘要
    structure_signals: dict[str, Any] = Field(default_factory=dict)
    # 配置版本
    strategy_config_version: str | None = None
    # 时间戳
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_db_dict(self) -> dict[str, Any]:
        """转换为数据库行 dict。"""
        return {
            "id": str(self.id),
            "structure_snapshot_id": str(self.structure_snapshot_id) if self.structure_snapshot_id else None,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "setup_type": self.setup_type.value,
            "entry_zone": {
                "upper": str(self.entry_zone_upper),
                "lower": str(self.entry_zone_lower),
            },
            "entry_price": str(self.entry_price) if self.entry_price else None,
            "stop_loss_price": str(self.stop_loss_price),
            "take_profit_prices": [str(tp) for tp in self.take_profit_prices],
            "risk_reward_ratio": str(self.risk_reward_ratio) if self.risk_reward_ratio else None,
            "opportunity_grade": self.opportunity_grade,
            "status": self.status.value,
            "invalidation_reason": self.invalidation_reason,
            "rationale": self.rationale,
            "structure_signals": self.structure_signals,
            "strategy_config_version": self.strategy_config_version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
