from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AccountRiskState as AccountRiskStateModel,
)
from app.models import (
    ConfigVersionModel,
)
from app.models import (
    UserSettings as UserSettingsModel,
)
from shared.account import AccountRiskState, UserSettings
from shared.configs import (
    ExecutionConfig,
    OpportunityGradeConfig,
    RiskConfig,
    SymbolRule,
    SymbolRules,
)
from shared.enums import ConfigType, MarginMode, OrderType


def _parse_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _get_payload(version: ConfigVersionModel) -> dict:
    return version.payload or {}


async def _get_active(db: AsyncSession, config_type: str) -> ConfigVersionModel:
    result = await db.execute(
        select(ConfigVersionModel).where(
            ConfigVersionModel.config_type == config_type,
            ConfigVersionModel.is_active == True,  # noqa: E712
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise LookupError(f"No active version for {config_type}")
    return version


async def get_active_risk_config(db: AsyncSession) -> tuple[RiskConfig, str]:
    version = await _get_active(db, ConfigType.RISK.value)
    p = _get_payload(version)
    return (
        RiskConfig(
            max_risk_percent=_parse_decimal(p["max_risk_percent"]),
            max_leverage=_parse_decimal(p["max_leverage"]),
            min_risk_reward_ratio=_parse_decimal(p["min_risk_reward_ratio"]),
            preferred_risk_reward_ratio=_parse_decimal(p["preferred_risk_reward_ratio"]),
            min_stop_distance_percent=_parse_decimal(p["min_stop_distance_percent"]),
            daily_loss_limit_r=_parse_decimal(p["daily_loss_limit_r"]),
            max_consecutive_losses=int(p["max_consecutive_losses"]),
            cooldown_minutes_after_loss=int(p["cooldown_minutes_after_loss"]),
            max_notional_equity_ratio=_parse_decimal(p.get("max_notional_equity_ratio", 20)),
        ),
        version.version_label,
    )


async def get_active_execution_config(db: AsyncSession) -> tuple[ExecutionConfig, str]:
    version = await _get_active(db, ConfigType.EXECUTION.value)
    p = _get_payload(version)
    return (
        ExecutionConfig(
            enabled=bool(p.get("enabled", False)),
            mode=p.get("mode", "dry_run"),
            margin_mode=MarginMode(p.get("margin_mode", "isolated")),
            allowed_order_types=[OrderType(t) for t in p.get("allowed_order_types", ["limit"])],
            require_stop_loss=bool(p.get("require_stop_loss", True)),
            require_user_confirmation=bool(p.get("require_user_confirmation", True)),
            require_second_confirmation=bool(p.get("require_second_confirmation", True)),
        ),
        version.version_label,
    )


async def get_active_opportunity_grade_config(db: AsyncSession) -> tuple[OpportunityGradeConfig, str]:
    version = await _get_active(db, ConfigType.OPPORTUNITY_GRADE.value)
    p = _get_payload(version)
    return (
        OpportunityGradeConfig(
            a_max_risk_percent=_parse_decimal(p["A"]["max_risk_percent"]),
            b_max_risk_percent=_parse_decimal(p["B"]["max_risk_percent"]),
            c_max_risk_percent=_parse_decimal(p["C"]["max_risk_percent"]),
            blocked_max_risk_percent=_parse_decimal(p["BLOCKED"]["max_risk_percent"]),
        ),
        version.version_label,
    )


async def get_ai_indicator_weights(db: AsyncSession) -> dict[str, Decimal]:
    """从 active opportunity_grade 配置 payload 中读取可选的 ai_weights 子字段。

    payload 结构示例：
      {"A": {...}, "B": {...}, ..., "ai_weights": {"rsi": 1.5, "macd": 1.5, ...}}

    配置不存在或无 ai_weights 字段时返回空 dict，调用方据此回退到默认权重。
    """
    try:
        version = await _get_active(db, ConfigType.OPPORTUNITY_GRADE.value)
    except LookupError:
        return {}
    p = _get_payload(version)
    raw = p.get("ai_weights") or {}
    return {k: _parse_decimal(v) for k, v in raw.items()}


async def get_active_symbol_rules(db: AsyncSession) -> tuple[SymbolRules, str]:
    version = await _get_active(db, ConfigType.SYMBOL_RULES.value)
    p = _get_payload(version)
    rules = {
        sym: SymbolRule(
            size_step=_parse_decimal(r["size_step"]),
            price_step=_parse_decimal(r["price_step"]),
            min_size=_parse_decimal(r["min_size"]),
            min_notional=_parse_decimal(r["min_notional"]),
            max_leverage=_parse_decimal(r["max_leverage"]),
            fee_rate=_parse_decimal(r["fee_rate"]),
            # P1-2: 滑点和资金费率（向后兼容，旧配置无此字段时使用默认值）
            slippage_rate=_parse_decimal(r.get("slippage_rate", "0.0005")),
            funding_rate=_parse_decimal(r.get("funding_rate", "0.0001")),
        )
        for sym, r in p.items()
    }
    return SymbolRules(rules=rules), version.version_label


async def get_symbol_rule(db: AsyncSession, symbol: str) -> SymbolRule:
    rules, _ = await get_active_symbol_rules(db)
    rule = rules.get(symbol)
    if rule is None:
        raise ValueError(f"Symbol {symbol} not in active symbol_rules")
    return rule


async def get_account_risk_state(db: AsyncSession) -> AccountRiskState:
    model = await db.get(AccountRiskStateModel, 1)
    if model is None:
        return AccountRiskState()
    return AccountRiskState(
        daily_loss_r=model.daily_loss_r,
        consecutive_losses=model.consecutive_losses,
        cooldown_until=model.cooldown_until,
        last_trade_date=model.last_trade_date,
    )


async def get_user_settings(db: AsyncSession) -> UserSettings | None:
    model = await db.get(UserSettingsModel, 1)
    if model is None:
        return None
    return UserSettings(
        execution_enabled=model.execution_enabled,
        kill_switch=model.kill_switch,
        account_equity=model.account_equity,
        mode=model.mode,
    )
