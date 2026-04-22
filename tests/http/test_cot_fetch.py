"""Tests HTTP mockés pour `cot.fetch` et `update`."""

from __future__ import annotations

import pytest
import responses

from config import COT_NAMES
from sentiment.scripts.cot import COT_URL, fetch, update
from utils.gestion_db import execute_read_query

pytestmark = pytest.mark.http


@responses.activate
def test_fetch_filters_to_known_markets(fixtures_dir):
    csv_text = (fixtures_dir / "cftc_cot.txt").read_text()
    responses.add(responses.GET, COT_URL, body=csv_text, status=200)

    df = fetch()
    assert df is not None
    # On doit avoir uniquement les 8 marchés listés dans COT_NAMES
    # (la 9e ligne est filtrée)
    assert len(df) == 8
    assert set(df["Market_and_Exchange_Names"]) <= set(COT_NAMES)


@responses.activate
def test_fetch_returns_none_on_http_error():
    responses.add(responses.GET, COT_URL, status=500)
    assert fetch() is None


@responses.activate
def test_update_writes_sentiment_for_each_pair(fixtures_dir, temp_db, monkeypatch):
    csv_text = (fixtures_dir / "cftc_cot.txt").read_text()
    responses.add(responses.GET, COT_URL, body=csv_text, status=200)
    # On force `should_update_cot` à True pour isoler le test du calendrier.
    monkeypatch.setattr("sentiment.scripts.cot.should_update_cot", lambda: True)

    count = update()
    assert count > 0

    # Chaque paire COT a une ligne de sentiment
    rows = execute_read_query("SELECT pair, pair_sentiment FROM cot_sentiment")
    pairs_written = {row["pair"] for row in rows}
    assert "EURUSD" in pairs_written
    assert "GBPUSD" in pairs_written
