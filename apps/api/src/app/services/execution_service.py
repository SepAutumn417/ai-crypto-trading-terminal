"""P0-3/P0-4 重写：execute_plan 服务端二次确认 + 状态机 + 行锁 + 对账恢复。

关键变更：
1. P0-3: 执行前验证 confirmation（token、TTL、plan_hash）
2. P0-4: 使用 with_for_update() 行锁防止并发抢占
3. P0-4: 引入 EXECUTING 中间态，下单前原子标记
4. P0-4: 稳定 client_order_id（仅基于 plan_id，不随 attempt 变化）
5. P0-4: EXECUTING 状态恢复：按 clientOid 查询交易所对账
6. P0-4: UNKNOWN/RECONCILIATION_REQUIRED 状态处理
"""
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import AppException, ExecutionDisabledException, SubmissionFailedException
from app.models import (
    PositionSizingResult as PositionSizingResultModel,
)
from app.models import (
    TradeJournal as TradeJournalModel,
)
from app.models import (
    TradePlan as TradePlanModel,
)
from app.services.config_service import get_user_settings
from app.services.confirmation_service import validate_confirmation
from app.services.plan_converter import to_schema as _to_schema
from exchange_adapter import (
    BitgetExchange,
    Exchange,
    MockExchange,
    Order,
    OrderSide,
    OrderType,
)
from shared.enums import Direction, PlanStatus
from shared.schemas import TradePlan as TradePlanSchema

logger = logging.getLogger(__name__)


_RETRYABLE_EXCHANGE_ERRORS = ("timeout", "connection", "reset", "503", "504", "502")

# 终态：不可再执行
_TERMINAL_STATES = frozenset({
    PlanStatus.FILLED.value,
    PlanStatus.CANCELLED.value,
    PlanStatus.EXPIRED.value,
})

# 幂等命中态：直接返回当前状态
_IDEMPOTENT_STATES = frozenset({
    PlanStatus.SUBMITTED.value,
    PlanStatus.PARTIALLY_FILLED.value,
})


_exchange_instance: Exchange | None = None


def _get_exchange() -> Exchange:
    """模块级 lazy 单例，避免每次调用 new BitgetExchange() 导致 socket 泄漏。"""
    global _exchange_instance
    if _exchange_instance is None:
        if settings.mock_exchange:
            _exchange_instance = MockExchange()
        else:
            _exchange_instance = BitgetExchange(
                api_key=settings.bitget_api_key,
                api_secret=settings.bitget_api_secret,
                passphrase=settings.bitget_passphrase,
            )
    return _exchange_instance


async def close_exchange() -> None:
    """FastAPI lifespan 调用：进程退出时关闭底层 HTTP session。"""
    global _exchange_instance
    if _exchange_instance is not None:
        await _exchange_instance.close()
        _exchange_instance = None


def reset_exchange_for_tests() -> None:
    """单测 reset 单例。"""
    global _exchange_instance
    _exchange_instance = None


async def check_system_health(db: AsyncSession, symbol: str | None = None) -> tuple[bool, bool]:
    """获取真实的 exchange / db 连接状态。"""
    db_healthy = True
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
    except Exception:
        db_healthy = False

    exchange_connected = False
    try:
        exchange = _get_exchange()
        probe_symbol = symbol or "BTCUSDT"
        await exchange.get_ticker(probe_symbol)
        exchange_connected = True
    except Exception:
        exchange_connected = False

    return exchange_connected, db_healthy


def _direction_to_side(direction: Direction) -> OrderSide:
    if direction == Direction.LONG:
        return OrderSide.BUY
    return OrderSide.SELL


def _build_client_order_id(plan_id: UUID) -> str:
    """P0-4: 稳定幂等键 — 仅基于 plan_id，不随 attempt 变化。

    这样即使重试也使用相同的 clientOid：
    - 如果交易所已有该 clientOid 的订单，查询恢复即可
    - 如果交易所没有，安全提交新订单
    """
    return f"plan-{plan_id.hex[:16]}"


