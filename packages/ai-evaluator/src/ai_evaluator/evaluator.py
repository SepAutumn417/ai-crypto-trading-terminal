from decimal import Decimal
from typing import List

from exchange_adapter import Kline, KlineInterval
from shared.enums import Direction
from .types import (
    AIEvaluationResult,
    EvaluationGrade,
    IndicatorResult,
    SignalType,
)
from .indicators import (
    rsi,
    macd,
    bollinger_bands,
    sma,
    get_closes,
)

# 指标权重默认值；可被 evaluate_trade(weights=...) 覆盖
DEFAULT_WEIGHTS: dict[str, Decimal] = {
    "rsi": Decimal("1.5"),
    "macd": Decimal("1.5"),
    "bollinger": Decimal("1"),
    "trend": Decimal("1.2"),
    "volume": Decimal("0.8"),
}


def _score_to_signal(score: Decimal) -> SignalType:
    if score >= Decimal("80"):
        return SignalType.STRONG_BUY
    elif score >= Decimal("60"):
        return SignalType.BUY
    elif score >= Decimal("40"):
        return SignalType.NEUTRAL
    elif score >= Decimal("20"):
        return SignalType.SELL
    else:
        return SignalType.STRONG_SELL


def _evaluate_rsi(closes: List[Decimal], direction: str, weight: Decimal = DEFAULT_WEIGHTS["rsi"]) -> IndicatorResult:
    rsi_values = rsi(closes, 14)
    if not rsi_values:
        return IndicatorResult(
            name="RSI(14)",
            signal=SignalType.NEUTRAL,
            weight=weight,
            score=Decimal("50"),
            explanation="数据不足，无法计算 RSI",
        )

    current_rsi = rsi_values[-1]

    if direction == "LONG":
        if current_rsi < Decimal("30"):
            score = Decimal("90")
            explanation = f"RSI={current_rsi:.1f}，处于超卖区间，做多机会较大"
        elif current_rsi < Decimal("40"):
            score = Decimal("75")
            explanation = f"RSI={current_rsi:.1f}，偏低，对做多有利"
        elif current_rsi < Decimal("60"):
            score = Decimal("60")
            explanation = f"RSI={current_rsi:.1f}，处于中性区间"
        elif current_rsi < Decimal("70"):
            score = Decimal("40")
            explanation = f"RSI={current_rsi:.1f}，偏高，注意回调风险"
        else:
            score = Decimal("20")
            explanation = f"RSI={current_rsi:.1f}，处于超买区间，做多风险较高"
    else:
        if current_rsi > Decimal("70"):
            score = Decimal("90")
            explanation = f"RSI={current_rsi:.1f}，处于超买区间，做空机会较大"
        elif current_rsi > Decimal("60"):
            score = Decimal("75")
            explanation = f"RSI={current_rsi:.1f}，偏高，对做空有利"
        elif current_rsi > Decimal("40"):
            score = Decimal("60")
            explanation = f"RSI={current_rsi:.1f}，处于中性区间"
        elif current_rsi > Decimal("30"):
            score = Decimal("40")
            explanation = f"RSI={current_rsi:.1f}，偏低，注意反弹风险"
        else:
            score = Decimal("20")
            explanation = f"RSI={current_rsi:.1f}，处于超卖区间，做空风险较高"

    return IndicatorResult(
        name="RSI(14)",
        value=f"{current_rsi:.2f}",
        signal=_score_to_signal(score),
        weight=weight,
        score=score,
        explanation=explanation,
    )


