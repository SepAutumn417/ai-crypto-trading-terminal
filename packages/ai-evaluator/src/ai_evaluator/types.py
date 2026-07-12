from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class EvaluationGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class SignalType(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class RecommendedAction(str, Enum):
    """AI 推荐动作——对应 AI_GUARDRAILS §5.1 DecisionGate 合并矩阵。"""
    WAIT = "WAIT"
    ALLOW_CONFIRM = "ALLOW_CONFIRM"
    REDUCE_RISK = "REDUCE_RISK"
    DO_NOT_TRADE = "DO_NOT_TRADE"


class IndicatorResult(BaseModel):
    name: str
    value: str | None = None
    signal: SignalType
    weight: Decimal
    score: Decimal
    explanation: str


class AIEvaluationResult(BaseModel):
    symbol: str
    direction: str
    overall_score: Decimal
    grade: EvaluationGrade
    recommendation: str
    signals: list[IndicatorResult]
    summary: str
    risk_level: str
    conviction: Decimal


# ===== v0.5: LLM 结构化输入/输出 =====


class AIInput(BaseModel):
    """AI 评估的结构化输入——对应 AI_GUARDRAILS §2。"""
    marketStructure: dict[str, Any]
    candidatePlan: dict[str, Any]
    riskResult: dict[str, Any]
    recentTradeState: dict[str, Any] | None = None
    systemMode: str = "L4_CONFIRM_EXECUTION"


class AIExplanation(BaseModel):
    """AI 评估的结构化输出——对应 AI_GUARDRAILS §3。"""
    summary: str = ""
    marketStateExplanation: str = ""
    planQualityExplanation: str = ""
    riskExplanation: str = ""
    opportunityGradeComment: str = ""
    recommendedAction: RecommendedAction = RecommendedAction.WAIT
    warnings: list[str] = []
    upgradeConditions: list[str] = []
    invalidationConditions: list[str] = []
    emotionalRiskFlags: list[str] = []


class AISource(str, Enum):
    """AI 评估结果来源。"""
    LLM = "llm"
    RULE_BASED = "rule_based"


class ComprehensiveEvaluation(BaseModel):
    """v0.5 综合评估结果——包含规则评分 + LLM 解释。"""
    # 规则评分部分（始终存在）
    symbol: str
    direction: str
    overall_score: Decimal
    grade: EvaluationGrade
    recommendation: str
    signals: list[IndicatorResult]
    risk_level: str
    conviction: Decimal
    # LLM 解释部分（超时/失败时为 None）
    explanation: AIExplanation | None = None
    source: AISource = AISource.RULE_BASED
