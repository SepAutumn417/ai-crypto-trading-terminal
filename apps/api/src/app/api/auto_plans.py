"""候选计划 API 端点。

v0.4: 自动候选计划生成——扫描、查询、提升为正式交易计划。

端点：
    POST /api/auto-plans/scan        扫描标的生成候选计划
    GET  /api/auto-plans             查询候选计划列表
    GET  /api/auto-plans/{id}        查询单个候选计划
    POST /api/auto-plans/{id}/promote 提升为正式交易计划
"""
import logging
from uuid import UUID, uuid4
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.candidate_plan import CandidatePlanModel
from app.models import TradePlan as TradePlanModel
from app.response import ApiResponse
from app.config import settings
from exchange_adapter import BitgetExchange, MockExchange, KlineInterval
from market_structure import analyze_structure
from auto_plan_engine import generate_candidates, is_promotable
from auto_plan_engine.types import CandidateStatus
from shared.enums import Direction, MarginMode, OpportunityGrade, PlanStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auto-plans", tags=["auto-plans"])


class PromoteRequest(BaseModel):
    """候选计划提升为正式交易计划的请求体。"""

    leverage: Decimal = Field(..., description="杠杆倍数", ge=Decimal("1"), le=Decimal("125"))
    risk_percent: Decimal = Field(..., description="风险百分比", ge=Decimal("0.1"), le=Decimal("10"))
    equity: Decimal = Field(..., description="账户权益（USDT）", ge=Decimal("1"))
    margin_mode: MarginMode = Field(default=MarginMode.ISOLATED, description="保证金模式")
    notes: Optional[str] = Field(default=None, description="备注")


def _get_exchange():
    """根据配置返回交易所实例。"""
    if settings.mock_exchange:
        return MockExchange()
    return BitgetExchange()


async def _broadcast(msg_type: str, payload: dict | None = None) -> None:
    """推送 auto-plans 频道。"""
    try:
        from app.websocket import ws_manager
        await ws_manager.broadcast("auto-plans", msg_type, payload or {})
    except Exception:
        logger.debug("broadcast auto-plans failed", exc_info=True)


