"""FastAPI dependencies — resolves the per-app sessionmaker via app.state."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a session bound to the current app's sessionmaker."""
    sm = getattr(request.app.state, "sessionmaker", None)
    if sm is None:
        raise RuntimeError("AsyncSession requested but no DB is configured (database_url empty)")
    async with sm() as session:
        yield session
