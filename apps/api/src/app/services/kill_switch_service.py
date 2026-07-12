"""P0-5: Kill Switch 服务 — 自动触发、强制关闭 execution mode、审计原因。

设计要点：
1. activate_kill_switch: 激活时同时强制关闭 execution_enabled，防止继续下单
2. 审计: 记录触发原因、触发源、关联计划/订单、前后状态差异
3. 联动: 与 RECONCILIATION_REQUIRED 状态机配合，孤儿订单/对账失败自动触发
4. 广播: 通过 WebSocket 推送状态变更，前端即时反馈

自动触发场景（由 execution_service 调用）：
- 孤儿订单产生（补偿撤单失败）
- 对账失败（订单状态未知且交易所未找到订单）
- 连续亏损达到上限（由 P1-1 的成交后更新逻辑调用）
- 日亏损达到上限（由 P1-1 的成交后更新逻辑调用）
"""
import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemEvent, UserSettings
from app.websocket import ws_manager

logger = logging.getLogger(__name__)


async def activate_kill_switch(
    db: AsyncSession,
    reason: str,
    triggered_by: str = "system",
    related_plan_id: UUID | None = None,
    severity: str = "critical",
) -> bool:
    """激活 Kill Switch 并强制关闭 execution mode。

    Args:
        db: 数据库会话
        reason: 触发原因（人类可读）
        triggered_by: 触发源 — "system" / "user" / "risk_engine" / "execution_service"
        related_plan_id: 关联的计划 ID（如有）
        severity: 事件严重级别 — "critical" / "warning" / "info"

    Returns:
        True 如果状态发生了变更（从 False → True），False 如果已经是激活状态
    """
    settings = await db.get(UserSettings, 1)
    if settings is None:
        logger.error("activate_kill_switch: user_settings not initialized")
        return False

    already_active = settings.kill_switch
    was_execution_enabled = settings.execution_enabled

    # 强制设置 kill_switch=True, execution_enabled=False
    settings.kill_switch = True
    settings.execution_enabled = False

    # 审计事件 — 包含完整的触发上下文
    payload = {
        "enabled": True,
        "reason": reason,
        "triggered_by": triggered_by,
        "previous_kill_switch": already_active,
        "previous_execution_enabled": was_execution_enabled,
        "forced_execution_mode_off": was_execution_enabled,
    }
    if related_plan_id is not None:
        payload["related_plan_id"] = str(related_plan_id)

    event = SystemEvent(
        id=uuid4(),
        event_type="kill_switch_activated",
        severity=severity,
        entity_type="user_settings",
        entity_id=related_plan_id,
        actor=triggered_by,
        message=f"Kill Switch 激活: {reason}",
        payload=payload,
    )
    db.add(event)
    await db.commit()
    await db.refresh(settings)

    logger.critical(
        "kill_switch_activated reason=%s triggered_by=%s related_plan_id=%s "
        "prev_kill_switch=%s prev_exec_enabled=%s",
        reason, triggered_by, related_plan_id,
        already_active, was_execution_enabled,
    )

    # 广播状态变更（失败不影响主流程）
    try:
        await ws_manager.broadcast("system", "kill_switch_activated", {
            "kill_switch": True,
            "execution_enabled": False,
            "reason": reason,
            "triggered_by": triggered_by,
            "severity": severity,
        })
    except Exception:
        logger.debug("broadcast kill_switch_activated failed", exc_info=True)

    return not already_active


async def deactivate_kill_switch(
    db: AsyncSession,
    reason: str,
    triggered_by: str = "user",
) -> bool:
    """手动恢复 Kill Switch。

    注意：恢复 kill_switch 不会自动开启 execution_enabled，需用户单独开启。

    Args:
        db: 数据库会话
        reason: 恢复原因（审计用）
        triggered_by: 恢复源

    Returns:
        True 如果状态发生了变更（从 True → False）
    """
    settings = await db.get(UserSettings, 1)
    if settings is None:
        logger.error("deactivate_kill_switch: user_settings not initialized")
        return False

    was_active = settings.kill_switch
    settings.kill_switch = False

    event = SystemEvent(
        id=uuid4(),
        event_type="kill_switch_deactivated",
        severity="warning",
        entity_type="user_settings",
        entity_id=None,
        actor=triggered_by,
        message=f"Kill Switch 解除: {reason}",
        payload={
            "enabled": False,
            "reason": reason,
            "triggered_by": triggered_by,
            "previous_kill_switch": was_active,
        },
    )
    db.add(event)
    await db.commit()
    await db.refresh(settings)

    logger.info(
        "kill_switch_deactivated reason=%s triggered_by=%s prev_active=%s",
        reason, triggered_by, was_active,
    )

    try:
        await ws_manager.broadcast("system", "kill_switch_deactivated", {
            "kill_switch": False,
            "execution_enabled": settings.execution_enabled,
            "reason": reason,
        })
    except Exception:
        logger.debug("broadcast kill_switch_deactivated failed", exc_info=True)

    return was_active


async def is_kill_switch_active(db: AsyncSession) -> bool:
    """检查 Kill Switch 是否激活（执行前快速检查）。"""
    settings = await db.get(UserSettings, 1)
    if settings is None:
        # 未初始化时 fail-closed
        return True
    return settings.kill_switch
