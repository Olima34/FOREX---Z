"""
Analyse du signal par régime temporel et de marché.

Un IC global moyenné sur 5 ans peut cacher un signal qui marchait en
2020 mais plus en 2023. On propose trois lectures complémentaires :

1. `backtest_by_calendar_period` — un `BacktestMetrics` par année (ou
   trimestre, mois). Regarde la stabilité dans le temps.

2. `rolling_ic` — IC calculé sur une fenêtre glissante de N
   observations. Série temporelle utile pour visualiser le momentum du
   signal.

3. `backtest_by_volatility_regime` — segmente les observations selon la
   volatilité réalisée du sous-jacent au moment du signal. Permet de
   répondre à « mon signal marche-t-il mieux quand le marché est
   calme ou nerveux ? ».

Toutes les fonctions s'appuient sur la pipeline existante (lecture DB,
alignement `merge_asof`, métriques). On ne réimplémente rien ici — on
orchestre.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from analytics.scripts.backtest import (
    DEFAULT_HORIZONS,
    BacktestMetrics,
    _add_forward_returns,
    _align_scores_with_prices,
    _get_scores,
    compute_metrics,
    metrics_from_aligned,
)
from analytics.scripts.prices import get_prices
from utils.logger import get_logger

logger = get_logger("REGIMES")

_MIN_SAMPLES_PER_PERIOD = 10  # aligné avec le reste du module analytics

CalendarPeriod = Literal["year", "quarter", "month"]


def _period_key(ts: pd.Timestamp, period: CalendarPeriod) -> str:
    """Clé lisible d'une période — `'2024'`, `'2024-Q2'`, `'2024-05'`."""
    if period == "year":
        return str(ts.year)
    if period == "quarter":
        return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"
    if period == "month":
        return f"{ts.year}-{ts.month:02d}"
    raise ValueError(f"période inconnue : {period}")


def backtest_by_calendar_period(
    pair: str,
    horizon: int = 5,
    period: CalendarPeriod = "year",
) -> list[BacktestMetrics]:
    """Backtest segmenté par année/trimestre/mois.

    Retourne une liste triée chronologiquement. Les sous-périodes avec
    trop peu d'observations sont omises (pas de NaN silencieux).
    """
    scores = _get_scores(pair)
    prices = get_prices(pair)
    if scores.empty or prices.empty:
        return []

    prices_fr = _add_forward_returns(prices, horizon)
    aligned = _align_scores_with_prices(scores, prices_fr)
    if aligned.empty:
        return []

    aligned = aligned.copy()
    aligned["period"] = aligned["timestamp"].map(lambda ts: _period_key(ts, period))

    out: list[BacktestMetrics] = []
    for period_label, group in aligned.groupby("period", sort=True):
        m = metrics_from_aligned(pair, horizon, group, label=str(period_label))
        if m is not None:
            out.append(m)
    return out


def rolling_ic(
    pair: str,
    horizon: int = 5,
    window: int = 60,
) -> pd.DataFrame:
    """IC de Spearman calculé sur fenêtre glissante.

    Retourne un DataFrame à deux colonnes : `timestamp` (fin de fenêtre)
    et `ic`. `window` est un nombre d'observations de scores, pas de
    jours calendaires — choix pragmatique car les scores ne sont pas
    émis à cadence fixe.

    `NaN` pour les fenêtres contenant moins de `window` observations
    ou contenant une série constante.
    """
    scores = _get_scores(pair)
    prices = get_prices(pair)
    if scores.empty or prices.empty:
        return pd.DataFrame(columns=["timestamp", "ic"])

    prices_fr = _add_forward_returns(prices, horizon)
    aligned = _align_scores_with_prices(scores, prices_fr)
    if len(aligned) < window:
        return pd.DataFrame(columns=["timestamp", "ic"])

    # pandas.Series.rolling().corr(other, method='spearman') n'existe pas
    # ; on passe par apply sur des sous-slices. Pour N observations
    # c'est O(N * window) mais ça reste négligeable à notre échelle.
    s = aligned["score"].reset_index(drop=True)
    r = aligned["forward_return"].reset_index(drop=True)
    ts = aligned["timestamp"].reset_index(drop=True)

    ics: list[float] = []
    for i in range(len(aligned)):
        if i + 1 < window:
            ics.append(float("nan"))
            continue
        sub_s = s.iloc[i + 1 - window : i + 1]
        sub_r = r.iloc[i + 1 - window : i + 1]
        if sub_s.nunique() < 2 or sub_r.nunique() < 2:
            ics.append(float("nan"))
        else:
            ics.append(float(sub_s.corr(sub_r, method="spearman")))

    return pd.DataFrame({"timestamp": ts, "ic": ics}).dropna().reset_index(drop=True)