def _evaluate_macd(closes: List[Decimal], direction: str, weight: Decimal = DEFAULT_WEIGHTS["macd"]) -> IndicatorResult:
    macd_line, signal_line, hist = macd(closes, 12, 26, 9)
    if not hist or len(hist) < 2:
        return IndicatorResult(
            name="MACD",
            signal=SignalType.NEUTRAL,
            weight=weight,
            score=Decimal("50"),
            explanation="数据不足，无法计算 MACD",
        )

    current_hist = hist[-1]
    prev_hist = hist[-2]

    macd_above_signal = macd_line[-1] > signal_line[-1] if macd_line and signal_line else False
    histogram_increasing = current_hist > prev_hist
    histogram_positive = current_hist > 0

    if direction == "LONG":
        if macd_above_signal and histogram_positive and histogram_increasing:
            score = Decimal("85")
            explanation = "MACD 金叉且动能增强，多头趋势明确"
        elif macd_above_signal and histogram_positive:
            score = Decimal("70")
            explanation = "MACD 在零轴上方运行，多头趋势"
        elif macd_above_signal and not histogram_increasing:
            score = Decimal("55")
            explanation = "MACD 金叉但动能减弱，注意回调"
        elif not macd_above_signal and not histogram_positive and not histogram_increasing:
            score = Decimal("25")
            explanation = "MACD 死叉且动能增强，空头趋势明确"
        else:
            score = Decimal("45")
            explanation = "MACD 信号不明确，观望为主"
    else:
        if not macd_above_signal and not histogram_positive and not histogram_increasing:
            score = Decimal("85")
            explanation = "MACD 死叉且动能增强，空头趋势明确"
        elif not macd_above_signal and not histogram_positive:
            score = Decimal("70")
            explanation = "MACD 在零轴下方运行，空头趋势"
        elif not macd_above_signal and histogram_increasing:
            score = Decimal("55")
            explanation = "MACD 死叉但动能减弱，注意反弹"
        elif macd_above_signal and histogram_positive and histogram_increasing:
            score = Decimal("25")
            explanation = "MACD 金叉且动能增强，多头趋势明确"
        else:
            score = Decimal("45")
            explanation = "MACD 信号不明确，观望为主"

    return IndicatorResult(
        name="MACD(12,26,9)",
        value=f"hist: {current_hist:.4f}",
        signal=_score_to_signal(score),
        weight=weight,
        score=score,
        explanation=explanation,
    )


def _evaluate_bollinger(klines: List[Kline], closes: List[Decimal], direction: str, weight: Decimal = DEFAULT_WEIGHTS["bollinger"]) -> IndicatorResult:
    upper, middle, lower = bollinger_bands(closes, 20, Decimal("2"))
    if not upper:
        return IndicatorResult(
            name="Bollinger Bands",
            signal=SignalType.NEUTRAL,
            weight=weight,
            score=Decimal("50"),
            explanation="数据不足，无法计算布林带",
        )

    current_price = closes[-1]
    current_upper = upper[-1]
    current_middle = middle[-1]
    current_lower = lower[-1]
    band_width = current_upper - current_lower

    position_pct = (current_price - current_lower) / band_width * Decimal("100") if band_width > 0 else Decimal("50")

    if direction == "LONG":
        if position_pct < Decimal("20"):
            score = Decimal("80")
            explanation = f"价格接近布林下轨（位置 {position_pct:.1f}%），有反弹可能"
        elif position_pct < Decimal("40"):
            score = Decimal("65")
            explanation = f"价格在布林带中轨下方（位置 {position_pct:.1f}%），偏弱势"
        elif position_pct < Decimal("60"):
            score = Decimal("50")
            explanation = f"价格在布林带中轨附近（位置 {position_pct:.1f}%），震荡格局"
        elif position_pct < Decimal("80"):
            score = Decimal("45")
            explanation = f"价格在布林带中轨上方（位置 {position_pct:.1f}%），偏强势但接近上轨"
        else:
            score = Decimal("30")
            explanation = f"价格接近布林上轨（位置 {position_pct:.1f}%），有回调风险"
    else:
        if position_pct > Decimal("80"):
            score = Decimal("80")
            explanation = f"价格接近布林上轨（位置 {position_pct:.1f}%），有回调可能"
        elif position_pct > Decimal("60"):
            score = Decimal("65")
            explanation = f"价格在布林带中轨上方（位置 {position_pct:.1f}%），偏强势"
        elif position_pct > Decimal("40"):
            score = Decimal("50")
            explanation = f"价格在布林带中轨附近（位置 {position_pct:.1f}%），震荡格局"
        elif position_pct > Decimal("20"):
            score = Decimal("45")
            explanation = f"价格在布林带中轨下方（位置 {position_pct:.1f}%），偏弱势但接近下轨"
        else:
            score = Decimal("30")
            explanation = f"价格接近布林下轨（位置 {position_pct:.1f}%），有反弹风险"

    return IndicatorResult(
        name="Bollinger Bands(20,2)",
        value=f"位置: {position_pct:.1f}%",
        signal=_score_to_signal(score),
        weight=weight,
        score=score,
        explanation=explanation,
    )


