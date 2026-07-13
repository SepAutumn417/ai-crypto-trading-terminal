"""Read-only account synchronization for the L4 terminal.

This module deliberately exposes no exchange mutation methods.  It reuses the
execution service's process-wide exchange client so the configured Bitget
credentials and HTTP session are shared without ever placing an order.
"""
import asyncio
from datetime import UTC, datetime

from app.exceptions import AppException
from app.services.execution_service import _get_exchange


def _balance_out(balance) -> dict:
    return {
        "asset": balance.asset,
        "available": str(balance.available),
        "total": str(balance.total),
        "unrealized_pnl": str(balance.unrealized_pnl) if balance.unrealized_pnl is not None else None,
        "margin_balance": str(balance.margin_balance) if balance.margin_balance is not None else None,
        "equity": str(balance.equity) if balance.equity is not None else None,
    }


def _position_out(position) -> dict:
    return {
        "symbol": position.symbol,
        "side": position.side.value,
        "quantity": str(position.quantity),
        "entry_price": str(position.entry_price),
        "mark_price": str(position.mark_price) if position.mark_price is not None else None,
        "unrealized_pnl": str(position.unrealized_pnl) if position.unrealized_pnl is not None else None,
        "unrealized_pnl_percent": str(position.unrealized_pnl_percent) if position.unrealized_pnl_percent is not None else None,
        "leverage": str(position.leverage),
        "margin_type": position.margin_type,
        "liquidation_price": str(position.liquidation_price) if position.liquidation_price is not None else None,
        "margin": str(position.margin) if position.margin is not None else None,
        "updated_at": position.updated_at.isoformat() if position.updated_at else None,
    }


def _order_out(order) -> dict:
    return {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side.value,
        "type": order.type.value,
        "status": order.status.value,
        "price": str(order.price) if order.price is not None else None,
        "quantity": str(order.quantity),
        "filled_quantity": str(order.filled_quantity),
        "average_fill_price": str(order.average_fill_price) if order.average_fill_price is not None else None,
        "stop_price": str(order.stop_price) if order.stop_price is not None else None,
        "take_profit_price": str(order.take_profit_price) if order.take_profit_price is not None else None,
        "stop_loss_price": str(order.stop_loss_price) if order.stop_loss_price is not None else None,
        "client_order_id": order.client_order_id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


async def get_account_snapshot(symbol: str, order_limit: int) -> dict:
    """Fetch balances, positions, and orders without invoking any write API."""
    exchange = _get_exchange()
    try:
        balances, positions, orders = await asyncio.gather(
            exchange.get_balances(),
            exchange.get_positions(),
            exchange.get_orders(symbol=symbol, limit=order_limit),
        )
    except Exception as exc:
        raise AppException(
            "ACCOUNT_SYNC_FAILED",
            "Unable to synchronize read-only exchange data. Check the API key and exchange connectivity.",
            502,
        ) from exc

    return {
        "symbol": symbol,
        "synced_at": datetime.now(UTC).isoformat(),
        "balances": [_balance_out(balance) for balance in balances],
        "positions": [_position_out(position) for position in positions],
        "orders": [_order_out(order) for order in orders],
    }
