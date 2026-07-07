from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


_engine = None
_async_session = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False, future=True)
    return _engine


def get_session_factory():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session