"""v0.5 AI Agent——LLM 解释层核心模块。

职责：
1. 组装结构化输入（marketStructure + candidatePlan + riskResult）
2. 构建 system prompt 约束 AI 输出格式
3. 调用 LLM（5s 超时）
4. 解析 JSON 输出为 AIExplanation
5. LLM 失败时降级为规则评分器（evaluate_trade）

对应 AI_GUARDRAILS：
- §2: AI 输入必须结构化
- §3: AI 输出必须结构化 JSON
- §4: AI 不得输出越界建议
- §8: AI 安全提示
"""
import json
import logging
from decimal import Decimal
from typing import Any

from exchange_adapter import Kline, KlineInterval

from .evaluator import evaluate_trade
from .llm import LLMClient, LLMError
from .types import (
    AIEvaluationResult,
    AIExplanation,
    AIInput,
    AISource,
    ComprehensiveEvaluation,
    RecommendedAction,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的加密货币交易分析助手。你的职责是解释市场结构、评估交易计划质量、解释风险，并给出结构化建议。

## 你的角色
- 解释器：解释当前市场结构和趋势
- 审查员：评估交易计划的质量
- 顾问：给出等待条件或失效条件
- 你不是交易执行主体，不能直接下单

## 硬性规则（不可违反）
1. 不能建议"直接满仓"、"不用止损"、"加大杠杆追回"、"忽略系统风控"
2. 不能输出"现在必须买/卖"、"保证盈利"
3. 风控 BLOCK 时你的建议不影响最终决策
4. 你的 recommendedAction 只能是以下之一: WAIT, ALLOW_CONFIRM, REDUCE_RISK, DO_NOT_TRADE

## 输出格式（必须为 JSON）
{
  "summary": "一句话总结",
  "marketStateExplanation": "市场状态解释",
  "planQualityExplanation": "计划质量分析",
  "riskExplanation": "风险解释",
  "opportunityGradeComment": "机会评级评论",
  "recommendedAction": "WAIT | ALLOW_CONFIRM | REDUCE_RISK | DO_NOT_TRADE",
  "warnings": ["警告1", "警告2"],
  "upgradeConditions": ["升级条件1"],
  "invalidationConditions": ["失效条件1"],
  "emotionalRiskFlags": ["情绪风险1"]
}

## 安全提示
所有评估基于当前数据和规则，不构成盈利保证。真实交易必须以风控引擎和用户确认结果为准。"""


def _truncate_for_llm(data: dict[str, Any], max_chars: int = 4000) -> str:
    """将结构化数据转为紧凑 JSON 字符串，限制长度避免 token 超限。"""
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) > max_chars:
        text = text[:max_chars] + "...(truncated)"
    return text


def build_user_prompt(ai_input: AIInput, rule_based: AIEvaluationResult) -> str:
    """构建 LLM user 消息——包含结构化输入 + 规则评分结果。"""
    input_json = _truncate_for_llm({
        "marketStructure": ai_input.marketStructure,
        "candidatePlan": ai_input.candidatePlan,
        "riskResult": ai_input.riskResult,
        "recentTradeState": ai_input.recentTradeState,
        "systemMode": ai_input.systemMode,
    })
    rule_json = _truncate_for_llm({
        "overallScore": str(rule_based.overall_score),
        "grade": rule_based.grade.value,
        "recommendation": rule_based.recommendation,
        "riskLevel": rule_based.risk_level,
        "signals": [
            {"name": s.name, "signal": s.signal.value, "score": str(s.score), "explanation": s.explanation}
            for s in rule_based.signals
        ],
    }, max_chars=2000)

    return f"""请分析以下交易机会并给出结构化评估。

## 系统已计算的结构化输入
{input_json}

## 技术指标规则评分结果（供参考，你需要在此基础上给出更深入的解释）
{rule_json}

请严格按照 JSON 格式输出你的评估，包含 summary, marketStateExplanation, planQualityExplanation, riskExplanation, opportunityGradeComment, recommendedAction, warnings, upgradeConditions, invalidationConditions, emotionalRiskFlags。"""


def _parse_llm_response(raw: dict[str, Any]) -> AIExplanation:
    """将 LLM 原始 JSON 响应解析为 AIExplanation，容忍字段缺失。"""
    action_str = raw.get("recommendedAction", "WAIT")
    try:
        action = RecommendedAction(action_str)
    except ValueError:
        action = RecommendedAction.WAIT

    def _str_list(key: str) -> list[str]:
        val = raw.get(key, [])
        if isinstance(val, list):
            return [str(x) for x in val]
        return [str(val)] if val else []

    return AIExplanation(
        summary=str(raw.get("summary", "")),
        marketStateExplanation=str(raw.get("marketStateExplanation", "")),
        planQualityExplanation=str(raw.get("planQualityExplanation", "")),
        riskExplanation=str(raw.get("riskExplanation", "")),
        opportunityGradeComment=str(raw.get("opportunityGradeComment", "")),
        recommendedAction=action,
        warnings=_str_list("warnings"),
        upgradeConditions=_str_list("upgradeConditions"),
        invalidationConditions=_str_list("invalidationConditions"),
        emotionalRiskFlags=_str_list("emotionalRiskFlags"),
    )


async def evaluate_with_llm(
    ai_input: AIInput,
    symbol: str,
    direction: str,
    entry_price: Decimal,
    klines: list[Kline],
    interval: KlineInterval = KlineInterval.ONE_HOUR,
    weights: dict[str, Decimal] | None = None,
    llm_client: LLMClient | None = None,
) -> ComprehensiveEvaluation:
    """v0.5 综合评估：规则评分 + LLM 解释。

    流程：
    1. 始终执行规则评分（evaluate_trade）
    2. 若 llm_client 可用，调用 LLM 获取结构化解释
    3. LLM 超时/失败时降级为纯规则评分（explanation=None）
    """
    # Step 1: 规则评分（始终执行）
    rule_result = evaluate_trade(symbol, direction, entry_price, klines, interval, weights=weights)

    # Step 2: LLM 解释（可选）
    if llm_client is None:
        return ComprehensiveEvaluation(
            symbol=rule_result.symbol,
            direction=rule_result.direction,
            overall_score=rule_result.overall_score,
            grade=rule_result.grade,
            recommendation=rule_result.recommendation,
            signals=rule_result.signals,
            risk_level=rule_result.risk_level,
            conviction=rule_result.conviction,
            explanation=None,
            source=AISource.RULE_BASED,
        )

    try:
        user_prompt = build_user_prompt(ai_input, rule_result)
        raw = await llm_client.chat_json(SYSTEM_PROMPT, user_prompt)
        explanation = _parse_llm_response(raw)
        logger.info("LLM 评估成功 symbol=%s action=%s", symbol, explanation.recommendedAction.value)
        return ComprehensiveEvaluation(
            symbol=rule_result.symbol,
            direction=rule_result.direction,
            overall_score=rule_result.overall_score,
            grade=rule_result.grade,
            recommendation=rule_result.recommendation,
            signals=rule_result.signals,
            risk_level=rule_result.risk_level,
            conviction=rule_result.conviction,
            explanation=explanation,
            source=AISource.LLM,
        )
    except LLMError as e:
        logger.warning("LLM 评估降级为规则评分 symbol=%s: %s", symbol, e)
        return ComprehensiveEvaluation(
            symbol=rule_result.symbol,
            direction=rule_result.direction,
            overall_score=rule_result.overall_score,
            grade=rule_result.grade,
            recommendation=rule_result.recommendation,
            signals=rule_result.signals,
            risk_level=rule_result.risk_level,
            conviction=rule_result.conviction,
            explanation=None,
            source=AISource.RULE_BASED,
        )
