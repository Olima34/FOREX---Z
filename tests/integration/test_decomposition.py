"""
Tests de la décomposition par indicateur.

Stratégie : on seed la DB avec des scores `pair_indicator_scores` par
indicateur et on vérifie que la décomposition remonte bien un backtest
par (indicateur, horizon).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from analytics.scripts.decomposition import (
    backtest_pair_indicator,
    decompose_pair,
    decomposition_matrix,
    run_decomposition,
)
from utils.gestion_db import execute_write_query

pytestmark = pytest.mark.integration


def _seed_prices(pair: str, closes: list[float], start: datetime) -> None:
    for i, close in enumerate(closes):
        execute_write_query(
            "INSERT INTO fx_prices (pair, date, close) VALUES (?, ?, ?)",
            (pair, (start + timedelta(days=i)).strftime("%Y-%m-%d"), close),
        )


def _seed_indicator_scores(
    pair: str, indicator: str, scores: list[float], start: datetime
) -> None:
    for i, score in enumerate(scores):
        ts = (start + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
        execute_write_query(
            "INSERT INTO pair_indicator_scores (pair, indicator, pair_score, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (pair, indicator, score, ts),
        )


def _build_series(n_scores: int, seed: int = 0) -> tuple[list[float], list[float]]:
    """Retourne (closes, scores) où les scores sont exactement les rendements
    forward à 1 jour : garantit IC=1 pour horizon=1."""
    rng = np.random.RandomState(seed)
    returns = rng.uniform(-0.01, 0.01, size=n_scores)
    closes = [1.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    while len(closes) < n_scores + 25:
        closes.append(closes[-1] * (1 + rng.uniform(-0.01, 0.01)))
    return closes[: n_scores + 25], list(returns)


def test_backtest_pair_indicator_returns_empty_when_no_scores(temp_db):
    assert backtest_pair_indicator("EURUSD", "gdp-growth") == {}


def test_backtest_pair_indicator_returns_empty_when_no_prices(temp_db):
    # On seed des scores mais pas de prix.
    start = datetime(2024, 1, 1)
    _seed_indicator_scores("EURUSD", "gdp-growth", [0.01] * 15, start)
    assert backtest_pair_indicator("EURUSD", "gdp-growth") == {}


def test_backtest_pair_indicator_perfect_signal(temp_db):
    closes, scores = _build_series(n_scores=30, seed=0)
    start = datetime(2024, 1, 1)
    _seed_prices("EURUSD", closes, start)
    _seed_indicator_scores("EURUSD", "gdp-growth", scores, start)

    result = backtest_pair_indicator("EURUSD", "gdp-growth", horizons=(1,))
    assert 1 in result
    m = result[1]
    assert m.indicator == "gdp-growth"
    assert m.pair == "EURUSD"
    assert m.ic_spearman == pytest.approx(1.0, abs=1e-9)
    assert m.hit_rate == pytest.approx(1.0)


def test_decompose_pair_tests_each_indicator_independently(temp_db):
    closes, returns = _build_series(n_scores=25, seed=1)
    start = datetime(2024, 1, 1)
    _seed_prices("EURUSD", closes, start)

    # gdp-growth : signal parfait. interest-rate : signal inversé.
    _seed_indicator_scores("EURUSD", "gdp-growth", returns, start)
    _seed_indicator_scores("EURUSD", "interest-rate", [-r for r in returns], start)

    result = decompose_pair("EURUSD", horizons=(1,))
    assert "gdp-growth" in result
    assert "interest-rate" in result
    # Indicateurs non seedés ne doivent pas apparaître (pas de NaN silencieux).
    assert "unemployment-rate" not in result

    gdp_ic = result["gdp-growth"][1].ic_spearman
    rate_ic = result["interest-rate"][1].ic_spearman
    assert gdp_ic == pytest.approx(1.0, abs=1e-9)
    assert rate_ic == pytest.approx(-1.0, abs=1e-9)


def test_run_decomposition_skips_pairs_without_data(temp_db):
    closes, returns = _build_series(n_scores=20, seed=2)
    start = datetime(2024, 1, 1)
    _seed_prices("EURUSD", closes, start)
    _seed_indicator_scores("EURUSD", "gdp-growth", returns, start)

    # GBPUSD n'a rien, doit être silencieusement absent.
    result = run_decomposition(pairs=["EURUSD", "GBPUSD"], horizons=(1,))
    assert "EURUSD" in result
    assert "GBPUSD" not in result


def test_decomposition_matrix_produces_indicator_by_pair_frame(temp_db):
    closes, returns = _build_series(n_scores=20, seed=3)
    start = datetime(2024, 1, 1)
    _seed_prices("EURUSD", closes, start)
    _seed_indicator_scores("EURUSD", "gdp-growth", returns, start)
    _seed_indicator_scores("EURUSD", "interest-rate", [-r for r in returns], start)

    results = run_decomposition(pairs=["EURUSD"], horizons=(1,))
    matrix = decomposition_matrix(results, horizon=1, metric="ic_spearman")

    assert isinstance(matrix, pd.DataFrame)
    # Lignes : 7 indicateurs ; colonnes : 1 paire.
    assert matrix.shape == (7, 1)
    assert "EURUSD" in matrix.columns
    assert matrix.loc["gdp-growth", "EURUSD"] == pytest.approx(1.0, abs=1e-9)
    assert matrix.loc["interest-rate", "EURUSD"] == pytest.approx(-1.0, abs=1e-9)
    # Les indicateurs non seedés remontent en NaN.
    assert math.isnan(matrix.loc["unemployment-rate", "EURUSD"])
