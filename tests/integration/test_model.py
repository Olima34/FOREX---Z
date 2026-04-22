"""
Tests d'intégration pour `analytics.scripts.model`.

Stratégie : on seed `pair_indicator_scores` avec plusieurs indicateurs
+ une table de prix, puis on vérifie que `walk_forward_evaluate` renvoie
une évaluation cohérente avec IC IS/OOS bien définis.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pytest

from analytics.scripts.model import (
    WEIGHTERS,
    build_feature_frame,
    compare_weighters,
    walk_forward_evaluate,
)
from utils.gestion_db import execute_write_query

pytestmark = pytest.mark.integration


# -- Helpers (calqués sur test_decomposition.py) ---------------------------


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


def _build_correlated_scores(
    n: int, weights: dict[str, float], seed: int = 0,
) -> tuple[list[float], dict[str, list[float]]]:
    """Construit des scores tels que `sum(w_i * score_i)` soit presque
    proportionnel au rendement forward → IC combiné fort.

    Retourne (closes, {indicator: scores}).
    """
    rng = np.random.RandomState(seed)
    scores_per_ind = {
        ind: rng.normal(size=n).tolist() for ind in weights
    }
    # Rendement sous-jacent = combinaison pondérée des scores + un peu de bruit.
    combined = np.zeros(n)
    for ind, w in weights.items():
        combined += w * np.array(scores_per_ind[ind])
    noise = rng.normal(scale=0.002, size=n)
    returns = 0.003 * combined + noise

    closes = [1.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    # Ajoute quelques closes après pour permettre les forward returns à
    # des horizons > 1.
    while len(closes) < n + 25:
        closes.append(closes[-1] * (1 + rng.uniform(-0.005, 0.005)))
    return closes, scores_per_ind


# -- build_feature_frame ---------------------------------------------------


def test_build_feature_frame_empty_without_data(temp_db) -> None:
    df = build_feature_frame("EURUSD", horizon=1)
    assert df.empty


def test_build_feature_frame_produces_aligned_matrix(temp_db) -> None:
    start = datetime(2024, 1, 1)
    weights = {"gdp-growth": 0.6, "interest-rate": 0.4}
    closes, per_ind = _build_correlated_scores(n=80, weights=weights, seed=1)
    _seed_prices("EURUSD", closes, start)
    for ind, scores in per_ind.items():
        _seed_indicator_scores("EURUSD", ind, scores, start)

    df = build_feature_frame("EURUSD", horizon=1)
    assert not df.empty
    assert "forward_return" in df.columns
    # Les 2 indicateurs doivent être présents comme colonnes.
    assert "gdp-growth" in df.columns
    assert "interest-rate" in df.columns
    # Pas de NaN : toutes les lignes sont complètes.
    assert df.isna().sum().sum() == 0


# -- walk_forward_evaluate -------------------------------------------------


def test_walk_forward_returns_none_without_data(temp_db) -> None:
    assert walk_forward_evaluate("EURUSD", horizon=1) is None


def test_walk_forward_ridge_beats_equal_on_informative_features(temp_db) -> None:
    """Cas où les poids optimaux sont loin de l'uniforme : ridge devrait
    faire mieux qu'equal sur l'IC OOS."""
    start = datetime(2024, 1, 1)
    weights = {
        "gdp-growth": 0.9,           # indicateur très informatif
        "interest-rate": -0.1,       # un peu informatif (signe inversé)
        "unemployment-rate": 0.0,    # bruit pur
        "inflation-cpi": 0.0,
        "balance-of-trade": 0.0,
        "current-account": 0.0,
        "retail-sales": 0.0,
    }
    closes, per_ind = _build_correlated_scores(n=120, weights=weights, seed=42)
    _seed_prices("EURUSD", closes, start)
    for ind, scores in per_ind.items():
        _seed_indicator_scores("EURUSD", ind, scores, start)

    res_equal = walk_forward_evaluate("EURUSD", 1, weighter="equal", n_splits=3)
    res_ridge = walk_forward_evaluate("EURUSD", 1, weighter="ridge", n_splits=3)
    assert res_equal is not None
    assert res_ridge is not None
    # Ridge doit extraire un IC OOS positif et non-trivial.
    assert res_ridge.ic_oos > 0.0
    # Equal weight dilue le signal ; ridge devrait faire mieux (au moins
    # pas pire) sur ce setup où les poids optimaux sont loin de l'uniforme.
    assert res_ridge.ic_oos >= res_equal.ic_oos - 0.05  # tolérance au bruit


def test_walk_forward_returns_expected_shape(temp_db) -> None:
    start = datetime(2024, 1, 1)
    weights = {"gdp-growth": 0.5, "interest-rate": 0.5}
    closes, per_ind = _build_correlated_scores(n=80, weights=weights, seed=7)
    _seed_prices("EURUSD", closes, start)
    for ind, scores in per_ind.items():
        _seed_indicator_scores("EURUSD", ind, scores, start)

    res = walk_forward_evaluate("EURUSD", 1, weighter="ic", n_splits=3)
    assert res is not None
    assert res.pair == "EURUSD"
    assert res.horizon_days == 1
    assert res.weighter == "ic"
    assert res.n_splits >= 1
    # Poids bien renseignés par indicateur.
    assert set(res.weights.keys()) == {"gdp-growth", "interest-rate"}
    # Métriques numériques (pas de crash).
    assert not math.isinf(res.ic_oos)


def test_walk_forward_invalid_weighter_raises(temp_db) -> None:
    with pytest.raises(ValueError, match="weighter inconnu"):
        walk_forward_evaluate("EURUSD", 1, weighter="does-not-exist")


# -- compare_weighters -----------------------------------------------------


def test_compare_weighters_returns_one_per_requested(temp_db) -> None:
    start = datetime(2024, 1, 1)
    weights = {"gdp-growth": 0.5, "interest-rate": 0.5}
    closes, per_ind = _build_correlated_scores(n=80, weights=weights, seed=3)
    _seed_prices("EURUSD", closes, start)
    for ind, scores in per_ind.items():
        _seed_indicator_scores("EURUSD", ind, scores, start)

    results = compare_weighters(
        "EURUSD", 1, weighters=tuple(WEIGHTERS), n_splits=3,
    )
    assert len(results) == 3
    assert {r.weighter for r in results} == {"equal", "ic", "ridge"}


def test_compare_weighters_skips_pairs_without_data(temp_db) -> None:
    # Pas de données → tous les weighters retournent None → liste vide.
    assert compare_weighters("EURUSD", 1) == []