def _is_retryable_error(error_message: str) -> bool:
    msg = error_message.lower()
    return any(token in msg for token in _RETRYABLE_EXCHANGE_ERRORS)


def _classify_error(error: Exception) -> tuple[str, bool, int | None]:
    msg = str(error)
    if _is_retryable_error(msg):
        return ("EXCHANGE_NETWORK_ERROR", True, 30)
    return ("EXCHANGE_REJECTED", False, None)


def _mark_failed(
    model: TradePlanModel,
    error_code: str,
    error_message: str,
    retryable: bool,
    retry_after_seconds: int | None,
) -> None:
    model.status = PlanStatus.FAILED.value
    model.execution_error = error_message
    model.execution_error_code = error_code
    model.execution_retryable = retryable
    model.execution_retry_after_seconds = retry_after_seconds


async def _get_latest_sizing(db: AsyncSession, plan_id: UUID) -> PositionSizingResultModel | None:
    q = (
        select(PositionSizingResultModel)
        .where(PositionSizingResultModel.trade_plan_id == plan_id)
        .order_by(PositionSizingResultModel.id.desc())
        .limit(1)
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def _auto_create_journal_on_fill(db: AsyncSession, model: TradePlanModel) -> None:
    """订单变为 FILLED 时自动创建 trade_journal。"""
    from datetime import datetime, timezone

    existing = await db.execute(
        select(TradeJournalModel).where(TradeJournalModel.trade_plan_id == model.id).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return

    filled_qty = model.filled_quantity or Decimal("0")
    fill_price = model.average_fill_price or model.entry_price

    journal = TradeJournalModel(
        trade_plan_id=model.id,
        exchange=model.exchange,
        symbol=model.symbol,
        direction=model.direction,
        entry_price=fill_price,
        quantity=filled_qty,
        leverage=model.leverage,
        setup_type=model.setup_type,
        entry_reason=model.notes,
        status="OPEN",
        entry_at=datetime.now(timezone.utc),
    )
    db.add(journal)
    logger.info("auto_created_journal plan_id=%s symbol=%s qty=%s", model.id, model.symbol, filled_qty)


async def _reconcile_executing_plan(db: AsyncSession, model: TradePlanModel, plan_id: UUID) -> TradePlanSchema | None:
    """P0-4: 对账恢复 — 处于 EXECUTING 状态的计划查询交易所确认订单状态。

    Returns:
        - TradePlanSchema: 如果订单已确认（成功或失败），返回更新后的 plan
        - None: 如果订单未找到，可以安全重试
    """
    exchange = _get_exchange()
    client_order_id = model.client_order_id

    # 优先按 exchange_order_id 查询
    if model.exchange_order_id:
        try:
            order = await exchange.get_order(model.symbol, model.exchange_order_id)
            model.status = _order_status_to_plan_status(order.status).value
            model.filled_quantity = order.filled_quantity
            model.average_fill_price = order.average_fill_price
            model.execution_error = None
            model.execution_error_code = None
            model.execution_retryable = None
            model.execution_retry_after_seconds = None
            if model.status == PlanStatus.FILLED.value:
                await _auto_create_journal_on_fill(db, model)
            await db.commit()
            await db.refresh(model)
            logger.info(
                "reconcile recovered by exchange_order_id plan_id=%s status=%s",
                plan_id, model.status,
            )
            return _to_schema(model)
        except Exception as e:
            logger.warning("reconcile by exchange_order_id failed plan_id=%s: %s", plan_id, e)

    # 按 client_order_id 查询
    if client_order_id:
        order = await exchange.get_order_by_client_id(model.symbol, client_order_id)
        if order is not None:
            model.status = _order_status_to_plan_status(order.status).value
            model.exchange_order_id = order.id
            model.filled_quantity = order.filled_quantity
            model.average_fill_price = order.average_fill_price
            model.execution_error = None
            model.execution_error_code = None
            model.execution_retryable = None
            model.execution_retry_after_seconds = None
            if model.status == PlanStatus.FILLED.value:
                await _auto_create_journal_on_fill(db, model)
            await db.commit()
            await db.refresh(model)
            logger.info(
                "reconcile recovered by client_order_id plan_id=%s status=%s",
                plan_id, model.status,
            )
            return _to_schema(model)

    # 订单未找到 — 标记为 RECONCILIATION_REQUIRED，需要人工介入或安全重试
    logger.warning(
        "reconcile: order not found plan_id=%s client_order_id=%s — safe to retry",
        plan_id, client_order_id,
    )
    return None


async def execute_plan(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    """P0-3/P0-4: 带二次确认和状态机的执行流程。

    状态机：
    - CONFIRMED → 验证确认 → EXECUTING → place_order → SUBMITTED/FILLED/FAILED
    - EXECUTING → 对账恢复（按 clientOid 查询交易所）
    - SUBMITTED/PARTIALLY_FILLED → 幂等命中，返回当前状态
    - FILLED/CANCELLED/EXPIRED → IDEMPOTENCY_CONFLICT
    - READY_FOR_CONFIRMATION → 错误：必须先确认
    - FAILED → 错误：必须重新 check_plan 并确认
    - UNKNOWN/RECONCILIATION_REQUIRED → 需要对账恢复
    """
    # P0-4: 行锁 — 防止并发执行同一计划
    result = await db.execute(
        select(TradePlanModel)
        .where(TradePlanModel.id == plan_id)
        .with_for_update()
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")

    current_status = model.status

    # 终态检查
    if current_status in _TERMINAL_STATES:
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="IDEMPOTENCY_CONFLICT",
            error_message=f"Plan 已在终态 {current_status}，无法再次提交",
            retryable=False,
        )

    # 幂等命中
    if current_status in _IDEMPOTENT_STATES:
        if model.client_order_id:
            logger.info(
                "execute_plan idempotent hit plan_id=%s client_order_id=%s status=%s",
                plan_id, model.client_order_id, current_status,
            )
            return _to_schema(model)

    # P0-4: EXECUTING 状态 — 对账恢复
    if current_status == PlanStatus.EXECUTING.value:
        recovered = await _reconcile_executing_plan(db, model, plan_id)
        if recovered is not None:
            return recovered
        # 订单未找到，可以安全重试 — 回到 CONFIRMED 状态
        model.status = PlanStatus.CONFIRMED.value
        await db.commit()
        await db.refresh(model)
        # 重新获取行锁
        result = await db.execute(
            select(TradePlanModel)
            .where(TradePlanModel.id == plan_id)
            .with_for_update()
        )
        model = result.scalar_one()
        current_status = model.status

    # P0-4: UNKNOWN / RECONCILIATION_REQUIRED — 需要对账
    if current_status in (PlanStatus.UNKNOWN.value, PlanStatus.RECONCILIATION_REQUIRED.value):
        recovered = await _reconcile_executing_plan(db, model, plan_id)
        if recovered is not None:
            return recovered
        # P0-5: 对账失败 — 订单状态未知且交易所未找到订单，自动触发 Kill Switch
        try:
            from app.services.kill_switch_service import activate_kill_switch
            await activate_kill_switch(
                db,
                reason=f"对账失败: 计划 {plan_id} 状态为 {current_status}，交易所未找到对应订单",
                triggered_by="execution_service",
                related_plan_id=plan_id,
                severity="critical",
            )
        except Exception:
            logger.exception("auto-trigger kill_switch on reconciliation failure failed plan_id=%s", plan_id)
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="RECONCILIATION_FAILED",
            error_message="订单状态未知且交易所未找到订单，需要人工介入。Kill Switch 已自动激活",
            retryable=False,
        )

    # P0-3: 必须是 CONFIRMED 状态才能执行
    if current_status == PlanStatus.READY_FOR_CONFIRMATION.value:
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="NOT_CONFIRMED",
            error_message="计划已就绪但未确认，请先调用 /confirm 端点完成二次确认",
            retryable=False,
        )

    if current_status == PlanStatus.FAILED.value:
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="RECHECK_REQUIRED",
            error_message="计划上次执行失败，请重新执行 check_plan 并确认后再试",
            retryable=False,
        )

    if current_status != PlanStatus.CONFIRMED.value:
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="PLAN_INVALID_STATE",
            error_message=f"Plan 状态 {current_status} 不允许执行，仅 CONFIRMED 可执行",
            retryable=False,
        )

    # P0-3: 验证二次确认（token、TTL、plan_hash）
    validate_confirmation(model)

    # 系统状态检查
    user_settings = await get_user_settings(db)
    if user_settings and not user_settings.execution_enabled:
        raise ExecutionDisabledException("交易执行未启用，请在设置中开启")
    if user_settings and user_settings.kill_switch:
        raise ExecutionDisabledException("Kill Switch 已激活，禁止下单")

    # P0-1: 实盘硬开关
    if not settings.mock_exchange and not settings.real_trading_enabled:
        raise ExecutionDisabledException(
            "实盘交易未启用：REAL_TRADING_ENABLED=false。请在 .env 中设为 true 并确认风险后重启服务"
        )

    sizing_model = await _get_latest_sizing(db, plan_id)
    if sizing_model is None or sizing_model.rounded_size is None:
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="INVALID_QUANTITY",
            error_message="未找到有效的仓位计算结果，请先执行 check_plan",
            retryable=False,
        )

    quantity = sizing_model.rounded_size
    if quantity <= Decimal("0"):
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="INVALID_QUANTITY",
            error_message="下单数量无效",
            retryable=False,
        )

    direction = Direction(model.direction)
    side = _direction_to_side(direction)

    take_profit_price = None
    if model.take_profit_prices and len(model.take_profit_prices) > 0:
        take_profit_price = Decimal(str(model.take_profit_prices[0]))

    # P0-4: 稳定 client_order_id — 仅基于 plan_id，不随 attempt 变化
    client_order_id = _build_client_order_id(plan_id)

    # P0-4: 原子标记为 EXECUTING，防止并发下单
    model.status = PlanStatus.EXECUTING.value
    model.client_order_id = client_order_id
    model.execution_attempts = (model.execution_attempts or 0) + 1
    model.execution_error = None
    model.execution_error_code = None
    model.execution_retryable = None
    model.execution_retry_after_seconds = None
    await db.commit()  # 释放行锁，但 EXECUTING 状态阻止并发

    # 刷新模型以获取最新状态
    await db.refresh(model)

    exchange = _get_exchange()
    try:
        # P0-1: set_leverage 可安全重复调用；margin_mode 在 place_order 请求体中携带
        await exchange.set_leverage(model.symbol, int(model.leverage))

        order: Order = await exchange.place_order(
            symbol=model.symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=model.entry_price,
            stop_loss_price=model.stop_loss_price,
            take_profit_price=take_profit_price,
            client_order_id=client_order_id,
            margin_mode=model.margin_mode,
            margin_coin="USDT",
        )

        # 重新获取行锁更新最终状态
        result = await db.execute(
            select(TradePlanModel)
            .where(TradePlanModel.id == plan_id)
            .with_for_update()
        )
        model = result.scalar_one()

        model.status = _order_status_to_plan_status(order.status).value
        model.exchange_order_id = order.id
        model.filled_quantity = order.filled_quantity
        model.average_fill_price = order.average_fill_price
        model.execution_error = None
        model.execution_error_code = None
        model.execution_retryable = None
        model.execution_retry_after_seconds = None

        # 订单成交时自动创建交易日志
        if model.status == PlanStatus.FILLED.value:
            await _auto_create_journal_on_fill(db, model)

        # P1-25: place_order 成功后 db.commit 失败时的补偿
        try:
            await db.commit()
        except Exception as commit_err:
            logger.error(
                "execute_plan commit failed after place_order success, compensating "
                "plan_id=%s exchange_order_id=%s error=%s",
                plan_id, order.id, commit_err,
            )
            await db.rollback()
            compensated = False
            try:
                await exchange.cancel_order(model.symbol, order.id)
                compensated = True
                logger.info(
                    "execute_plan compensation cancel succeeded plan_id=%s order_id=%s",
                    plan_id, order.id,
                )
            except Exception as cancel_err:
                logger.error(
                    "execute_plan compensation cancel FAILED — ORPHAN ORDER "
                    "plan_id=%s order_id=%s error=%s",
                    plan_id, order.id, cancel_err,
                )
                # P0-5: 孤儿订单产生 — 补偿撤单失败，自动触发 Kill Switch 防止进一步风险
                try:
                    from app.services.kill_switch_service import activate_kill_switch
                    await activate_kill_switch(
                        db,
                        reason=f"孤儿订单: 计划 {plan_id} 提交成功但本地保存失败，"
                               f"补偿撤单失败，交易所订单 {order.id} 可能仍然存活",
                        triggered_by="execution_service",
                        related_plan_id=plan_id,
                        severity="critical",
                    )
                except Exception:
                    logger.exception(
                        "auto-trigger kill_switch on orphan order failed plan_id=%s order_id=%s",
                        plan_id, order.id,
                    )
            _mark_failed(
                model,
                error_code="COMMIT_FAILED",
                error_message=f"订单已提交但本地保存失败（补偿撤单={'成功' if compensated else '失败'}）: {commit_err}",
                retryable=True,
                retry_after_seconds=30,
            )
            try:
                await db.commit()
                await db.refresh(model)
            except Exception:
                await db.rollback()
            raise SubmissionFailedException(
                plan_id=str(plan_id),
                error_code="COMMIT_FAILED",
                error_message=f"订单已提交但本地保存失败（补偿撤单={'成功' if compensated else '失败'}）: {commit_err}",
                retryable=True,
                retry_after_seconds=30,
            ) from commit_err

        await db.refresh(model)
        logger.info(
            "execute_plan success plan_id=%s exchange_order_id=%s client_order_id=%s",
            plan_id, order.id, client_order_id,
        )
        return _to_schema(model)

    except Exception as e:
        error_code, retryable, retry_after = _classify_error(e)
        logger.exception(
            "execute_plan failed plan_id=%s client_order_id=%s error_code=%s",
            plan_id, client_order_id, error_code,
        )

        # P0-4: 网络超时类错误保持 EXECUTING 状态，等待对账恢复
        # 非网络错误标记为 FAILED
        try:
            result = await db.execute(
                select(TradePlanModel)
                .where(TradePlanModel.id == plan_id)
                .with_for_update()
            )
            model = result.scalar_one()

            if retryable:
                # 网络错误：保持 EXECUTING，等待对账恢复或用户重试
                model.status = PlanStatus.EXECUTING.value
                model.execution_error = str(e)
                model.execution_error_code = error_code
                model.execution_retryable = retryable
                model.execution_retry_after_seconds = retry_after
                logger.warning(
                    "execute_plan network error, kept EXECUTING for reconciliation "
                    "plan_id=%s client_order_id=%s",
                    plan_id, client_order_id,
                )
            else:
                _mark_failed(model, error_code, str(e), retryable, retry_after)
            await db.commit()
            await db.refresh(model)
        except Exception:
            logger.exception("execute_plan: failed to persist error state plan_id=%s", plan_id)
            await db.rollback()

        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code=error_code,
            error_message=str(e),
            retryable=retryable,
            retry_after_seconds=retry_after,
        ) from e


