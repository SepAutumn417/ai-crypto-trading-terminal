from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from ai_evaluator import DEFAULT_WEIGHTS, EvaluationGrade, SignalType, evaluate_trade
from exchange_adapter import Kline, KlineInterval


def generate_klines(count: int, start_price: Decimal, trend: str = "sideways") -> list[Kline]:
    klines = []
    price = start_price
    now = datetime.now(UTC)
    for i in range(count):
        if trend == "up":
            change = Decimal("0.5")
        elif trend == "down":
            change = Decimal("-0.5")
        else:
            change = Decimal("0")

        open_p = price
        close_p = price + change * Decimal("0.6")
        high_p = max(open_p, close_p) + Decimal("0.3")
        low_p = min(open_p, close_p) - Decimal("0.3")
        volume = Decimal("1000") + Decimal(str(i * 10))

        kline = Kline(
            timestamp=now - timedelta(hours=count - i),
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=volume,
        )
        klines.append(kline)
        price = close_p
    return klines


def test_evaluate_trade_returns_result():
    klines = generate_klines(100, Decimal("65000"))
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    assert result.symbol == "BTCUSDT"
    assert result.direction == "LONG"
    assert result.overall_score >= 0
    assert result.overall_score <= 100
    assert len(result.signals) == 5


def test_evaluate_trade_grades():
    klines = generate_klines(100, Decimal("65000"))
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    assert isinstance(result.grade, EvaluationGrade)
    assert result.grade in [
        EvaluationGrade.A,
        EvaluationGrade.B,
        EvaluationGrade.C,
        EvaluationGrade.D,
        EvaluationGrade.F,
    ]


def test_evaluate_trade_signals_have_weights():
    klines = generate_klines(100, Decimal("65000"))
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    for signal in result.signals:
        assert signal.weight > 0
        assert signal.score >= 0
        assert signal.score <= 100
        assert isinstance(signal.signal, SignalType)
        assert signal.explanation
        assert signal.name


def test_evaluate_trade_uptrend_has_positive_trend_signal():
    klines = generate_klines(100, Decimal("65000"), trend="up")
    long_result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    trend_signal = next(s for s in long_result.signals if "Trend" in s.name)
    assert trend_signal.score >= 60


def test_evaluate_trade_downtrend_short_score_higher_than_long():
    klines = generate_klines(100, Decimal("65000"), trend="down")
    long_result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    short_result = evaluate_trade("BTCUSDT", "SHORT", Decimal("65000"), klines)
    assert short_result.overall_score > long_result.overall_score


def test_evaluate_trade_with_insufficient_data():
    klines = generate_klines(10, Decimal("65000"))
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    assert result is not None
    assert result.overall_score >= 0


def test_evaluate_trade_summary_not_empty():
    klines = generate_klines(100, Decimal("65000"))
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    assert result.summary
    assert len(result.summary) > 0


def test_evaluate_trade_conviction_matches_score():
    klines = generate_klines(100, Decimal("65000"))
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    assert result.conviction == result.overall_score


def test_evaluate_trade_risk_level():
    klines = generate_klines(100, Decimal("65000"))
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    assert result.risk_level in ["低", "中低", "中等", "中高", "高"]


def test_evaluate_trade_with_custom_weights_overrides_defaults():
    """自定义权重应覆盖默认权重体现在 signal.weight 上"""
    klines = generate_klines(100, Decimal("65000"), trend="up")
    weights = {
        "rsi": Decimal("3"),
        "macd": Decimal("2"),
        "bollinger": Decimal("2"),
        "trend": Decimal("2"),
        "volume": Decimal("2"),
    }
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines, weights=weights)
    signal_by_name = {s.name: s for s in result.signals}
    assert signal_by_name["RSI(14)"].weight == Decimal("3")
    assert signal_by_name["MACD(12,26,9)"].weight == Decimal("2")
    assert signal_by_name["Bollinger Bands(20,2)"].weight == Decimal("2")
    assert signal_by_name["Trend (SMA20/SMA50)"].weight == Decimal("2")
    assert signal_by_name["Volume"].weight == Decimal("2")


def test_evaluate_trade_with_partial_weights_uses_defaults_for_missing():
    """只传入部分权重，缺失的应使用默认值"""
    klines = generate_klines(100, Decimal("65000"), trend="up")
    weights = {"rsi": Decimal("5")}  # 只传 rsi
    result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines, weights=weights)
    signal_by_name = {s.name: s for s in result.signals}
    assert signal_by_name["RSI(14)"].weight == Decimal("5")
    assert signal_by_name["MACD(12,26,9)"].weight == DEFAULT_WEIGHTS["macd"]
    assert signal_by_name["Bollinger Bands(20,2)"].weight == DEFAULT_WEIGHTS["bollinger"]
    assert signal_by_name["Trend (SMA20/SMA50)"].weight == DEFAULT_WEIGHTS["trend"]
    assert signal_by_name["Volume"].weight == DEFAULT_WEIGHTS["volume"]


def test_evaluate_trade_with_none_weights_uses_defaults():
    """weights=None 应使用默认权重，与不传一致"""
    klines = generate_klines(100, Decimal("65000"))
    result_none = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines, weights=None)
    result_default = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    assert result_none.overall_score == result_default.overall_score
    signal_by_name = {s.name: s for s in result_none.signals}
    assert signal_by_name["RSI(14)"].weight == DEFAULT_WEIGHTS["rsi"]
    assert signal_by_name["MACD(12,26,9)"].weight == DEFAULT_WEIGHTS["macd"]


def test_evaluate_trade_weights_affect_overall_score():
    """不同权重应导致不同的 overall_score"""
    klines = generate_klines(100, Decimal("65000"), trend="up")
    result_default = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    # 极端放大 trend 权重（上升趋势中 trend 得分较高）
    result_trend_heavy = evaluate_trade(
        "BTCUSDT", "LONG", Decimal("65000"), klines,
        weights={"trend": Decimal("100")},
    )
    assert result_default.overall_score != result_trend_heavy.overall_score
