from decimal import Decimal
from typing import List, Tuple
from exchange_adapter import Kline


def sma(prices: List[Decimal], period: int) -> List[Decimal]:
    if len(prices) < period:
        return []
    result = []
    for i in range(period - 1, len(prices)):
        avg = sum(prices[i - period + 1 : i + 1]) / Decimal(str(period))
        result.append(avg)
    return result


def ema(prices: List[Decimal], period: int) -> List[Decimal]:
    if len(prices) < period:
        return []
    multiplier = Decimal("2") / (Decimal(str(period)) + Decimal("1"))
    result = [sum(prices[:period]) / Decimal(str(period))]
    for i in range(period, len(prices)):
        val = (prices[i] - result[-1]) * multiplier + result[-1]
        result.append(val)
    return result


def rsi(prices: List[Decimal], period: int = 14) -> List[Decimal]:
    if len(prices) < period + 1:
        return []
    gains: List[Decimal] = []
    losses: List[Decimal] = []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains.append(diff)
            losses.append(Decimal("0"))
        else:
            gains.append(Decimal("0"))
            losses.append(abs(diff))

    result = []
    avg_gain = sum(gains[:period]) / Decimal(str(period))
    avg_loss = sum(losses[:period]) / Decimal(str(period))

    if avg_loss == 0:
        result.append(Decimal("100"))
    else:
        rs = avg_gain / avg_loss
        result.append(Decimal("100") - (Decimal("100") / (Decimal("1") + rs)))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * Decimal(str(period - 1)) + gains[i]) / Decimal(str(period))
        avg_loss = (avg_loss * Decimal(str(period - 1)) + losses[i]) / Decimal(str(period))
        if avg_loss == 0:
            result.append(Decimal("100"))
        else:
            rs = avg_gain / avg_loss
            result.append(Decimal("100") - (Decimal("100") / (Decimal("1") + rs)))

    return result


def macd(
    prices: List[Decimal], fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[List[Decimal], List[Decimal], List[Decimal]]:
    fast_ema = ema(prices, fast)
    slow_ema = ema(prices, slow)

    if len(fast_ema) == 0 or len(slow_ema) == 0:
        return [], [], []

    macd_line_start = len(fast_ema) - len(slow_ema)
    macd_line = [fast_ema[i + macd_line_start] - slow_ema[i] for i in range(len(slow_ema))]

    if len(macd_line) < signal:
        return macd_line, [], []

    signal_line = ema(macd_line, signal)
    signal_start = len(macd_line) - len(signal_line)
    histogram = [macd_line[i + signal_start] - signal_line[i] for i in range(len(signal_line))]

    return macd_line, signal_line, histogram


def bollinger_bands(
    prices: List[Decimal], period: int = 20, num_std: Decimal = Decimal("2")
) -> Tuple[List[Decimal], List[Decimal], List[Decimal]]:
    if len(prices) < period:
        return [], [], []

    middle = sma(prices, period)
    upper: List[Decimal] = []
    lower: List[Decimal] = []

    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1 : i + 1]
        mean = middle[i - period + 1]
        variance = sum((x - mean) ** 2 for x in window) / Decimal(str(period))
        std_dev = variance.sqrt()
        upper.append(mean + num_std * std_dev)
        lower.append(mean - num_std * std_dev)

    return upper, middle, lower


def get_closes(klines: List[Kline]) -> List[Decimal]:
    return [k.close for k in klines]
