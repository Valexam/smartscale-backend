"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Iterator
from typing import cast

import pytest
import pytest_asyncio
import sqlalchemy as sa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from smartscale_api.app import create_app
from smartscale_api.config import Settings


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Single Postgres container for the whole test session.

    Tests rely on Alembic migrations to set up the schema; per-test cleanup
    happens via TRUNCATE in the `db_session` fixture.
    """
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    url = postgres_container.get_connection_url()
    return cast(str, url).replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest_asyncio.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url, future=True, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def schema(engine: AsyncEngine, database_url: str) -> AsyncIterator[None]:
    """Apply Alembic migrations once per session."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("../db/alembic.ini")
    cfg.set_main_option("script_location", "../db/migrations")
    cfg.set_main_option(
        "sqlalchemy.url", database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    )
    await asyncio.to_thread(command.upgrade, cfg, "head")
    yield


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine, schema: None) -> AsyncIterator[AsyncSession]:
    """Per-test AsyncSession with TRUNCATE of all data tables on teardown."""
    sm = async_sessionmaker(engine, expire_on_commit=False)
    session = sm()
    try:
        yield session
    finally:
        with contextlib.suppress(Exception):
            await session.close()
    async with engine.connect() as conn:
        await conn.execute(
            sa.text("TRUNCATE measurements, scrape_jobs, products RESTART IDENTITY CASCADE")
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# HTTP-level fixtures (B10)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(database_url: str, schema: None) -> FastAPI:
    settings = Settings(
        env="test",
        device_key=SecretStr("test-key"),
        database_url=database_url,
    )
    return create_app(settings=settings)


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-device-key": "test-key"},
    ) as c:
        yield c
