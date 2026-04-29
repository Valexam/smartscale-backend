"""add product_source_payloads audit table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_source_payloads",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("barcode", sa.Text, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("content_type", sa.Text, nullable=False),
        sa.Column("body", sa.LargeBinary, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("barcode", "source", name="product_source_payloads_uq"),
    )
    op.create_index(
        "product_source_payloads_barcode_idx",
        "product_source_payloads",
        ["barcode"],
    )


def downgrade() -> None:
    op.drop_index("product_source_payloads_barcode_idx")
    op.drop_table("product_source_payloads")
