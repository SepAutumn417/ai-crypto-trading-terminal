from decimal import Decimal
from shared.enums import Direction, OpportunityGrade
from shared.schemas import TradePlanInput, PositionSizingResult
from shared.configs import RiskConfig, SymbolRule, SymbolRules


def test_trade_plan_input_creation():
    plan = TradePlanInput(
        symbol="BTCUSDT",
        direction=Direction.LONG,
        entry_price=Decimal("62400"),
        stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800"), Decimal("64500")],
        leverage=Decimal("10"),
        risk_percent=Decimal("1"),
        opportunity_grade=OpportunityGrade.A,
        equity=Decimal("1500"),
    )
    assert plan.symbol == "BTCUSDT"
    assert plan.entry_price == Decimal("62400")


def test_position_sizing_result_defaults():
    result = PositionSizingResult(
        equity=Decimal("1500"), risk_percent=Decimal("1"), risk_amount=Decimal("15"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"), notional_value=Decimal("1875"),
        raw_size=Decimal("0.03"), rounded_size=Decimal("0.030"),
        required_margin=Decimal("187.5"), leverage=Decimal("10"),
        estimated_fee=Decimal("0.9375"), risk_reward_ratio=Decimal("2.24"),
        estimated_loss_at_stop=Decimal("15.9375"),
    )
    assert result.sizing_warnings == []


def test_symbol_rules_lookup():
    rules = SymbolRules(rules={
        "BTCUSDT": SymbolRule(
            size_step=Decimal("0.001"), price_step=Decimal("0.1"),
            min_size=Decimal("0.001"), min_notional=Decimal("5"),
            max_leverage=Decimal("100"), fee_rate=Decimal("0.0005"),
        )
    })
    assert rules.get("BTCUSDT") is not None
    assert rules.get("ETHUSDT") is None
