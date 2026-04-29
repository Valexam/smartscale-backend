"""user_foods I/O."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.ids import new_user_food_id
from smartscale_api.repos.models import UserFood


async def create(
    session: AsyncSession,
    *,
    device_id: str,
    name: str,
    brand: str | None,
    kcal: Decimal,
    protein_g: Decimal,
    carbs_g: Decimal,
    fat_g: Decimal,
    fiber_g: Decimal | None,
    default_serving_g: Decimal | None,
) -> UserFood:
    row = UserFood(
        id=new_user_food_id(),
        device_id=device_id,
        name=name,
        brand=brand,
        kcal_per_100g=kcal,
        protein_g_per_100g=protein_g,
        carbs_g_per_100g=carbs_g,
        fat_g_per_100g=fat_g,
        fiber_g_per_100g=fiber_g,
        default_serving_g=default_serving_g,
    )
    session.add(row)
    await session.flush()
    return row


async def get(session: AsyncSession, *, user_food_id: str, device_id: str) -> UserFood | None:
    return (
        await session.execute(
            select(UserFood).where(UserFood.id == user_food_id, UserFood.device_id == device_id)
        )
    ).scalar_one_or_none()
