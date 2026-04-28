"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


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
    return postgres_container.get_connection_url().replace(
        "postgresql+psycopg2", "postgresql+asyncpg"
    )


@pytest_asyncio.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url, future=True)
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
    async with sm() as session:
        yield session
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "TRUNCATE measurements, scrape_jobs, products RESTART IDENTITY CASCADE"
        )
