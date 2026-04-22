"""Tests du calcul des z-scores."""

from __future__ import annotations

import pytest

from maths_stats.z_score_calculation import (
    get_z_score,
    get_z_score_factor,
    update_z_scores,
)
from utils.gestion_db import execute_write_query

pytestmark = pytest.mark.integration


def _seed_indicator_history(country: str, indicator: str, values: list[tuple[float, float]]) -> None:
    """values = [(actual, consensus), ...]"""
    for actual, consensus in values:
        execute_write_query(
            "INSERT INTO country_indicators (country, indicator, actual, consensus) VALUES (?, ?, ?, ?)",
            (country, indicator, actual, consensus),
        )


def test_update_z_scores_skips_series_with_too_few_points(temp_db):
    _seed_indicator_history("france", "gdp-growth", [(1.0, 0.9), (1.1, 1.0)])
    update_z_scores()

    # Pas assez de points historiques -> aucune ligne dans z_scores.
    assert get_z_score("france", "gdp-growth") is None


def test_update_z_scores_generates_score_when_variance_is_present(temp_db):
    _seed_indicator_history(
        "france",
        "inflation-cpi",
        [
            (2.0, 1.8),  # surprise +0.2
            (2.5, 2.0),  # surprise +0.5
            (1.8, 2.0),  # surprise -0.2
            (3.0, 2.0),  # surprise +1.0 (latest)
        ],
    )
    update_z_scores()

    z = get_z_score("france", "inflation-cpi")
    assert z is not None
    assert z > 0  # la surprise positive écarte fortement de l'historique


def test_z_score_factor_is_one_when_no_score(temp_db):
    """Pas de z-score stocké => facteur neutre 1.0."""
    assert get_z_score_factor("atlantis", "gdp-growth") == 1.0


def test_z_score_factor_scales_with_indicator_coefficient(temp_db):
    execute_write_query(
        "INSERT INTO z_scores (country, indicator, z_score) VALUES (?, ?, ?)",
        ("france", "gdp-growth", 2.0),
    )
    # factor = 1 + |2| * 0.173 = 1.346
    assert get_z_score_factor("france", "gdp-growth") == pytest.approx(1.346, rel=1e-3)
