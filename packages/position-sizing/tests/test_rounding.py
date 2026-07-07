from decimal import Decimal
from position_sizing.rounding import round_to_step


def test_round_to_step_exact():
    assert round_to_step(Decimal("0.03"), Decimal("0.001")) == Decimal("0.030")


def test_round_to_step_down():
    assert round_to_step(Decimal("0.0305"), Decimal("0.001")) == Decimal("0.030")


def test_round_to_step_large():
    assert round_to_step(Decimal("1.2345"), Decimal("0.1")) == Decimal("1.2")


def test_round_to_step_zero():
    assert round_to_step(Decimal("0"), Decimal("0.001")) == Decimal("0")


def test_round_to_step_smaller_than_step():
    assert round_to_step(Decimal("0.0005"), Decimal("0.001")) == Decimal("0")