from decimal import Decimal

from position_sizing.calculator import calculate
from shared.configs import SymbolRule
from shared.enums import Direction


def _btc_rules():
    return SymbolRule(
        size_step=Decimal("0.001"), price_step=Decimal("0.1"),
        min_size=Decimal("0.001"), min_notional=Decimal("5"),
        max_leverage=Decimal("100"), fee_rate=Decimal("0.0005"),
    )


def test_calculate_long_basic():
    result = calculate(
        equity=Decimal("1500"), risk_percent=Decimal("1"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.LONG,
        symbol_rules=_btc_rules(),
    )
    assert result.risk_amount == Decimal("15")
    assert result.notional_value == Decimal("1872")
    assert result.raw_size == Decimal("0.03")
    assert result.rounded_size == Decimal("0.030")
    assert result.required_margin == Decimal("187.2")
    # P1-2: estimated_fee 现在是双边手续费（开仓 + 平仓）
    assert result.estimated_fee == Decimal("1.872")
    # P1-2: 滑点和资金费率
    assert result.estimated_slippage == Decimal("0.936")
    assert result.estimated_funding == Decimal("0.1872")
    assert result.risk_reward_ratio == Decimal("2.8")
    # P1-2: 最大损失 = 风险金额 + 双边手续费 + 滑点 + 资金费率
    assert result.estimated_loss_at_stop == Decimal("17.9952")
    assert result.sizing_warnings == []


def test_calculate_short_basic():
    result = calculate(
        equity=Decimal("1500"), risk_percent=Decimal("1"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("62900"),
        take_profit_prices=[Decimal("61000")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.SHORT,
        symbol_rules=_btc_rules(),
    )
    assert result.risk_amount == Decimal("15")
    assert result.risk_reward_ratio == Decimal("2.8")


def test_calculate_rounded_below_min_size():
    tiny_rules = SymbolRule(
        size_step=Decimal("1"), price_step=Decimal("0.1"),
        min_size=Decimal("1"), min_notional=Decimal("5"),
        max_leverage=Decimal("100"), fee_rate=Decimal("0.0005"),
    )
    result = calculate(
        equity=Decimal("10"), risk_percent=Decimal("0.1"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.LONG,
        symbol_rules=tiny_rules,
    )
    assert result.rounded_size is None
    assert any("min_size" in w or "min_notional" in w for w in result.sizing_warnings)


def test_calculate_no_stop_loss():
    result = calculate(
        equity=Decimal("1500"), risk_percent=Decimal("1"),
        entry_price=Decimal("62400"), stop_loss_price=None,
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.LONG,
        symbol_rules=_btc_rules(),
    )
    assert result.stop_distance_percent == Decimal("0")
    assert result.notional_value == Decimal("0")
    assert result.rounded_size is None
    assert any("stop_loss" in w.lower() for w in result.sizing_warnings)
