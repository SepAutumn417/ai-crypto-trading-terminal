"""决策门：融合风控结果与 AI 评估，输出最终决策。

v0.5 DecisionFusion 矩阵（AI recommendedAction × 风控结果 → 最终决策）：
对应 AI_GUARDRAILS §5.1 合并矩阵。

规则总结：
1. 风控 BLOCK → 永远 BLOCK（AI 不可覆盖）
2. 风控 REDUCE_RISK → AI DO_NOT_TRADE 升级为 BLOCK；WAIT 保持 WAIT；其他保持 REDUCE_RISK
3. 风控 WARN → AI DO_NOT_TRADE/WAIT/REDUCE_RISK 降为 WAIT；ALLOW_CONFIRM 也降为 WAIT（需用户调整后重检）
4. 风控 ALLOW → AI DO_NOT_TRADE/WAIT 降为 WAIT；REDUCE_RISK 采纳；ALLOW_CONFIRM 保持 ALLOW_CONFIRM
5. execution_disabled / kill_switch → 始终 BLOCK（最高优先级）

v0.1~v0.4: ai_evaluation 恒为 None，按风控结果直接映射。
v0.5: 优先使用 recommendedAction 融合；若无 recommendedAction 则降级为 grade 融合。
"""
from typing import Optional

from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import DecisionGateResult, RiskCheckResult


def _ai_recommended_action(ai_evaluation: dict | None) -> str | None:
    """从 ai_evaluation dict 提取 recommended_action 字段。None 表示无 LLM 评估。"""
    if not ai_evaluation:
        return None
    action = ai_evaluation.get("recommended_action")
    return str(action) if action else None


def _ai_grade_value(ai_evaluation: dict | None) -> str | None:
    """从 ai_evaluation dict 提取 grade 字段（A/B/C/D/F）。None 表示无 AI 评估。"""
    if not ai_evaluation:
        return None
    grade = ai_evaluation.get("grade")
    if grade is None:
        grade = ai_evaluation.get("overall_score")
        if grade is not None:
            try:
                from decimal import Decimal
                score = Decimal(str(grade))
                if score >= 75:
                    return "A"
                elif score >= 60:
                    return "B"
                elif score >= 45:
                    return "C"
                elif score >= 30:
                    return "D"
                else:
                    return "F"
            except Exception:
                return None
    return str(grade) if grade else None


def _fuse_with_recommended_action(
    risk_status: RiskStatus,
    action: str,
) -> tuple[DecisionGateStatus, list[str]]:
    """v0.5: 使用 AI recommendedAction 与风控结果融合。

    对应 AI_GUARDRAILS §5.1 合并矩阵。
    """
    reasons: list[str] = [f"ai_fusion: AI recommendedAction={action}, risk={risk_status.value}"]

    if risk_status == RiskStatus.BLOCK:
        return DecisionGateStatus.BLOCK, reasons

    if risk_status == RiskStatus.REDUCE_RISK:
        if action == "DO_NOT_TRADE":
            reasons.append("ai_fusion: AI 拒绝交易，升级为 BLOCK")
            return DecisionGateStatus.BLOCK, reasons
        elif action == "WAIT":
            reasons.append("ai_fusion: AI 建议等待")
            return DecisionGateStatus.WAIT, reasons
        else:  # ALLOW_CONFIRM or REDUCE_RISK
            reasons.append("ai_fusion: AI 不能把降险升级为确认，保持 REDUCE_RISK")
            return DecisionGateStatus.REDUCE_RISK, reasons

    if risk_status == RiskStatus.WARN:
        # 风控有警告时不能直接确认，需用户调整后重检
        if action == "DO_NOT_TRADE":
            reasons.append("ai_fusion: AI 拒绝，进入等待")
            return DecisionGateStatus.WAIT, reasons
        elif action == "WAIT":
            reasons.append("ai_fusion: 一致等待")
            return DecisionGateStatus.WAIT, reasons
        elif action == "REDUCE_RISK":
            reasons.append("ai_fusion: 降为等待")
            return DecisionGateStatus.WAIT, reasons
        else:  # ALLOW_CONFIRM
            reasons.append("ai_fusion: 风控警告时不能直接确认，降为 WAIT")
            return DecisionGateStatus.WAIT, reasons

    # risk_status == ALLOW or ALLOW_CONFIRM
    if action == "DO_NOT_TRADE":
        reasons.append("ai_fusion: 风控通过但 AI 拒绝，进入 WAIT")
        return DecisionGateStatus.WAIT, reasons
    elif action == "WAIT":
        reasons.append("ai_fusion: AI 建议等待")
        return DecisionGateStatus.WAIT, reasons
    elif action == "REDUCE_RISK":
        reasons.append("ai_fusion: AI 建议降险，采纳")
        return DecisionGateStatus.REDUCE_RISK, reasons
    else:  # ALLOW_CONFIRM
        reasons.append("ai_fusion: 风控与 AI 一致通过，进入确认")
        return DecisionGateStatus.ALLOW_CONFIRM, reasons


