"""PUT /v1/products/{barcode}."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.deps import get_session
from smartscale_api.repos import products as products_repo
from smartscale_api.repos import scrape_jobs as scrape_jobs_repo
from smartscale_api.schemas.product import (
    Per100gIn,
    ProductPutRequest,
    ProductPutResponse,
    ProductPutResponseProduct,
)

router = APIRouter(tags=["products"])

_BARCODE_RE = re.compile(r"^[0-9A-Za-z\-]{4,32}$")

# Annotated alias avoids a bare Depends() call in the function signature (ruff B008).
DbSession = Annotated[AsyncSession, Depends(get_session)]


@router.put(
    "/products/{barcode}",
    response_model=ProductPutResponse,
    responses={
        200: {"description": "Existing product replaced."},
        201: {"description": "New product created."},
    },
)
async def put_product(
    barcode: str,
    body: ProductPutRequest,
    response: Response,
    session: DbSession,
) -> ProductPutResponse:
    if not _BARCODE_RE.match(barcode):
        raise HTTPException(status_code=422, detail="invalid barcode in path")

    product, created = await products_repo.upsert(
        session,
        barcode=barcode,
        name=body.name,
        brand=body.brand,
        kcal=body.per_100g.kcal,
        protein_g=body.per_100g.protein_g,
        carbs_g=body.per_100g.carbs_g,
        fat_g=body.per_100g.fat_g,
        fiber_g=body.per_100g.fiber_g,
    )
    backfilled = await products_repo.backfill_measurements(
        session,
        barcode=barcode,
        kcal=body.per_100g.kcal,
        protein_g=body.per_100g.protein_g,
        carbs_g=body.per_100g.carbs_g,
        fat_g=body.per_100g.fat_g,
    )
    await scrape_jobs_repo.complete_by_user(session, barcode)
    await session.commit()

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return ProductPutResponse(
        product=ProductPutResponseProduct(
            barcode=product.barcode,
            name=product.name,
            brand=product.brand,
            per_100g=Per100gIn(
                kcal=product.kcal_per_100g,
                protein_g=product.protein_g_per_100g,
                carbs_g=product.carbs_g_per_100g,
                fat_g=product.fat_g_per_100g,
                fiber_g=product.fiber_g_per_100g,
            ),
        ),
        measurements_backfilled=backfilled,
    )
