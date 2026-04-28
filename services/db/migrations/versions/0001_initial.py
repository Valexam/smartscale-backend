"""initial schema: products, measurements, scrape_jobs

Revision ID: 0001
Revises:
Create Date: 2026-04-27

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("barcode", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("brand", sa.Text, nullable=True),
        sa.Column("source", sa.Text, nullable=False, server_default=sa.text("'user'")),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("kcal_per_100g", sa.Numeric, nullable=False),
        sa.Column("protein_g_per_100g", sa.Numeric, nullable=False),
        sa.Column("carbs_g_per_100g", sa.Numeric, nullable=False),
        sa.Column("fat_g_per_100g", sa.Numeric, nullable=False),
        sa.Column("fiber_g_per_100g", sa.Numeric, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("kcal_per_100g >= 0", name="products_kcal_nonneg"),
        sa.CheckConstraint("protein_g_per_100g >= 0", name="products_protein_nonneg"),
        sa.CheckConstraint("carbs_g_per_100g >= 0", name="products_carbs_nonneg"),
        sa.CheckConstraint("fat_g_per_100g >= 0", name="products_fat_nonneg"),
        sa.CheckConstraint(
            "(fiber_g_per_100g IS NULL) OR (fiber_g_per_100g >= 0)",
            name="products_fiber_nonneg",
        ),
        sa.CheckConstraint(
            "protein_g_per_100g + carbs_g_per_100g + fat_g_per_100g <= 100",
            name="products_macros_within_100g",
        ),
        sa.CheckConstraint(
            "barcode ~ '^[0-9A-Za-z-]{4,32}$'",
            name="products_barcode_format",
        ),
    )

    op.create_table(
        "measurements",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("device_id", sa.Text, nullable=False),
        sa.Column("observed_barcode", sa.Text, nullable=False),
        sa.Column(
            "product_barcode",
            sa.Text,
            sa.ForeignKey("products.barcode", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("weight_grams", sa.Numeric, nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_kcal", sa.Numeric, nullable=True),
        sa.Column("computed_protein_g", sa.Numeric, nullable=True),
        sa.Column("computed_carbs_g", sa.Numeric, nullable=True),
        sa.Column("computed_fat_g", sa.Numeric, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column(
            "server_received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("weight_grams > 0", name="measurements_weight_positive"),
        sa.CheckConstraint(
            "(computed_kcal IS NULL) = (computed_protein_g IS NULL) "
            "AND (computed_protein_g IS NULL) = (computed_carbs_g IS NULL) "
            "AND (computed_carbs_g IS NULL) = (computed_fat_g IS NULL)",
            name="measurements_macros_all_or_nothing",
        ),
        sa.CheckConstraint(
            "(computed_kcal IS NULL) OR (computed_kcal >= 0)",
            name="measurements_kcal_nonneg",
        ),
        sa.CheckConstraint(
            "observed_barcode ~ '^[0-9A-Za-z-]{4,32}$'",
            name="measurements_observed_barcode_format",
        ),
    )
    op.execute(
        "CREATE INDEX measurements_unresolved_idx "
        "ON measurements (observed_barcode) WHERE product_barcode IS NULL"
    )

    op.create_table(
        "scrape_jobs",
        sa.Column("barcode", sa.Text, primary_key=True),
        sa.Column(
            "status", sa.Text, nullable=False, server_default=sa.text("'queued'")
        ),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "scheduled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'in_progress', 'completed', 'completed_by_user', 'failed')",
            name="scrape_jobs_status_enum",
        ),
    )


def downgrade() -> None:
    op.drop_table("scrape_jobs")
    op.execute("DROP INDEX IF EXISTS measurements_unresolved_idx")
    op.drop_table("measurements")
    op.drop_table("products")
