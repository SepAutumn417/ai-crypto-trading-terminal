"""PR-1 重写：execute_plan 错误处理与幂等键 + exchange 单例。

关键变更：
1. execute_plan 在异常路径用 _mark_failed 写状态 + raise SubmissionFailedException（替代 finally 强制 commit）
2. 客户端幂等键：{plan_id_short}-{attempt}，attempt 来自 trade_plan.execution_attempts + 1
3. 已提交（SUBMITTED/PARTIALLY_FILLED）plan 二次 execute → 幂等命中，不调交易所
4. FAILED plan execute → 允许重试，attempt 增 1
5. exchange 实例模块级 lazy 单例，close_exchange() 给 FastAPI lifespan 调用
"""
from uuid import UUID
from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ExecutionDisabledException, SubmissionFailedException
from app.models import (
    PositionSizingResult as PositionSizingResultModel,
    TradeJournal as TradeJournalModel,
    TradePlan as TradePlanModel,
)
from app.services.config_service import get_user_settings
from app.services.plan_converter import to_schema as _to_schema
from exchange_adapter import (
    BitgetExchange, Exchange, MockExchange, OrderSide, OrderType, Order,
)
from shared.enums import Direction, PlanStatus
from shared.schemas import TradePlan as TradePlanSchema


logger = logging.getLogger(__name__)


_RETRYABLE_EXCHANGE_ERRORS = ("timeout", "connection", "reset", "503", "504", "502")


_exchange_instance: Exchange | None = None


def _get_exchange() -> Exchange:
    """模块级 lazy 单例，避免每次调用 new BitgetExchange() 导致 socket 泄漏。

    BitgetExchange 内部维护 aiohttp.ClientSession，只在 close() 时释放。
    """
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
    """单测 reset 单例。每条 execute_plan 测试 setUp 调用。"""
    global _exchange_instance
    _exchange_instance = None


def _direction_to_side(direction: Direction) -> OrderSide:
    if direction == Direction.LONG:
        return OrderSide.BUY
    return OrderSide.SELL


def _build_client_order_id(plan_id: UUID, attempt: int) -> str:
    """幂等键格式：{plan_id_hex16}-{attempt}。

    同一 plan_id + attempt 在 Bitget 端只允许一次提交，重复提交会返回 order already exists。
    """
    return f"{plan_id.hex[:16]}-{attempt}"


def _is_retryable_error(error_message: str) -> bool:
    msg = error_message.lower()
    return any(token in msg for token in _RETRYABLE_EXCHANGE_ERRORS)


def _classify_error(error: Exception) -> tuple[str, bool, int | None]:
    """根据异常消息决定 error_code、retryable、retry_after_seconds。"""
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
    """订单变为 FILLED 时自动创建 trade_journal（若尚未存在）。

    幂等：通过 trade_plan_id 检查是否已存在 journal，避免重复创建。
    字段从 trade_plan 自动填充，用户后续可在日志页补充复盘信息。
    """
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
        entry_at=model.updated_at,
    )
    db.add(journal)
    logger.info("auto_created_journal plan_id=%s symbol=%s qty=%s", model.id, model.symbol, filled_qty)


async def execute_plan(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    """提交或幂等命中。

    状态机：
    - DRAFT / CHECKED / READY_FOR_CONFIRMATION → 走 place_order 路径
    - SUBMITTED / PARTIALLY_FILLED → 幂等命中，return 当前 plan
    - FILLED / CANCELLED / EXPIRED → AppException(IDEMPOTENCY_CONFLICT)
    - FAILED → 允许重试，attempt 增 1
    """
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")

    if model.status in (PlanStatus.FILLED.value, PlanStatus.CANCELLED.value, PlanStatus.EXPIRED.value):
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="IDEMPOTENCY_CONFLICT",
            error_message=f"Plan 已在终态 {model.status}，无法再次提交",
            retryable=False,
        )

    if model.status in (PlanStatus.SUBMITTED.value, PlanStatus.PARTIALLY_FILLED.value):
        if model.client_order_id:
            logger.info(
                "execute_plan idempotent hit plan_id=%s client_order_id=%s status=%s",
                plan_id, model.client_order_id, model.status,
            )
            return _to_schema(model)

    if model.status not in (PlanStatus.READY_FOR_CONFIRMATION.value, PlanStatus.FAILED.value):
        raise SubmissionFailedException(
            plan_id=str(plan_id),
            error_code="PLAN_INVALID_STATE",
            error_message=f"Plan 状态 {model.status} 不允许执行",
            retryable=False,
        )

    user_settings = await get_user_settings(db)
    if user_settings and not user_settings.execution_enabled:
        raise ExecutionDisabledException("交易执行未启用，请在设置中开启")
    if user_settings and user_settings.kill_switch:
        raise ExecutionDisabledException("Kill Switch 已激活，禁止下单")

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

    next_attempt = (model.execution_attempts or 0) + 1
    client_order_id = _build_client_order_id(plan_id, next_attempt)

    exchange = _get_exchange()
    try:
        # 实盘下单前设置杠杆和保证金模式（MockExchange 实现为 no-op）
        await exchange.set_leverage(model.symbol, int(model.leverage))
        await exchange.set_margin_mode(model.symbol, model.margin_mode)

        order: Order = await exchange.place_order(
            symbol=model.symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=model.entry_price,
            stop_loss_price=model.stop_loss_price,
            take_profit_price=take_profit_price,
            client_order_id=client_order_id,
        )

        model.status = _order_status_to_plan_status(order.status).value
        model.exchange_order_id = order.id
        model.client_order_id = client_order_id
        model.execution_attempts = next_attempt
        model.filled_quantity = order.filled_quantity
        model.average_fill_price = order.average_fill_price
        model.execution_error = None
        model.execution_error_code = None
        model.execution_retryable = None
        model.execution_retry_after_seconds = None

        # 订单成交时自动创建交易日志
        if model.status == PlanStatus.FILLED.value:
            await _auto_create_journal_on_fill(db, model)

        await db.commit()
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
        try:
            _mark_failed(model, error_code, str(e), retryable, retry_after)
            model.client_order_id = client_order_id
            model.execution_attempts = next_attempt
            await db.commit()
            await db.refresh(model)
        except Exception:
            logger.exception("execute_plan: failed to persist failure state plan_id=%s", plan_id)
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
    return mapping.get(order_status, PlanStatus.SUBMITTED)