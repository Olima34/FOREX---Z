"""
Couche "data" du dashboard — fonctions pures qui mettent en forme les
sorties du module `analytics` pour l'UI.

Séparation stricte : aucune fonction ici ne touche Streamlit. Tout ce
qui est testable sans DB ni Streamlit est testé par la suite. Ce qui
touche la DB est encapsulé derrière une API claire (`overview_table`,
`pair_equity_curve`, etc.), facilement mockable.
"""

from __future__ import annotations

import pandas as pd

from analytics.scripts.backtest import (
    BacktestMetrics,
    _add_forward_returns,
    _align_scores_with_prices,
    _get_scores,
)
from analytics.scripts.markov import MarkovAnalysis
from analytics.scripts.metrics import strategy_returns
from analytics.scripts.model import WalkForwardResult
from analytics.scripts.prices import get_prices


def overview_frame(
    results: dict[str, dict[int, BacktestMetrics]],
    horizon: int,
) -> pd.DataFrame:
    """Met les résultats `run_backtest` en table plate pour un horizon donné.

    Colonnes : pair, n_samples, ic_spearman, hit_rate, cumulative_return,
    sharpe, max_drawdown. Triée par IC décroissant.
    """
    rows: list[dict[str, float | int | str]] = []
    for pair, by_h in results.items():
        m = by_h.get(horizon)
        if m is None:
            continue
        rows.append(
            {
                "pair": pair,
                "n_samples": m.n_samples,
                "ic_spearman": m.ic_spearman,
                "hit_rate": m.hit_rate,
                "cumulative_return": m.cumulative_return,
                "sharpe": m.sharpe,
                "max_drawdown": m.max_drawdown,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "pair", "n_samples", "ic_spearman", "hit_rate",
                "cumulative_return", "sharpe", "max_drawdown",
            ]
        )
    return (
        pd.DataFrame(rows)
        .sort_values("ic_spearman", ascending=False, na_position="last")
        .reset_index(drop=True)
    )


def pair_equity_curve(pair: str, horizon: int) -> pd.DataFrame:
    """Courbe cumulée de la stratégie long/short pour une paire.

    Retourne un DataFrame trié avec colonnes `timestamp` et `equity`
    (valeur d'un portefeuille partant de 1). Vide si pas de données.
    """
    scores = _get_scores(pair)
    prices = get_prices(pair)
    if scores.empty or prices.empty:
        return pd.DataFrame(columns=["timestamp", "equity"])

    prices_fr = _add_forward_returns(prices, horizon)
    aligned = _align_scores_with_prices(scores, prices_fr)
    if aligned.empty:
        return pd.DataFrame(columns=["timestamp", "equity"])

    strat = strategy_returns(aligned["score"], aligned["forward_return"])
    equity = (1.0 + strat).cumprod()
    return pd.DataFrame(
        {"timestamp": aligned["timestamp"].reset_index(drop=True),
         "equity": equity.reset_index(drop=True)}
    )


def score_return_scatter(pair: str, horizon: int) -> pd.DataFrame:
    """Nuage (score, rendement forward) pour un pair. Vide si pas de données.

    Colonnes : `score`, `forward_return`, `timestamp`.
    """
    scores = _get_scores(pair)
    prices = get_prices(pair)
    if scores.empty or prices.empty:
        return pd.DataFrame(columns=["score", "forward_return", "timestamp"])

    prices_fr = _add_forward_returns(prices, horizon)
    aligned = _align_scores_with_prices(scores, prices_fr)
    if aligned.empty:
        return pd.DataFrame(columns=["score", "forward_return", "timestamp"])
    return aligned[["timestamp", "score", "forward_return"]].reset_index(drop=True)


def indicator_heatmap_frame(
    decomposition_results: dict[str, dict[str, dict[int, BacktestMetrics]]],
    horizon: int,
    metric: str = "ic_spearman",
) -> pd.DataFrame:
    """Délègue à `analytics.decomposition.decomposition_matrix` (simple alias).

    Facilite un futur switch de format sans toucher aux plots.
    """
    # Import local : évite un cycle éventuel, et garde `dashboard.data`
    # léger.
    from analytics.scripts.decomposition import decomposition_matrix

    return decomposition_matrix(decomposition_results, horizon=horizon, metric=metric)