async def sync_order_status(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")

    if not model.exchange_order_id:
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="NO_ORDER_TO_SYNC",
            error_message="该计划没有关联的交易所订单",
            retryable=False,
        )

    if model.status in (
        PlanStatus.FILLED.value,
        PlanStatus.CANCELLED.value,
        PlanStatus.FAILED.value,
    ):
        return _to_schema(model)

    exchange = _get_exchange()
    try:
        order = await exchange.get_order(model.symbol, model.exchange_order_id)
        prev_status = model.status
        model.status = _order_status_to_plan_status(order.status).value
        model.filled_quantity = order.filled_quantity
        model.average_fill_price = order.average_fill_price
        model.execution_error = None
        model.execution_error_code = None
        model.execution_retryable = None
        model.execution_retry_after_seconds = None

        # 订单状态变为 FILLED 时自动创建交易日志
        if prev_status != PlanStatus.FILLED.value and model.status == PlanStatus.FILLED.value:
            await _auto_create_journal_on_fill(db, model)

        await db.commit()
        await db.refresh(model)
    except Exception as e:
        error_code, retryable, retry_after = _classify_error(e)
        logger.exception("sync_order_status failed plan_id=%s error=%s", plan_id, e)
        try:
            model.execution_error = str(e)
            model.execution_error_code = error_code
            model.execution_retryable = retryable
            model.execution_retry_after_seconds = retry_after
            await db.commit()
            await db.refresh(model)
        except Exception:
            logger.exception("sync_order_status: failed to persist failure state plan_id=%s", plan_id)
            await db.rollback()
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code=error_code,
            error_message=str(e),
            retryable=retryable,
            retry_after_seconds=retry_after,
        ) from e

    return _to_schema(model)


