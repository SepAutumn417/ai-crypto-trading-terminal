"""v0.6 safe order preview and dry-run service. Never calls an exchange."""
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DecisionGateResult, ExecutionLog, OrderIntent, PositionSizingResult, TradePlan


def _intent_out(intent: OrderIntent, logs: list[ExecutionLog] | None = None) -> dict:
    return {
        "id": str(intent.id), "trade_plan_id": str(intent.trade_plan_id),
        "client_order_id": intent.client_order_id, "symbol": intent.symbol,
        "direction": intent.direction, "order_type": intent.order_type,
        "margin_mode": intent.margin_mode, "entry_price": str(intent.entry_price),
        "stop_loss_price": str(intent.stop_loss_price) if intent.stop_loss_price is not None else None,
        "take_profit_prices": [str(value) for value in intent.take_profit_prices],
        "quantity": str(intent.quantity), "leverage": str(intent.leverage),
        "status": intent.status, "request_payload": intent.request_payload,
        "created_at": intent.created_at.isoformat(),
        "logs": [
            {"event_type": log.event_type, "status": log.status, "message": log.message, "created_at": log.created_at.isoformat()}
            for log in (logs or [])
        ],
    }


async def _intent_logs(db: AsyncSession, intent_id: UUID) -> list[ExecutionLog]:
    return list((await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.order_intent_id == intent_id)
        .order_by(ExecutionLog.created_at)
    )).scalars().all())


async def get_intent(db: AsyncSession, intent_id: UUID) -> dict:
    intent = await db.get(OrderIntent, intent_id)
    if intent is None:
        raise LookupError(f"Order intent {intent_id} not found")
    return _intent_out(intent, await _intent_logs(db, intent.id))


async def list_plan_intents(db: AsyncSession, plan_id: UUID) -> list[dict]:
    if await db.get(TradePlan, plan_id) is None:
        raise LookupError(f"Plan {plan_id} not found")
    intents = (await db.execute(
        select(OrderIntent)
        .where(OrderIntent.trade_plan_id == plan_id)
        .order_by(OrderIntent.created_at.desc())
    )).scalars().all()
    return [_intent_out(intent, await _intent_logs(db, intent.id)) for intent in intents]


async def create_preview(db: AsyncSession, plan_id: UUID) -> dict:
    plan = await db.get(TradePlan, plan_id)
    if plan is None:
        raise LookupError(f"Plan {plan_id} not found")
    sizing = (await db.execute(
        select(PositionSizingResult).where(PositionSizingResult.trade_plan_id == plan_id, PositionSizingResult.is_latest.is_(True))
    )).scalar_one_or_none()
    decision = (await db.execute(
        select(DecisionGateResult).where(DecisionGateResult.trade_plan_id == plan_id, DecisionGateResult.is_latest.is_(True))
    )).scalar_one_or_none()
    if sizing is None or sizing.rounded_size is None or sizing.rounded_size <= Decimal("0"):
        raise ValueError("A valid position sizing result is required before creating an order preview")
    if decision is None or decision.result != "ALLOW_CONFIRM":
        raise ValueError("Only plans allowed by the decision gate can be previewed")
    if plan.stop_loss_price is None:
        raise ValueError("A stop-loss price is required for every order preview")

    client_order_id = f"dry-{uuid4().hex[:20]}"
    payload = {
        "symbol": plan.symbol, "side": "buy" if plan.direction == "LONG" else "sell", "order_type": "limit",
        "quantity": str(sizing.rounded_size), "price": str(plan.entry_price), "stop_loss_price": str(plan.stop_loss_price),
        "take_profit_price": str(plan.take_profit_prices[0]) if plan.take_profit_prices else None,
        "client_order_id": client_order_id, "margin_mode": plan.margin_mode, "dry_run": True,
    }
    intent = OrderIntent(
        trade_plan_id=plan.id, client_order_id=client_order_id, symbol=plan.symbol, direction=plan.direction,
        order_type="limit", margin_mode=plan.margin_mode, entry_price=plan.entry_price,
        stop_loss_price=plan.stop_loss_price, take_profit_prices=plan.take_profit_prices,
        quantity=sizing.rounded_size, leverage=plan.leverage, status="PREVIEWED", request_payload=payload,
    )
    db.add(intent)
    await db.flush()
    db.add(ExecutionLog(order_intent_id=intent.id, event_type="ORDER_PREVIEW_CREATED", status="PREVIEWED", message="Order preview created; no exchange request was sent.", payload=payload))
    await db.commit()
    await db.refresh(intent)
    return _intent_out(intent, await _intent_logs(db, intent.id))


async def run_dry_run(db: AsyncSession, intent_id: UUID) -> dict:
    intent = await db.get(OrderIntent, intent_id)
    if intent is None:
        raise LookupError(f"Order intent {intent_id} not found")
    if intent.status == "DRY_RUN_PASSED":
        return _intent_out(intent, await _intent_logs(db, intent.id))
    if intent.status != "PREVIEWED":
        raise ValueError(f"Order intent in state {intent.status} cannot be dry-run")
    payload = intent.request_payload
    required = ("symbol", "side", "order_type", "quantity", "price", "stop_loss_price", "client_order_id")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        intent.status = "DRY_RUN_FAILED"
        db.add(ExecutionLog(order_intent_id=intent.id, event_type="DRY_RUN_FAILED", status=intent.status, message=f"Missing required payload fields: {', '.join(missing)}"))
    else:
        intent.status = "DRY_RUN_PASSED"
        db.add(ExecutionLog(order_intent_id=intent.id, event_type="DRY_RUN_PASSED", status=intent.status, message="Payload serialization and safety checks passed. No exchange request was sent.", payload=payload))
    await db.commit()
    await db.refresh(intent)
    return _intent_out(intent, await _intent_logs(db, intent.id))
