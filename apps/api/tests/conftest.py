import os
from typing import AsyncGenerator

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test",
)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import *  # noqa
from app.seed import seed_all
from app.security import require_auth
from app.services import execution_service


settings.database_url = os.environ["DATABASE_URL"]
# P0-2: 测试环境配置 API token，使高风险端点可通过认证
_TEST_API_TOKEN = "test-api-token-for-pytest"
settings.api_token = _TEST_API_TOKEN


async def _override_require_auth() -> str:
    """测试环境覆盖 require_auth，所有请求自动通过认证。
    真实的认证逻辑通过 test_security.py 直接测试 require_auth 函数验证。
    """
    return _TEST_API_TOKEN


app.dependency_overrides[require_auth] = _override_require_auth

# P1-3: 使用 NullPool 避免连接复用导致的 "another operation is in progress" 错误
engine = create_async_engine(
    os.environ["DATABASE_URL"], echo=False, future=True, poolclass=NullPool
)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def _reset_exchange_singleton():
    execution_service.reset_exchange_for_tests()
    yield
    execution_service.reset_exchange_for_tests()

@pytest_asyncio.fixture
async def db_setup():
    """创建表 + seed 数据，测试后清理。被 client 和 db_session 共享。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        await seed_all(session)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_setup):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_setup):
    async with TestSession() as session:
        yield session
