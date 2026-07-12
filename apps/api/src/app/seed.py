from datetime import UTC, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccountRiskState, ConfigVersionModel, UserSettings
from shared.enums import ConfigType

SEED_RISK_V1 = {
    "max_risk_percent": Decimal("3"),
    "max_leverage": Decimal("10"),
    "min_risk_reward_ratio": Decimal("1.5"),
    "preferred_risk_reward_ratio": Decimal("2.0"),
    "min_stop_distance_percent": Decimal("0.3"),  # 0.3%（百分数基）
    "daily_loss_limit_r": Decimal("2"),
    "max_consecutive_losses": 2,
    "cooldown_minutes_after_loss": 30,
    "max_notional_equity_ratio": Decimal("20"),  # 名义价值/权益上限
}

SEED_EXECUTION_V1 = {
    "enabled": False,
    "mode": "dry_run",
    "margin_mode": "isolated",
    "allowed_order_types": ["limit"],
    "require_stop_loss": True,
    "require_user_confirmation": True,
    "require_second_confirmation": True,
}

SEED_OPPORTUNITY_GRADE_V1 = {
    "A": {"max_risk_percent": Decimal("3")},
    "B": {"max_risk_percent": Decimal("1.5")},
    "C": {"max_risk_percent": Decimal("0")},
    "BLOCKED": {"max_risk_percent": Decimal("0")},
}

SEED_SYMBOL_RULES_V1 = {
    "BTCUSDT": {
        "size_step": Decimal("0.001"),
        "price_step": Decimal("0.1"),
        "min_size": Decimal("0.001"),
        "min_notional": Decimal("5"),
        "max_leverage": Decimal("100"),
        "fee_rate": Decimal("0.0005"),
        # P1-2: 滑点和资金费率纳入最大损失约束
        "slippage_rate": Decimal("0.0005"),  # 0.05%
        "funding_rate": Decimal("0.0001"),  # 0.01%（8h）
    },
    "ETHUSDT": {
        "size_step": Decimal("0.01"),
        "price_step": Decimal("0.01"),
        "min_size": Decimal("0.01"),
        "min_notional": Decimal("5"),
        "max_leverage": Decimal("75"),
        "fee_rate": Decimal("0.0005"),
        "slippage_rate": Decimal("0.0005"),
        "funding_rate": Decimal("0.0001"),
    },
    "SOLUSDT": {
        "size_step": Decimal("0.1"),
        "price_step": Decimal("0.001"),
        "min_size": Decimal("0.1"),
        "min_notional": Decimal("5"),
        "max_leverage": Decimal("50"),
        "fee_rate": Decimal("0.0005"),
        "slippage_rate": Decimal("0.0005"),
        "funding_rate": Decimal("0.0001"),
    },
}


def _decimal_to_str(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _decimal_to_str(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decimal_to_str(v) for v in value]
    return value


async def seed_all(db: AsyncSession) -> None:
    existing = await db.get(UserSettings, 1)
    if existing is None:
        db.add(UserSettings(
            id=1,
            execution_enabled=False,
            kill_switch=True,
            account_equity=None,
            mode="training",
        ))

    existing = await db.get(AccountRiskState, 1)
    if existing is None:
        db.add(AccountRiskState(
            id=1,
            daily_loss_r=Decimal("0"),
            consecutive_losses=0,
            cooldown_until=None,
            last_trade_date=None,
        ))

    seeds = [
        (ConfigType.RISK, "risk-v1", SEED_RISK_V1),
        (ConfigType.EXECUTION, "execution-v1", SEED_EXECUTION_V1),
        (ConfigType.OPPORTUNITY_GRADE, "opportunity_grade-v1", SEED_OPPORTUNITY_GRADE_V1),
        (ConfigType.SYMBOL_RULES, "symbol_rules-v1", SEED_SYMBOL_RULES_V1),
    ]
    for cfg_type, label, payload in seeds:
        result = await db.execute(
            select(ConfigVersionModel).where(
                ConfigVersionModel.config_type == cfg_type.value,
                ConfigVersionModel.version_label == label,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(ConfigVersionModel(
                id=uuid4(),
                config_type=cfg_type.value,
                version_label=label,
                payload=_decimal_to_str(payload),
                is_active=True,
                activated_at=datetime.now(UTC),
            ))

    await db.commit()
