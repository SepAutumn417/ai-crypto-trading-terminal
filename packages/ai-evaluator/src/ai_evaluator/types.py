from decimal import Decimal
from enum import Enum
from typing import Optional
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


class IndicatorResult(BaseModel):
    name: str
    value: Optional[str] = None
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
