from typing import Optional
from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import DecisionGateResult, RiskCheckResult


def decide(
    risk_result: RiskCheckResult,
    execution_enabled: bool,
    kill_switch: bool,
    ai_evaluation: Optional[dict] = None,
    plan_expired: bool = False,
) -> DecisionGateResult:
    reasons: list[str] = []

    if plan_expired:
        return DecisionGateResult(result=DecisionGateStatus.EXPIRED, reasons=["plan_expired"])

    if not execution_enabled:
        return DecisionGateResult(
            result=DecisionGateStatus.BLOCK,
            reasons=["execution_disabled: 执行模式未开启"],
        )

    if kill_switch:
        return DecisionGateResult(
            result=DecisionGateStatus.BLOCK,
            reasons=["kill_switch_active: Kill Switch 已开启"],
        )

    match risk_result.status:
        case RiskStatus.ALLOW | RiskStatus.ALLOW_CONFIRM:
            return DecisionGateResult(result=DecisionGateStatus.ALLOW_CONFIRM, reasons=reasons)
        case RiskStatus.REDUCE_RISK:
            return DecisionGateResult(result=DecisionGateStatus.REDUCE_RISK, reasons=reasons)
        case RiskStatus.WARN:
            return DecisionGateResult(
                result=DecisionGateStatus.WAIT,
                reasons=["risk_warn: 风控警告，等待用户调整"],
            )
        case RiskStatus.BLOCK:
            return DecisionGateResult(
                result=DecisionGateStatus.BLOCK,
                reasons=list(risk_result.block_reasons),
            )