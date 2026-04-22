"""Tests des métriques de performance (fonctions pures)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from analytics.scripts.metrics import (
    cumulative_return,
    hit_rate,
    information_coefficient,
    max_drawdown,
    sharpe_ratio,
    strategy_returns,
)


def test_ic_perfect_positive_correlation():
    # scores et rendements parfaitement monotones → IC de Spearman = 1.0
    scores = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10])
    assert information_coefficient(scores, returns) == pytest.approx(1.0)


def test_ic_perfect_negative_correlation():
    scores = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    returns = pd.Series([0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01])
    assert information_coefficient(scores, returns) == pytest.approx(-1.0)


def test_ic_returns_nan_when_too_few_samples():
    scores = pd.Series([1, 2, 3])
    returns = pd.Series([0.01, 0.02, 0.03])
    assert math.isnan(information_coefficient(scores, returns))


def test_ic_returns_nan_when_series_is_constant():
    # Série de scores constante → corrélation indéfinie.
    scores = pd.Series([0.0] * 15)
    returns = pd.Series(np.random.RandomState(0).randn(15))
    assert math.isnan(information_coefficient(scores, returns))


def test_ic_drops_nan_pairs():
    # La paire (nan, 0.05) doit être ignorée sans faire crasher le calcul.
    scores = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, float("nan")])
    returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.05])
    assert information_coefficient(scores, returns) == pytest.approx(1.0)


def test_hit_rate_all_agree():
    scores = pd.Series([1, 2, -1, -2, 3])
    returns = pd.Series([0.01, 0.02, -0.01, -0.02, 0.03])
    assert hit_rate(scores, returns) == pytest.approx(1.0)


def test_hit_rate_all_disagree():
    scores = pd.Series([1, 2, -1, -2, 3])
    returns = pd.Series([-0.01, -0.02, 0.01, 0.02, -0.03])
    assert hit_rate(scores, returns) == pytest.approx(0.0)


def test_hit_rate_ignores_zero_scores_and_returns():
    # Le score=0 et le rendement=0 sont exclus du décompte.
    scores = pd.Series([1, 0, 2, -1])
    returns = pd.Series([0.01, 0.05, 0.02, -0.01])  # 3 obs utiles, toutes d'accord
    assert hit_rate(scores, returns) == pytest.approx(1.0)


def test_hit_rate_nan_when_no_useful_observations():
    scores = pd.Series([0, 0, 0])
    returns = pd.Series([0.01, 0.02, -0.01])
    assert math.isnan(hit_rate(scores, returns))


def test_sharpe_ratio_is_nan_when_returns_are_constant():
    # Rendements constants → std ≈ 0 → Sharpe indéfini (convention : nan).
    # On teste avec des zéros stricts pour éviter le bruit float.
    assert math.isnan(sharpe_ratio(pd.Series([0.0] * 10)))
    # Et avec une constante non nulle (nécessite la tolérance dans le metric).
    assert math.isnan(sharpe_ratio(pd.Series([0.01] * 10)))


def test_sharpe_ratio_positive_when_mean_positive():
    rng = np.random.RandomState(42)
    returns = pd.Series(rng.normal(loc=0.001, scale=0.01, size=500))
    assert sharpe_ratio(returns) > 0


def test_sharpe_ratio_nan_on_empty_series():
    assert math.isnan(sharpe_ratio(pd.Series([], dtype=float)))


def test_max_drawdown_monotonic_gain_is_zero():
    # Rendements tous positifs → jamais de drawdown.
    returns = pd.Series([0.01] * 10)
    assert max_drawdown(returns) == pytest.approx(0.0)


def test_max_drawdown_captures_worst_decline():
    # +10%, -20% : cum = 1.1, 0.88. Peak=1.1, drawdown=(0.88-1.1)/1.1 = -0.2
    returns = pd.Series([0.10, -0.20])
    assert max_drawdown(returns) == pytest.approx(-0.2)


def test_cumulative_return_composes_correctly():
    # +10% puis -10% → 1.1 * 0.9 - 1 = -0.01
    returns = pd.Series([0.10, -0.10])
    assert cumulative_return(returns) == pytest.approx(-0.01)


def test_strategy_returns_sign_flips_correctly():
    scores = pd.Series([2.0, -1.0, 0.0, 3.0])
    forward = pd.Series([0.01, 0.02, 0.05, -0.04])
    result = strategy_returns(scores, forward)
    # sign(scores) = [1, -1, 0, 1]  → strat = [0.01, -0.02, 0.00, -0.04]
    assert result.tolist() == pytest.approx([0.01, -0.02, 0.0, -0.04])
