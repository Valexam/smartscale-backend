"""Product I/O."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.repos.models import Product


async def get_by_barcode(session: AsyncSession, barcode: str) -> Product | None:
    return (
        await session.execute(select(Product).where(Product.barcode == barcode))
    ).scalar_one_or_none()
