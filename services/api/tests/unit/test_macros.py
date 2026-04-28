"""compute_macros — pure function; no DB."""

from __future__ import annotations

from decimal import Decimal

from smartscale_api.domain.macros import Per100g, compute_macros


def test_142_7g_of_oat_milk() -> None:
    per_100g = Per100g(
        kcal=Decimal("46"),
        protein_g=Decimal("1.0"),
        carbs_g=Decimal("6.7"),
        fat_g=Decimal("1.5"),
    )
    out = compute_macros(Decimal("142.7"), per_100g)
    # 142.7g of 46 kcal/100g = 65.642 kcal
    assert out.kcal == Decimal("65.642")
    assert out.protein_g == Decimal("1.427")
    assert out.carbs_g == Decimal("9.5609")
    assert out.fat_g == Decimal("2.1405")


def test_zero_weight_raises() -> None:
    import pytest

    per = Per100g(kcal=Decimal(1), protein_g=Decimal(1), carbs_g=Decimal(1), fat_g=Decimal(1))
    with pytest.raises(ValueError, match="weight_grams must be > 0"):
        compute_macros(Decimal(0), per)


def test_negative_weight_raises() -> None:
    import pytest

    per = Per100g(kcal=Decimal(1), protein_g=Decimal(1), carbs_g=Decimal(1), fat_g=Decimal(1))
    with pytest.raises(ValueError, match="weight_grams must be > 0"):
        compute_macros(Decimal("-0.001"), per)
