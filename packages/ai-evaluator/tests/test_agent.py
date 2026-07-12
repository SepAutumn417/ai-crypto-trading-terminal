"""AI Agent 单元测试 — v0.5 LLM 解释层核心模块。

测试 ai_evaluator.agent 模块：
- evaluate_with_llm: 综合评估（规则评分 + LLM 解释 / 降级）
- _parse_llm_response: LLM JSON 响应解析与容错
- build_user_prompt: 结构化 user 消息构建
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_evaluator import (
    AIInput,
    AISource,
    LLMClient,
    LLMError,
    RecommendedAction,
    evaluate_trade,
    evaluate_with_llm,
)
from ai_evaluator.agent import _parse_llm_response, build_user_prompt
from exchange_adapter import Kline, KlineInterval


def make_klines(n: int = 100, base: Decimal = Decimal("100")) -> list[Kline]:
    """生成 mock Kline 列表（timestamp 必须为 datetime）。"""
    now = datetime.now(UTC)
    return [
        Kline(
            timestamp=now - timedelta(hours=n - i),
            open=base,
            high=base + Decimal("1"),
            low=base - Decimal("1"),
            close=base,
            volume=Decimal("1000"),
        )
        for i in range(n)
    ]


def make_ai_input(symbol: str = "BTCUSDT", direction: str = "LONG") -> AIInput:
    return AIInput(
        marketStructure={
            "symbol": symbol,
            "direction": direction,
            "entry_price": "65000",
        },
        candidatePlan={
            "setup_type": "breakout",
            "opportunity_grade": "A",
            "leverage": "10",
            "risk_percent": "1",
            "stop_loss_price": "61900",
            "take_profit_prices": ["63800"],
        },
        riskResult={"status": "ALLOW"},
        systemMode="L4_CONFIRM_EXECUTION",
    )


def _valid_llm_response() -> dict:
    """构造一份完整的 LLM JSON 响应。"""
    return {
        "summary": "测试总结",
        "marketStateExplanation": "市场处于上升趋势",
        "planQualityExplanation": "计划质量良好",
        "riskExplanation": "风险可控",
        "opportunityGradeComment": "A 级机会",
        "recommendedAction": "ALLOW_CONFIRM",
        "warnings": ["注意波动率"],
        "upgradeConditions": ["突破 66000 后可加仓"],
        "invalidationConditions": ["跌破 61900 止损"],
        "emotionalRiskFlags": ["FOMO 风险"],
    }


# ===== evaluate_with_llm 综合评估 =====


@pytest.mark.asyncio
async def test_comprehensive_evaluation_without_llm():
    """不传 llm_client 时，返回 source=rule_based, explanation=None。"""
    klines = make_klines()
    result = await evaluate_with_llm(
        ai_input=make_ai_input(),
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=Decimal("65000"),
        klines=klines,
        llm_client=None,
    )
    assert result.source == AISource.RULE_BASED
    assert result.explanation is None
    assert result.symbol == "BTCUSDT"
    assert result.direction == "LONG"
    assert result.overall_score >= 0
    assert len(result.signals) == 5


@pytest.mark.asyncio
async def test_comprehensive_evaluation_with_llm_success():
    """传入 mock LLMClient，返回 source=llm, explanation 有值。"""
    klines = make_klines()
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat_json = AsyncMock(return_value=_valid_llm_response())

    result = await evaluate_with_llm(
        ai_input=make_ai_input(),
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=Decimal("65000"),
        klines=klines,
        llm_client=mock_llm,
    )
    assert result.source == AISource.LLM
    assert result.explanation is not None
    assert result.explanation.summary == "测试总结"
    assert result.explanation.recommendedAction == RecommendedAction.ALLOW_CONFIRM
    assert result.explanation.warnings == ["注意波动率"]
    # 规则评分部分仍然存在
    assert result.overall_score >= 0
    assert len(result.signals) == 5


@pytest.mark.asyncio
async def test_comprehensive_evaluation_llm_timeout():
    """LLM 超时降级为 rule_based。"""
    klines = make_klines()
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat_json = AsyncMock(side_effect=LLMError("LLM 调用超时（5s）"))

    result = await evaluate_with_llm(
        ai_input=make_ai_input(),
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=Decimal("65000"),
        klines=klines,
        llm_client=mock_llm,
    )
    assert result.source == AISource.RULE_BASED
    assert result.explanation is None
    assert result.overall_score >= 0


# ===== _parse_llm_response 解析 =====


def test_parse_llm_response_valid():
    """测试 _parse_llm_response 解析有效 JSON。"""
    explanation = _parse_llm_response(_valid_llm_response())
    assert explanation.summary == "测试总结"
    assert explanation.marketStateExplanation == "市场处于上升趋势"
    assert explanation.planQualityExplanation == "计划质量良好"
    assert explanation.riskExplanation == "风险可控"
    assert explanation.opportunityGradeComment == "A 级机会"
    assert explanation.recommendedAction == RecommendedAction.ALLOW_CONFIRM
    assert explanation.warnings == ["注意波动率"]
    assert explanation.upgradeConditions == ["突破 66000 后可加仓"]
    assert explanation.invalidationConditions == ["跌破 61900 止损"]
    assert explanation.emotionalRiskFlags == ["FOMO 风险"]


def test_parse_llm_response_invalid_action():
    """recommendedAction 无效时降级为 WAIT。"""
    raw = {"summary": "x", "recommendedAction": "INVALID_ACTION"}
    explanation = _parse_llm_response(raw)
    assert explanation.recommendedAction == RecommendedAction.WAIT


def test_parse_llm_response_missing_fields():
    """字段缺失时使用默认值。"""
    explanation = _parse_llm_response({})
    assert explanation.summary == ""
    assert explanation.marketStateExplanation == ""
    assert explanation.recommendedAction == RecommendedAction.WAIT
    assert explanation.warnings == []
    assert explanation.upgradeConditions == []
    assert explanation.invalidationConditions == []
    assert explanation.emotionalRiskFlags == []


# ===== build_user_prompt =====


def test_build_user_prompt():
    """测试 build_user_prompt 生成包含输入数据的字符串。"""
    klines = make_klines()
    rule_result = evaluate_trade("BTCUSDT", "LONG", Decimal("65000"), klines)
    ai_input = make_ai_input()

    prompt = build_user_prompt(ai_input, rule_result)
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    # 包含结构化输入数据
    assert "BTCUSDT" in prompt
    assert "marketStructure" in prompt
    assert "candidatePlan" in prompt
    assert "riskResult" in prompt
    # 包含规则评分结果
    assert "overallScore" in prompt
    assert "grade" in prompt
    assert "signals" in prompt
