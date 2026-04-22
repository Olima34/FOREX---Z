"""
Décomposition du signal par indicateur.

Le score total d'une paire est une somme de scores par indicateur (GDP,
taux, inflation, ...) + une composante COT. Quand on mesure un IC agrégé,
on ne sait pas *quels indicateurs* portent le signal et lesquels ajoutent
du bruit.

Ce module backteste chaque `(paire, indicateur)` séparément, en lisant
les scores dans `pair_indicator_scores`. Sortie : `dict[pair][indicator]
[horizon] = BacktestMetrics` — directement exploitable par le dashboard.
"""

from __future__ import annotations

import pandas as pd

from analytics.scripts.backtest import (
    DEFAULT_HORIZONS,
    BacktestMetrics,
    compute_metrics,
)
from analytics.scripts.prices import get_prices
from config import INDICATORS, PAIRS
from utils.gestion_db import execute_read_query
from utils.logger import get_logger

logger = get_logger("DECOMPOSITION")

_MIN_SAMPLES = 10  # aligné avec backtest._MIN_SAMPLES


def _get_indicator_scores(pair: str, indicator: str) -> pd.DataFrame:
    """Charge l'historique des scores `(pair, indicator)` depuis la DB.

    Retourne un DataFrame vide si rien n'est trouvé.
    """
    rows = execute_read_query(
        "SELECT timestamp, pair_score FROM pair_indicator_scores "
        "WHERE pair = ? AND indicator = ? "
        "ORDER BY timestamp, id",
        (pair, indicator),
    )
    if not rows:
        return pd.DataFrame(columns=["timestamp", "score"])
    df = pd.DataFrame(rows).rename(columns={"pair_score": "score"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # On drop les scores NULL (certains indicateurs peuvent ne pas avoir
    # été calculables à un instant donné).
    df = df.dropna(subset=["score"]).reset_index(drop=True)
    df["score"] = df["score"].astype(float)
    return df


def backtest_pair_indicator(
    pair: str,
    indicator: str,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    prices: pd.DataFrame | None = None,
) -> dict[int, BacktestMetrics]:
    """Backtest pour un couple `(paire, indicateur)`.

    `prices` peut être passé pour éviter de re-lire la DB quand on
    orchestre plusieurs indicateurs sur la même paire.
    """
    scores = _get_indicator_scores(pair, indicator)
    if len(scores) < _MIN_SAMPLES:
        return {}

    if prices is None:
        prices = get_prices(pair)
    if prices.empty:
        return {}

    out: dict[int, BacktestMetrics] = {}
    for h in horizons:
        m = compute_metrics(pair, h, scores, prices, indicator=indicator)
        if m is not None:
            out[h] = m
    return out


def decompose_pair(
    pair: str,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, dict[int, BacktestMetrics]]:
    """Décompose une paire en un backtest par indicateur.

    Lit les prix une seule fois et les réutilise pour tous les
    indicateurs (7 appels DB + 1 prix = plus efficace que 8 appels DB).
    """
    prices = get_prices(pair)
    if prices.empty:
        logger.info("Paire %s : pas de prix en base — skip décomposition", pair)
        return {}

    out: dict[str, dict[int, BacktestMetrics]] = {}
    for indicator in INDICATORS:
        res = backtest_pair_indicator(pair, indicator, horizons=horizons, prices=prices)
        if res:
            out[indicator] = res
    return out


def run_decomposition(
    pairs: list[str] | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, dict[str, dict[int, BacktestMetrics]]]:
    """Orchestre la décomposition sur plusieurs paires.

    Retourne `{pair: {indicator: {horizon: BacktestMetrics}}}`.
    Les paires/indicateurs sans assez de données sont écartés.
    """
    target_pairs = pairs if pairs is not None else list(PAIRS.keys())
    out: dict[str, dict[str, dict[int, BacktestMetrics]]] = {}
    for pair in target_pairs:
        res = decompose_pair(pair, horizons=horizons)
        if res:
            out[pair] = res
    return out


def decomposition_matrix(
    results: dict[str, dict[str, dict[int, BacktestMetrics]]],
    horizon: int,
    metric: str = "ic_spearman",
) -> pd.DataFrame:
    """Met en forme la décomposition en matrice indicateur × paire.

    Pratique pour un affichage en heatmap. `metric` peut être toute
    propriété numérique de `BacktestMetrics` (`ic_spearman`, `hit_rate`,
    `sharpe`, etc.). Cellules non calculables → `NaN`.
    """
    pairs = sorted(results.keys())
    data: dict[str, list[float]] = {}
    for indicator in INDICATORS:
        row: list[float] = []
        for pair in pairs:
            m = results.get(pair, {}).get(indicator, {}).get(horizon)
            if m is None:
                row.append(float("nan"))
            else:
                row.append(getattr(m, metric))
        data[indicator] = row
    return pd.DataFrame(data, index=pairs).T
