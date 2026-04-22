"""
Tests d'intégration pour `analytics.scripts.markov`.

Seed la DB avec un score + prix, puis vérifie que l'analyse Markov
renvoie des quantités cohérentes (matrice stochastique, rendements
par état non-triviaux).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pytest

from analytics.scripts.markov import build_markov_analysis
from utils.gestion_db import execute_write_query

pytestmark = pytest.mark.integration


def _seed_prices(pair: str, closes: list[float], start: datetime) -> None:
    for i, close in enumerate(closes):
        execute_write_query(
            "INSERT INTO fx_prices (pair, date, close) VALUES (?, ?, ?)",
            (pair, (start + timedelta(days=i)).strftime("%Y-%m-%d"), close),
        )


def _seed_total_scores(pair: str, scores: list[float], start: datetime) -> None:
    for i, score in enumerate(scores):
        ts = (start + timedelta(days=i)).strftime("%Y-%m-%d %H:%M:%S")
        execute_write_query(
            "INSERT INTO pair_total_scores (pair, total_score, timestamp) "
            "VALUES (?, ?, ?)",
            (pair, score, ts),
        )


def _build_signal_series(n: int, seed: int = 0) -> tuple[list[float], list[float]]:
    """Scores quasi-linéairement corrélés aux rendements forward.

    Retourne (closes, scores). Garantit qu'un état "haut" du score donne
    un rendement forward moyen plus élevé qu'un état "bas".
    """
    rng = np.random.RandomState(seed)
    scores = rng.normal(size=n).tolist()
    returns = 0.003 * np.array(scores) + rng.normal(scale=0.002, size=n)
    closes = [1.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    # Padding pour les forward returns.
    while len(closes) < n + 25:
        closes.append(closes[-1] * (1 + rng.uniform(-0.003, 0.003)))
    return closes, scores


def test_markov_returns_none_without_data(temp_db) -> None:
    assert build_markov_analysis("EURUSD", horizon=1) is None


def test_markov_returns_none_when_too_few_samples(temp_db) -> None:
    start = datetime(2024, 1, 1)
    # Seulement 15 scores → sous le seuil _MIN_SAMPLES de 30.
    closes, scores = _build_signal_series(n=15, seed=0)
    _seed_prices("EURUSD", closes, start)
    _seed_total_scores("EURUSD", scores, start)
    assert build_markov_analysis("EURUSD", horizon=1) is None


def test_markov_transition_matrix_is_stochastic(temp_db) -> None:
    start = datetime(2024, 1, 1)
    closes, scores = _build_signal_series(n=100, seed=1)
    _seed_prices("EURUSD", closes, start)
    _seed_total_scores("EURUSD", scores, start)

    analysis = build_markov_analysis("EURUSD", horizon=1, n_states=3)
    assert analysis is not None
    assert analysis.n_states == 3
    assert len(analysis.transition_matrix) == 3
    # Chaque ligne somme à ~1 (ou 0 si état jamais visité — rare ici).
    for row in analysis.transition_matrix:
        assert len(row) == 3
        row_sum = sum(row)
        assert math.isclose(row_sum, 1.0, abs_tol=1e-6) or math.isclose(
            row_sum, 0.0, abs_tol=1e-6,
        )


def test_markov_high_state_has_higher_mean_return(temp_db) -> None:
    """Score corrélé positivement aux returns : l'état 'high' doit
    avoir un rendement moyen > 'low'."""
    start = datetime(2024, 1, 1)
    closes, scores = _build_signal_series(n=150, seed=2)
    _seed_prices("EURUSD", closes, start)
    _seed_total_scores("EURUSD", scores, start)

    analysis = build_markov_analysis("EURUSD", horizon=1, n_states=3)
    assert analysis is not None
    low_ret = analysis.state_returns[0]
    high_ret = analysis.state_returns[-1]
    assert high_ret > low_ret


def test_markov_conditional_ic_positive_on_signal(temp_db) -> None:
    start = datetime(2024, 1, 1)
    closes, scores = _build_signal_series(n=120, seed=3)
    _seed_prices("EURUSD", closes, start)
    _seed_total_scores("EURUSD", scores, start)

    analysis = build_markov_analysis("EURUSD", horizon=1, n_states=3)
    assert analysis is not None
    assert analysis.conditional_ic > 0.0


def test_markov_edges_cover_full_range(temp_db) -> None:
    start = datetime(2024, 1, 1)
    closes, scores = _build_signal_series(n=100, seed=4)
    _seed_prices("EURUSD", closes, start)
    _seed_total_scores("EURUSD", scores, start)

    analysis = build_markov_analysis("EURUSD", horizon=1, n_states=3)
    assert analysis is not None
    assert len(analysis.state_edges) == 4
    assert analysis.state_edges[0] == -math.inf
    assert analysis.state_edges[-1] == math.inf


def test_markov_n_by_state_sums_to_n_samples(temp_db) -> None:
    start = datetime(2024, 1, 1)
    closes, scores = _build_signal_series(n=100, seed=5)
    _seed_prices("EURUSD", closes, start)
    _seed_total_scores("EURUSD", scores, start)

    analysis = build_markov_analysis("EURUSD", horizon=1, n_states=3)
    assert analysis is not None
    assert sum(analysis.n_by_state) == analysis.n_samples


def test_markov_labels_match_n_states(temp_db) -> None:
    start = datetime(2024, 1, 1)
    closes, scores = _build_signal_series(n=100, seed=6)
    _seed_prices("EURUSD", closes, start)
    _seed_total_scores("EURUSD", scores, start)

    analysis = build_markov_analysis("EURUSD", horizon=1, n_states=3)
    assert analysis is not None
    assert analysis.state_labels == ["low", "mid", "high"]


def test_markov_rejects_n_states_below_two(temp_db) -> None:
    with pytest.raises(ValueError, match="n_states doit"):
        build_markov_analysis("EURUSD", horizon=1, n_states=1)
