"""候选计划 API 端点。

v0.4: 自动候选计划生成——扫描、查询、提升为正式交易计划。

端点：
    POST /api/auto-plans/scan        扫描标的生成候选计划
    GET  /api/auto-plans             查询候选计划列表
    GET  /api/auto-plans/{id}        查询单个候选计划
    POST /api/auto-plans/{id}/promote 提升为正式交易计划
"""
from uuid import UUID, uuid4
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.candidate_plan import CandidatePlanModel
from app.models.trade_plan import TradePlanModel
from app.response import ApiResponse
from app.config import settings
from exchange_adapter import BitgetExchange, MockExchange, KlineInterval
from market_structure import analyze_structure
from auto_plan_engine import generate_candidates, is_promotable
from auto_plan_engine.types import CandidateStatus
from shared.enums import PlanStatus

router = APIRouter(prefix="/api/auto-plans", tags=["auto-plans"])


class PromoteRequest(BaseModel):
    """候选计划提升为正式交易计划的请求体。"""

    leverage: str = Field(..., description="杠杆倍数")
    risk_percent: str = Field(..., description="风险百分比")
    equity: str = Field(..., description="账户权益（USDT）")
    margin_mode: str = Field(default="isolated", description="保证金模式")
    notes: Optional[str] = Field(default=None, description="备注")


def _get_exchange():
    """根据配置返回交易所实例。"""
    if settings.mock_exchange:
        return MockExchange()
    return BitgetExchange()


async def _broadcast(msg_type: str, plan_id: str | None = None) -> None:
    """推送 auto-plans 频道。"""
    import logging
    log = logging.getLogger(__name__)
    try:
        from app.websocket import ws_manager
        await ws_manager.broadcast("auto-plans", msg_type, {"plan_id": plan_id} if plan_id else {})
    except Exception:
        log.debug("broadcast auto-plans failed", exc_info=True)


