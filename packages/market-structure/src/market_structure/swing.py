"""Swing High/Low 检测——基于 Fractal（分形）方法。

Fractal 算法：一根 K 线的 high 是左右各 N 根 K 线中最高的 → Swing High；
                一根 K 线的 low 是左右各 N 根 K 线中最低的 → Swing Low。

N 称为"确认窗口"，默认 2（即左右各 2 根，共 5 根 K 线构成一个分形）。
N 越大越严格、信号越少但更可靠；N 越小信号越多但噪音也多。
"""
from __future__ import annotations

from decimal import Decimal

from exchange_adapter import Kline

from .types import SwingPoint, SwingType


def detect_swings(
    klines: list[Kline],
    left_bars: int = 2,
    right_bars: int = 2,
) -> list[SwingPoint]:
    """检测 Swing High 和 Swing Low。

    Args:
        klines: K 线序列（按时间升序）
        left_bars: 左侧确认 K 线数量
        right_bars: 右侧确认 K 线数量

    Returns:
        按时间排序的 SwingPoint 列表（high 和 low 混合）
    """
    if len(klines) < left_bars + right_bars + 1:
        return []

    swings: list[SwingPoint] = []

    for i in range(left_bars, len(klines) - right_bars):
        k = klines[i]
        left = klines[i - left_bars : i]
        right = klines[i + 1 : i + 1 + right_bars]

        # Swing High: k.high 是窗口内最高
        left_max = max(nk.high for nk in left)
        right_max = max(nk.high for nk in right)
        if k.high > left_max and k.high > right_max:
            swings.append(
                SwingPoint(
                    type=SwingType.HIGH,
                    index=i,
                    price=k.high,
                    timestamp=k.timestamp,
                    confirmed=True,
                )
            )

        # Swing Low: k.low 是窗口内最低
        left_min = min(nk.low for nk in left)
        right_min = min(nk.low for nk in right)
        if k.low < left_min and k.low < right_min:
            swings.append(
                SwingPoint(
                    type=SwingType.LOW,
                    index=i,
                    price=k.low,
                    timestamp=k.timestamp,
                    confirmed=True,
                )
            )

    # 标注结构序列：HH/HL/LH/LL
    _label_structure_sequence(swings)

    return swings


def _label_structure_sequence(swings: list[SwingPoint]) -> None:
    """为 swing 点标注 HH/HL/LH/LL 结构标签。

    - HH (Higher High): 本次 swing high 高于上一个 swing high → 上涨趋势延续
    - LH (Lower High):  本次 swing high 低于上一个 swing high → 下跌趋势信号
    - HL (Higher Low):  本次 swing low 高于上一个 swing low  → 上涨趋势延续
    - LL (Lower Low):   本次 swing low 低于上一个 swing low  → 下跌趋势信号

    标签写入 swing.structure_label。
    """
    prev_high: SwingPoint | None = None
    prev_low: SwingPoint | None = None

    for sw in swings:
        if sw.type == SwingType.HIGH:
            if prev_high is not None:
                if sw.price > prev_high.price:
                    sw.structure_label = "HH"
                elif sw.price < prev_high.price:
                    sw.structure_label = "LH"
                else:
                    sw.structure_label = "EQ_H"
            else:
                sw.structure_label = "H0"  # 首个 swing high 无前序
            prev_high = sw
        elif sw.type == SwingType.LOW:
            if prev_low is not None:
                if sw.price > prev_low.price:
                    sw.structure_label = "HL"
                elif sw.price < prev_low.price:
                    sw.structure_label = "LL"
                else:
                    sw.structure_label = "EQ_L"
            else:
                sw.structure_label = "L0"  # 首个 swing low 无前序
            prev_low = sw
