"""POST /v1/user-foods."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.deps import get_session
from smartscale_api.repos import user_foods as user_foods_repo
from smartscale_api.schemas.user_food import UserFoodCreateRequest, UserFoodOut

router = APIRouter(tags=["user-foods"])

DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/user-foods",
    response_model=UserFoodOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Free-form food created."},
        422: {"description": "Validation error (macros, name length, ...)."},
    },
)
async def create_user_food(body: UserFoodCreateRequest, session: DbSession) -> UserFoodOut:
    row = await user_foods_repo.create(
        session,
        device_id=body.device_id,
        name=body.name,
        brand=body.brand,
        kcal=body.per_100g.kcal,
        protein_g=body.per_100g.protein_g,
        carbs_g=body.per_100g.carbs_g,
        fat_g=body.per_100g.fat_g,
        fiber_g=body.per_100g.fiber_g,
        default_serving_g=body.default_serving_g,
    )
    await session.commit()
    await session.refresh(row, ["created_at", "updated_at"])
    return UserFoodOut.model_validate(row)