@router.post("/scan")
async def scan_candidates(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    interval: KlineInterval = Query(default=KlineInterval.ONE_HOUR, description="K线周期"),
    limit: int = Query(default=200, ge=50, le=1000, description="K线数量"),
    swing_left: int = Query(default=2, ge=1, le=10),
    swing_right: int = Query(default=2, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """扫描标的，生成候选交易计划。

    流程：获取K线 → 市场结构识别 → 候选计划生成 → 落库 → 返回。
    """
    exchange = _get_exchange()
    klines = await exchange.get_klines(symbol, interval, limit=limit)
    snapshot = analyze_structure(
        klines, symbol=symbol, timeframe=interval.value,
        swing_left=swing_left, swing_right=swing_right,
    )
    candidates = generate_candidates(snapshot)

    # 落库
    saved = []
    for c in candidates:
        model = CandidatePlanModel(
            id=c.id,
            structure_snapshot_id=c.structure_snapshot_id,
            exchange=c.exchange,
            symbol=c.symbol,
            timeframe=c.timeframe,
            direction=c.direction.value,
            setup_type=c.setup_type.value,
            entry_zone={"upper": str(c.entry_zone_upper), "lower": str(c.entry_zone_lower)},
            entry_price=c.entry_price,
            stop_loss_price=c.stop_loss_price,
            take_profit_prices=[str(tp) for tp in c.take_profit_prices],
            risk_reward_ratio=c.risk_reward_ratio,
            opportunity_grade=c.opportunity_grade,
            status=c.status.value,
            invalidation_reason=c.invalidation_reason,
            rationale=c.rationale,
            structure_signals=c.structure_signals,
        )
        db.add(model)
        saved.append(c)

    if saved:
        await db.commit()
    await _broadcast("candidates_scanned", None)

    return ApiResponse.ok({
        "symbol": symbol,
        "timeframe": interval.value,
        "market_state": snapshot.market_state.value,
        "trend_direction": snapshot.trend_direction.value,
        "candidates": [c.model_dump(mode="json") for c in saved],
        "total": len(saved),
    }).model_dump()


@router.get("")
async def list_candidates(
    status: Optional[str] = Query(default=None, description="按状态过滤"),
    symbol: Optional[str] = Query(default=None, description="按标的过滤"),
    grade: Optional[str] = Query(default=None, description="按评级过滤"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """查询候选计划列表。"""
    q = select(CandidatePlanModel)
    if status:
        q = q.where(CandidatePlanModel.status == status)
    if symbol:
        q = q.where(CandidatePlanModel.symbol == symbol)
    if grade:
        q = q.where(CandidatePlanModel.opportunity_grade == grade)
    q = q.order_by(CandidatePlanModel.created_at.desc()).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()

    return ApiResponse.ok({
        "items": [_candidate_to_dict(m) for m in items],
        "total": len(items),
    }).model_dump()


@router.get("/{candidate_id}")
async def get_candidate(candidate_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """查询单个候选计划。"""
    model = await db.get(CandidatePlanModel, candidate_id)
    if model is None:
        return ApiResponse.err("NOT_FOUND", f"候选计划 {candidate_id} 不存在").model_dump()
    return ApiResponse.ok(_candidate_to_dict(model)).model_dump()


@router.post("/{candidate_id}/promote")
async def promote_candidate(
    candidate_id: UUID,
    body: PromoteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """将候选计划提升为正式交易计划。

    仅状态为 READY / RISK_CHECKED / AI_EVALUATED / ALLOW_CONFIRM 的候选计划可提升。
    promote 后候选计划状态不变，创建新的 TradePlan（candidate_plan_id 关联）。
    """
    model = await db.get(CandidatePlanModel, candidate_id)
    if model is None:
        return ApiResponse.err("NOT_FOUND", f"候选计划 {candidate_id} 不存在").model_dump()

    current_status = CandidateStatus(model.status)
    if not is_promotable(current_status):
        return ApiResponse.err(
            "NOT_PROMOTABLE",
            f"候选计划状态 {model.status} 不可提升，仅 READY/RISK_CHECKED/AI_EVALUATED/ALLOW_CONFIRM 可提升",
        ).model_dump()

    if not model.entry_price:
        return ApiResponse.err("INVALID_CANDIDATE", "候选计划缺少入场价，无法提升").model_dump()

    # 创建正式交易计划
    plan = TradePlanModel(
        id=uuid4(),
        candidate_plan_id=model.id,
        exchange=model.exchange,
        symbol=model.symbol,
        direction=model.direction,
        setup_type=model.setup_type,
        entry_price=model.entry_price,
        stop_loss_price=model.stop_loss_price,
        take_profit_prices=model.take_profit_prices,
        leverage=body.leverage,
        margin_mode=body.margin_mode,
        risk_percent=body.risk_percent,
        opportunity_grade=model.opportunity_grade,
        equity=body.equity,
        status=PlanStatus.DRAFT.value,
        notes=body.notes or f"从候选计划 {model.setup_type} 提升",
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    await _broadcast("candidate_promoted", str(plan.id))

    return ApiResponse.ok({
        "candidate_id": str(model.id),
        "trade_plan_id": str(plan.id),
        "status": plan.status,
        "message": "候选计划已提升为正式交易计划，请进行风控检查",
    }).model_dump()


def _candidate_to_dict(m: CandidatePlanModel) -> dict:
    """将 ORM 模型转为字典。"""
    return {
        "id": str(m.id),
        "structure_snapshot_id": str(m.structure_snapshot_id) if m.structure_snapshot_id else None,
        "exchange": m.exchange,
        "symbol": m.symbol,
        "timeframe": m.timeframe,
        "direction": m.direction,
        "setup_type": m.setup_type,
        "entry_zone": m.entry_zone,
        "entry_price": str(m.entry_price) if m.entry_price else None,
        "stop_loss_price": str(m.stop_loss_price),
        "take_profit_prices": m.take_profit_prices,
        "risk_reward_ratio": str(m.risk_reward_ratio) if m.risk_reward_ratio else None,
        "opportunity_grade": m.opportunity_grade,
        "status": m.status,
        "invalidation_reason": m.invalidation_reason,
        "rationale": m.rationale,
        "structure_signals": m.structure_signals,
        "strategy_config_version": m.strategy_config_version,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
