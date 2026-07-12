from datetime import UTC, datetime, timezone
from decimal import Decimal

from risk_engine.rules import (
    check_hard_blocks,
    check_warnings,
    grade_max_risk,
    grade_to_status,
)
from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import RiskStatus
from shared.schemas import PositionSizingResult, RiskCheckResult, TradePlanInput


def check(
    sizing_result: PositionSizingResult,
    risk_config: RiskConfig,
    execution_config: ExecutionConfig,
    opportunity_grade_config: OpportunityGradeConfig,
    account_risk_state: AccountRiskState,
    plan: TradePlanInput,
    execution_enabled: bool,
    kill_switch: bool,
    exchange_connected: bool,
    db_healthy: bool,
) -> RiskCheckResult:
    now = datetime.now(UTC)

    block_reasons = check_hard_blocks(
        sizing=sizing_result, risk_cfg=risk_config, exec_cfg=execution_config,
        account=account_risk_state, plan=plan,
        kill_switch=kill_switch, db_healthy=db_healthy, now=now,
    )

    if block_reasons:
        return RiskCheckResult(
            status=RiskStatus.BLOCK,
            risk_amount=sizing_result.risk_amount,
            notional_value=sizing_result.notional_value,
            required_margin=sizing_result.required_margin,
            risk_reward_ratio=sizing_result.risk_reward_ratio,
            max_allowed_risk_percent=Decimal("0"),
            warnings=[], block_reasons=block_reasons, risk_config_version=None,
        )

    grade_status = grade_to_status(plan.opportunity_grade)
    max_allowed = grade_max_risk(plan.opportunity_grade, opportunity_grade_config)
    warnings = check_warnings(sizing=sizing_result, account=account_risk_state, plan=plan)

    if not exchange_connected:
        warnings.append("exchange_disconnected: v0.1 无交易所连接（正常）")

    if grade_status == RiskStatus.BLOCK:
        return RiskCheckResult(
            status=RiskStatus.BLOCK,
            risk_amount=sizing_result.risk_amount,
            notional_value=sizing_result.notional_value,
            required_margin=sizing_result.required_margin,
            risk_reward_ratio=sizing_result.risk_reward_ratio,
            max_allowed_risk_percent=Decimal("0"),
            warnings=warnings,
            block_reasons=[f"grade_blocked: 机会等级 {plan.opportunity_grade.value} 不允许交易"],
            risk_config_version=None,
        )

    if grade_status == RiskStatus.REDUCE_RISK:
        return RiskCheckResult(
            status=RiskStatus.REDUCE_RISK,
            risk_amount=sizing_result.risk_amount,
            notional_value=sizing_result.notional_value,
            required_margin=sizing_result.required_margin,
            risk_reward_ratio=sizing_result.risk_reward_ratio,
            max_allowed_risk_percent=max_allowed,
            warnings=warnings, block_reasons=[], risk_config_version=None,
        )

    return RiskCheckResult(
        status=RiskStatus.ALLOW,
        risk_amount=sizing_result.risk_amount,
        notional_value=sizing_result.notional_value,
        required_margin=sizing_result.required_margin,
        risk_reward_ratio=sizing_result.risk_reward_ratio,
        max_allowed_risk_percent=max_allowed,
        warnings=warnings, block_reasons=[], risk_config_version=None,
    )
