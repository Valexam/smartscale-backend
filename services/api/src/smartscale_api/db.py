"""Async engine, sessionmaker, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from smartscale_api.config import Settings


def make_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.database_url, future=True, pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_dependency(sm: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Yield a session per request. Caller is responsible for commit/rollback semantics."""
    async with sm() as session:
        yield session