def _candidate_direction_to_direction(candidate_dir: str) -> Direction:
    """P0-2: 候选计划方向（小写 long/short）转 TradePlan 方向（大写 LONG/SHORT）。"""
    mapping = {"long": Direction.LONG, "short": Direction.SHORT}
    result = mapping.get(candidate_dir.lower())
    if result is None:
        raise ValueError(f"无效的候选计划方向: {candidate_dir}")
    return result


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

    流程：获取K线 → 市场结构识别 → 候选计划生成 → 去重 → 落库 → 返回。
    """
    # P1-3: 错误处理
    exchange = _get_exchange()
    try:
        klines = await exchange.get_klines(symbol, interval, limit=limit)
    except Exception as e:
        logger.exception("scan_candidates: exchange.get_klines failed symbol=%s", symbol)
        return ApiResponse.err(
            "EXCHANGE_UNAVAILABLE",
            f"获取K线失败: {e}",
        ).model_dump()

    if not klines:
        return ApiResponse.err("NO_DATA", f"未获取到 {symbol} 的K线数据").model_dump()

    try:
        snapshot = analyze_structure(
            klines, symbol=symbol, timeframe=interval.value,
            swing_left=swing_left, swing_right=swing_right,
        )
    except Exception as e:
        logger.exception("scan_candidates: analyze_structure failed symbol=%s", symbol)
        return ApiResponse.err("STRUCTURE_ANALYSIS_FAILED", f"市场结构分析失败: {e}").model_dump()

    try:
        candidates = generate_candidates(snapshot)
    except Exception as e:
        logger.exception("scan_candidates: generate_candidates failed symbol=%s", symbol)
        return ApiResponse.err("CANDIDATE_GENERATION_FAILED", f"候选计划生成失败: {e}").model_dump()

    # P1-4: 数据库去重——查询近 1 小时内同 symbol+timeframe+setup_type 的候选，跳过已存在的
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    existing_q = select(
        CandidatePlanModel.setup_type, CandidatePlanModel.direction
    ).where(
        CandidatePlanModel.symbol == symbol,
        CandidatePlanModel.timeframe == interval.value,
        CandidatePlanModel.created_at >= cutoff,
    )
    existing_result = await db.execute(existing_q)
    existing_keys = {(r[0], r[1]) for r in existing_result.all()}

    saved = []
    for c in candidates:
        key = (c.setup_type.value, c.direction.value)
        if key in existing_keys:
            logger.info("scan_candidates: skip duplicate %s/%s for %s", c.setup_type.value, c.direction.value, symbol)
            continue

        # P0-3: scan 落库后将状态推进到 READY（使候选计划可 promote）
        initial_status = CandidateStatus.READY
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
            status=initial_status.value,
            invalidation_reason=c.invalidation_reason,
            rationale=c.rationale,
            structure_signals=c.structure_signals,
        )
        db.add(model)
        saved.append(c)

    if saved:
        await db.commit()
    await _broadcast("candidates_scanned", {"symbol": symbol, "count": len(saved)})

    return ApiResponse.ok({
        "symbol": symbol,
        "timeframe": interval.value,
        "market_state": snapshot.market_state.value,
        "trend_direction": snapshot.trend_direction.value,
        "candidates": [c.model_dump(mode="json") for c in saved],
        "total": len(saved),
        "skipped_duplicates": len(candidates) - len(saved),
    }).model_dump()


@router.get("")
async def list_candidates(
    status: Optional[str] = Query(default=None, description="按状态过滤"),
    symbol: Optional[str] = Query(default=None, description="按标的过滤"),
    grade: Optional[str] = Query(default=None, description="按评级过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=50, ge=1, le=200, description="每页条数"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """查询候选计划列表（分页）。"""
    # P1-7: 分页 + 正确的 total
    base_q = select(CandidatePlanModel)
    count_q = select(func.count(CandidatePlanModel.id))

    if status:
        base_q = base_q.where(CandidatePlanModel.status == status)
        count_q = count_q.where(CandidatePlanModel.status == status)
    if symbol:
        base_q = base_q.where(CandidatePlanModel.symbol == symbol)
        count_q = count_q.where(CandidatePlanModel.symbol == symbol)
    if grade:
        base_q = base_q.where(CandidatePlanModel.opportunity_grade == grade)
        count_q = count_q.where(CandidatePlanModel.opportunity_grade == grade)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    base_q = base_q.order_by(CandidatePlanModel.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(base_q)
    items = result.scalars().all()

    return ApiResponse.ok({
        "items": [_candidate_to_dict(m) for m in items],
        "total": total,
        "page": page,
        "page_size": page_size,
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

    P0-2: direction 转换为 TradePlan 的大写枚举值。
    P0-3: 允许 READY 及后续状态 promote。
    P1-2: 幂等性检查——同一候选计划不可重复提升。
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

    # P1-2: 幂等性——检查是否已有关联的 TradePlan
    existing_q = select(TradePlanModel.id).where(TradePlanModel.candidate_plan_id == model.id).limit(1)
    existing = await db.execute(existing_q)
    if existing.first() is not None:
        return ApiResponse.err(
            "ALREADY_PROMOTED",
            f"候选计划 {candidate_id} 已提升为交易计划，不可重复提升",
        ).model_dump()

    # P0-2: direction 转换（小写 → 大写）
    direction = _candidate_direction_to_direction(model.direction)

    # 创建正式交易计划
    plan = TradePlanModel(
        id=uuid4(),
        candidate_plan_id=model.id,
        exchange=model.exchange,
        symbol=model.symbol,
        direction=direction.value,  # 大写 LONG/SHORT
        setup_type=model.setup_type,
        entry_price=model.entry_price,
        stop_loss_price=model.stop_loss_price,
        take_profit_prices=model.take_profit_prices,
        leverage=body.leverage,
        margin_mode=body.margin_mode.value,
        risk_percent=body.risk_percent,
        opportunity_grade=model.opportunity_grade,
        equity=body.equity,
        status=PlanStatus.DRAFT.value,
        notes=body.notes or f"从候选计划 {model.setup_type} 提升",
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    await _broadcast("candidate_promoted", {"candidate_id": str(model.id), "trade_plan_id": str(plan.id)})

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
        "entry_price": str(m.entry_price) if m.entry_price is not None else None,
        "stop_loss_price": str(m.stop_loss_price),
        "take_profit_prices": m.take_profit_prices,
        "risk_reward_ratio": str(m.risk_reward_ratio) if m.risk_reward_ratio is not None else None,
        "opportunity_grade": m.opportunity_grade,
        "status": m.status,
        "invalidation_reason": m.invalidation_reason,
        "rationale": m.rationale,
        "structure_signals": m.structure_signals,
        "strategy_config_version": m.strategy_config_version,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
