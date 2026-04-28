"""FastAPI dependency callables.

Populated by ``create_app()`` at startup so that route modules can import
``get_session`` without creating a circular dependency on ``app.py``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Module-level reference populated by create_app() before routers are included.
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _set_sessionmaker(sm: async_sessionmaker[AsyncSession]) -> None:
    """Called once from create_app() to bind the sessionmaker."""
    global _sessionmaker
    _sessionmaker = sm


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one AsyncSession per request."""
    assert _sessionmaker is not None, "sessionmaker not initialised - call create_app() first"
    async with _sessionmaker() as session:
        yield session
