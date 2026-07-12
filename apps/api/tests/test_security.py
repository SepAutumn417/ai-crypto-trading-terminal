"""P0-2: 直接测试 require_auth 函数的认证逻辑。

conftest 中已覆盖 require_auth 依赖使 API 测试无需 auth headers，
真实的认证逻辑通过本文件直接测试 require_auth 函数验证。
"""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import settings
from app.security import require_auth


@pytest.mark.asyncio
async def test_require_auth_no_token_configured():
    """api_token 未配置时 fail-closed，拒绝所有请求。"""
    original = settings.api_token
    settings.api_token = None
    try:
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "AUTH_NOT_CONFIGURED"
    finally:
        settings.api_token = original


@pytest.mark.asyncio
async def test_require_auth_missing_credentials():
    """api_token 已配置但未提供 credentials 时拒绝。"""
    original = settings.api_token
    settings.api_token = "secret-token"
    try:
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "AUTH_MISSING"
    finally:
        settings.api_token = original


@pytest.mark.asyncio
async def test_require_auth_invalid_token():
    """token 不匹配时拒绝。"""
    original = settings.api_token
    settings.api_token = "secret-token"
    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")
        with pytest.raises(HTTPException) as exc_info:
            await require_auth(creds)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "AUTH_INVALID"
    finally:
        settings.api_token = original


@pytest.mark.asyncio
async def test_require_auth_valid_token():
    """token 匹配时通过认证。"""
    original = settings.api_token
    settings.api_token = "secret-token"
    try:
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="secret-token")
        result = await require_auth(creds)
        assert result == "secret-token"
    finally:
        settings.api_token = original
