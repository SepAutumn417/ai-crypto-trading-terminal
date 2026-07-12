"""P0-2: REST API 认证模块。

安全策略：
- 高风险写入/执行端点必须携带 Authorization: Bearer <token> 头
- 如果 settings.api_token 未配置，高风险端点全部拒绝（fail-closed）
- 只读 GET 端点不需要认证，便于前端轮询和健康检查
- 认证失败返回 401 + 标准 error envelope
"""
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_security_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_scheme),
) -> str:
    """高风险端点认证依赖。

    - api_token 未配置 → 拒绝所有请求（fail-closed）
    - api_token 已配置 → 要求 Bearer token 匹配
    - 使用 secrets.compare_digest 防止时序攻击

    Returns:
        认证通过的 token 字符串

    Raises:
        HTTPException 401: 未配置 token 或 token 不匹配
    """
    if not settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_NOT_CONFIGURED",
                "message": "服务端未配置 API_TOKEN，高风险操作被禁止。请在 .env 中设置 API_TOKEN",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_MISSING",
                "message": "缺少 Authorization 头或 Bearer token",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(credentials.credentials, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_INVALID",
                "message": "API token 无效",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


async def require_auth_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_scheme),
) -> bool:
    """可选认证：用于需要认证但不强制拒绝的端点。

    - 如果 api_token 未配置，允许通过（返回 False）
    - 如果 api_token 已配置但未提供 token，拒绝
    - 如果 api_token 已配置且 token 匹配，允许通过
    """
    if not settings.api_token:
        return True

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_MISSING", "message": "缺少 Authorization Bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(credentials.credentials, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID", "message": "API token 无效"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True
