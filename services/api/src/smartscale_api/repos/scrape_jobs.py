"""Scrape-job I/O."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.repos.models import ScrapeJob


async def upsert_queued(session: AsyncSession, barcode: str) -> None:
    """Insert a scrape job at status='queued' if absent. No-op otherwise."""
    stmt = (
        insert(ScrapeJob).values(barcode=barcode).on_conflict_do_nothing(index_elements=["barcode"])
    )
    await session.execute(stmt)


async def requeue(session: AsyncSession, barcode: str) -> None:
    """Force-set the job for this barcode to status='queued' (POST /refresh).

    Resets attempts, clears last_error, clears completed_at, and refreshes
    scheduled_at so the worker picks it up next cycle.
    """
    now = datetime.now(UTC)
    stmt = (
        insert(ScrapeJob)
        .values(barcode=barcode)
        .on_conflict_do_update(
            index_elements=["barcode"],
            set_={
                "status": "queued",
                "attempts": 0,
                "last_error": None,
                "scheduled_at": now,
                "completed_at": None,
            },
        )
    )
    await session.execute(stmt)


async def complete_by_user(session: AsyncSession, barcode: str) -> None:
    """Mark any existing scrape job for this barcode as completed_by_user. No-op if absent."""
    await session.execute(
        update(ScrapeJob)
        .where(ScrapeJob.barcode == barcode)
        .values(status="completed_by_user", completed_at=datetime.now(UTC))
    )
