"""
Modèle prédictif : apprendre une pondération optimale des indicateurs.

Contexte
--------
Le pipeline existant combine les scores individuels des indicateurs (GDP,
taux, inflation...) en un score total, mais la pondération est implicite
(somme simple). Ce module teste plusieurs façons *apprises* de combiner
ces scores en un signal unique, et mesure rigoureusement leur pouvoir
prédictif out-of-sample.

Pondérateurs implémentés
------------------------
- `equal_weights`  : baseline, 1/N.
- `ic_weights`     : chaque indicateur pondéré par son IC (Spearman) sur
                     la fenêtre d'entraînement. Poids = IC normalisé,
                     zéro si IC < 0 (on ignore les indicateurs à contre-
                     sens sur la période).
- `ridge_weights`  : régression linéaire L2-régularisée fermée
                     (X'X + αI)⁻¹ X'y. Gère la colinéarité et les
                     échantillons courts.

Validation
----------
`walk_forward_evaluate` évalue un pondérateur avec une fenêtre expanding
(train = [0, t], test = [t, t+h]). On ne fit **jamais** le pondérateur
sur des données futures. L'IC out-of-sample est la moyenne des IC
calculés sur chaque tranche de test.

Sorties
-------
`WalkForwardResult` — dataclass frozen avec IC IS vs OOS, hit rate OOS,
poids moyens. Utilisable directement par le dashboard.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from analytics.scripts.backtest import _add_forward_returns
from analytics.scripts.metrics import (
    cumulative_return,
    hit_rate,
    information_coefficient,
    sharpe_ratio,
    strategy_returns,
)
from analytics.scripts.prices import get_prices
from config import INDICATORS
from utils.gestion_db import execute_read_query
from utils.logger import get_logger

logger = get_logger("MODEL")

DEFAULT_N_SPLITS = 5
_MIN_TRAIN_SIZE = 20   # en dessous, le fit de pondération n'est pas fiable
_MIN_TEST_SIZE = 5     # en dessous, l'IC OOS sur la tranche n'est pas défini


# ---------------------------------------------------------------------------
# Résultat
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WalkForwardResult:
    """Résultat d'une évaluation walk-forward pour un pondérateur donné.

    `weights` est la moyenne (sur les splits) des poids appris par
    indicateur. Toujours rempli même pour `equal` (pour faciliter le
    rendu côté dashboard).
    """

    pair: str
    horizon_days: int
    weighter: str
    n_splits: int
    n_samples: int
    ic_is: float
    ic_oos: float
    hit_rate_oos: float
    cumulative_return_oos: float
    sharpe_oos: float
    weights: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Lecture / mise en forme des features
# ---------------------------------------------------------------------------


def _load_indicator_scores(pair: str) -> pd.DataFrame:
    """Charge tous les scores indicateur de `pair`, en format long.

    Colonnes : `timestamp`, `indicator`, `score`. Trié par timestamp.
    DataFrame vide si aucune ligne.
    """
    rows = execute_read_query(
        "SELECT timestamp, indicator, pair_score AS score "
        "FROM pair_indicator_scores "
        "WHERE pair = ? AND pair_score IS NOT NULL "
        "ORDER BY timestamp, id",
        (pair,),
    )
    if not rows:
        return pd.DataFrame(columns=["timestamp", "indicator", "score"])
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["score"] = df["score"].astype(float)
    return df


def build_feature_frame(pair: str, horizon: int) -> pd.DataFrame:
    """Construit la table (features indicateurs, rendement forward) pour `pair`.

    Sortie : DataFrame indexé par `timestamp`, une colonne par indicateur
    présent dans `INDICATORS`, plus une colonne `forward_return`. Les
    lignes où au moins un indicateur est manquant sont supprimées (fit
    vectorisé stable → on ne veut pas d'imputation cachée).

    Empty DataFrame si pas de scores ou pas de prix.
    """
    scores_long = _load_indicator_scores(pair)
    prices = get_prices(pair)
    if scores_long.empty or prices.empty:
        return pd.DataFrame()

    # Pivot long → wide : une colonne par indicateur *effectivement
    # présent en DB*. On reordonne selon l'ordre canonique de
    # `config.INDICATORS` pour que les poids soient stables — mais on
    # n'impose pas la présence des 7 indicateurs : si un seul a été
    # scoré à une date, le dropna vide la table et on perd tout. On se
    # contente donc des indicateurs effectivement observés.
    wide = scores_long.pivot_table(
        index="timestamp", columns="indicator",
        values="score", aggfunc="last",
    )
    present_cols = [c for c in INDICATORS if c in wide.columns]
    if not present_cols:
        return pd.DataFrame()
    wide = wide[present_cols].dropna().sort_index()
    if wide.empty:
        return pd.DataFrame()

    # Rendements forward, alignés sur la même logique que `backtest`
    # (merge_asof direction='forward', snap au prochain close).
    prices_fr = _add_forward_returns(prices, horizon)
    merged = pd.merge_asof(
        wide.reset_index().sort_values("timestamp"),
        prices_fr.sort_values("date")[["date", "forward_return"]],
        left_on="timestamp", right_on="date", direction="forward",
    ).dropna(subset=["forward_return"])

    if merged.empty:
        return pd.DataFrame()
    merged = merged.drop(columns=["date"]).set_index("timestamp")
    # On reordonne : features puis target en dernière colonne.
    cols = [c for c in INDICATORS if c in merged.columns] + ["forward_return"]
    return merged[cols]


# ---------------------------------------------------------------------------
# Pondérateurs
# ---------------------------------------------------------------------------


Weighter = Callable[[pd.DataFrame, pd.Series], pd.Series]


def equal_weights(X: pd.DataFrame, y: pd.Series) -> pd.Series:  # noqa: ARG001
    """Poids uniformes 1/N. Baseline — ignore `y`."""
    n = X.shape[1]
    if n == 0:
        return pd.Series(dtype=float)
    return pd.Series(np.full(n, 1.0 / n), index=X.columns)


def ic_weights(X: pd.DataFrame, y: pd.Series) -> pd.Series:
    """Poids proportionnels à l'IC historique de chaque indicateur.

    Un IC négatif est traité comme zéro : on ne retourne pas le signal
    d'un indicateur à contre-sens, trop risqué sur petit échantillon.
    Si tous les IC sont ≤ 0 → retombe sur equal-weight (signal neutre
    plutôt qu'explosif).
    """
    ics = np.array(
        [information_coefficient(X[col], y) for col in X.columns]
    )
    ics = np.nan_to_num(ics, nan=0.0)
    positive = np.clip(ics, 0.0, None)
    total = positive.sum()
    if total <= 1e-12:
        return equal_weights(X, y)
    return pd.Series(positive / total, index=X.columns)


def ridge_weights(
    X: pd.DataFrame, y: pd.Series, alpha: float = 1.0
) -> pd.Series:
    """Ridge closed-form : `(X'X + αI)⁻¹ X'y`.

    On centre `X` et `y` (intercept implicite) et on standardise `X`
    pour que `alpha` agisse uniformément sur tous les indicateurs. Les
    poids retournés sont **sur l'échelle originale** (donc directement
    applicables à `X` sans pré-traitement supplémentaire côté test).
    """
    X_np = X.to_numpy(dtype=float)
    y_np = y.to_numpy(dtype=float)

    x_mean = X_np.mean(axis=0)
    x_std = X_np.std(axis=0, ddof=1)
    # Évite la division par zéro sur un indicateur constant.
    x_std_safe = np.where(x_std > 1e-12, x_std, 1.0)
    X_scaled = (X_np - x_mean) / x_std_safe
    y_centered = y_np - y_np.mean()

    n_features = X_scaled.shape[1]
    gram = X_scaled.T @ X_scaled
    penalty = alpha * np.eye(n_features)
    try:
        beta_scaled = np.linalg.solve(gram + penalty, X_scaled.T @ y_centered)
    except np.linalg.LinAlgError:
        # Cas dégénéré : on retombe sur equal-weight plutôt que lever.
        return equal_weights(X, y)

    # Remise à l'échelle d'origine (on applique directement à X, pas à X_scaled).
    beta = beta_scaled / x_std_safe
    # Normalisation : la somme |poids| = 1 pour que l'échelle du signal
    # soit comparable entre pondérateurs (l'IC est invariant à l'échelle,
    # mais la cumulative return / sharpe non).
    total = np.abs(beta).sum()
    if total <= 1e-12:
        return equal_weights(X, y)
    return pd.Series(beta / total, index=X.columns)


WEIGHTERS: dict[str, Weighter] = {
    "equal": equal_weights,
    "ic": ic_weights,
    "ridge": ridge_weights,
}


# ---------------------------------------------------------------------------
# Walk-forward splits
# ---------------------------------------------------------------------------


def expanding_window_splits(
    n: int, n_splits: int = DEFAULT_N_SPLITS,
) -> Iterator[tuple[slice, slice]]:
    """Génère `n_splits` splits train/test en fenêtre expanding.

    Conforme à `sklearn.model_selection.TimeSeriesSplit` : pour chaque
    split, train = [0, train_end[, test = [train_end, train_end + test_size[.
    `test_size = n // (n_splits + 1)`. Les splits où train ou test sont
    trop courts (seuils `_MIN_TRAIN_SIZE` / `_MIN_TEST_SIZE`) sont
    silencieusement ignorés.
    """
    if n_splits < 1 or n <= 0:
        return
    test_size = n // (n_splits + 1)
    if test_size < _MIN_TEST_SIZE:
        return
    for i in range(n_splits):
        train_end = (i + 1) * test_size
        test_end = train_end + test_size
        if test_end > n:
            break
        if train_end < _MIN_TRAIN_SIZE:
            continue
        yield slice(0, train_end), slice(train_end, test_end)


# ---------------------------------------------------------------------------
# Évaluation walk-forward
# ---------------------------------------------------------------------------


def _combine(X: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """Produit le signal combiné `X @ w` avec alignement des colonnes."""
    return (X * weights).sum(axis=1)


def walk_forward_evaluate(
    pair: str,
    horizon: int,
    weighter: str = "ridge",
    n_splits: int = DEFAULT_N_SPLITS,
) -> WalkForwardResult | None:
    """Évalue un pondérateur sur `pair, horizon` en walk-forward.

    Retourne `None` si pas assez de données pour faire au moins un
    split valide. Sinon, renvoie un `WalkForwardResult` agrégé :
    - `ic_is`  : moyenne pondérée (par taille) des IC sur les tranches
                 d'entraînement,
    - `ic_oos` : moyenne pondérée des IC sur les tranches de test,
    - `weights` : moyenne des poids appris sur chaque split.
    """
    fn = WEIGHTERS.get(weighter)
    if fn is None:
        msg = f"weighter inconnu: {weighter!r}. Options: {list(WEIGHTERS)}"
        raise ValueError(msg)

    df = build_feature_frame(pair, horizon)
    if df.empty or "forward_return" not in df.columns:
        logger.info("Pas de données exploitables pour %s @ %dj", pair, horizon)
        return None

    feature_cols = [c for c in df.columns if c != "forward_return"]
    X = df[feature_cols]
    y = df["forward_return"]
    n = len(df)

    ic_is_list: list[tuple[int, float]] = []
    ic_oos_list: list[tuple[int, float]] = []
    weights_list: list[pd.Series] = []
    oos_signals: list[pd.Series] = []
    oos_returns: list[pd.Series] = []

    splits = list(expanding_window_splits(n, n_splits=n_splits))
    if not splits:
        logger.info("Walk-forward impossible pour %s @ %dj (n=%d)", pair, horizon, n)
        return None

    for train_slice, test_slice in splits:
        X_tr, y_tr = X.iloc[train_slice], y.iloc[train_slice]
        X_te, y_te = X.iloc[test_slice], y.iloc[test_slice]

        w = fn(X_tr, y_tr)
        weights_list.append(w)

        sig_tr = _combine(X_tr, w)
        sig_te = _combine(X_te, w)

        ic_is = information_coefficient(sig_tr, y_tr)
        ic_oos = information_coefficient(sig_te, y_te)
        if not np.isnan(ic_is):
            ic_is_list.append((len(y_tr), ic_is))
        if not np.isnan(ic_oos):
            ic_oos_list.append((len(y_te), ic_oos))
        oos_signals.append(sig_te)
        oos_returns.append(y_te)

    # Moyennes pondérées par la taille de chaque tranche — les petites
    # tranches ne tirent pas la moyenne artificiellement.
    def _weighted_mean(items: list[tuple[int, float]]) -> float:
        if not items:
            return float("nan")
        total = sum(n_i for n_i, _ in items)
        if total == 0:
            return float("nan")
        return sum(n_i * v for n_i, v in items) / total

    ic_is_mean = _weighted_mean(ic_is_list)
    ic_oos_mean = _weighted_mean(ic_oos_list)

    # Courbe OOS agrégée pour Sharpe / cumulative return.
    if oos_signals:
        sig_all = pd.concat(oos_signals)
        ret_all = pd.concat(oos_returns)
        strat = strategy_returns(sig_all, ret_all)
        periods_per_year = 252.0 / horizon
        cum_ret = cumulative_return(strat)
        sharpe = sharpe_ratio(strat, periods_per_year=periods_per_year)
        hit = hit_rate(sig_all, ret_all)
    else:
        cum_ret = sharpe = hit = float("nan")

    mean_weights = (
        pd.concat(weights_list, axis=1).mean(axis=1)
        if weights_list
        else pd.Series(dtype=float, index=feature_cols)
    )

    return WalkForwardResult(
        pair=pair,
        horizon_days=horizon,
        weighter=weighter,
        n_splits=len(splits),
        n_samples=n,
        ic_is=ic_is_mean,
        ic_oos=ic_oos_mean,
        hit_rate_oos=hit,
        cumulative_return_oos=cum_ret,
        sharpe_oos=sharpe,
        weights={k: float(v) for k, v in mean_weights.items()},
    )


def compare_weighters(
    pair: str,
    horizon: int,
    weighters: tuple[str, ...] = ("equal", "ic", "ridge"),
    n_splits: int = DEFAULT_N_SPLITS,
) -> list[WalkForwardResult]:
    """Compare plusieurs pondérateurs pour `pair, horizon`.

    Retourne la liste des résultats non-None, dans l'ordre d'entrée.
    """
    out: list[WalkForwardResult] = []
    for w in weighters:
        res = walk_forward_evaluate(pair, horizon, weighter=w, n_splits=n_splits)
        if res is not None:
            out.append(res)
    return out
