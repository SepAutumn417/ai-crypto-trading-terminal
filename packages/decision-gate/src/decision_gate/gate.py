"""决策门：融合风控结果与 AI 评估，输出最终决策。

DecisionFusion 矩阵（AI 评估 × 风控结果 → 最终决策）：
- 风控 BLOCK → 始终 BLOCK（AI 无法覆盖硬风控）
- 风控 REDUCE_RISK → 保持 REDUCE_RISK（AI 不影响降仓建议）
- 风控 WARN → AI F/D 降级为 BLOCK；AI 其他保持 WAIT
- 风控 ALLOW/ALLOW_CONFIRM → AI F 降级为 BLOCK；AI D 降级为 WAIT；AI A/B/C 保持 ALLOW_CONFIRM
- execution_disabled / kill_switch → 始终 BLOCK（最高优先级）
"""
from typing import Optional
from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import DecisionGateResult, RiskCheckResult


def _ai_grade_value(ai_evaluation: dict | None) -> str | None:
    """从 ai_evaluation dict 提取 grade 字段（A/B/C/D/F）。None 表示无 AI 评估。"""
    if not ai_evaluation:
        return None
    grade = ai_evaluation.get("grade")
    if grade is None:
        # 兼容嵌套结构
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


def _fuse_with_ai(
    risk_status: RiskStatus,
    ai_grade: str | None,
) -> tuple[DecisionGateStatus, list[str]]:
    """AI 评分与风控结果融合，返回 (决策状态, 融合原因)。

    仅在 risk 为 WARN/ALLOW/ALLOW_CONFIRM 时 AI 有话语权。
    risk 为 BLOCK/REDUCE_RISK 时 AI 不干预。
    """
    reasons: list[str] = []

    if ai_grade is None:
        # 无 AI 评估，按原逻辑
        if risk_status in (RiskStatus.ALLOW, RiskStatus.ALLOW_CONFIRM):
            return DecisionGateStatus.ALLOW_CONFIRM, reasons
        elif risk_status == RiskStatus.WARN:
            return DecisionGateStatus.WAIT, ["risk_warn: 风控警告，等待用户调整"]
        elif risk_status == RiskStatus.REDUCE_RISK:
            return DecisionGateStatus.REDUCE_RISK, reasons
        return DecisionGateStatus.BLOCK, reasons

    # 有 AI 评估
    if risk_status == RiskStatus.BLOCK:
        return DecisionGateStatus.BLOCK, reasons
    elif risk_status == RiskStatus.REDUCE_RISK:
        return DecisionGateStatus.REDUCE_RISK, reasons
    elif risk_status == RiskStatus.WARN:
        # 风控警告 + AI 差评 → 升级为 BLOCK
        if ai_grade in ("D", "F"):
            reasons.append(f"ai_fusion: AI 评级 {ai_grade} + 风控警告 → 升级为禁止")
            return DecisionGateStatus.BLOCK, reasons
        # 风控警告 + AI 中性/好评 → 保持 WAIT
        reasons.append(f"ai_fusion: AI 评级 {ai_grade}，维持等待")
        return DecisionGateStatus.WAIT, ["risk_warn: 风控警告，等待用户调整"] + reasons
    else:
        # risk_status == ALLOW or ALLOW_CONFIRM
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
    ai_evaluation: Optional[dict] = None,
    plan_expired: bool = False,
) -> DecisionGateResult:
    reasons: list[str] = []

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

    # AI 评估与风控融合
    ai_grade = _ai_grade_value(ai_evaluation)
    result_status, fusion_reasons = _fuse_with_ai(risk_result.status, ai_grade)

    # BLOCK 时附加风控的 block_reasons
    if result_status == DecisionGateStatus.BLOCK and risk_result.block_reasons:
        return DecisionGateResult(
            result=result_status,
            reasons=list(risk_result.block_reasons) + fusion_reasons,
        )

    return DecisionGateResult(result=result_status, reasons=fusion_reasons)