def _evaluate_trend(closes: List[Decimal], direction: str, weight: Decimal = DEFAULT_WEIGHTS["trend"]) -> IndicatorResult:
    sma_20 = sma(closes, 20)
    sma_50 = sma(closes, 50)

    if not sma_20 or not sma_50:
        return IndicatorResult(
            name="Trend (SMA)",
            signal=SignalType.NEUTRAL,
            weight=weight,
            score=Decimal("50"),
            explanation="数据不足，无法计算趋势",
        )

    current_price = closes[-1]
    current_sma20 = sma_20[-1]
    current_sma50 = sma_50[-1]

    price_above_sma20 = current_price > current_sma20
    price_above_sma50 = current_price > current_sma50
    sma20_above_sma50 = current_sma20 > current_sma50

    if direction == "LONG":
        if price_above_sma20 and price_above_sma50 and sma20_above_sma50:
            score = Decimal("80")
            explanation = "价格在 SMA20 和 SMA50 上方，且 SMA20 > SMA50，多头排列"
        elif price_above_sma20 and price_above_sma50:
            score = Decimal("65")
            explanation = "价格在两条均线上方，短期趋势偏多"
        elif price_above_sma50:
            score = Decimal("55")
            explanation = "价格在 SMA50 上方，中期趋势偏多"
        elif sma20_above_sma50:
            score = Decimal("45")
            explanation = "均线多头排列，但价格跌破 SMA20"
        else:
            score = Decimal("25")
            explanation = "价格在 SMA50 下方，且均线空头排列，空头趋势"
    else:
        if not price_above_sma20 and not price_above_sma50 and not sma20_above_sma50:
            score = Decimal("80")
            explanation = "价格在 SMA20 和 SMA50 下方，且 SMA20 < SMA50，空头排列"
        elif not price_above_sma20 and not price_above_sma50:
            score = Decimal("65")
            explanation = "价格在两条均线下方，短期趋势偏空"
        elif not price_above_sma50:
            score = Decimal("55")
            explanation = "价格在 SMA50 下方，中期趋势偏空"
        elif not sma20_above_sma50:
            score = Decimal("45")
            explanation = "均线空头排列，但价格突破 SMA20"
        else:
            score = Decimal("25")
            explanation = "价格在 SMA50 上方，且均线多头排列，多头趋势"

    return IndicatorResult(
        name="Trend (SMA20/SMA50)",
        value=f"SMA20: {current_sma20:.2f}",
        signal=_score_to_signal(score),
        weight=weight,
        score=score,
        explanation=explanation,
    )


