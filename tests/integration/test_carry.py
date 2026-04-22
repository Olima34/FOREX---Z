"""Tests pour `economic_data.scripts.carry`."""

from __future__ import annotations

import pytest

from economic_data.scripts.carry import (
    calculate_pair_carry,
    get_due,
    get_latest_carry,
    update_due,
)
from utils.gestion_db import execute_write_query

pytestmark = pytest.mark.integration


def _seed_rate(country: str, actual: float | None) -> None:
    execute_write_query(
        "INSERT INTO country_indicators (country, indicator, actual) VALUES (?, ?, ?)",
        (country, "interest-rate", actual),
    )


def test_carry_returns_none_without_data(temp_db):
    assert calculate_pair_carry("EURUSD") is None


def test_carry_returns_none_when_actual_is_missing(temp_db):
    _seed_rate("euro-area", None)
    _seed_rate("united-states", 5.0)
    assert calculate_pair_carry("EURUSD") is None


def test_carry_difference_is_base_minus_quote(temp_db):
    _seed_rate("euro-area", 4.0)
    _seed_rate("united-states", 5.25)

    result = calculate_pair_carry("EURUSD")
    assert result is not None
    assert result["carry_value"] == pytest.approx(-1.25)
    assert result["base_country"] == "euro-area"
    assert result["quote_country"] == "united-states"


def test_update_due_persists_result(temp_db):
    _seed_rate("euro-area", 4.0)
    _seed_rate("united-states", 5.0)

    count = update_due()
    assert count > 0

    latest = get_latest_carry("EURUSD")
    assert latest is not None
    assert latest["carry_value"] == pytest.approx(-1.0)


def test_get_due_drops_pair_after_calculation(temp_db):
    _seed_rate("euro-area", 4.0)
    _seed_rate("united-states", 5.0)

    update_due()  # première passe : EURUSD est calculée
    # EURUSD ne doit plus apparaître comme "due" (les autres paires sont
    # encore "due" car leurs taux ne sont pas seedés).
    due_pairs = {pair for pair, _, _ in get_due()}
    assert "EURUSD" not in due_pairs
