"""/v1/pantry — list, add (3 shapes), archive, log."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.deps import get_session
from smartscale_api.domain.macros import Per100g, compute_macros
from smartscale_api.ids import new_measurement_id, synth_observed_barcode_for_user_food
from smartscale_api.repos import measurements as measurements_repo
from smartscale_api.repos import pantry as pantry_repo
from smartscale_api.repos import products as products_repo
from smartscale_api.repos import user_foods as user_foods_repo
from smartscale_api.repos.pantry import PantryRow
from smartscale_api.schemas.measurement import (
    ComputedOut,
    MeasurementResponse,
    Per100gOut,
    ProductOut,
)
from smartscale_api.schemas.pantry import (
    PantryAddRequest,
    PantryItemOut,
    PantryListResponse,
    PantryLogRequest,
)
from smartscale_api.schemas.product import Per100gIn

router = APIRouter(tags=["pantry"])

DbSession = Annotated[AsyncSession, Depends(get_session)]


def _row_to_out(row: PantryRow) -> PantryItemOut:
    if row.product is not None:
        return PantryItemOut(
            id=row.item.id,
            source="product",
            barcode=row.product.barcode,
            user_food_id=None,
            name=row.product.name,
            brand=row.product.brand,
            per_100g=Per100gIn(
                kcal=row.product.kcal_per_100g,
                protein_g=row.product.protein_g_per_100g,
                carbs_g=row.product.carbs_g_per_100g,
                fat_g=row.product.fat_g_per_100g,
                fiber_g=row.product.fiber_g_per_100g,
            ),
            default_serving_g=row.item.default_serving_g,
            added_at=row.item.added_at,
            last_used_at=row.item.last_used_at,
        )
    uf = row.user_food
    if uf is None:
        # CHECK constraint guarantees one source non-null; loud failure if not.
        raise RuntimeError(f"pantry item {row.item.id} has no source row")
    return PantryItemOut(
        id=row.item.id,
        source="user_food",
        barcode=None,
        user_food_id=uf.id,
        name=uf.name,
        brand=uf.brand,
        per_100g=Per100gIn(
            kcal=uf.kcal_per_100g,
            protein_g=uf.protein_g_per_100g,
            carbs_g=uf.carbs_g_per_100g,
            fat_g=uf.fat_g_per_100g,
            fiber_g=uf.fiber_g_per_100g,
        ),
        default_serving_g=row.item.default_serving_g,
        added_at=row.item.added_at,
        last_used_at=row.item.last_used_at,
    )


@router.get(
    "/pantry",
    response_model=PantryListResponse,
    responses={200: {"description": "Live pantry items, most-recently-used first."}},
)
async def list_pantry(
    session: DbSession,
    device_id: Annotated[str, Query(min_length=1, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PantryListResponse:
    rows = await pantry_repo.list_live(session, device_id=device_id, limit=limit, offset=offset)
    return PantryListResponse(items=[_row_to_out(r) for r in rows], limit=limit, offset=offset)


@router.post(
    "/pantry",
    response_model=PantryItemOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Pantry item added."},
        404: {"description": "Source not found (barcode/user_food_id)."},
        422: {"description": "Validation error."},
    },
)
async def add_pantry_item(body: PantryAddRequest, session: DbSession) -> PantryItemOut:
    if body.barcode is not None:
        product = await products_repo.get_by_barcode(session, body.barcode)
        if product is None:
            raise HTTPException(status_code=404, detail="product not found; PUT /v1/products first")
        item = await pantry_repo.add_by_barcode(
            session,
            device_id=body.device_id,
            barcode=body.barcode,
            default_serving_g=body.default_serving_g,
        )
    elif body.user_food_id is not None:
        uf = await user_foods_repo.get(
            session, user_food_id=body.user_food_id, device_id=body.device_id
        )
        if uf is None:
            raise HTTPException(status_code=404, detail="user_food not found for this device")
        item = await pantry_repo.add_by_user_food(
            session,
            device_id=body.device_id,
            user_food_id=body.user_food_id,
            default_serving_g=body.default_serving_g,
        )
    else:
        # custom path — create user_food then pantry_item atomically.
        custom = body.custom
        if custom is None:  # pragma: no cover — model validator guarantees this
            raise HTTPException(status_code=422, detail="missing custom payload")
        uf = await user_foods_repo.create(
            session,
            device_id=body.device_id,
            name=custom.name,
            brand=custom.brand,
            kcal=custom.per_100g.kcal,
            protein_g=custom.per_100g.protein_g,
            carbs_g=custom.per_100g.carbs_g,
            fat_g=custom.per_100g.fat_g,
            fiber_g=custom.per_100g.fiber_g,
            default_serving_g=custom.default_serving_g,
        )
        item = await pantry_repo.add_by_user_food(
            session,
            device_id=body.device_id,
            user_food_id=uf.id,
            default_serving_g=body.default_serving_g or custom.default_serving_g,
        )

    await session.commit()

    row = await pantry_repo.get_with_source(
        session, pantry_item_id=item.id, device_id=body.device_id
    )
    if row is None:  # pragma: no cover — just-inserted row should always be findable
        raise HTTPException(status_code=500, detail="pantry item disappeared after insert")
    return _row_to_out(row)


@router.delete(
    "/pantry/{pantry_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Archived (idempotent if already archived)."},
        404: {"description": "Pantry item not found for this device."},
    },
)
async def archive_pantry_item(
    pantry_item_id: str,
    session: DbSession,
    device_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> Response:
    archived = await pantry_repo.archive(
        session, pantry_item_id=pantry_item_id, device_id=device_id
    )
    if archived is None:
        raise HTTPException(status_code=404, detail="pantry item not found")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/pantry/{pantry_item_id}/log",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Measurement logged from pantry."},
        404: {"description": "Pantry item not found."},
        410: {"description": "Pantry item is archived; cannot log."},
    },
)
async def log_from_pantry(
    pantry_item_id: str, body: PantryLogRequest, session: DbSession
) -> MeasurementResponse:
    row = await pantry_repo.get_with_source(
        session, pantry_item_id=pantry_item_id, device_id=body.device_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="pantry item not found")
    if row.item.archived_at is not None:
        raise HTTPException(
            status_code=410,
            detail={
                "msg": "pantry item is archived",
                "archived_at": row.item.archived_at.isoformat(),
            },
        )

    if row.product is not None:
        per_100g = Per100g(
            kcal=row.product.kcal_per_100g,
            protein_g=row.product.protein_g_per_100g,
            carbs_g=row.product.carbs_g_per_100g,
            fat_g=row.product.fat_g_per_100g,
        )
        observed_barcode = row.product.barcode
        product_barcode: str | None = row.product.barcode
        product_out: ProductOut | None = ProductOut(
            barcode=row.product.barcode,
            name=row.product.name,
            brand=row.product.brand,
            per_100g=Per100gOut(
                kcal=row.product.kcal_per_100g,
                protein_g=row.product.protein_g_per_100g,
                carbs_g=row.product.carbs_g_per_100g,
                fat_g=row.product.fat_g_per_100g,
                fiber_g=row.product.fiber_g_per_100g,
            ),
        )
    else:
        uf = cast("object", row.user_food)
        if row.user_food is None:  # pragma: no cover — CHECK guarantees one source
            raise RuntimeError(f"pantry item {row.item.id} has no source row")
        per_100g = Per100g(
            kcal=row.user_food.kcal_per_100g,
            protein_g=row.user_food.protein_g_per_100g,
            carbs_g=row.user_food.carbs_g_per_100g,
            fat_g=row.user_food.fat_g_per_100g,
        )
        observed_barcode = synth_observed_barcode_for_user_food(row.user_food.id)
        product_barcode = None
        product_out = None
        _ = uf  # quieten unused-binding lint; user_food info isn't surfaced in response

    computed = compute_macros(body.weight_grams, per_100g)
    measurement = await measurements_repo.insert(
        session,
        measurement_id=new_measurement_id(),
        device_id=body.device_id,
        observed_barcode=observed_barcode,
        product_barcode=product_barcode,
        weight_grams=body.weight_grams,
        measured_at=body.measured_at.astimezone(UTC),
        computed_kcal=computed.kcal,
        computed_protein_g=computed.protein_g,
        computed_carbs_g=computed.carbs_g,
        computed_fat_g=computed.fat_g,
        note=body.note,
    )

    await pantry_repo.bump_last_used_at(
        session, pantry_item_id=pantry_item_id, when=datetime.now(UTC)
    )
    await session.commit()

    return MeasurementResponse(
        id=measurement.id,
        observed_barcode=measurement.observed_barcode,
        product_barcode=measurement.product_barcode,
        weight_grams=measurement.weight_grams,
        measured_at=measurement.measured_at,
        device_id=measurement.device_id,
        note=measurement.note,
        product=product_out,
        computed=ComputedOut(
            kcal=computed.kcal,
            protein_g=computed.protein_g,
            carbs_g=computed.carbs_g,
            fat_g=computed.fat_g,
        ),
        server_received_at=measurement.server_received_at,
    )
