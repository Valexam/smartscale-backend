"""add user_foods and pantry_items tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_foods",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("device_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("brand", sa.Text, nullable=True),
        sa.Column("kcal_per_100g", sa.Numeric, nullable=False),
        sa.Column("protein_g_per_100g", sa.Numeric, nullable=False),
        sa.Column("carbs_g_per_100g", sa.Numeric, nullable=False),
        sa.Column("fat_g_per_100g", sa.Numeric, nullable=False),
        sa.Column("fiber_g_per_100g", sa.Numeric, nullable=True),
        sa.Column("default_serving_g", sa.Numeric, nullable=True),
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
        sa.CheckConstraint("kcal_per_100g >= 0", name="user_foods_kcal_nonneg"),
        sa.CheckConstraint("protein_g_per_100g >= 0", name="user_foods_protein_nonneg"),
        sa.CheckConstraint("carbs_g_per_100g >= 0", name="user_foods_carbs_nonneg"),
        sa.CheckConstraint("fat_g_per_100g >= 0", name="user_foods_fat_nonneg"),
        sa.CheckConstraint(
            "(fiber_g_per_100g IS NULL) OR (fiber_g_per_100g >= 0)",
            name="user_foods_fiber_nonneg",
        ),
        sa.CheckConstraint(
            "protein_g_per_100g + carbs_g_per_100g + fat_g_per_100g <= 100",
            name="user_foods_macros_within_100g",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200",
            name="user_foods_name_length",
        ),
    )
    op.create_index(
        "user_foods_device_id_idx",
        "user_foods",
        ["device_id"],
    )

    op.create_table(
        "pantry_items",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("device_id", sa.Text, nullable=False),
        sa.Column(
            "product_barcode",
            sa.Text,
            sa.ForeignKey("products.barcode", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_food_id",
            sa.Text,
            sa.ForeignKey("user_foods.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("default_serving_g", sa.Numeric, nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "num_nonnulls(product_barcode, user_food_id) = 1",
            name="pantry_items_one_source",
        ),
    )
    op.create_index(
        "pantry_items_device_archived_idx",
        "pantry_items",
        ["device_id", "archived_at"],
    )
    op.create_index(
        "pantry_items_device_last_used_idx",
        "pantry_items",
        ["device_id", sa.text("last_used_at DESC NULLS LAST")],
    )


def downgrade() -> None:
    op.drop_index("pantry_items_device_last_used_idx", table_name="pantry_items")
    op.drop_index("pantry_items_device_archived_idx", table_name="pantry_items")
    op.drop_table("pantry_items")
    op.drop_index("user_foods_device_id_idx", table_name="user_foods")
    op.drop_table("user_foods")
