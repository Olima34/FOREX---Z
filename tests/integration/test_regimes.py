"""
Tests de l'analyse par régime temporel et de marché.

On vérifie que :
- le découpage calendaire produit une métrique par période ;
- les périodes trop courtes sont silencieusement omises ;
- le rolling IC renvoie une série temporelle cohérente ;
- le backtest par régime de volatilité segmente correctement.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pytest

from analytics.scripts.regimes import (
    backtest_by_calendar_period,
    backtest_by_horizon_sweep,
    backtest_by_volatility_regime,
    rolling_ic,
)
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
            "INSERT INTO pair_total_scores (pair, total_score, timestamp) VALUES (?, ?, ?)",
            (pair, score, ts),
        )


def _build_series(n_scores: int, seed: int = 0, buffer: int = 25) -> tuple[list[float], list[float]]:
    rng = np.random.RandomState(seed)
    returns = rng.uniform(-0.01, 0.01, size=n_scores)
    closes = [1.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    while len(closes) < n_scores + buffer:
        closes.append(closes[-1] * (1 + rng.uniform(-0.01, 0.01)))
    return closes[: n_scores + buffer], list(returns)


def test_calendar_period_returns_empty_on_empty_db(temp_db):
    assert backtest_by_calendar_period("EURUSD") == []


def test_calendar_period_by_year_splits_sample(temp_db):
    # 120 jours qui couvrent fin 2023 + début 2024 → 2 périodes annuelles.
    pair = "EURUSD"
    n = 120
    closes, scores = _build_series(n, seed=0)
    start = datetime(2023, 11, 1)  # s'étend vers 2024
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    result = backtest_by_calendar_period(pair, horizon=1, period="year")
    assert len(result) == 2
    labels = {m.label for m in result}
    assert labels == {"2023", "2024"}
    # Chaque sous-période doit avoir suffisamment d'observations.
    for m in result:
        assert m.n_samples >= 10


def test_calendar_period_skips_short_periods(temp_db):
    # ~5 jours en 2024 seulement → la période doit être omise.
    pair = "EURUSD"
    n = 40
    closes, scores = _build_series(n, seed=0)
    # 40 jours à partir du 27 nov 2023 → 35 jours en 2023 + 5 en 2024.
    start = datetime(2023, 11, 27)
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    result = backtest_by_calendar_period(pair, horizon=1, period="year")
    labels = {m.label for m in result}
    # 2024 a moins de 10 obs → omis. 2023 doit être présent.
    assert "2023" in labels
    assert "2024" not in labels


def test_calendar_period_quarter_produces_fine_grained_labels(temp_db):
    pair = "EURUSD"
    closes, scores = _build_series(90, seed=1)
    start = datetime(2024, 1, 1)
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    result = backtest_by_calendar_period(pair, horizon=1, period="quarter")
    # On s'attend aux labels Q1 et Q2 2024 au moins.
    labels = {m.label for m in result}
    assert any(lbl.startswith("2024-Q") for lbl in labels)


def test_rolling_ic_returns_series_after_warmup(temp_db):
    pair = "EURUSD"
    n = 80
    closes, scores = _build_series(n, seed=2)
    start = datetime(2024, 1, 1)
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    df = rolling_ic(pair, horizon=1, window=30)
    # Après la fenêtre de warmup, on attend un nombre raisonnable de points.
    assert len(df) >= 40
    assert set(df.columns) == {"timestamp", "ic"}
    # Avec scores = returns, l'IC doit rester proche de 1 sur chaque fenêtre.
    assert (df["ic"] > 0.9).all()


def test_rolling_ic_empty_when_window_larger_than_sample(temp_db):
    pair = "EURUSD"
    closes, scores = _build_series(15, seed=3)
    start = datetime(2024, 1, 1)
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    df = rolling_ic(pair, horizon=1, window=100)
    assert df.empty


def test_volatility_regime_segments_observations(temp_db):
    pair = "EURUSD"
    # Construction explicite : première moitié très calme (rendements
    # tout petits), seconde moitié agitée.
    rng = np.random.RandomState(7)
    low_vol_returns = rng.normal(0, 0.001, size=80)
    high_vol_returns = rng.normal(0, 0.02, size=80)
    returns = np.concatenate([low_vol_returns, high_vol_returns])
    closes = [1.0]
    for r in returns:
        closes.append(closes[-1] * (1 + r))
    # Ajoute du buffer à droite pour les forward returns.
    while len(closes) < len(returns) + 25:
        closes.append(closes[-1] * (1 + rng.normal(0, 0.01)))

    start = datetime(2024, 1, 1)
    _seed_prices(pair, closes[: len(returns) + 25], start)
    _seed_total_scores(pair, list(returns), start)

    result = backtest_by_volatility_regime(pair, horizon=1, vol_window=10, n_regimes=3)
    # 3 régimes attendus : low / mid / high.
    labels = {m.label for m in result}
    assert labels == {"low", "mid", "high"}
    # Chaque régime a des observations.
    for m in result:
        assert m.n_samples >= 10


def test_horizon_sweep_returns_one_metric_per_horizon(temp_db):
    pair = "EURUSD"
    closes, scores = _build_series(50, seed=4, buffer=30)
    start = datetime(2024, 1, 1)
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    result = backtest_by_horizon_sweep(pair, horizons=(1, 5, 20))
    assert [m.horizon_days for m in result] == [1, 5, 20]
    # Les labels sont décorés automatiquement.
    assert [m.label for m in result] == ["1d", "5d", "20d"]


def test_rolling_ic_handles_empty_db(temp_db):
    df = rolling_ic("EURUSD", horizon=1, window=30)
    assert df.empty
    assert list(df.columns) == ["timestamp", "ic"]


def test_volatility_regime_returns_empty_when_too_few_observations(temp_db):
    pair = "EURUSD"
    closes, scores = _build_series(15, seed=5)
    start = datetime(2024, 1, 1)
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    # 15 obs et 3 régimes attendus → min requis = 30 → vide.
    result = backtest_by_volatility_regime(pair, horizon=1, n_regimes=3)
    assert result == []


def test_calendar_period_handles_months(temp_db):
    # Test côté sanity check : le format "YYYY-MM" doit apparaître.
    pair = "EURUSD"
    closes, scores = _build_series(60, seed=6)
    start = datetime(2024, 3, 1)
    _seed_prices(pair, closes, start)
    _seed_total_scores(pair, scores, start)

    result = backtest_by_calendar_period(pair, horizon=1, period="month")
    labels = {m.label for m in result}
    assert any(lbl == "2024-03" or lbl == "2024-04" for lbl in labels)
    # Pas de NaN dans les ICs.
    for m in result:
        assert not math.isnan(m.ic_spearman) or m.n_samples < 2
