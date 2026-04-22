"""
Test bout-en-bout du pipeline : DB vierge -> ingestion mockée -> scores finaux.

Vérifie que les étapes s'enchaînent correctement sans toucher au réseau.
On remplace la config `COUNTRIES` par un sous-ensemble dont toutes les
références correspondent à la fixture HTML, de sorte que le fetch renvoie
bien des valeurs utilisables par la suite du pipeline.
"""

from __future__ import annotations

import pytest
import responses

from economic_data.scripts.carry import update_due as update_carry
from economic_data.scripts.country_indicator import update_due as update_country
from economic_data.scripts.pair_indicator_score import update_due as update_pair_score
from economic_data.scripts.pair_total_score import update_due as update_total_score
from sentiment.scripts.cot import COT_URL
from sentiment.scripts.cot import update as update_cot
from utils.gestion_db import execute_read_query

pytestmark = [pytest.mark.integration, pytest.mark.http]


# Sous-ensemble minimaliste de COUNTRIES utilisant la Reference de la fixture.
# Cela suffit à exercer toutes les étapes du pipeline pour la paire EURUSD.
_FAKE_COUNTRIES = {
    "euro-area": {ind: "QoQ Final" for ind in (
        "gdp-growth", "interest-rate", "unemployment-rate", "inflation-cpi",
        "balance-of-trade", "current-account", "retail-sales",
    )},
    "united-states": {ind: "QoQ Final" for ind in (
        "gdp-growth", "interest-rate", "unemployment-rate", "inflation-cpi",
        "balance-of-trade", "current-account", "retail-sales",
    )},
}


@responses.activate
def test_full_pipeline_on_empty_db(fixtures_dir, temp_db, monkeypatch):
    monkeypatch.setattr("economic_data.scripts.country_indicator.time.sleep", lambda _: None)
    monkeypatch.setattr("economic_data.scripts.country_indicator.COUNTRIES", _FAKE_COUNTRIES)
    monkeypatch.setattr("sentiment.scripts.cot.should_update_cot", lambda: True)

    # Mock Trading Economics pour chaque (pays, indicateur) du sous-ensemble
    html = (fixtures_dir / "te_gdp_growth.html").read_text()
    for country, indicators in _FAKE_COUNTRIES.items():
        for indicator in indicators:
            responses.add(
                responses.GET,
                f"https://tradingeconomics.com/{country}/{indicator}",
                body=html,
                status=200,
            )

    # Mock CFTC
    responses.add(
        responses.GET, COT_URL,
        body=(fixtures_dir / "cftc_cot.txt").read_text(),
        status=200,
    )

    # --- 1) Country indicators (appelle update_z_scores en interne)
    nb_country = update_country()
    assert nb_country == 14  # 2 pays × 7 indicateurs

    # Toutes les lignes insérées ont actual=0.9 (fixture HTML)
    rows = execute_read_query("SELECT DISTINCT actual FROM country_indicators")
    assert [r["actual"] for r in rows] == [0.9]

    # --- 2) COT
    assert update_cot() > 0
    assert execute_read_query("SELECT COUNT(*) AS n FROM cot_sentiment")[0]["n"] > 0

    # --- 3) Carry : EUR actual=0.9 vs US actual=0.9 -> carry = 0.0
    nb_carry = update_carry()
    assert nb_carry >= 1
    eur_usd_carry = execute_read_query(
        "SELECT carry_value FROM carry_trade WHERE pair = ?", ("EURUSD",)
    )
    assert eur_usd_carry and eur_usd_carry[0]["carry_value"] == pytest.approx(0.0)

    # --- 4) Scores par (paire, indicateur) : EUR = US donc pair_score = 0 partout
    assert update_pair_score() > 0
    scores = execute_read_query(
        "SELECT DISTINCT pair_score FROM pair_indicator_scores WHERE pair = ?",
        ("EURUSD",),
    )
    assert [s["pair_score"] for s in scores] == [0]

    # --- 5) Score total
    assert update_total_score() > 0
    totals = execute_read_query(
        "SELECT total_score FROM pair_total_scores WHERE pair = ?", ("EURUSD",)
    )
    assert totals  # au moins une ligne écrite

    # --- Idempotence : rejouer sans nouvelle donnée ne réécrit rien
    assert update_country() == 0
    assert update_pair_score() == 0
    assert update_total_score() == 0