def _realized_volatility(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Volatilité réalisée (écart-type des log-rendements journaliers).

    Retourne un DataFrame `(date, realized_vol)`, où `realized_vol` est
    annualisée. Utilisée pour segmenter les observations en régimes.
    """
    out = prices.copy().sort_values("date").reset_index(drop=True)
    log_ret = np.log(out["close"]).diff()
    out["realized_vol"] = log_ret.rolling(window).std() * np.sqrt(252)
    return out[["date", "realized_vol"]].dropna().reset_index(drop=True)


def backtest_by_volatility_regime(
    pair: str,
    horizon: int = 5,
    vol_window: int = 20,
    n_regimes: int = 3,
) -> list[BacktestMetrics]:
    """Segmente les observations en régimes de volatilité et backteste.

    On calcule la vol réalisée du sous-jacent sur une fenêtre de
    `vol_window` jours, puis on assigne chaque observation au quantile
    correspondant. `n_regimes=3` → tercile bas / moyen / haut.

    Label du résultat : `"low"`, `"mid"`, `"high"` pour n=3, sinon
    `"q1"`, ..., `"qN"`.
    """
    scores = _get_scores(pair)
    prices = get_prices(pair)
    if scores.empty or prices.empty:
        return []

    prices_fr = _add_forward_returns(prices, horizon)
    vol_df = _realized_volatility(prices, window=vol_window)
    prices_with_vol = prices_fr.merge(vol_df, on="date", how="left")

    aligned = _align_scores_with_prices(scores, prices_with_vol).copy()
    # On n'a besoin de realized_vol que pour les lignes alignées.
    # merge_asof perd les colonnes additionnelles — on refait le merge
    # proprement via la date snappée.
    aligned = aligned.merge(vol_df, on="date", how="left").dropna(
        subset=["realized_vol"]
    )
    if len(aligned) < _MIN_SAMPLES_PER_PERIOD * n_regimes:
        logger.info(
            "Paire %s : %d obs, pas assez pour %d régimes de volatilité",
            pair, len(aligned), n_regimes,
        )
        return []

    # Découpage en quantiles. `duplicates='drop'` protège contre les
    # séries de vol très concentrées.
    try:
        aligned["regime"] = pd.qcut(
            aligned["realized_vol"],
            q=n_regimes,
            labels=False,
            duplicates="drop",
        )
    except ValueError:
        logger.warning("Paire %s : qcut a échoué, volatilité trop concentrée", pair)
        return []

    labels = _regime_labels(n_regimes)

    out: list[BacktestMetrics] = []
    for regime_idx, group in aligned.groupby("regime", sort=True):
        idx = int(regime_idx)
        label = labels[idx] if idx < len(labels) else f"q{idx + 1}"
        m = metrics_from_aligned(pair, horizon, group, label=label)
        if m is not None:
            out.append(m)
    return out


def _regime_labels(n_regimes: int) -> list[str]:
    """Libellés humains pour les quantiles de volatilité."""
    if n_regimes == 2:
        return ["low", "high"]
    if n_regimes == 3:
        return ["low", "mid", "high"]
    if n_regimes == 4:
        return ["q1", "q2", "q3", "q4"]
    return [f"q{i + 1}" for i in range(n_regimes)]


def backtest_by_horizon_sweep(
    pair: str,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> list[BacktestMetrics]:
    """Rejoue le backtest sur une gamme d'horizons — utile pour un plot en balai.

    Simple wrapper pour offrir une API symétrique au reste de ce
    module (liste triée). Réutilise `compute_metrics`.
    """
    scores = _get_scores(pair)
    prices = get_prices(pair)
    if scores.empty or prices.empty:
        return []

    out: list[BacktestMetrics] = []
    for h in horizons:
        m = compute_metrics(pair, h, scores, prices, label=f"{h}d")
        if m is not None:
            out.append(m)
    return out
