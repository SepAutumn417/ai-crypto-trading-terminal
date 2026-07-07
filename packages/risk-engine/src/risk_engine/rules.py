from datetime import datetime
from decimal import Decimal

from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import OpportunityGrade, RiskStatus
from shared.schemas import PositionSizingResult, TradePlanInput


def grade_max_risk(grade: OpportunityGrade, cfg: OpportunityGradeConfig) -> Decimal:
    match grade:
        case OpportunityGrade.A: return cfg.a_max_risk_percent
        case OpportunityGrade.B: return cfg.b_max_risk_percent
        case OpportunityGrade.C: return cfg.c_max_risk_percent
        case OpportunityGrade.BLOCKED: return cfg.blocked_max_risk_percent


def grade_to_status(grade: OpportunityGrade) -> RiskStatus:
    match grade:
        case OpportunityGrade.A: return RiskStatus.ALLOW
        case OpportunityGrade.B: return RiskStatus.REDUCE_RISK
        case OpportunityGrade.C | OpportunityGrade.BLOCKED: return RiskStatus.BLOCK


def check_hard_blocks(
    sizing: PositionSizingResult,
    risk_cfg: RiskConfig,
    exec_cfg: ExecutionConfig,
    account: AccountRiskState,
    plan: TradePlanInput,
    kill_switch: bool,
    db_healthy: bool,
    now: datetime,
) -> list[str]:
    reasons: list[str] = []

    if plan.stop_loss_price is None:
        reasons.append("no_stop_loss: 缺少止损价")

    if plan.risk_percent > risk_cfg.max_risk_percent:
        reasons.append(f"risk_percent_excessive: {plan.risk_percent} > {risk_cfg.max_risk_percent}")

    if plan.leverage > risk_cfg.max_leverage:
        reasons.append(f"leverage_excessive: {plan.leverage} > {risk_cfg.max_leverage}")

    # 单位换算：sizing.stop_distance_percent 是小数（如 0.008 = 0.8%），
    # min_stop_distance_percent 是百分数基（如 0.3 = 0.3%），
    # 比较前乘 100 转为同一量级。
    stop_dist_pct = sizing.stop_distance_percent * Decimal("100")
    if plan.stop_loss_price is not None and stop_dist_pct < risk_cfg.min_stop_distance_percent:
        reasons.append(
            f"stop_distance_too_small: {stop_dist_pct}% "
            f"< {risk_cfg.min_stop_distance_percent}%"
        )

    if sizing.risk_reward_ratio < risk_cfg.min_risk_reward_ratio:
        reasons.append(f"risk_reward_too_low: {sizing.risk_reward_ratio} < {risk_cfg.min_risk_reward_ratio}")

    if account.daily_loss_r >= risk_cfg.daily_loss_limit_r:
        reasons.append(f"daily_loss_limit_reached: {account.daily_loss_r} >= {risk_cfg.daily_loss_limit_r}")

    if account.consecutive_losses >= risk_cfg.max_consecutive_losses:
        reasons.append(f"consecutive_loss_limit_reached: {account.consecutive_losses} >= {risk_cfg.max_consecutive_losses}")

    if account.cooldown_until is not None and now < account.cooldown_until:
        reasons.append(f"cooldown_active: {account.cooldown_until} > {now}")

    if kill_switch:
        reasons.append("kill_switch_active: Kill Switch 已开启")

    if not db_healthy:
        reasons.append("db_unhealthy: 数据库不可用")

    if plan.stop_loss_price is not None and sizing.rounded_size is None:
        reasons.append(f"sizing_failed: {', '.join(sizing.sizing_warnings) or 'rounded_size is None'}")

    if sizing.equity > 0 and sizing.notional_value / sizing.equity > risk_cfg.max_notional_equity_ratio:
        reasons.append(
            f"notional_equity_ratio_exceeded: "
            f"notional/equity={sizing.notional_value / sizing.equity:.2f} "
            f"> {risk_cfg.max_notional_equity_ratio}"
        )

    return reasons


def check_warnings(
    sizing: PositionSizingResult,
    account: AccountRiskState,
    plan: TradePlanInput,
) -> list[str]:
    warnings: list[str] = []
    if account.consecutive_losses > 0:
        warnings.append(f"recent_loss: consecutive_losses={account.consecutive_losses}")
    if sizing.notional_value > 0:
        ratio = sizing.notional_value / sizing.equity
        if ratio > Decimal("5"):
            warnings.append(f"wide_stop: notional/equity={ratio} 偏高")
    return warnings