def _evaluate_volume(klines: List[Kline], direction: str, weight: Decimal = DEFAULT_WEIGHTS["volume"]) -> IndicatorResult:
    if len(klines) < 20:
        return IndicatorResult(
            name="Volume",
            signal=SignalType.NEUTRAL,
            weight=weight,
            score=Decimal("50"),
            explanation="数据不足，无法分析成交量",
        )

    volumes = [k.volume for k in klines]
    avg_volume = sum(volumes[-20:]) / Decimal("20")
    current_volume = volumes[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else Decimal("1")

    current_price = klines[-1].close
    prev_price = klines[-2].close
    price_up = current_price > prev_price

    if direction == "LONG":
        if volume_ratio > Decimal("1.5") and price_up:
            score = Decimal("75")
            explanation = f"放量上涨（量比 {volume_ratio:.2f}），多头动能充足"
        elif volume_ratio > Decimal("1.5") and not price_up:
            score = Decimal("35")
            explanation = f"放量下跌（量比 {volume_ratio:.2f}），空头动能较强"
        elif volume_ratio < Decimal("0.7") and price_up:
            score = Decimal("45")
            explanation = f"缩量上涨（量比 {volume_ratio:.2f}），上涨动能不足"
        elif volume_ratio < Decimal("0.7") and not price_up:
            score = Decimal("55")
            explanation = f"缩量下跌（量比 {volume_ratio:.2f}），下跌动能减弱"
        else:
            score = Decimal("50")
            explanation = f"成交量正常（量比 {volume_ratio:.2f}）"
    else:
        if volume_ratio > Decimal("1.5") and not price_up:
            score = Decimal("75")
            explanation = f"放量下跌（量比 {volume_ratio:.2f}），空头动能充足"
        elif volume_ratio > Decimal("1.5") and price_up:
            score = Decimal("35")
            explanation = f"放量上涨（量比 {volume_ratio:.2f}），多头动能较强"
        elif volume_ratio < Decimal("0.7") and not price_up:
            score = Decimal("45")
            explanation = f"缩量下跌（量比 {volume_ratio:.2f}），下跌动能不足"
        elif volume_ratio < Decimal("0.7") and price_up:
            score = Decimal("55")
            explanation = f"缩量上涨（量比 {volume_ratio:.2f}），上涨动能减弱"
        else:
            score = Decimal("50")
            explanation = f"成交量正常（量比 {volume_ratio:.2f}）"

    return IndicatorResult(
        name="Volume",
        value=f"量比: {volume_ratio:.2f}",
        signal=_score_to_signal(score),
        weight=weight,
        score=score,
        explanation=explanation,
    )


def evaluate_trade(
    symbol: str,
    direction: str,
    entry_price: Decimal,
    klines: List[Kline],
    interval: KlineInterval = KlineInterval.ONE_HOUR,
    weights: dict[str, Decimal] | None = None,
) -> AIEvaluationResult:
    Direction(direction)  # 校验 direction 是合法的 Direction 枚举值
    effective = dict(DEFAULT_WEIGHTS)
    if weights:
        for k, v in weights.items():
            if k in effective:
                effective[k] = Decimal(str(v))
    closes = get_closes(klines)

    signals = [
        _evaluate_rsi(closes, direction, effective["rsi"]),
        _evaluate_macd(closes, direction, effective["macd"]),
        _evaluate_bollinger(klines, closes, direction, effective["bollinger"]),
        _evaluate_trend(closes, direction, effective["trend"]),
        _evaluate_volume(klines, direction, effective["volume"]),
    ]

    total_weight = sum(s.weight for s in signals)
    if total_weight <= 0:
        # 权重全 0 或负数时降级为等权平均，避免除零崩溃
        weighted_score = sum(s.score for s in signals) / Decimal(len(signals)) if signals else Decimal("0")
    else:
        weighted_score = sum(s.score * s.weight for s in signals) / total_weight

    if weighted_score >= Decimal("75"):
        grade = EvaluationGrade.A
        recommendation = "强烈推荐"
        risk_level = "低"
    elif weighted_score >= Decimal("60"):
        grade = EvaluationGrade.B
        recommendation = "推荐"
        risk_level = "中低"
    elif weighted_score >= Decimal("45"):
        grade = EvaluationGrade.C
        recommendation = "一般"
        risk_level = "中等"
    elif weighted_score >= Decimal("30"):
        grade = EvaluationGrade.D
        recommendation = "不推荐"
        risk_level = "中高"
    else:
        grade = EvaluationGrade.F
        recommendation = "强烈不推荐"
        risk_level = "高"

    conviction = weighted_score

    positive_signals = [s for s in signals if s.signal in (SignalType.BUY, SignalType.STRONG_BUY)]
    negative_signals = [s for s in signals if s.signal in (SignalType.SELL, SignalType.STRONG_SELL)]
    neutral_signals = [s for s in signals if s.signal == SignalType.NEUTRAL]

    summary_parts = []
    if positive_signals:
        summary_parts.append(f"有利指标 {len(positive_signals)} 个")
    if neutral_signals:
        summary_parts.append(f"中性指标 {len(neutral_signals)} 个")
    if negative_signals:
        summary_parts.append(f"不利指标 {len(negative_signals)} 个")

    top_signal = max(signals, key=lambda s: s.score)
    bottom_signal = min(signals, key=lambda s: s.score)

    summary = f"综合评估：{', '.join(summary_parts)}。"
    summary += f"最强信号：{top_signal.name}（{top_signal.explanation}）。"
    summary += f"最弱信号：{bottom_signal.name}（{bottom_signal.explanation}）。"

    return AIEvaluationResult(
        symbol=symbol,
        direction=direction,
        overall_score=weighted_score,
        grade=grade,
        recommendation=recommendation,
        signals=signals,
        summary=summary,
        risk_level=risk_level,
        conviction=conviction,
    )
