"""
Métriques de performance pour le backtest.

Fonctions pures, sans IO — testables directement sans DB ni réseau.
Toutes prennent des `pandas.Series` alignées et retournent des `float`
(ou `nan` quand l'échantillon est trop petit / dégénéré).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# Sous ce seuil on renvoie nan : une corrélation sur 5 obs ne dit rien.
_MIN_OBS = 10


def _clean_pair(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Aligne deux séries et supprime les paires contenant des NaN ou des inf."""
    df = pd.concat([a, b], axis=1, join="inner").replace([np.inf, -np.inf], np.nan).dropna()
    if df.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    return df.iloc[:, 0], df.iloc[:, 1]


def information_coefficient(scores: pd.Series, returns: pd.Series) -> float:
    """Corrélation de Spearman entre scores et rendements futurs."""
    s, r = _clean_pair(scores, returns)
    if len(s) < _MIN_OBS:
        return float("nan")
    # Si l'une des séries est constante, la corrélation n'est pas définie.
    if s.nunique() < 2 or r.nunique() < 2:
        return float("nan")
    return float(s.corr(r, method="spearman"))


def hit_rate(scores: pd.Series, returns: pd.Series) -> float:
    """Fraction des observations où sign(score) == sign(rendement).

    Les observations où score == 0 ou rendement == 0 sont exclues
    (le signal ne dit rien dans ces cas-là).
    """
    s, r = _clean_pair(scores, returns)
    mask = (s != 0) & (r != 0)
    s, r = s[mask], r[mask]
    if len(s) == 0:
        return float("nan")
    return float((np.sign(s) == np.sign(r)).mean())


def sharpe_ratio(returns: pd.Series, periods_per_year: float = 252.0) -> float:
    """Sharpe annualisé pour une série de rendements périodiques.

    On suppose un taux sans risque nul (approximation raisonnable pour un
    backtest éducatif sur des horizons courts).
    """
    r = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 2:
        return float("nan")
    std = r.std(ddof=1)
    # Tolérance : pandas peut retourner un std très petit (pas strictement 0)
    # sur une série constante à cause de l'algo à deux passes en float.
    if math.isnan(std) or std < 1e-12:
        return float("nan")
    return float(r.mean() / std * math.sqrt(periods_per_year))


def max_drawdown(returns: pd.Series) -> float:
    """Drawdown max (valeur négative) d'une courbe de rendements composés."""
    r = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if r.empty:
        return float("nan")
    cum = (1.0 + r).cumprod()
    peak = cum.cummax()
    drawdown = (cum - peak) / peak
    return float(drawdown.min())


def cumulative_return(returns: pd.Series) -> float:
    """Rendement total composé de la série."""
    r = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if r.empty:
        return float("nan")
    return float((1.0 + r).prod() - 1.0)


def strategy_returns(scores: pd.Series, forward_returns: pd.Series) -> pd.Series:
    """Rendements d'une stratégie long/short pilotée par le signe du score.

    Position = sign(score) ∈ {-1, 0, +1}. Rendement de la stratégie sur
    chaque observation = position * forward_return. Aucune contrainte de
    capital : chaque observation est traitée indépendamment (pas de
    composition entre overlapping positions).
    """
    s, r = _clean_pair(scores, forward_returns)
    if s.empty:
        return pd.Series(dtype=float)
    return np.sign(s) * r
