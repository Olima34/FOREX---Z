"""Tests HTTP mockés pour `country_indicator.fetch`."""

from __future__ import annotations

import pytest
import responses

from economic_data.scripts.country_indicator import fetch

pytestmark = pytest.mark.http


@responses.activate
def test_fetch_parses_most_recent_past_row(fixtures_dir, monkeypatch):
    # On neutralise le rate-limit de 1s pour ne pas ralentir la suite.
    monkeypatch.setattr("economic_data.scripts.country_indicator.time.sleep", lambda _: None)

    html = (fixtures_dir / "te_gdp_growth.html").read_text()
    responses.add(
        responses.GET,
        "https://tradingeconomics.com/united-states/gdp-growth",
        body=html,
        status=200,
    )

    result = fetch("united-states", "gdp-growth", "QoQ Final")

    assert result is not None
    assert result["country"] == "united-states"
    # La dernière ligne "past" de la fixture a actual=0.9% -> 0.9
    assert result["actual"] == pytest.approx(0.9)
    assert result["consensus"] == pytest.approx(0.8)
    assert result["forecast"] == pytest.approx(0.75)
    # La ligne future est bien détectée
    assert result["next_update_ts"] is not None


@responses.activate
def test_fetch_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr("economic_data.scripts.country_indicator.time.sleep", lambda _: None)
    responses.add(
        responses.GET,
        "https://tradingeconomics.com/xx/foo",
        status=500,
    )

    assert fetch("xx", "foo", "Ref") is None


@responses.activate
def test_fetch_returns_none_on_unparseable_html(monkeypatch):
    monkeypatch.setattr("economic_data.scripts.country_indicator.time.sleep", lambda _: None)
    responses.add(
        responses.GET,
        "https://tradingeconomics.com/xx/foo",
        body="<html>not a table</html>",
        status=200,
    )

    assert fetch("xx", "foo", "Ref") is None
