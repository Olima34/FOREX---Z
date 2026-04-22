"""
Backtest : aligne les scores produits par le pipeline avec les rendements
FX à plusieurs horizons et calcule des métriques de pouvoir prédictif.

Entrée : rien (lit tout depuis SQLite).
Sortie : un `dict` `{pair: {horizon: BacktestMetrics}}`.

Le point d'entrée utilisateur est `run_backtest()`. Le CLI (voir
`analytics.__main__`) enchaîne : update_prices → run_backtest → report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from analytics.scripts.metrics import (
    cumulative_return,
    hit_rate,
    information_coefficient,
    max_drawdown,
    sharpe_ratio,
    strategy_returns,
)
from analytics.scripts.prices import get_prices
from config import PAIRS
from utils.gestion_db import execute_read_query
from utils.logger import get_logger

logger = get_logger("BACKTEST")

DEFAULT_HORIZONS: tuple[int, ...] = (1, 5, 20)
_MIN_SAMPLES = 10  # en dessous, le backtest n'est pas significatif


@dataclass(frozen=True)
class BacktestMetrics:
    """Résultats d'un backtest pour une paire et un horizon.

    `indicator` est `None` quand le score testé est le total agrégé ;
    sinon c'est le nom de l'indicateur pour la décomposition.
    `label` est un libellé libre (ex: nom de régime) utilisé par les
    analyses par sous-période.
    """

    pair: str
    horizon_days: int
    n_samples: int
    ic_spearman: float
    hit_rate: float
    cumulative_return: float
    sharpe: float
    max_drawdown: float
    indicator: str | None = None
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_scores(pair: str) -> pd.DataFrame:
    """Charge les scores totaux d'une paire en DataFrame trié."""
    rows = execute_read_query(
        "SELECT timestamp, total_score FROM pair_total_scores "
        "WHERE pair = ? ORDER BY timestamp, id",
        (pair,),
    )
    if not rows:
        return pd.DataFrame(columns=["timestamp", "score"])
    df = pd.DataFrame(rows).rename(columns={"total_score": "score"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["score"] = df["score"].astype(float)
    return df.sort_values("timestamp").reset_index(drop=True)


def _add_forward_returns(prices: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    """Ajoute à `prices` la colonne `forward_return` à `horizon_days`.

    `forward_return[t] = close[t + h] / close[t] - 1`. Les lignes en
    bord droit (sans `close[t+h]` connu) sont supprimées.
    """
    out = prices.copy()
    out["forward_return"] = out["close"].shift(-horizon_days) / out["close"] - 1.0
    return out.dropna(subset=["forward_return"]).reset_index(drop=True)


def _align_scores_with_prices(
    scores: pd.DataFrame, prices_with_fr: pd.DataFrame
) -> pd.DataFrame:
    """Joint chaque score à la prochaine date de prix disponible.

    `merge_asof` direction='forward' : pour un score émis à `ts`, on prend
    la première ligne de prix dont la `date` est >= `ts`. Hypothèse
    réaliste — un signal construit pendant la journée s'exécute au
    prochain close disponible.
    """
    if scores.empty or prices_with_fr.empty:
        return pd.DataFrame(columns=["timestamp", "score", "close", "forward_return"])

    merged = pd.merge_asof(
        scores.sort_values("timestamp"),
        prices_with_fr.sort_values("date")[["date", "close", "forward_return"]],
        left_on="timestamp",
        right_on="date",
        direction="forward",
    )
    return merged.dropna(subset=["close", "forward_return"]).reset_index(drop=True)


def metrics_from_aligned(
    pair: str,
    horizon: int,
    aligned: pd.DataFrame,
    *,
    indicator: str | None = None,
    label: str | None = None,
) -> BacktestMetrics | None:
    """Calcule un `BacktestMetrics` à partir d'un DataFrame déjà aligné.

    `aligned` doit contenir au minimum les colonnes `score` et
    `forward_return`. Fonction-pivot exploitée par les analyses par
    régime, qui filtrent les observations *après* l'alignement.
    Retourne `None` si l'échantillon est trop petit.
    """
    if len(aligned) < _MIN_SAMPLES:
        return None

    strat = strategy_returns(aligned["score"], aligned["forward_return"])
    # Annualisation : un rendement à h jours donne 252/h périodes par an.
    periods_per_year = 252.0 / horizon
    return BacktestMetrics(
        pair=pair,
        horizon_days=horizon,
        n_samples=len(aligned),
        ic_spearman=information_coefficient(aligned["score"], aligned["forward_return"]),
        hit_rate=hit_rate(aligned["score"], aligned["forward_return"]),
        cumulative_return=cumulative_return(strat),
        sharpe=sharpe_ratio(strat, periods_per_year=periods_per_year),
        max_drawdown=max_drawdown(strat),
        indicator=indicator,
        label=label,
    )


def compute_metrics(
    pair: str,
    horizon: int,
    scores: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    indicator: str | None = None,
    label: str | None = None,
) -> BacktestMetrics | None:
    """Calcule un `BacktestMetrics` à partir de scores + prix bruts.

    Enchaîne les étapes : calcul des rendements forward, alignement
    `merge_asof`, agrégation métriques. Utilisé par `backtest_pair` et la
    décomposition par indicateur.
    """
    prices_fr = _add_forward_returns(prices, horizon)
    merged = _align_scores_with_prices(scores, prices_fr)
    return metrics_from_aligned(
        pair, horizon, merged, indicator=indicator, label=label
    )


def backtest_pair(
    pair: str, horizons: tuple[int, ...] = DEFAULT_HORIZONS
) -> dict[int, BacktestMetrics]:
    """Calcule les métriques pour une paire à plusieurs horizons.

    Retourne `{}` si pas assez de données. Ne lève pas d'exception :
    les paires sans données sont simplement absentes du résultat.
    """
    scores = _get_scores(pair)
    prices = get_prices(pair)

    if len(scores) < _MIN_SAMPLES:
        logger.info("Paire %s : %d scores seulement (min %d) — skip",
                    pair, len(scores), _MIN_SAMPLES)
        return {}
    if prices.empty:
        logger.info("Paire %s : aucun prix en base — skip", pair)
        return {}

    results: dict[int, BacktestMetrics] = {}
    for h in horizons:
        m = compute_metrics(pair, h, scores, prices)
        if m is not None:
            results[h] = m
    return results


def run_backtest(
    pairs: list[str] | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[str, dict[int, BacktestMetrics]]:
    """Exécute le backtest sur un ensemble de paires.

    `pairs=None` → toutes les paires connues du projet. Les paires sans
    assez de données sont silencieusement écartées.
    """
    target_pairs = pairs if pairs is not None else list(PAIRS.keys())
    out: dict[str, dict[int, BacktestMetrics]] = {}
    for pair in target_pairs:
        res = backtest_pair(pair, horizons=horizons)
        if res:
            out[pair] = res
    return out
