"""
Factories plotly — uniquement des fonctions `DataFrame → Figure`.

Aucune fonction ici ne touche Streamlit. Ça garde `app.py` lisible
(il n'est qu'un orchestrateur) et rend les graphes réutilisables
hors-dashboard (notebook, export PNG, etc.).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard.theme import COLORS


def _empty_figure(message: str) -> go.Figure:
    """Placeholder graphique quand aucune donnée n'est disponible."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper", x=0.5, y=0.5,
        showarrow=False,
        font={"color": COLORS["muted"], "size": 13},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=280)
    return fig


def plot_pair_ic_bar(overview_df: pd.DataFrame) -> go.Figure:
    """Barres horizontales : IC par paire (overview)."""
    if overview_df.empty:
        return _empty_figure("Aucune paire n'a assez de données")

    df = overview_df.dropna(subset=["ic_spearman"]).sort_values("ic_spearman")
    colors = [COLORS["positive"] if v >= 0 else COLORS["negative"]
              for v in df["ic_spearman"]]
    fig = go.Figure(
        go.Bar(
            x=df["ic_spearman"],
            y=df["pair"],
            orientation="h",
            marker={"color": colors},
            hovertemplate="<b>%{y}</b><br>IC: %{x:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(240, 24 * len(df) + 80),
        xaxis_title="Information Coefficient (Spearman)",
        yaxis_title=None,
    )
    fig.add_vline(x=0, line_width=1, line_color=COLORS["grid"])
    return fig


def plot_equity_curve(equity_df: pd.DataFrame) -> go.Figure:
    """Courbe d'équity de la stratégie long/short."""
    if equity_df.empty:
        return _empty_figure("Pas d'historique suffisant pour la courbe d'équity")

    final = equity_df["equity"].iloc[-1]
    color = COLORS["positive"] if final >= 1.0 else COLORS["negative"]

    fig = go.Figure(
        go.Scatter(
            x=equity_df["timestamp"],
            y=equity_df["equity"],
            mode="lines",
            line={"color": color, "width": 2.2},
            fill="tozeroy",
            fillcolor=f"rgba{(*_hex_to_rgb(color), 0.06)}",
            hovertemplate="%{x|%Y-%m-%d}<br>Equity: %{y:.4f}<extra></extra>",
        )
    )
    fig.add_hline(y=1.0, line_width=1, line_dash="dot",
                  line_color=COLORS["grid"])
    fig.update_layout(
        height=320,
        xaxis_title=None,
        yaxis_title="Équity (base 1.0)",
    )
    return fig


def plot_score_return_scatter(scatter_df: pd.DataFrame) -> go.Figure:
    """Nuage score × rendement forward."""
    if scatter_df.empty:
        return _empty_figure("Pas d'observations alignées")

    fig = go.Figure(
        go.Scattergl(
            x=scatter_df["score"],
            y=scatter_df["forward_return"],
            mode="markers",
            marker={
                "size": 6,
                "color": COLORS["accent"],
                "opacity": 0.55,
                "line": {"width": 0},
            },
            hovertemplate=(
                "Score: %{x:.3f}<br>Rendement: %{y:.3%}<extra></extra>"
            ),
        )
    )
    # Droite de régression simple pour guider l'œil.
    if len(scatter_df) >= 5 and scatter_df["score"].nunique() >= 2:
        x = scatter_df["score"].to_numpy()
        y = scatter_df["forward_return"].to_numpy()
        slope, intercept = np.polyfit(x, y, 1)
        x_line = np.linspace(x.min(), x.max(), 50)
        fig.add_trace(
            go.Scatter(
                x=x_line, y=slope * x_line + intercept,
                mode="lines",
                line={"color": COLORS["muted"], "width": 1.5, "dash": "dash"},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_hline(y=0, line_width=1, line_color=COLORS["grid"])
    fig.add_vline(x=0, line_width=1, line_color=COLORS["grid"])
    fig.update_layout(
        height=320,
        xaxis_title="Score (signal)",
        yaxis_title="Rendement forward",
    )
    return fig


def plot_indicator_heatmap(matrix: pd.DataFrame, metric_label: str = "IC") -> go.Figure:
    """Heatmap indicateur × paire (IC ou autre métrique)."""
    if matrix.empty:
        return _empty_figure("Pas de résultats de décomposition")

    # Gradient rouge doux → blanc → vert froid, centré sur 0.
    z = matrix.to_numpy(dtype=float)
    vmax = float(np.nanmax(np.abs(z))) if np.isfinite(z).any() else 1.0
    vmax = max(vmax, 0.05)  # évite un gradient trop serré

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=list(matrix.columns),
            y=list(matrix.index),
            zmin=-vmax, zmax=vmax,
            colorscale=[
                [0.0, COLORS["negative"]],
                [0.5, "#FFFFFF"],
                [1.0, COLORS["positive"]],
            ],
            colorbar={"title": metric_label, "thickness": 12},
            hovertemplate="Indicateur: %{y}<br>Paire: %{x}<br>Valeur: %{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(320, 28 * len(matrix.index) + 120),
        xaxis_title=None,
        yaxis_title=None,
    )
    return fig


def plot_rolling_ic(rolling_df: pd.DataFrame) -> go.Figure:
    """Série temporelle de l'IC sur fenêtre glissante."""
    if rolling_df.empty:
        return _empty_figure("Pas assez d'observations pour un IC glissant")

    fig = go.Figure(
        go.Scatter(
            x=rolling_df["timestamp"],
            y=rolling_df["ic"],
            mode="lines",
            line={"color": COLORS["accent"], "width": 2},
            hovertemplate="%{x|%Y-%m-%d}<br>IC: %{y:.3f}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_width=1, line_dash="dot",
                  line_color=COLORS["grid"])
    fig.update_layout(
        height=300,
        xaxis_title=None,
        yaxis_title="IC glissant",
    )
    return fig


def plot_period_bars(period_df: pd.DataFrame, column: str = "ic_spearman",
                     label_column: str = "period") -> go.Figure:
    """Barres pour un tableau par période (calendrier ou régime)."""
    if period_df.empty:
        return _empty_figure("Pas de résultats par période")

    values = period_df[column]
    colors = [COLORS["positive"] if v >= 0 else COLORS["negative"]
              for v in values]
    fig = go.Figure(
        go.Bar(
            x=period_df[label_column],
            y=values,
            marker={"color": colors},
            hovertemplate="<b>%{x}</b><br>" + column + ": %{y:.3f}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_width=1, line_color=COLORS["grid"])
    fig.update_layout(
        height=300,
        xaxis_title=None,
        yaxis_title=column,
    )
    return fig


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """`'#AABBCC'` → `(170, 187, 204)`. Utilitaire pour les `rgba(...)`."""
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# -- Modèle prédictif -------------------------------------------------------


def plot_ic_is_vs_oos(comparison_df: pd.DataFrame) -> go.Figure:
    """Barres groupées IC in-sample vs out-of-sample par pondérateur.

    Le gap IS − OOS est révélateur : plus il est grand, plus le modèle
    overfit. Un pondérateur sain a un IC OOS proche de l'IS.
    """
    if comparison_df.empty:
        return _empty_figure("Pas de résultats à comparer")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="IC in-sample",
            x=comparison_df["weighter"],
            y=comparison_df["ic_is"],
            marker={"color": COLORS["accent_soft"]},
            hovertemplate="<b>%{x}</b><br>IC IS: %{y:.3f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="IC out-of-sample",
            x=comparison_df["weighter"],
            y=comparison_df["ic_oos"],
            marker={"color": COLORS["accent"]},
            hovertemplate="<b>%{x}</b><br>IC OOS: %{y:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        height=320,
        xaxis_title=None,
        yaxis_title="Information Coefficient",
        legend={"orientation": "h", "y": 1.15},
    )
    fig.add_hline(y=0, line_width=1, line_color=COLORS["grid"])
    return fig


def plot_weights_heatmap(weights_df: pd.DataFrame) -> go.Figure:
    """Heatmap indicateur × pondérateur des poids appris.

    Gradient rouge/blanc/vert centré sur zéro (ridge peut aller en
    négatif). Permet de voir d'un coup quelles colonnes diffèrent.
    """
    if weights_df.empty or "indicator" not in weights_df.columns:
        return _empty_figure("Pas de poids à afficher")

    matrix = weights_df.set_index("indicator")
    z = matrix.to_numpy(dtype=float)
    vmax = float(np.nanmax(np.abs(z))) if np.isfinite(z).any() else 1.0
    vmax = max(vmax, 0.1)

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=list(matrix.columns),
            y=list(matrix.index),
            zmin=-vmax, zmax=vmax,
            colorscale=[
                [0.0, COLORS["negative"]],
                [0.5, "#FFFFFF"],
                [1.0, COLORS["positive"]],
            ],
            colorbar={"title": "Poids", "thickness": 12},
            hovertemplate="<b>%{y}</b><br>%{x}: %{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(240, 28 * len(matrix.index) + 120),
        xaxis_title=None,
        yaxis_title=None,
    )
    return fig


# -- Markov ------------------------------------------------------------------


def plot_markov_transition(matrix_df: pd.DataFrame) -> go.Figure:
    """Heatmap de la matrice de transition P(s_{t+1} | s_t).

    Gradient monotone (blanc → accent) : une probabilité est toujours
    dans [0, 1], pas besoin de centrer sur zéro.
    """
    if matrix_df.empty:
        return _empty_figure("Pas assez de données pour une matrice de transition")

    accent_rgb = _hex_to_rgb(COLORS["accent"])
    fig = go.Figure(
        go.Heatmap(
            z=matrix_df.to_numpy(),
            x=[f"t+1: {c}" for c in matrix_df.columns],
            y=[f"t: {i}" for i in matrix_df.index],
            zmin=0.0, zmax=1.0,
            colorscale=[
                [0.0, "#FFFFFF"],
                [1.0, f"rgb{accent_rgb}"],
            ],
            colorbar={"title": "P", "thickness": 12},
            hovertemplate="%{y} → %{x}<br>P = %{z:.2f}<extra></extra>",
            text=matrix_df.to_numpy(),
            texttemplate="%{text:.2f}",
            textfont={"size": 12, "color": COLORS["text"]},
        )
    )
    fig.update_layout(
        height=320,
        xaxis_title=None,
        yaxis_title=None,
    )
    return fig


def plot_markov_state_returns(state_df: pd.DataFrame) -> go.Figure:
    """Barres du rendement forward moyen par état du score."""
    if state_df.empty:
        return _empty_figure("Pas de données par état")

    values = state_df["mean_forward_return"]
    colors = [COLORS["positive"] if v >= 0 else COLORS["negative"]
              for v in values]
    fig = go.Figure(
        go.Bar(
            x=state_df["state"],
            y=values,
            marker={"color": colors},
            hovertemplate=(
                "<b>État: %{x}</b><br>Rendement moyen: %{y:.3%}"
                "<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line_width=1, line_color=COLORS["grid"])
    fig.update_layout(
        height=300,
        xaxis_title="État du score",
        yaxis_title="Rendement forward moyen",
        yaxis_tickformat=".2%",
    )
    return fig
