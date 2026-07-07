from decimal import Decimal, ROUND_DOWN


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    """按 step 向下取整。开仓量不能超过计算值。"""
    if step == 0:
        return value
    quotient = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return quotient * step