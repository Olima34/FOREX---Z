"""Tests de la couche d'accès DB (`utils.gestion_db`)."""

from __future__ import annotations

import pytest

from utils.gestion_db import (
    execute_read_query,
    execute_write_query,
    get_cot_sentiment,
    get_latest_indicator,
)

pytestmark = pytest.mark.integration


def _insert_indicator(country, indicator, actual, consensus=None):
    execute_write_query(
        "INSERT INTO country_indicators (country, indicator, actual, consensus) VALUES (?, ?, ?, ?)",
        (country, indicator, actual, consensus),
    )


def test_write_then_read(temp_db):
    row_id = execute_write_query(
        "INSERT INTO country_indicators (country, indicator, actual) VALUES (?, ?, ?)",
        ("france", "gdp-growth", 1.1),
    )
    assert row_id is not None

    rows = execute_read_query("SELECT country, indicator, actual FROM country_indicators")
    assert rows == [{"country": "france", "indicator": "gdp-growth", "actual": 1.1}]


def test_failing_query_returns_empty_list_without_raising(temp_db, caplog):
    # Table inexistante -> sqlite3.OperationalError -> loggée, renvoie [].
    rows = execute_read_query("SELECT * FROM nonexistent_table")
    assert rows == []


def test_failing_write_returns_none(temp_db):
    assert execute_write_query("INSERT INTO nonexistent_table VALUES (?)", (1,)) is None


def test_get_latest_indicator_returns_most_recent(temp_db):
    _insert_indicator("japan", "interest-rate", 0.1)
    _insert_indicator("japan", "interest-rate", 0.25)  # le plus récent

    latest = get_latest_indicator("japan", "interest-rate")
    assert latest is not None
    assert latest["actual"] == 0.25


def test_get_latest_indicator_returns_none_when_absent(temp_db):
    assert get_latest_indicator("atlantis", "gdp-growth") is None


def test_get_cot_sentiment_returns_most_recent(temp_db):
    execute_write_query(
        "INSERT INTO cot_sentiment (pair, pair_sentiment) VALUES (?, ?)",
        ("EURUSD", 1.0),
    )
    execute_write_query(
        "INSERT INTO cot_sentiment (pair, pair_sentiment) VALUES (?, ?)",
        ("EURUSD", 2.5),
    )
    latest = get_cot_sentiment("EURUSD")
    assert latest is not None
    assert latest["pair_sentiment"] == 2.5
