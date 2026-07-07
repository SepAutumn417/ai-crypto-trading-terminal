from decimal import Decimal
from shared.configs import SymbolRule, SymbolRules
from shared.enums import Direction
from shared.schemas import PositionSizingResult
from position_sizing.rounding import round_to_step


def calculate(
    equity: Decimal,
    risk_percent: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal | None,
    take_profit_prices: list[Decimal],
    leverage: Decimal,
    fee_rate: Decimal,
    direction: Direction,
    symbol_rules: SymbolRule,
) -> PositionSizingResult:
    if isinstance(symbol_rules, SymbolRules):
        raise TypeError("请传入 SymbolRule 而非 SymbolRules")

    if equity <= 0:
        raise ValueError(f"equity 必须为正数，当前值: {equity}")
    if risk_percent < 0:
        raise ValueError(f"risk_percent 不能为负数，当前值: {risk_percent}")
    if entry_price <= 0:
        raise ValueError(f"entry_price 必须为正数，当前值: {entry_price}")
    if leverage <= 0:
        raise ValueError(f"leverage 必须为正数，当前值: {leverage}")
    if fee_rate < 0:
        raise ValueError(f"fee_rate 不能为负数，当前值: {fee_rate}")
    if stop_loss_price is not None and stop_loss_price <= 0:
        raise ValueError(f"stop_loss_price 必须为正数，当前值: {stop_loss_price}")
    if any(tp <= 0 for tp in take_profit_prices):
        raise ValueError("take_profit_prices 中的价格必须为正数")

    risk_amount = equity * risk_percent / Decimal("100")

    if stop_loss_price is None or entry_price == 0:
        stop_distance_percent = Decimal("0")
    else:
        stop_distance_percent = abs(entry_price - stop_loss_price) / entry_price

    if stop_distance_percent > 0:
        notional_value = risk_amount / stop_distance_percent
    else:
        notional_value = Decimal("0")

    if entry_price > 0 and notional_value > 0:
        raw_size = notional_value / entry_price
    else:
        raw_size = Decimal("0")

    warnings: list[str] = []
    rounded_size: Decimal | None = None

    if stop_loss_price is None:
        warnings.append("no_stop_loss: 缺少止损价，无法计算有效仓位")
    elif stop_distance_percent == 0:
        warnings.append("zero_stop_distance: 止损距离为 0")
    else:
        rounded_size = round_to_step(raw_size, symbol_rules.size_step)
        if rounded_size < symbol_rules.min_size:
            warnings.append(f"below_min_size: rounded_size={rounded_size} < min_size={symbol_rules.min_size}")
            rounded_size = None
        elif rounded_size * entry_price < symbol_rules.min_notional:
            warnings.append(f"below_min_notional: notional={rounded_size * entry_price} < min_notional={symbol_rules.min_notional}")
            rounded_size = None

    required_margin = notional_value / leverage if leverage > 0 else Decimal("0")
    estimated_fee = notional_value * fee_rate

    if stop_distance_percent > 0 and take_profit_prices:
        if direction == Direction.LONG:
            tp_distance = take_profit_prices[0] - entry_price
        else:
            tp_distance = entry_price - take_profit_prices[0]
        risk_reward_ratio = tp_distance / (stop_distance_percent * entry_price)
    else:
        risk_reward_ratio = Decimal("0")

    estimated_loss_at_stop = risk_amount + estimated_fee

    return PositionSizingResult(
        equity=equity, risk_percent=risk_percent, risk_amount=risk_amount,
        entry_price=entry_price, stop_loss_price=stop_loss_price,
        stop_distance_percent=stop_distance_percent, notional_value=notional_value,
        raw_size=raw_size, rounded_size=rounded_size, required_margin=required_margin,
        leverage=leverage, estimated_fee=estimated_fee,
        risk_reward_ratio=risk_reward_ratio,
        estimated_loss_at_stop=estimated_loss_at_stop,
        sizing_warnings=warnings,
    )