async def cancel_plan_order(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")

    if not model.exchange_order_id:
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="NO_ORDER_TO_CANCEL",
            error_message="该计划没有关联的交易所订单",
            retryable=False,
        )

    if model.status in (
        PlanStatus.FILLED.value,
        PlanStatus.CANCELLED.value,
        PlanStatus.FAILED.value,
    ):
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="INVALID_STATE_FOR_CANCEL",
            error_message=f"订单状态 {model.status} 无法取消",
            retryable=False,
        )

    exchange = _get_exchange()
    try:
        await exchange.cancel_order(model.symbol, model.exchange_order_id)
        model.status = PlanStatus.CANCELLED.value
        model.execution_error = None
        model.execution_error_code = None
        model.execution_retryable = None
        model.execution_retry_after_seconds = None
        await db.commit()
        await db.refresh(model)
    except Exception as e:
        error_code, retryable, retry_after = _classify_error(e)
        logger.exception("cancel_plan_order failed plan_id=%s error=%s", plan_id, e)
        try:
            model.execution_error = str(e)
            model.execution_error_code = error_code
            model.execution_retryable = retryable
            model.execution_retry_after_seconds = retry_after
            await db.commit()
            await db.refresh(model)
        except Exception:
            logger.exception("cancel_plan_order: failed to persist failure state plan_id=%s", plan_id)
            await db.rollback()
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code=error_code,
            error_message=str(e),
            retryable=retryable,
            retry_after_seconds=retry_after,
        ) from e

    return _to_schema(model)


def _order_status_to_plan_status(order_status) -> PlanStatus:
    from exchange_adapter import OrderStatus as ExchangeOrderStatus

    mapping = {
        ExchangeOrderStatus.NEW: PlanStatus.SUBMITTED,
        ExchangeOrderStatus.PARTIALLY_FILLED: PlanStatus.PARTIALLY_FILLED,
        ExchangeOrderStatus.FILLED: PlanStatus.FILLED,
        ExchangeOrderStatus.CANCELED: PlanStatus.CANCELLED,
        ExchangeOrderStatus.REJECTED: PlanStatus.FAILED,
        ExchangeOrderStatus.EXPIRED: PlanStatus.FAILED,
    }
    # P0-4: 未知状态映射为 UNKNOWN 而非 SUBMITTED，触发对账流程
    return mapping.get(order_status, PlanStatus.UNKNOWN)
