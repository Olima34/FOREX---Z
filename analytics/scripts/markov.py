"""
Analyse par chaîne de Markov discrète sur les états du score.

Pourquoi
--------
L'IC global mesure la corrélation linéaire de rang entre score et
rendement. Mais le signal peut être **non-linéaire** : un score très
négatif ne prédit pas forcément un rendement proportionnellement
négatif (peut saturer, ou inverser). Une chaîne de Markov discrète sur
des états de score (quantiles) répond directement à la question :

    "Quand le score est dans tel régime, quelle est l'espérance du
     rendement forward, et avec quelle probabilité de gain ?"

On calcule aussi la **matrice de transition** entre états successifs
(P(s_{t+1} | s_t)) — elle dit si le régime persiste ou oscille. Une
matrice quasi-identité indique de la persistance (régime clustering),
une matrice uniforme indique que le score saute au hasard.

Sortie
------
`MarkovAnalysis` — dataclass frozen contenant les quantités utilisées
par le dashboard (matrice de transition, rendement conditionnel par
état, hit rate conditionnel, et un IC "par état" qui compare la
prédiction "rendement moyen historique du régime courant" à la réalité).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from analytics.scripts.backtest import (
    _add_forward_returns,
    _align_scores_with_prices,
    _get_scores,
)
from analytics.scripts.metrics import information_coefficient
from analytics.scripts.prices import get_prices
from utils.logger import get_logger

logger = get_logger("MARKOV")

DEFAULT_N_STATES = 3
_MIN_SAMPLES = 30  # en dessous, la matrice de transition est trop bruitée


@dataclass(frozen=True)
class MarkovAnalysis:
    """Résultats de l'analyse Markov sur un couple `(pair, horizon)`.

    Attributs
    ---------
    n_states : int
        Nombre d'états (quantiles) utilisés pour discrétiser le score.
    state_edges : tuple[float, ...]
        Bornes utilisées pour la discrétisation. `len = n_states + 1`.
        Une ligne observée `x` est dans l'état `i` si
        `state_edges[i] <= x < state_edges[i+1]` (dernier état inclusif).
    transition_matrix : list[list[float]]
        Matrice `n_states × n_states`. `P[i][j]` = fréquence empirique
        des transitions `état i → état j`. Lignes sommant à 1 (sauf si
        l'état `i` n'a pas été observé, auquel cas ligne de zéros).
    state_returns : list[float]
        Rendement forward moyen *quand le score est dans l'état i*.
    state_hit_rates : list[float]
        Fraction d'observations où `sign(state_returns) == sign(
        signal_state)` ; pour l'état médian on calcule
        `P(forward_return > 0)`, utilisé comme référence neutre.
    n_by_state : list[int]
        Nombre d'observations par état.
    state_labels : list[str]
        Libellés lisibles ("low", "mid", "high" pour 3 états, etc.).
    conditional_ic : float
        IC Spearman entre "rendement moyen historique de l'état du jour"
        et rendement réalisé. Mesure à quel point la segmentation en
        états extrait de l'information du score au-delà du rang.
    """

    pair: str
    horizon_days: int
    n_samples: int
    n_states: int
    state_edges: tuple[float, ...]
    transition_matrix: list[list[float]]
    state_returns: list[float]
    state_hit_rates: list[float]
    n_by_state: list[int]
    state_labels: list[str]
    conditional_ic: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_labels(n_states: int) -> list[str]:
    """Libellés lisibles pour les régimes."""
    if n_states == 2:
        return ["low", "high"]
    if n_states == 3:
        return ["low", "mid", "high"]
    return [f"q{i + 1}" for i in range(n_states)]


def _quantile_edges(values: np.ndarray, n_states: int) -> np.ndarray:
    """Renvoie `n_states + 1` bornes basées sur les quantiles empiriques.

    Utilise `np.quantile(q=linspace(0, 1, n+1))`. Les extrêmes sont
    élargis (±inf) pour couvrir proprement les valeurs futures
    légèrement hors-range.
    """
    qs = np.linspace(0.0, 1.0, n_states + 1)
    edges = np.quantile(values, qs)
    # Garantit la monotonie stricte en cas de valeurs très concentrées :
    # sinon digitize retourne des états vides et la matrice explose.
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def _assign_state(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Discrétise `values` en indices d'états selon `edges`.

    `edges` doit être trié croissant. Renvoie un array d'entiers dans
    `[0, len(edges) - 2]`.
    """
    # np.digitize avec right=False : edges[i-1] <= x < edges[i] → idx = i
    # On décale de -1 pour obtenir des indices 0-based, puis on clippe.
    idx = np.digitize(values, edges[1:-1], right=False)
    return np.clip(idx, 0, len(edges) - 2)


def _transition_matrix(states: np.ndarray, n_states: int) -> np.ndarray:
    """Matrice `n_states × n_states` des transitions empiriques.

    `P[i][j]` = nombre de transitions `i → j` divisé par les transitions
    partant de `i`. Une ligne toute à zéro est conservée telle quelle
    (pas de normalisation artificielle) : c'est une info utile pour
    l'UI ("état jamais observé sur la période").
    """
    matrix = np.zeros((n_states, n_states), dtype=float)
    if len(states) < 2:
        return matrix
    for s_from, s_to in zip(states[:-1], states[1:], strict=True):
        matrix[s_from, s_to] += 1.0
    row_sums = matrix.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        normalized = np.where(row_sums > 0, matrix / row_sums, 0.0)
    return np.asarray(normalized, dtype=float).reshape(n_states, n_states)


# ---------------------------------------------------------------------------
# Analyse principale
# ---------------------------------------------------------------------------


def build_markov_analysis(
    pair: str,
    horizon: int,
    n_states: int = DEFAULT_N_STATES,
) -> MarkovAnalysis | None:
    """Analyse de Markov complète pour un couple `(pair, horizon)`.

    Étapes :
    1. Charge les scores totaux et les prix, aligne comme dans le backtest.
    2. Discrétise le score en `n_states` quantiles.
    3. Calcule la matrice de transition entre états successifs.
    4. Calcule le rendement forward moyen *par état courant*.
    5. Calcule un IC conditionnel : remplace chaque score par le
       rendement moyen historique de son état → corrélation avec le
       rendement réalisé.

    Retourne `None` si moins de `_MIN_SAMPLES` observations alignées
    ou si le score est constant (discrétisation impossible).
    """
    if n_states < 2:
        msg = f"n_states doit être >= 2 (reçu {n_states})"
        raise ValueError(msg)

    scores = _get_scores(pair)
    prices = get_prices(pair)
    if scores.empty or prices.empty:
        logger.info("Markov: pas de données pour %s", pair)
        return None

    prices_fr = _add_forward_returns(prices, horizon)
    aligned = _align_scores_with_prices(scores, prices_fr)
    if len(aligned) < _MIN_SAMPLES:
        logger.info(
            "Markov: %s @ %dj a %d obs (min %d)",
            pair, horizon, len(aligned), _MIN_SAMPLES,
        )
        return None

    score_vals = aligned["score"].to_numpy(dtype=float)
    ret_vals = aligned["forward_return"].to_numpy(dtype=float)

    if np.nanstd(score_vals) < 1e-12:
        logger.info("Markov: score constant pour %s", pair)
        return None

    edges = _quantile_edges(score_vals, n_states)
    states = _assign_state(score_vals, edges)

    matrix = _transition_matrix(states, n_states)

    # Rendement / hit rate par état courant.
    state_returns = np.zeros(n_states, dtype=float)
    state_hits = np.zeros(n_states, dtype=float)
    n_by_state = np.zeros(n_states, dtype=int)
    for s in range(n_states):
        mask = states == s
        n_s = int(mask.sum())
        n_by_state[s] = n_s
        if n_s == 0:
            state_returns[s] = np.nan
            state_hits[s] = np.nan
            continue
        r_s = ret_vals[mask]
        state_returns[s] = float(r_s.mean())
        state_hits[s] = float((r_s > 0).mean())

    # IC conditionnel : on remplace chaque score par le rendement moyen
    # historique de son état, puis on corrèle à la réalité. Un IC élevé
    # indique que la segmentation en états extrait du signal réel.
    expected_ret_by_state = pd.Series(
        np.where(n_by_state > 0, state_returns, 0.0)
    )
    predicted = pd.Series(expected_ret_by_state.to_numpy()[states])
    cond_ic = information_coefficient(predicted, pd.Series(ret_vals))

    return MarkovAnalysis(
        pair=pair,
        horizon_days=horizon,
        n_samples=len(aligned),
        n_states=n_states,
        state_edges=tuple(float(e) for e in edges),
        transition_matrix=[[float(v) for v in row] for row in matrix],
        state_returns=[float(v) for v in state_returns],
        state_hit_rates=[float(v) for v in state_hits],
        n_by_state=[int(v) for v in n_by_state],
        state_labels=_state_labels(n_states),
        conditional_ic=float(cond_ic),
    )
