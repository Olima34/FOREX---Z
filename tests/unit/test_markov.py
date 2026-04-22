"""
Tests unitaires pour `analytics.scripts.markov` — primitives pures
(discrétisation, matrice de transition, labels).
"""

from __future__ import annotations

import numpy as np
import pytest

from analytics.scripts.markov import (
    _assign_state,
    _quantile_edges,
    _state_labels,
    _transition_matrix,
)

# -- state labels ----------------------------------------------------------


def test_state_labels_known_sizes() -> None:
    assert _state_labels(2) == ["low", "high"]
    assert _state_labels(3) == ["low", "mid", "high"]


def test_state_labels_generic() -> None:
    assert _state_labels(5) == ["q1", "q2", "q3", "q4", "q5"]


# -- quantile_edges --------------------------------------------------------


def test_quantile_edges_covers_extremes() -> None:
    values = np.arange(100, dtype=float)
    edges = _quantile_edges(values, 3)
    assert len(edges) == 4
    assert edges[0] == -np.inf
    assert edges[-1] == np.inf


def test_quantile_edges_strict_monotone_even_with_ties() -> None:
    # Valeurs très concentrées : les quantiles peuvent coïncider.
    values = np.array([0.0] * 50 + [1.0] * 50)
    edges = _quantile_edges(values, 3)
    # On force la monotonie stricte → len = 4 et tous distincts.
    assert len(edges) == 4
    assert np.all(np.diff(edges) > 0)


# -- assign_state ----------------------------------------------------------


def test_assign_state_bucketing() -> None:
    edges = np.array([-np.inf, 0.0, 1.0, np.inf])
    values = np.array([-5.0, -0.01, 0.0, 0.5, 1.0, 1.5, 100.0])
    states = _assign_state(values, edges)
    # [-inf, 0[ → 0 ; [0, 1[ → 1 ; [1, inf[ → 2
    expected = np.array([0, 0, 1, 1, 2, 2, 2])
    np.testing.assert_array_equal(states, expected)


def test_assign_state_indices_in_range() -> None:
    edges = np.array([-np.inf, 0.0, 1.0, 2.0, np.inf])
    rng = np.random.default_rng(0)
    values = rng.normal(size=500)
    states = _assign_state(values, edges)
    assert states.min() >= 0
    assert states.max() <= 3


# -- transition_matrix -----------------------------------------------------


def test_transition_matrix_shape() -> None:
    states = np.array([0, 1, 2, 0, 1, 2])
    m = _transition_matrix(states, 3)
    assert m.shape == (3, 3)


def test_transition_matrix_rows_sum_to_one_when_visited() -> None:
    states = np.array([0, 1, 0, 1, 2, 2, 0])
    m = _transition_matrix(states, 3)
    for i in range(3):
        row_sum = m[i].sum()
        # Chaque ligne visitée somme à 1 ; les autres à 0.
        assert row_sum == pytest.approx(0.0) or row_sum == pytest.approx(1.0)


def test_transition_matrix_unvisited_row_is_zero() -> None:
    states = np.array([0, 0, 1, 0, 1])
    m = _transition_matrix(states, 3)
    # L'état 2 n'apparaît jamais → ligne de zéros.
    np.testing.assert_allclose(m[2], 0.0)


def test_transition_matrix_deterministic_chain() -> None:
    # 0 → 1 → 2 → 0 → 1 → 2 (chaîne déterministe).
    states = np.array([0, 1, 2, 0, 1, 2])
    m = _transition_matrix(states, 3)
    # Chaque état visité transite exclusivement vers le suivant.
    assert m[0, 1] == pytest.approx(1.0)
    assert m[1, 2] == pytest.approx(1.0)
    assert m[2, 0] == pytest.approx(1.0)
    # Et non vers autre chose.
    assert m[0, 0] == 0.0
    assert m[0, 2] == 0.0


def test_transition_matrix_empty_input() -> None:
    m = _transition_matrix(np.array([], dtype=int), 3)
    assert m.shape == (3, 3)
    np.testing.assert_allclose(m, 0.0)


def test_transition_matrix_single_state() -> None:
    # Un seul état → pas de transition définie.
    m = _transition_matrix(np.array([1]), 3)
    np.testing.assert_allclose(m, 0.0)
