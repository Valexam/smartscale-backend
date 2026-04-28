"""Sanity checks on the ORM metadata — these run without a database."""

from __future__ import annotations

from smartscale_api.repos import models
from smartscale_api.repos.base import Base


def test_three_tables_registered() -> None:
    names = set(Base.metadata.tables)
    assert names == {"products", "measurements", "scrape_jobs"}


def test_measurements_has_observed_and_product_barcode() -> None:
    cols = {c.name for c in Base.metadata.tables["measurements"].columns}
    assert "observed_barcode" in cols
    assert "product_barcode" in cols


def test_measurements_product_barcode_is_nullable() -> None:
    col = Base.metadata.tables["measurements"].c["product_barcode"]
    assert col.nullable is True


def test_measurements_observed_barcode_is_not_nullable() -> None:
    col = Base.metadata.tables["measurements"].c["observed_barcode"]
    assert col.nullable is False


def test_measurement_id_is_text_pk() -> None:
    col = Base.metadata.tables["measurements"].c["id"]
    assert col.primary_key
    assert "TEXT" in str(col.type).upper() or "VARCHAR" in str(col.type).upper()


def test_unresolved_partial_index_exists() -> None:
    indexes = Base.metadata.tables["measurements"].indexes
    names = {idx.name for idx in indexes}
    assert "measurements_unresolved_idx" in names

    idx = next(idx for idx in indexes if idx.name == "measurements_unresolved_idx")
    assert idx.dialect_kwargs.get("postgresql_where") is not None  # partial index


# Reference `models` so import-effect is explicit.
_ = models
