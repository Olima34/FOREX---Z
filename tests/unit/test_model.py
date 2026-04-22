"""
Tests unitaires pour `analytics.scripts.model` — focus sur les pièces
qui ne touchent pas la DB : pondérateurs, splits walk-forward, fonctions
algébriques.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.scripts.model import (
    WEIGHTERS,
    equal_weights,
    expanding_window_splits,
    ic_weights,
    ridge_weights,
)

# -- expanding_window_splits -----------------------------------------------


def test_expanding_window_splits_basic() -> None:
    splits = list(expanding_window_splits(60, n_splits=5))
    # test_size = 60 // 6 = 10, donc 5 splits viables si train ≥ 20.
    # split 0 : train=[0,10[ (<20) → skip
    # split 1 : train=[0,20[, test=[20,30[ → ok
    # split 2 : train=[0,30[, test=[30,40[ → ok
    # ...
    assert len(splits) == 4
    for tr, te in splits:
        assert tr.start == 0
        assert tr.stop < te.stop
        assert te.stop - te.start == 10


def test_expanding_window_splits_skips_when_test_too_small() -> None:
    # test_size = 20 // 6 = 3 < _MIN_TEST_SIZE (5) → aucun split.
    assert list(expanding_window_splits(20, n_splits=5)) == []


def test_expanding_window_splits_zero_or_negative() -> None:
    assert list(expanding_window_splits(0, n_splits=5)) == []
    assert list(expanding_window_splits(100, n_splits=0)) == []


def test_expanding_window_splits_respects_bounds() -> None:
    n = 100
    splits = list(expanding_window_splits(n, n_splits=4))
    for tr, te in splits:
        assert 0 <= tr.start < tr.stop <= te.start < te.stop <= n


# -- Weighters : forme et invariants ---------------------------------------


@pytest.fixture
def sample_data() -> tuple[pd.DataFrame, pd.Series]:
    """Petit échantillon synthétique : 3 features, 1 target."""
    rng = np.random.default_rng(42)
    n = 100
    X = pd.DataFrame(
        {
            "ind_a": rng.normal(size=n),
            "ind_b": rng.normal(size=n),
            "ind_c": rng.normal(size=n),
        }
    )
    # Target corrélée surtout à ind_a.
    y = 0.02 * X["ind_a"] + 0.005 * X["ind_b"] + rng.normal(scale=0.01, size=n)
    return X, y


def test_equal_weights_sums_to_one(sample_data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, y = sample_data
    w = equal_weights(X, y)
    assert set(w.index) == set(X.columns)
    assert w.sum() == pytest.approx(1.0)
    assert (w == w.iloc[0]).all()


def test_ic_weights_normalized(sample_data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, y = sample_data
    w = ic_weights(X, y)
    # Somme positive, ≤ 1 à epsilon près (somme exacte = 1 si au moins un IC > 0).
    assert w.sum() == pytest.approx(1.0, abs=1e-6)
    # Pas de poids négatif : on clippe les IC négatifs à 0.
    assert (w >= 0).all()


def test_ic_weights_privileges_highest_ic(sample_data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, y = sample_data
    w = ic_weights(X, y)
    # ind_a est le plus corrélé à y → doit avoir le plus gros poids.
    assert w["ind_a"] == w.max()


def test_ic_weights_fallback_when_all_negative() -> None:
    rng = np.random.default_rng(0)
    n = 100
    X = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)})
    # Target corrélée *négativement* aux deux features.
    y = -X["a"] - X["b"] + rng.normal(scale=0.1, size=n)
    w = ic_weights(X, y)
    # Tous IC < 0 → équipondération.
    assert w["a"] == pytest.approx(0.5, abs=1e-6)
    assert w["b"] == pytest.approx(0.5, abs=1e-6)


def test_ridge_weights_sum_abs_one(sample_data: tuple[pd.DataFrame, pd.Series]) -> None:
    X, y = sample_data
    w = ridge_weights(X, y, alpha=1.0)
    # Normalisé : somme des |poids| = 1.
    assert float(np.abs(w).sum()) == pytest.approx(1.0, abs=1e-6)


def test_ridge_weights_recovers_dominant_feature() -> None:
    rng = np.random.default_rng(1)
    n = 200
    X = pd.DataFrame(
        {"dominant": rng.normal(size=n), "noise": rng.normal(size=n)}
    )
    # Target presque linéaire en dominant, noise pur.
    y = 0.5 * X["dominant"] + rng.normal(scale=0.05, size=n)
    w = ridge_weights(X, y, alpha=0.5)
    # Le poids de "dominant" doit dominer celui de "noise".
    assert abs(w["dominant"]) > abs(w["noise"]) * 2


def test_ridge_weights_degenerate_input_falls_back() -> None:
    # Colonnes constantes → std = 0, doit retomber sur equal-weight.
    X = pd.DataFrame({"a": [1.0] * 20, "b": [2.0] * 20})
    y = pd.Series(np.arange(20, dtype=float))
    w = ridge_weights(X, y)
    # Equal weight (sans normalisation à somme|w|=1, parce que c'est
    # deja somme=1 d'equal_weights).
    assert w["a"] == pytest.approx(0.5, abs=1e-6)
    assert w["b"] == pytest.approx(0.5, abs=1e-6)


def test_weighters_registry_contains_all() -> None:
    assert set(WEIGHTERS) == {"equal", "ic", "ridge"}
    # Chaque entrée est callable et renvoie une Series pour des inputs valides.
    X = pd.DataFrame({"a": [1.0, 2.0, 3.0] * 10, "b": [3.0, 2.0, 1.0] * 10})
    y = pd.Series([0.1, -0.1, 0.2] * 10)
    for name, fn in WEIGHTERS.items():
        w = fn(X, y)
        assert isinstance(w, pd.Series), f"{name} ne renvoie pas une Series"
        assert len(w) == 2, f"{name} ne renvoie pas le bon nombre de poids"
