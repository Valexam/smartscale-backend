"""ORM-mapped tables. Migrations in services/db/migrations/ must mirror these."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from smartscale_api.repos.base import Base


class Product(Base):
    __tablename__ = "products"

    barcode: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    brand: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'user'"))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    kcal_per_100g: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    protein_g_per_100g: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    carbs_g_per_100g: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    fat_g_per_100g: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    fiber_g_per_100g: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("kcal_per_100g >= 0", name="products_kcal_nonneg"),
        CheckConstraint("protein_g_per_100g >= 0", name="products_protein_nonneg"),
        CheckConstraint("carbs_g_per_100g >= 0", name="products_carbs_nonneg"),
        CheckConstraint("fat_g_per_100g >= 0", name="products_fat_nonneg"),
        CheckConstraint(
            "(fiber_g_per_100g IS NULL) OR (fiber_g_per_100g >= 0)",
            name="products_fiber_nonneg",
        ),
        CheckConstraint(
            "protein_g_per_100g + carbs_g_per_100g + fat_g_per_100g <= 100",
            name="products_macros_within_100g",
        ),
        CheckConstraint("barcode ~ '^[0-9A-Za-z-]{4,32}$'", name="products_barcode_format"),
    )


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    device_id: Mapped[str] = mapped_column(Text, nullable=False)
    observed_barcode: Mapped[str] = mapped_column(Text, nullable=False)
    product_barcode: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("products.barcode", ondelete="SET NULL"),
        nullable=True,
    )
    weight_grams: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    computed_kcal: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    computed_protein_g: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    computed_carbs_g: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    computed_fat_g: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("weight_grams > 0", name="measurements_weight_positive"),
        CheckConstraint(
            "(computed_kcal IS NULL) = (computed_protein_g IS NULL) "
            "AND (computed_protein_g IS NULL) = (computed_carbs_g IS NULL) "
            "AND (computed_carbs_g IS NULL) = (computed_fat_g IS NULL)",
            name="measurements_macros_all_or_nothing",
        ),
        CheckConstraint(
            "(computed_kcal IS NULL) OR (computed_kcal >= 0)",
            name="measurements_kcal_nonneg",
        ),
        CheckConstraint(
            "observed_barcode ~ '^[0-9A-Za-z-]{4,32}$'",
            name="measurements_observed_barcode_format",
        ),
        Index(
            "measurements_unresolved_idx",
            "observed_barcode",
            postgresql_where=text("product_barcode IS NULL"),
        ),
    )


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    barcode: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'in_progress', 'completed', 'completed_by_user', 'failed')",
            name="scrape_jobs_status_enum",
        ),
    )
