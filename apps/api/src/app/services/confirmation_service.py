"""P0-3: 服务端二次确认服务。

安全机制：
1. check_plan 将计划设为 READY_FOR_CONFIRMATION 时，生成：
   - plan_hash: 计划关键字段的 SHA256 哈希（用于检测执行前计划是否被篡改）
   - confirmation_token: 一次性随机 token
   - confirmation_expires_at: TTL 过期时间
2. 用户调用 /confirm 端点提交 token + 口令进行二次确认
3. execute_plan 执行前验证：
   - 计划已确认（confirmed_at 已设置）
   - 确认未过期（confirmed_at + TTL > now）
   - 计划内容未变（plan_hash 匹配）
   - 重新检查风控、配置版本、行情偏离
"""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import AppException
from app.models import TradePlan as TradePlanModel


def _compute_plan_hash(model: TradePlanModel) -> str:
    """计算计划关键字段的 SHA256 哈希。

    包含所有影响交易决策的字段，任何字段变更都会导致哈希不匹配。
    """
    fields = [
        model.symbol,
        model.direction,
        str(model.entry_price),
        str(model.stop_loss_price) if model.stop_loss_price else "None",
        str(model.take_profit_prices),
        str(model.leverage),
        str(model.risk_percent),
        model.margin_mode,
        str(model.equity),
    ]
    raw = "|".join(fields)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_confirmation(model: TradePlanModel) -> None:
    """为计划生成二次确认挑战（在 check_plan 中调用）。

    生成 plan_hash、confirmation_token 和 confirmation_expires_at。
    """
    model.plan_hash = _compute_plan_hash(model)
    model.confirmation_token = secrets.token_urlsafe(32)
    model.confirmation_expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.confirmation_ttl_seconds
    )
    model.confirmed_at = None


async def confirm_plan(
    db: AsyncSession,
    plan_id: UUID,
    token: str,
    passphrase: str | None = None,
) -> None:
    """验证二次确认请求。

    校验流程：
    1. 计划必须处于 READY_FOR_CONFIRMATION 状态
    2. confirmation_token 必须匹配
    3. 确认未过期
    4. 口令验证（如果配置了 confirmation_passphrase）
    5. 设置 confirmed_at，状态变为 CONFIRMED

    Raises:
        AppException: 状态无效、token 不匹配、已过期、口令错误
    """
    model = await db.get(TradePlanModel, plan_id)
    if model is None:
        raise AppException("NOT_FOUND", f"计划 {plan_id} 不存在", 404)

    if model.status != "READY_FOR_CONFIRMATION":
        raise AppException(
            "INVALID_STATE",
            f"计划状态 {model.status} 不允许确认，仅 READY_FOR_CONFIRMATION 可确认",
            400,
        )

    if not model.confirmation_token:
        raise AppException(
            "NO_CONFIRMATION_CHALLENGE",
            "计划没有确认挑战，请先执行 check_plan",
            400,
        )

    if not secrets.compare_digest(token, model.confirmation_token):
        raise AppException("CONFIRMATION_TOKEN_INVALID", "确认 token 无效", 401)

    # 口令验证
    if settings.confirmation_passphrase:
        if not passphrase or not secrets.compare_digest(passphrase, settings.confirmation_passphrase):
            raise AppException("PASSPHRASE_INVALID", "二次确认口令错误", 401)

    # 过期检查
    if model.confirmation_expires_at:
        now = datetime.now(UTC)
        if now > model.confirmation_expires_at:
            raise AppException(
                "CONFIRMATION_EXPIRED",
                f"确认已过期（过期时间: {model.confirmation_expires_at.isoformat()}），请重新执行 check_plan",
                410,
            )

    # 验证通过，设置确认时间
    model.confirmed_at = datetime.now(UTC)
    model.status = "CONFIRMED"
    await db.commit()
    await db.refresh(model)


def validate_confirmation(model: TradePlanModel) -> None:
    """在 execute_plan 中调用，验证确认状态。

    检查：
    1. 计划已确认（confirmed_at 已设置）
    2. 确认未过期（confirmed_at 到现在不超过 TTL）
    3. 计划内容未变（plan_hash 匹配）

    Raises:
        AppException: 未确认、已过期、内容已变更
    """
    if not model.confirmed_at:
        raise AppException(
            "NOT_CONFIRMED",
            "计划未进行二次确认，请先调用 /confirm 端点",
            400,
        )

    # 确认有效期检查（从确认时间开始计算）
    if model.confirmation_expires_at:
        now = datetime.now(UTC)
        # 确认时间 + TTL 作为最终有效期
        effective_expiry = model.confirmed_at + timedelta(
            seconds=settings.confirmation_ttl_seconds
        )
        if now > effective_expiry or now > model.confirmation_expires_at:
            raise AppException(
                "CONFIRMATION_EXPIRED",
                "确认已过期，请重新执行 check_plan 并确认",
                410,
            )

    # 计划内容哈希验证
    if model.plan_hash:
        current_hash = _compute_plan_hash(model)
        if not secrets.compare_digest(current_hash, model.plan_hash):
            raise AppException(
                "PLAN_CONTENT_CHANGED",
                "计划内容已变更，请重新执行 check_plan 并确认",
                409,
            )
