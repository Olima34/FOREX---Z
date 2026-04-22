"""Tests pour `pair_indicator_score` et `pair_total_score` sur DB temporaire."""

from __future__ import annotations

import json

import pytest

from economic_data.scripts.pair_indicator_score import (
    calculate_pair_indicator_score,
)
from economic_data.scripts.pair_indicator_score import (
    update_due as update_pair_scores,
)
from economic_data.scripts.pair_total_score import (
    calculate_pair_total_score,
    get_cot_sentiment_score,
)
from economic_data.scripts.pair_total_score import (
    update_due as update_total_scores,
)
from utils.gestion_db import execute_read_query, execute_write_query

pytestmark = pytest.mark.integration


def _insert(country, indicator, actual, consensus):
    execute_write_query(
        "INSERT INTO country_indicators (country, indicator, actual, consensus) VALUES (?, ?, ?, ?)",
        (country, indicator, actual, consensus),
    )


def test_pair_score_is_base_minus_quote_without_zscore(temp_db):
    _insert("euro-area", "gdp-growth", 0.8, 0.5)  # actual > consensus -> +1
    _insert("united-states", "gdp-growth", 0.3, 0.5)  # actual < consensus -> -1

    result = calculate_pair_indicator_score("EURUSD", "gdp-growth")
    assert result is not None
    # base_score = +1, quote_score = -1 -> pair_score = 2
    assert result["base_score"] == pytest.approx(1.0)
    assert result["quote_score"] == pytest.approx(-1.0)
    assert result["pair_score"] == pytest.approx(2.0)


def test_calculate_returns_none_without_both_sides(temp_db):
    _insert("euro-area", "gdp-growth", 0.8, 0.5)
    # Pas de données US
    assert calculate_pair_indicator_score("EURUSD", "gdp-growth") is None


def test_update_due_persists_scores_for_all_indicators(temp_db):
    # On insère des données pour tous les indicateurs nécessaires à EURUSD
    from config import INDICATORS

    for indicator in INDICATORS:
        _insert("euro-area", indicator, 1.0, 0.8)
        _insert("united-states", indicator, 0.5, 0.8)

    count = update_pair_scores()
    assert count >= len(INDICATORS)  # au moins tous les indicateurs EURUSD

    rows = execute_read_query(
        "SELECT DISTINCT indicator FROM pair_indicator_scores WHERE pair = ?",
        ("EURUSD",),
    )
    assert {r["indicator"] for r in rows} >= set(INDICATORS)


def test_cot_sentiment_score_weighted_exponentially(temp_db):
    execute_write_query(
        "INSERT INTO cot_sentiment (pair, pair_sentiment) VALUES (?, ?)",
        ("EURUSD", 5.0),
    )
    # factor = 0.1 -> poids = exp(|5| * 0.1) = exp(0.5)
    # score = 5 * exp(0.5)
    import math

    expected = 5.0 * math.exp(0.5)
    assert get_cot_sentiment_score("EURUSD") == pytest.approx(expected, rel=1e-4)


def test_cot_sentiment_score_zero_when_absent(temp_db):
    assert get_cot_sentiment_score("EURUSD") == 0.0


def test_total_score_combines_economic_and_cot(temp_db):
    from config import INDICATORS

    # Crée les scores par indicateur
    for indicator in INDICATORS:
        _insert("euro-area", indicator, 1.0, 0.8)
        _insert("united-states", indicator, 0.5, 0.8)

    update_pair_scores()

    # Ajoute un sentiment COT
    execute_write_query(
        "INSERT INTO cot_sentiment (pair, pair_sentiment) VALUES (?, ?)",
        ("EURUSD", 2.0),
    )

    result = calculate_pair_total_score("EURUSD")
    assert result["total_score"] != 0  # les scores éco sont positifs
    assert "gdp-growth" in result["indicator_scores"]


def test_update_total_scores_writes_json(temp_db):
    from config import INDICATORS

    for indicator in INDICATORS:
        _insert("euro-area", indicator, 1.0, 0.8)
        _insert("united-states", indicator, 0.5, 0.8)
    update_pair_scores()
    update_total_scores()

    rows = execute_read_query("SELECT * FROM pair_total_scores WHERE pair = ?", ("EURUSD",))
    assert rows
    parsed = json.loads(rows[0]["indicator_scores_json"])
    assert set(parsed.keys()) == set(INDICATORS)
