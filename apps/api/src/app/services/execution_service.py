from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PositionSizingResult as PositionSizingResultModel,
    TradePlan as TradePlanModel,
)
from app.services.plan_service import _to_schema
from app.services.config_service import get_user_settings
from app.config import settings
from exchange_adapter import (
    BitgetExchange, MockExchange, OrderSide, OrderType, Order,
)
from shared.enums import Direction, PlanStatus
from shared.schemas import TradePlan as TradePlanSchema


def _get_exchange():
    if settings.mock_exchange:
        return MockExchange()
    return BitgetExchange(
        api_key=settings.bitget_api_key if hasattr(settings, 'bitget_api_key') else None,
        api_secret=settings.bitget_api_secret if hasattr(settings, 'bitget_api_secret') else None,
        passphrase=settings.bitget_passphrase if hasattr(settings, 'bitget_passphrase') else None,
    )


def _direction_to_side(direction: Direction) -> OrderSide:
    if direction == Direction.LONG:
        return OrderSide.BUY
    return OrderSide.SELL


async def execute_plan(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")

    if model.status not in (
        PlanStatus.READY_FOR_CONFIRMATION.value,
        PlanStatus.SUBMITTED.value,
    ):
        raise ValueError(
            f"Plan status {model.status} 不允许执行，仅 READY_FOR_CONFIRMATION 状态可执行"
        )

    user_settings = await get_user_settings(db)
    if user_settings and not user_settings.execution_enabled:
        raise ValueError("交易执行未启用，请在设置中开启")
    if user_settings and user_settings.kill_switch:
        raise ValueError("Kill Switch 已激活，禁止下单")

    sizing_model = await _get_latest_sizing(db, plan_id)
    if sizing_model is None or sizing_model.rounded_size is None:
        raise ValueError("未找到有效的仓位计算结果，请先执行 check_plan")

    quantity = sizing_model.rounded_size
    if quantity <= Decimal("0"):
        raise ValueError("下单数量无效")

    direction = Direction(model.direction)
    side = _direction_to_side(direction)

    take_profit_price = None
    if model.take_profit_prices and len(model.take_profit_prices) > 0:
        take_profit_price = Decimal(str(model.take_profit_prices[0]))

    client_order_id = f"plan_{plan_id.hex[:16]}_{uuid4().hex[:8]}"

    exchange = _get_exchange()
    try:
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
        model.filled_quantity = order.filled_quantity
        model.average_fill_price = order.average_fill_price
        model.execution_error = None

    except Exception as e:
        model.status = PlanStatus.FAILED.value
        model.execution_error = str(e)
        raise
    finally:
        await db.commit()
        await db.refresh(model)

    return _to_schema(model)


async def sync_order_status(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")

    if not model.exchange_order_id:
        raise ValueError("该计划没有关联的交易所订单")

    if model.status in (
        PlanStatus.FILLED.value,
        PlanStatus.CANCELLED.value,
        PlanStatus.FAILED.value,
    ):
        return _to_schema(model)

    exchange = _get_exchange()
    try:
        order = await exchange.get_order(model.symbol, model.exchange_order_id)
        model.status = _order_status_to_plan_status(order.status).value
        model.filled_quantity = order.filled_quantity
        model.average_fill_price = order.average_fill_price
    except Exception as e:
        model.execution_error = str(e)
    finally:
        await db.commit()
        await db.refresh(model)

    return _to_schema(model)


async def cancel_plan_order(db: AsyncSession, plan_id: UUID) -> TradePlanSchema:
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise LookupError(f"Plan {plan_id} not found")

    if not model.exchange_order_id:
        raise ValueError("该计划没有关联的交易所订单")

    if model.status in (
        PlanStatus.FILLED.value,
        PlanStatus.CANCELLED.value,
        PlanStatus.FAILED.value,
    ):
        raise ValueError(f"订单状态 {model.status} 无法取消")

    exchange = _get_exchange()
    try:
        await exchange.cancel_order(model.symbol, model.exchange_order_id)
        model.status = PlanStatus.CANCELLED.value
    except Exception as e:
        model.execution_error = str(e)
        raise
    finally:
        await db.commit()
        await db.refresh(model)

    return _to_schema(model)


async def _get_latest_sizing(
    db: AsyncSession, plan_id: UUID
) -> PositionSizingResultModel | None:
    from sqlalchemy import select
    from app.models import PositionSizingResult as PositionSizingResultModel

    q = (
        select(PositionSizingResultModel)
        .where(PositionSizingResultModel.trade_plan_id == plan_id)
        .order_by(PositionSizingResultModel.id.desc())
        .limit(1)
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()


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