def calendar_period_frame(metrics: list[BacktestMetrics]) -> pd.DataFrame:
    """Met un list[BacktestMetrics] (par période) en DataFrame tabulaire."""
    if not metrics:
        return pd.DataFrame(
            columns=["period", "n_samples", "ic_spearman", "hit_rate",
                     "cumulative_return", "sharpe"]
        )
    rows = [
        {
            "period": m.label,
            "n_samples": m.n_samples,
            "ic_spearman": m.ic_spearman,
            "hit_rate": m.hit_rate,
            "cumulative_return": m.cumulative_return,
            "sharpe": m.sharpe,
        }
        for m in metrics
    ]
    return pd.DataFrame(rows)


def volatility_regime_frame(metrics: list[BacktestMetrics]) -> pd.DataFrame:
    """Même principe que `calendar_period_frame` pour les régimes de vol."""
    if not metrics:
        return pd.DataFrame(
            columns=["regime", "n_samples", "ic_spearman", "hit_rate",
                     "cumulative_return", "sharpe"]
        )
    rows = [
        {
            "regime": m.label,
            "n_samples": m.n_samples,
            "ic_spearman": m.ic_spearman,
            "hit_rate": m.hit_rate,
            "cumulative_return": m.cumulative_return,
            "sharpe": m.sharpe,
        }
        for m in metrics
    ]
    return pd.DataFrame(rows)


# -- Modèle prédictif -------------------------------------------------------


def weighter_comparison_frame(results: list[WalkForwardResult]) -> pd.DataFrame:
    """Compare plusieurs pondérateurs sur une paire/horizon.

    Une ligne par pondérateur, colonnes lisibles pour `st.dataframe`.
    """
    if not results:
        return pd.DataFrame(
            columns=["weighter", "n_splits", "n_samples", "ic_is", "ic_oos",
                     "hit_rate_oos", "cumulative_return_oos", "sharpe_oos"]
        )
    rows = [
        {
            "weighter": r.weighter,
            "n_splits": r.n_splits,
            "n_samples": r.n_samples,
            "ic_is": r.ic_is,
            "ic_oos": r.ic_oos,
            "hit_rate_oos": r.hit_rate_oos,
            "cumulative_return_oos": r.cumulative_return_oos,
            "sharpe_oos": r.sharpe_oos,
        }
        for r in results
    ]
    return pd.DataFrame(rows)


def weights_frame(results: list[WalkForwardResult]) -> pd.DataFrame:
    """Table `indicateur × pondérateur` des poids moyens appris.

    Utile pour voir d'un coup d'œil *où les approches diffèrent* :
    l'equal-weight met 1/N partout, l'IC-weighted met zéro sur les
    indicateurs à contre-sens, le ridge peut aller en négatif.
    """
    if not results:
        return pd.DataFrame()
    all_indicators: list[str] = []
    for r in results:
        for ind in r.weights:
            if ind not in all_indicators:
                all_indicators.append(ind)
    rows = []
    for ind in all_indicators:
        row: dict[str, float | str] = {"indicator": ind}
        for r in results:
            row[r.weighter] = r.weights.get(ind, float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)


# -- Markov -----------------------------------------------------------------


def markov_transition_frame(analysis: MarkovAnalysis) -> pd.DataFrame:
    """Matrice de transition en DataFrame labellisé (pour la heatmap)."""
    labels = list(analysis.state_labels)
    return pd.DataFrame(
        analysis.transition_matrix,
        index=labels, columns=labels,
    )


def markov_state_frame(analysis: MarkovAnalysis) -> pd.DataFrame:
    """Tableau par état : label, n, rendement moyen, hit rate."""
    return pd.DataFrame(
        {
            "state": analysis.state_labels,
            "n_samples": analysis.n_by_state,
            "mean_forward_return": analysis.state_returns,
            "hit_rate": analysis.state_hit_rates,
        }
    )
