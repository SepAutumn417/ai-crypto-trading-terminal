"""P1-1: 风控状态更新服务 — 成交/平仓后更新 daily_loss_r、consecutive_losses、cooldown_until。

核心逻辑：
1. 交易日切换时重置 daily_loss_r
2. 平仓亏损时：增加 consecutive_losses，累加 daily_loss_r，设置 cooldown
3. 平仓盈利时：重置 consecutive_losses
4. 风控超限时自动触发 Kill Switch

R 倍数计算：pnl / risk_amount（risk_amount 来自 PositionSizingResult）
"""
import logging
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AccountRiskState as AccountRiskStateModel,
)
from app.models import (
    PositionSizingResult as PositionSizingResultModel,
)
from app.models import (
    TradeJournal as TradeJournalModel,
)
from app.services.config_service import get_active_risk_config
from app.services.kill_switch_service import activate_kill_switch

logger = logging.getLogger(__name__)


async def _get_or_create_risk_state(db: AsyncSession) -> AccountRiskStateModel:
    """获取 AccountRiskState（id=1），不存在则创建。"""
    model = await db.get(AccountRiskStateModel, 1)
    if model is None:
        model = AccountRiskStateModel(
            id=1,
            daily_loss_r=Decimal("0"),
            consecutive_losses=0,
            cooldown_until=None,
            last_trade_date=None,
        )
        db.add(model)
        await db.flush()
    return model


async def _get_risk_amount_for_journal(db: AsyncSession, journal: TradeJournalModel) -> Decimal | None:
    """从 PositionSizingResult 获取 risk_amount（用于计算 R 倍数）。"""
    if journal.trade_plan_id is None:
        return None

    result = await db.execute(
        select(PositionSizingResultModel)
        .where(PositionSizingResultModel.trade_plan_id == journal.trade_plan_id)
        .order_by(PositionSizingResultModel.id.desc())
        .limit(1)
    )
    sizing = result.scalar_one_or_none()
    if sizing is None:
        return None
    return sizing.risk_amount


async def reset_daily_loss_if_new_day(db: AsyncSession) -> bool:
    """如果交易日已切换，重置 daily_loss_r 为 0。

    Returns:
        True 如果执行了重置
    """
    state = await _get_or_create_risk_state(db)
    today = date.today()

    if state.last_trade_date is not None and state.last_trade_date < today:
        state.daily_loss_r = Decimal("0")
        state.consecutive_losses = 0  # 新的一天也重置连续亏损
        await db.flush()
        logger.info(
            "daily_loss_reset new_day=%s prev_date=%s prev_loss_r=%s",
            today, state.last_trade_date, state.daily_loss_r,
        )
        return True

    return False


async def update_risk_state_on_close(
    db: AsyncSession,
    journal: TradeJournalModel,
) -> None:
    """平仓后更新风控状态。

    在 TradeJournalService.update 中，当 journal 状态变为 CLOSED 且有 pnl 时调用。

    逻辑：
    1. 交易日切换时重置 daily_loss_r 和 consecutive_losses
    2. 计算 R 倍数 = pnl / risk_amount
    3. 亏损：consecutive_losses + 1，daily_loss_r += |R|，设置 cooldown
    4. 盈利：consecutive_losses = 0
    5. 检查风控超限 → 自动触发 Kill Switch
    """
    if journal.status != "CLOSED" or journal.pnl is None:
        return

    # 交易日切换重置
    await reset_daily_loss_if_new_day(db)

    state = await _get_or_create_risk_state(db)
    state.last_trade_date = date.today()

    # 获取 risk_amount 计算 R 倍数
    risk_amount = await _get_risk_amount_for_journal(db, journal)
    pnl = journal.pnl

    if risk_amount and risk_amount > 0:
        r_multiple = pnl / risk_amount
    else:
        # 无法计算 R 倍数时，亏损按 1R 估算
        r_multiple = Decimal("-1") if pnl < 0 else Decimal("1")

    risk_cfg, _ = await get_active_risk_config(db)

    if pnl < 0:
        # 亏损
        state.consecutive_losses += 1
        state.daily_loss_r += abs(r_multiple)
        # 设置冷却期
        if risk_cfg.cooldown_minutes_after_loss > 0:
            state.cooldown_until = datetime.now(UTC) + timedelta(
                minutes=int(risk_cfg.cooldown_minutes_after_loss)
            )
        logger.warning(
            "trade_closed LOSS journal_id=%s pnl=%s r_multiple=%s "
            "consecutive_losses=%s daily_loss_r=%s cooldown_until=%s",
            journal.id, pnl, r_multiple,
            state.consecutive_losses, state.daily_loss_r, state.cooldown_until,
        )
    elif pnl > 0:
        # 盈利 — 重置连续亏损
        state.consecutive_losses = 0
        logger.info(
            "trade_closed WIN journal_id=%s pnl=%s r_multiple=%s consecutive_losses reset to 0",
            journal.id, pnl, r_multiple,
        )

    await db.flush()

    # 检查风控超限 → 自动触发 Kill Switch
    reasons: list[str] = []
    if state.daily_loss_r >= risk_cfg.daily_loss_limit_r:
        reasons.append(
            f"daily_loss_limit_reached: {state.daily_loss_r}R >= {risk_cfg.daily_loss_limit_r}R"
        )
    if state.consecutive_losses >= risk_cfg.max_consecutive_losses:
        reasons.append(
            f"consecutive_loss_limit_reached: {state.consecutive_losses} >= {risk_cfg.max_consecutive_losses}"
        )

    if reasons:
        reason = "风控超限自动触发: " + "; ".join(reasons)
        await activate_kill_switch(
            db,
            reason=reason,
            triggered_by="risk_engine",
            related_plan_id=journal.trade_plan_id,
            severity="critical",
        )
        logger.critical(
            "kill_switch_auto_triggered_by_risk_engine journal_id=%s reasons=%s",
            journal.id, reasons,
        )
