"""
Tests unitaires pour `dashboard.data` — focus sur les transformations pures
(overview_frame, calendar_period_frame, volatility_regime_frame).

Les fonctions qui touchent la DB (pair_equity_curve, score_return_scatter)
sont testées à part via des tests d'intégration. Ici on vérifie que la
mise en forme DataFrame est correcte, sans dépendre de Streamlit ni de
SQLite.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from analytics.scripts.backtest import BacktestMetrics
from analytics.scripts.markov import MarkovAnalysis
from analytics.scripts.model import WalkForwardResult
from dashboard import data as data_layer


def _metrics(
    pair: str,
    horizon: int,
    ic: float,
    *,
    label: str | None = None,
    indicator: str | None = None,
    n: int = 120,
) -> BacktestMetrics:
    """Factory pour construire une BacktestMetrics synthétique."""
    return BacktestMetrics(
        pair=pair,
        horizon_days=horizon,
        n_samples=n,
        ic_spearman=ic,
        hit_rate=0.55,
        cumulative_return=0.12,
        sharpe=1.3,
        max_drawdown=-0.08,
        indicator=indicator,
        label=label,
    )


# -- overview_frame ---------------------------------------------------------


def test_overview_frame_empty_when_no_results() -> None:
    df = data_layer.overview_frame({}, horizon=5)
    assert df.empty
    # Colonnes présentes même en cas de DataFrame vide (facilite l'UI).
    for col in ["pair", "ic_spearman", "sharpe", "max_drawdown"]:
        assert col in df.columns


def test_overview_frame_keeps_only_requested_horizon() -> None:
    results = {
        "EURUSD": {
            1: _metrics("EURUSD", 1, ic=0.02),
            5: _metrics("EURUSD", 5, ic=0.08),
        },
        "USDJPY": {
            5: _metrics("USDJPY", 5, ic=0.04),
        },
    }
    df = data_layer.overview_frame(results, horizon=5)
    assert list(df["pair"]) == ["EURUSD", "USDJPY"]  # trié par IC décroissant
    assert all(col in df.columns for col in ["ic_spearman", "sharpe"])


def test_overview_frame_skips_pairs_without_metrics_at_horizon() -> None:
    results = {
        "EURUSD": {5: _metrics("EURUSD", 5, ic=0.1)},
        "GBPUSD": {1: _metrics("GBPUSD", 1, ic=0.2)},  # pas d'horizon 5
    }
    df = data_layer.overview_frame(results, horizon=5)
    assert list(df["pair"]) == ["EURUSD"]


def test_overview_frame_sorts_by_ic_descending_nan_last() -> None:
    results = {
        "A": {5: _metrics("A", 5, ic=0.01)},
        "B": {5: _metrics("B", 5, ic=math.nan)},
        "C": {5: _metrics("C", 5, ic=0.15)},
    }
    df = data_layer.overview_frame(results, horizon=5)
    # C (IC le plus haut) en tête, NaN (B) en dernier.
    assert list(df["pair"]) == ["C", "A", "B"]


# -- calendar_period_frame --------------------------------------------------


def test_calendar_period_frame_empty_when_no_metrics() -> None:
    df = data_layer.calendar_period_frame([])
    assert df.empty
    assert {"period", "ic_spearman", "sharpe"}.issubset(df.columns)


def test_calendar_period_frame_preserves_order() -> None:
    metrics = [
        _metrics("EURUSD", 5, ic=0.03, label="2023"),
        _metrics("EURUSD", 5, ic=0.07, label="2024"),
    ]
    df = data_layer.calendar_period_frame(metrics)
    # On ne trie pas : l'ordre d'origine (chronologique) doit être conservé.
    assert list(df["period"]) == ["2023", "2024"]
    assert df.loc[1, "ic_spearman"] == 0.07


# -- volatility_regime_frame ------------------------------------------------


def test_volatility_regime_frame_empty_when_no_metrics() -> None:
    df = data_layer.volatility_regime_frame([])
    assert df.empty
    assert "regime" in df.columns


def test_volatility_regime_frame_uses_label_as_regime() -> None:
    metrics = [
        _metrics("EURUSD", 5, ic=0.05, label="low"),
        _metrics("EURUSD", 5, ic=0.01, label="mid"),
        _metrics("EURUSD", 5, ic=-0.03, label="high"),
    ]
    df = data_layer.volatility_regime_frame(metrics)
    assert list(df["regime"]) == ["low", "mid", "high"]
    assert list(df["ic_spearman"]) == [0.05, 0.01, -0.03]
    # Colonnes attendues pour le styling dans l'app.
    for col in ["n_samples", "hit_rate", "cumulative_return", "sharpe"]:
        assert col in df.columns


def test_volatility_regime_frame_is_plain_dataframe() -> None:
    metrics = [_metrics("EURUSD", 5, ic=0.05, label="low")]
    df = data_layer.volatility_regime_frame(metrics)
    # On doit pouvoir concat / styler → ce n'est pas un sous-type.
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1


# -- weighter_comparison_frame + weights_frame ------------------------------


def _wf(
    weighter: str, ic_is: float, ic_oos: float, weights: dict[str, float],
) -> WalkForwardResult:
    return WalkForwardResult(
        pair="EURUSD", horizon_days=5, weighter=weighter,
        n_splits=3, n_samples=120,
        ic_is=ic_is, ic_oos=ic_oos,
        hit_rate_oos=0.55, cumulative_return_oos=0.08, sharpe_oos=1.1,
        weights=weights,
    )


def test_weighter_comparison_frame_empty() -> None:
    df = data_layer.weighter_comparison_frame([])
    assert df.empty
    for col in ["weighter", "ic_is", "ic_oos", "sharpe_oos"]:
        assert col in df.columns


def test_weighter_comparison_frame_one_row_per_weighter() -> None:
    results = [
        _wf("equal", 0.08, 0.05, {"a": 0.5, "b": 0.5}),
        _wf("ridge", 0.20, 0.07, {"a": 0.9, "b": 0.1}),
    ]
    df = data_layer.weighter_comparison_frame(results)
    assert list(df["weighter"]) == ["equal", "ridge"]
    assert df.loc[1, "ic_oos"] == pytest.approx(0.07)


def test_weights_frame_handles_empty() -> None:
    assert data_layer.weights_frame([]).empty


def test_weights_frame_pivots_by_indicator() -> None:
    results = [
        _wf("equal", 0.05, 0.05, {"a": 0.5, "b": 0.5}),
        _wf("ridge", 0.10, 0.07, {"a": 0.8, "b": 0.2}),
    ]
    df = data_layer.weights_frame(results)
    assert list(df["indicator"]) == ["a", "b"]
    assert "equal" in df.columns
    assert "ridge" in df.columns
    assert df.loc[0, "ridge"] == pytest.approx(0.8)


def test_weights_frame_tolerates_missing_indicator_in_one_weighter() -> None:
    # Un pondérateur peut ne pas retourner le même jeu d'indicateurs.
    results = [
        _wf("equal", 0.05, 0.05, {"a": 0.5, "b": 0.5}),
        _wf("ridge", 0.10, 0.07, {"a": 0.9}),  # pas de "b"
    ]
    df = data_layer.weights_frame(results)
    assert set(df["indicator"]) == {"a", "b"}
    b_row = df[df["indicator"] == "b"].iloc[0]
    # La cellule manquante doit être NaN, pas une exception.
    assert b_row["ridge"] != b_row["ridge"]  # NaN test


# -- markov frames ----------------------------------------------------------


def _markov(
    n_states: int = 3, conditional_ic: float = 0.1,
) -> MarkovAnalysis:
    return MarkovAnalysis(
        pair="EURUSD", horizon_days=5, n_samples=120,
        n_states=n_states,
        state_edges=(-math.inf, -0.5, 0.5, math.inf),
        transition_matrix=[[0.7, 0.2, 0.1], [0.3, 0.4, 0.3], [0.1, 0.2, 0.7]],
        state_returns=[-0.002, 0.0001, 0.003],
        state_hit_rates=[0.40, 0.50, 0.62],
        n_by_state=[40, 40, 40],
        state_labels=["low", "mid", "high"],
        conditional_ic=conditional_ic,
    )


def test_markov_transition_frame_shape_and_labels() -> None:
    analysis = _markov()
    df = data_layer.markov_transition_frame(analysis)
    assert df.shape == (3, 3)
    assert list(df.index) == ["low", "mid", "high"]
    assert list(df.columns) == ["low", "mid", "high"]


def test_markov_state_frame_columns() -> None:
    analysis = _markov()
    df = data_layer.markov_state_frame(analysis)
    assert list(df["state"]) == ["low", "mid", "high"]
    for col in ["n_samples", "mean_forward_return", "hit_rate"]:
        assert col in df.columns
    assert df.loc[2, "mean_forward_return"] == pytest.approx(0.003)
