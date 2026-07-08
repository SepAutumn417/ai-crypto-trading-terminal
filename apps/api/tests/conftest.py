import os
from typing import AsyncGenerator

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test",
)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import *  # noqa
from app.seed import seed_all


settings.database_url = os.environ["DATABASE_URL"]

engine = create_async_engine(os.environ["DATABASE_URL"], echo=False, future=True)
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
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        await seed_all(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    async with TestSession() as session:
        yield session
