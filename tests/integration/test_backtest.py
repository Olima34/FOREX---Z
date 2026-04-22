"""
Tests d'intégration pour le module `analytics.scripts.backtest`.

On seed la DB avec des scores et des prix synthétiques puis on vérifie
que :
- un signal parfaitement corrélé donne IC=1 et hit_rate=1 ;
- un signal aléatoire donne IC ≈ 0 ;
- les paires sans assez de données sont écartées silencieusement.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pytest

from analytics.scripts.backtest import (
    BacktestMetrics,
    backtest_pair,
    run_backtest,
)
from utils.gestion_db import execute_write_query

pytestmark = pytest.mark.integration


def _seed_score(pair: str, ts: datetime, score: float) -> None:
    execute_write_query(
        "INSERT INTO pair_total_scores (pair, total_score, timestamp) VALUES (?, ?, ?)",
        (pair, score, ts.strftime("%Y-%m-%d %H:%M:%S")),
    )


def _seed_price(pair: str, day: datetime, close: float) -> None:
    execute_write_query(
        "INSERT INTO fx_prices (pair, date, close) VALUES (?, ?, ?)",
        (pair, day.strftime("%Y-%m-%d"), close),
    )


def _seed_aligned_series(pair: str, closes: list[float], scores: list[float]) -> None:
    """Seed une séquence alignée prix/score.

    Chaque score à l'index `i` est émis à la même date que `close[i]`
    (minuit). `merge_asof(direction='forward', allow_exact_matches=True)`
    snappe donc exactement le score `i` au close `i`.

    On attend au moins 20 closes de plus que de scores pour garantir que
    les rendements forward à l'horizon max (20 jours) sont calculables.
    """
    assert len(closes) >= len(scores) + 20
    start = datetime(2024, 1, 1)
    for i, close in enumerate(closes):
        day = start + timedelta(days=i)
        _seed_price(pair, day, close)
    for i, score in enumerate(scores):
        ts = start + timedelta(days=i)
        _seed_score(pair, ts, score)


def test_backtest_returns_empty_on_empty_db(temp_db):
    # Pas de données → tous les résultats sont écartés silencieusement.
    assert backtest_pair("EURUSD") == {}
    assert run_backtest(pairs=["EURUSD"]) == {}


def test_backtest_skips_pair_with_too_few_scores(temp_db):
    # Seulement 3 scores → sous le seuil minimal (10) → skip.
    for i in range(3):
        _seed_score("EURUSD", datetime(2024, 1, 1) + timedelta(days=i), 1.0)
    assert backtest_pair("EURUSD") == {}


def test_backtest_perfect_signal_yields_ic_one_and_positive_hitrate(temp_db):
    pair = "EURUSD"
    n_scores = 30
    horizon = 1

    # Rendements cibles choisis par avance : les prix sont construits
    # pour que `close[t+1]/close[t] - 1` = `returns[i]`.
    rng = np.random.RandomState(0)
    returns = rng.uniform(-0.01, 0.01, size=n_scores)
    # Reconstruit la série de prix à partir des rendements (close de base = 1).
    closes: list[float] = [1.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    # Il faut encore des prix à droite pour les horizons > 1.
    while len(closes) < n_scores + 20:
        closes.append(closes[-1] * (1 + rng.uniform(-0.01, 0.01)))

    # Score parfait : exactement les rendements (donc corrélation 1 avec h=1).
    scores = list(returns)

    _seed_aligned_series(pair, closes, scores)

    result = backtest_pair(pair, horizons=(horizon,))
    assert horizon in result
    m = result[horizon]
    assert isinstance(m, BacktestMetrics)
    assert m.n_samples >= 10
    assert m.ic_spearman == pytest.approx(1.0, abs=1e-9)
    assert m.hit_rate == pytest.approx(1.0)
    # Stratégie parfaite → cumul > 0 et Sharpe positif.
    assert m.cumulative_return > 0
    assert m.sharpe > 0
    # Pas de drawdown (tous les rendements de la stratégie sont positifs).
    assert m.max_drawdown == pytest.approx(0.0)


def test_backtest_random_signal_yields_ic_near_zero(temp_db):
    pair = "EURUSD"
    n_scores = 60
    rng = np.random.RandomState(42)

    # Prix : marche aléatoire.
    closes = [1.0]
    for _ in range(n_scores + 20):
        closes.append(closes[-1] * (1 + rng.uniform(-0.01, 0.01)))
    closes = closes[: n_scores + 20]

    # Scores : indépendants des rendements → IC ≈ 0.
    scores = rng.uniform(-1, 1, size=n_scores).tolist()

    _seed_aligned_series(pair, closes, scores)

    result = backtest_pair(pair, horizons=(1,))
    assert 1 in result
    # Sur 60 obs avec données indépendantes, |IC| < 0.4 avec confort
    # (seed fixe donc le test est déterministe).
    assert abs(result[1].ic_spearman) < 0.4


def test_backtest_multiple_horizons_return_all(temp_db):
    pair = "EURUSD"
    n_scores = 40
    rng = np.random.RandomState(7)

    closes = [1.0]
    for _ in range(n_scores + 25):
        closes.append(closes[-1] * (1 + rng.uniform(-0.01, 0.01)))
    closes = closes[: n_scores + 25]
    scores = rng.uniform(-1, 1, size=n_scores).tolist()

    _seed_aligned_series(pair, closes, scores)

    result = backtest_pair(pair, horizons=(1, 5, 20))
    assert set(result.keys()) == {1, 5, 20}
    for h, m in result.items():
        assert m.horizon_days == h
        assert m.n_samples >= 10


def test_backtest_dataclass_is_serializable(temp_db):
    pair = "EURUSD"
    n = 30
    rng = np.random.RandomState(1)
    closes = [1.0]
    for _ in range(n + 20):
        closes.append(closes[-1] * (1 + rng.uniform(-0.01, 0.01)))
    closes = closes[: n + 20]
    scores = rng.uniform(-1, 1, size=n).tolist()
    _seed_aligned_series(pair, closes, scores)

    result = backtest_pair(pair, horizons=(1,))[1]
    d = result.to_dict()
    assert d["pair"] == pair
    assert d["horizon_days"] == 1
    assert "ic_spearman" in d
    # Aucune valeur n'est NaN sur une run bien alimentée (sauf corner case).
    for key in ("ic_spearman", "hit_rate", "cumulative_return", "sharpe", "max_drawdown"):
        assert not math.isnan(d[key])