def _fuse_with_grade(
    risk_status: RiskStatus,
    ai_grade: str | None,
) -> tuple[DecisionGateStatus, list[str]]:
    """v0.1~v0.4 兼容：使用 AI grade 与风控结果融合。"""
    reasons: list[str] = []

    if ai_grade is None:
        if risk_status in (RiskStatus.ALLOW, RiskStatus.ALLOW_CONFIRM):
            return DecisionGateStatus.ALLOW_CONFIRM, reasons
        elif risk_status == RiskStatus.WARN:
            return DecisionGateStatus.WAIT, ["risk_warn: 风控警告，等待用户调整"]
        elif risk_status == RiskStatus.REDUCE_RISK:
            return DecisionGateStatus.REDUCE_RISK, reasons
        return DecisionGateStatus.BLOCK, reasons

    if risk_status == RiskStatus.BLOCK:
        return DecisionGateStatus.BLOCK, reasons
    elif risk_status == RiskStatus.REDUCE_RISK:
        return DecisionGateStatus.REDUCE_RISK, reasons
    elif risk_status == RiskStatus.WARN:
        if ai_grade in ("D", "F"):
            reasons.append(f"ai_fusion: AI 评级 {ai_grade} + 风控警告 → 升级为禁止")
            return DecisionGateStatus.BLOCK, reasons
        reasons.append(f"ai_fusion: AI 评级 {ai_grade}，维持等待")
        return DecisionGateStatus.WAIT, ["risk_warn: 风控警告，等待用户调整"] + reasons
    else:
        if ai_grade == "F":
            reasons.append("ai_fusion: AI 评级 F（强烈不推荐）→ 降级为禁止")
            return DecisionGateStatus.BLOCK, reasons
        elif ai_grade == "D":
            reasons.append("ai_fusion: AI 评级 D（不推荐）→ 降级为等待")
            return DecisionGateStatus.WAIT, reasons
        else:
            if ai_grade in ("A", "B"):
                reasons.append(f"ai_fusion: AI 评级 {ai_grade}，与风控 ALLOW 共识，允许执行")
            else:
                reasons.append(f"ai_fusion: AI 评级 {ai_grade}（中性），维持风控 ALLOW")
            return DecisionGateStatus.ALLOW_CONFIRM, reasons


def decide(
    risk_result: RiskCheckResult,
    execution_enabled: bool,
    kill_switch: bool,
    ai_evaluation: dict | None = None,
    plan_expired: bool = False,
) -> DecisionGateResult:
    if plan_expired:
        return DecisionGateResult(result=DecisionGateStatus.EXPIRED, reasons=["plan_expired"])

    if not execution_enabled:
        return DecisionGateResult(
            result=DecisionGateStatus.BLOCK,
            reasons=["execution_disabled: 执行模式未开启"],
        )

    if kill_switch:
        return DecisionGateResult(
            result=DecisionGateStatus.BLOCK,
            reasons=["kill_switch_active: Kill Switch 已开启"],
        )

    # v0.5: 优先使用 recommendedAction 融合；降级为 grade 融合
    recommended_action = _ai_recommended_action(ai_evaluation)
    if recommended_action:
        result_status, fusion_reasons = _fuse_with_recommended_action(
            risk_result.status, recommended_action
        )
    else:
        ai_grade = _ai_grade_value(ai_evaluation)
        result_status, fusion_reasons = _fuse_with_grade(risk_result.status, ai_grade)

    # BLOCK 时附加风控的 block_reasons
    if result_status == DecisionGateStatus.BLOCK and risk_result.block_reasons:
        return DecisionGateResult(
            result=result_status,
            reasons=list(risk_result.block_reasons) + fusion_reasons,
        )

    return DecisionGateResult(result=result_status, reasons=fusion_reasons)
