"""pantry_items I/O."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from smartscale_api.ids import new_pantry_item_id
from smartscale_api.repos.models import PantryItem, Product, UserFood


@dataclass(frozen=True)
class PantryRow:
    """Row + joined source columns. Used for list + get responses."""

    item: PantryItem
    product: Product | None
    user_food: UserFood | None


async def add_by_barcode(
    session: AsyncSession,
    *,
    device_id: str,
    barcode: str,
    default_serving_g: Decimal | None,
) -> PantryItem:
    row = PantryItem(
        id=new_pantry_item_id(),
        device_id=device_id,
        product_barcode=barcode,
        user_food_id=None,
        default_serving_g=default_serving_g,
    )
    session.add(row)
    await session.flush()
    return row


async def add_by_user_food(
    session: AsyncSession,
    *,
    device_id: str,
    user_food_id: str,
    default_serving_g: Decimal | None,
) -> PantryItem:
    row = PantryItem(
        id=new_pantry_item_id(),
        device_id=device_id,
        product_barcode=None,
        user_food_id=user_food_id,
        default_serving_g=default_serving_g,
    )
    session.add(row)
    await session.flush()
    return row


async def get_with_source(
    session: AsyncSession, *, pantry_item_id: str, device_id: str
) -> PantryRow | None:
    """Return the pantry item + its source row, scoped by device. None if not found."""
    result = await session.execute(
        select(PantryItem).where(
            PantryItem.id == pantry_item_id,
            PantryItem.device_id == device_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        return None
    return PantryRow(
        item=item,
        product=await _load_product(session, item),
        user_food=await _load_user_food(session, item),
    )


async def list_live(
    session: AsyncSession,
    *,
    device_id: str,
    limit: int,
    offset: int,
) -> list[PantryRow]:
    """Live (non-archived) pantry rows + their source data, ordered by last-used desc."""
    stmt = (
        select(PantryItem)
        .where(PantryItem.device_id == device_id, PantryItem.archived_at.is_(None))
        .order_by(PantryItem.last_used_at.desc().nullslast(), PantryItem.added_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await session.execute(stmt)).scalars().all())
    if not items:
        return []

    barcodes = {i.product_barcode for i in items if i.product_barcode}
    user_food_ids = {i.user_food_id for i in items if i.user_food_id}

    products: dict[str, Product] = {}
    if barcodes:
        product_result = await session.execute(select(Product).where(Product.barcode.in_(barcodes)))
        products = {p.barcode: p for p in product_result.scalars()}

    user_foods: dict[str, UserFood] = {}
    if user_food_ids:
        uf_result = await session.execute(select(UserFood).where(UserFood.id.in_(user_food_ids)))
        user_foods = {u.id: u for u in uf_result.scalars()}

    return [
        PantryRow(
            item=i,
            product=products.get(i.product_barcode) if i.product_barcode else None,
            user_food=user_foods.get(i.user_food_id) if i.user_food_id else None,
        )
        for i in items
    ]


async def archive(
    session: AsyncSession, *, pantry_item_id: str, device_id: str
) -> PantryItem | None:
    """Soft-delete. Returns the row if it existed, None if not. Idempotent."""
    item = (
        await session.execute(
            select(PantryItem).where(
                PantryItem.id == pantry_item_id, PantryItem.device_id == device_id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        return None
    if item.archived_at is None:
        item.archived_at = datetime.now(UTC)
        await session.flush()
    return item


async def bump_last_used_at(session: AsyncSession, *, pantry_item_id: str, when: datetime) -> None:
    await session.execute(
        update(PantryItem).where(PantryItem.id == pantry_item_id).values(last_used_at=when)
    )


async def _load_product(session: AsyncSession, item: PantryItem) -> Product | None:
    if item.product_barcode is None:
        return None
    return (
        await session.execute(select(Product).where(Product.barcode == item.product_barcode))
    ).scalar_one_or_none()


async def _load_user_food(session: AsyncSession, item: PantryItem) -> UserFood | None:
    if item.user_food_id is None:
        return None
    return (
        await session.execute(select(UserFood).where(UserFood.id == item.user_food_id))
    ).scalar_one_or_none()
