from enum import Enum


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class MarginMode(str, Enum):
    ISOLATED = "isolated"
    CROSSED = "crossed"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OpportunityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    BLOCKED = "BLOCKED"


class RiskStatus(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_CONFIRM = "ALLOW_CONFIRM"
    WARN = "WARN"
    REDUCE_RISK = "REDUCE_RISK"
    BLOCK = "BLOCK"


class DecisionGateStatus(str, Enum):
    ALLOW_CONFIRM = "ALLOW_CONFIRM"
    WAIT = "WAIT"
    REDUCE_RISK = "REDUCE_RISK"
    BLOCK = "BLOCK"
    EXPIRED = "EXPIRED"


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    CHECKED = "CHECKED"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ConfigType(str, Enum):
    RISK = "risk"
    EXECUTION = "execution"
    OPPORTUNITY_GRADE = "opportunity_grade"
    SYMBOL_RULES = "symbol_rules"
