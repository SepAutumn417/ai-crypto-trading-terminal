from fastapi import APIRouter, Query
from typing import Optional

from app.response import ApiResponse
from exchange_adapter import BitgetExchange, MockExchange, KlineInterval
from app.config import settings

router = APIRouter(prefix="/api/market", tags=["market"])


def _get_exchange():
    """根据配置返回交易所实例。

    开发环境用 Mock，生产环境用 Bitget。
    目前默认用 Mock，后续可从 settings 读取。
    """
    if settings.mock_exchange:
        return MockExchange()
    return BitgetExchange()


@router.get("/ticker")
async def get_ticker(symbol: str = Query(..., description="交易对，如 BTCUSDT")) -> dict:
    exchange = _get_exchange()
    ticker = await exchange.get_ticker(symbol)
    return ApiResponse.ok({
        "symbol": ticker.symbol,
        "last_price": str(ticker.last_price),
        "mark_price": str(ticker.mark_price) if ticker.mark_price else None,
        "index_price": str(ticker.index_price) if ticker.index_price else None,
        "high_24h": str(ticker.high_24h) if ticker.high_24h else None,
        "low_24h": str(ticker.low_24h) if ticker.low_24h else None,
        "volume_24h": str(ticker.volume_24h) if ticker.volume_24h else None,
        "change_percent_24h": str(ticker.change_percent_24h) if ticker.change_percent_24h else None,
        "timestamp": ticker.timestamp.isoformat() if ticker.timestamp else None,
    }).model_dump()


@router.get("/klines")
async def get_klines(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    interval: KlineInterval = Query(default=KlineInterval.ONE_HOUR, description="K线周期"),
    limit: int = Query(default=100, ge=1, le=1000, description="返回数量"),
) -> dict:
    exchange = _get_exchange()
    klines = await exchange.get_klines(symbol, interval, limit=limit)
    data = [
        {
            "timestamp": k.timestamp.isoformat(),
            "open": str(k.open),
            "high": str(k.high),
            "low": str(k.low),
            "close": str(k.close),
            "volume": str(k.volume),
            "quote_volume": str(k.quote_volume) if k.quote_volume else None,
        }
        for k in klines
    ]
    return ApiResponse.ok(data).model_dump()


@router.get("/orderbook")
async def get_orderbook(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    limit: int = Query(default=20, ge=1, le=100, description="档位数量"),
) -> dict:
    exchange = _get_exchange()
    ob = await exchange.get_orderbook(symbol, limit=limit)
    return ApiResponse.ok({
        "symbol": ob.symbol,
        "bids": [{"price": str(b.price), "quantity": str(b.quantity)} for b in ob.bids],
        "asks": [{"price": str(a.price), "quantity": str(a.quantity)} for a in ob.asks],
        "timestamp": ob.timestamp.isoformat() if ob.timestamp else None,
    }).model_dump()
