"""
Tests unitaires pour `dashboard.plots` — factories plotly pures.

On vérifie surtout :
- qu'un DataFrame vide renvoie une figure "placeholder" (pas d'exception),
- qu'un DataFrame normal renvoie une `go.Figure` avec au moins une trace.

Les propriétés visuelles fines (couleurs exactes, hovertemplate) ne sont
pas testées — elles changeraient à chaque tweak esthétique.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard import plots


def test_plot_pair_ic_bar_handles_empty() -> None:
    fig = plots.plot_pair_ic_bar(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_plot_pair_ic_bar_renders_bars() -> None:
    df = pd.DataFrame(
        {"pair": ["EURUSD", "USDJPY"], "ic_spearman": [0.08, -0.03]}
    )
    fig = plots.plot_pair_ic_bar(df)
    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"


def test_plot_equity_curve_handles_empty() -> None:
    fig = plots.plot_equity_curve(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_plot_equity_curve_renders_line() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="D"),
            "equity": [1.0, 1.01, 1.005, 1.02, 1.03],
        }
    )
    fig = plots.plot_equity_curve(df)
    assert len(fig.data) == 1
    assert fig.data[0].type == "scatter"


def test_plot_score_return_scatter_handles_empty() -> None:
    fig = plots.plot_score_return_scatter(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_plot_score_return_scatter_adds_regression_line() -> None:
    rng = np.random.default_rng(0)
    n = 50
    score = rng.normal(size=n)
    ret = 0.01 * score + rng.normal(scale=0.005, size=n)
    df = pd.DataFrame({"score": score, "forward_return": ret})
    fig = plots.plot_score_return_scatter(df)
    # Une trace scatter (les points) + une trace pour la régression.
    assert len(fig.data) == 2


def test_plot_rolling_ic_handles_empty() -> None:
    fig = plots.plot_rolling_ic(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_plot_rolling_ic_renders_line() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="D"),
            "ic": np.linspace(-0.1, 0.1, 10),
        }
    )
    fig = plots.plot_rolling_ic(df)
    assert len(fig.data) == 1


def test_plot_period_bars_handles_empty() -> None:
    fig = plots.plot_period_bars(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_plot_period_bars_renders_bars() -> None:
    df = pd.DataFrame(
        {"period": ["2023", "2024"], "ic_spearman": [0.05, -0.02]}
    )
    fig = plots.plot_period_bars(df)
    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"


def test_plot_indicator_heatmap_handles_empty() -> None:
    fig = plots.plot_indicator_heatmap(pd.DataFrame())
    assert isinstance(fig, go.Figure)


def test_plot_indicator_heatmap_renders() -> None:
    matrix = pd.DataFrame(
        {"EURUSD": [0.05, -0.02], "USDJPY": [0.01, 0.03]},
        index=["carry", "growth"],
    )
    fig = plots.plot_indicator_heatmap(matrix)
    assert len(fig.data) == 1
    assert fig.data[0].type == "heatmap"


def test_hex_to_rgb() -> None:
    assert plots._hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert plots._hex_to_rgb("#000000") == (0, 0, 0)
    assert plots._hex_to_rgb("#2563EB") == (37, 99, 235)
