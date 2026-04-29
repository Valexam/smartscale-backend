"""POST /v1/measurements and GET /v1/measurements (paginated list)."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.deps import get_session
from smartscale_api.domain.macros import Per100g, compute_macros
from smartscale_api.ids import new_measurement_id
from smartscale_api.repos import measurements as measurements_repo
from smartscale_api.repos import products as products_repo
from smartscale_api.repos import scrape_jobs as scrape_jobs_repo
from smartscale_api.repos.models import Measurement, Product
from smartscale_api.schemas.measurement import (
    ComputedOut,
    MeasurementListResponse,
    MeasurementRequest,
    MeasurementResponse,
    Per100gOut,
    ProductOut,
)

router = APIRouter(tags=["measurements"])

# Annotated alias avoids a bare Depends() call in the function signature (ruff B008).
DbSession = Annotated[AsyncSession, Depends(get_session)]


def _measurement_to_response(row: Measurement, product: Product | None) -> MeasurementResponse:
    product_out: ProductOut | None = None
    computed_out: ComputedOut | None = None
    if product is not None:
        product_out = ProductOut(
            barcode=product.barcode,
            name=product.name,
            brand=product.brand,
            per_100g=Per100gOut(
                kcal=product.kcal_per_100g,
                protein_g=product.protein_g_per_100g,
                carbs_g=product.carbs_g_per_100g,
                fat_g=product.fat_g_per_100g,
                fiber_g=product.fiber_g_per_100g,
            ),
        )
    if (
        row.computed_kcal is not None
        and row.computed_protein_g is not None
        and row.computed_carbs_g is not None
        and row.computed_fat_g is not None
    ):
        computed_out = ComputedOut(
            kcal=row.computed_kcal,
            protein_g=row.computed_protein_g,
            carbs_g=row.computed_carbs_g,
            fat_g=row.computed_fat_g,
        )
    return MeasurementResponse(
        id=row.id,
        observed_barcode=row.observed_barcode,
        product_barcode=row.product_barcode,
        weight_grams=row.weight_grams,
        measured_at=row.measured_at,
        device_id=row.device_id,
        note=row.note,
        product=product_out,
        computed=computed_out,
        server_received_at=row.server_received_at,
    )


@router.get(
    "/measurements",
    response_model=MeasurementListResponse,
    responses={200: {"description": "Paginated list of measurements (most recent first)."}},
)
async def list_measurements(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    device_id: str | None = None,
) -> MeasurementListResponse:
    rows = await measurements_repo.list_paginated(
        session, limit=limit, offset=offset, device_id=device_id
    )
    barcodes = {r.product_barcode for r in rows if r.product_barcode is not None}
    product_map: dict[str, Product] = {}
    if barcodes:
        result = await session.execute(select(Product).where(Product.barcode.in_(barcodes)))
        product_map = {p.barcode: p for p in result.scalars()}
    items = [
        _measurement_to_response(
            r, product_map.get(r.product_barcode) if r.product_barcode else None
        )
        for r in rows
    ]
    return MeasurementListResponse(items=items, limit=limit, offset=offset)


@router.post(
    "/measurements",
    response_model=MeasurementResponse,
    responses={
        201: {"description": "Created with computed macros (product known)."},
        202: {"description": "Created without macros (product unknown)."},
    },
)
async def create_measurement(
    body: MeasurementRequest,
    response: Response,
    session: DbSession,
) -> MeasurementResponse:
    product = await products_repo.get_by_barcode(session, body.observed_barcode)

    if product is None:
        await scrape_jobs_repo.upsert_queued(session, body.observed_barcode)
        row = await measurements_repo.insert(
            session,
            measurement_id=new_measurement_id(),
            device_id=body.device_id,
            observed_barcode=body.observed_barcode,
            product_barcode=None,
            weight_grams=body.weight_grams,
            measured_at=body.measured_at.astimezone(UTC),
            computed_kcal=None,
            computed_protein_g=None,
            computed_carbs_g=None,
            computed_fat_g=None,
            note=body.note,
        )
        await session.commit()
        response.status_code = status.HTTP_202_ACCEPTED
        return MeasurementResponse(
            id=row.id,
            observed_barcode=row.observed_barcode,
            product_barcode=None,
            weight_grams=row.weight_grams,
            measured_at=row.measured_at,
            device_id=row.device_id,
            note=row.note,
            product=None,
            computed=None,
            server_received_at=row.server_received_at,
        )

    per_100g = Per100g(
        kcal=product.kcal_per_100g,
        protein_g=product.protein_g_per_100g,
        carbs_g=product.carbs_g_per_100g,
        fat_g=product.fat_g_per_100g,
    )
    computed = compute_macros(body.weight_grams, per_100g)
    row = await measurements_repo.insert(
        session,
        measurement_id=new_measurement_id(),
        device_id=body.device_id,
        observed_barcode=body.observed_barcode,
        product_barcode=product.barcode,
        weight_grams=body.weight_grams,
        measured_at=body.measured_at.astimezone(UTC),
        computed_kcal=computed.kcal,
        computed_protein_g=computed.protein_g,
        computed_carbs_g=computed.carbs_g,
        computed_fat_g=computed.fat_g,
        note=body.note,
    )
    await session.commit()
    response.status_code = status.HTTP_201_CREATED
    return MeasurementResponse(
        id=row.id,
        observed_barcode=row.observed_barcode,
        product_barcode=row.product_barcode,
        weight_grams=row.weight_grams,
        measured_at=row.measured_at,
        device_id=row.device_id,
        note=row.note,
        product=ProductOut(
            barcode=product.barcode,
            name=product.name,
            brand=product.brand,
            per_100g=Per100gOut(
                kcal=product.kcal_per_100g,
                protein_g=product.protein_g_per_100g,
                carbs_g=product.carbs_g_per_100g,
                fat_g=product.fat_g_per_100g,
                fiber_g=product.fiber_g_per_100g,
            ),
        ),
        computed=ComputedOut(
            kcal=computed.kcal,
            protein_g=computed.protein_g,
            carbs_g=computed.carbs_g,
            fat_g=computed.fat_g,
        ),
        server_received_at=row.server_received_at,
    )
