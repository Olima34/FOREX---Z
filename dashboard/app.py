"""
Dashboard Streamlit FOREX-Z.

Lancement :
    streamlit run dashboard/app.py

Architecture :
- `dashboard.theme`  : CSS + palette + template plotly.
- `dashboard.data`   : fonctions pures DB → DataFrame.
- `dashboard.plots`  : DataFrame → Figure plotly.
- `dashboard.app`    : colle le tout en UI.

5 onglets :
    Overview    — vue d'ensemble toutes paires à un horizon.
    Pair detail — équity curve + scatter + métriques pour une paire.
    Décomposition — IC par indicateur (heatmap + bar chart).
    Régimes     — rolling IC + par année + par régime de volatilité.
    Modèle      — pondérateurs appris (IS vs OOS) + analyse Markov.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from typing import cast

import pandas as pd
import streamlit as st

from analytics.scripts.backtest import DEFAULT_HORIZONS, run_backtest
from analytics.scripts.decomposition import decompose_pair
from analytics.scripts.markov import build_markov_analysis
from analytics.scripts.model import WEIGHTERS, compare_weighters
from analytics.scripts.regimes import (
    backtest_by_calendar_period,
    backtest_by_volatility_regime,
    rolling_ic,
)
from config import PAIRS
from dashboard import data as data_layer
from dashboard import plots
from dashboard.theme import apply_theme

# -- Configuration globale (doit être la première commande Streamlit) --
st.set_page_config(
    page_title="FOREX-Z Backtest",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


# -- Cache ------------------------------------------------------------------
# On cache les lectures DB par horizon. TTL court : les tests font tourner
# le pipeline et la DB évolue — mais pas à la seconde.
@st.cache_data(ttl=60, show_spinner=False)
def _cached_run_backtest(horizons: tuple[int, ...]) -> dict:
    return run_backtest(horizons=horizons)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_equity_curve(pair: str, horizon: int) -> pd.DataFrame:
    return data_layer.pair_equity_curve(pair, horizon)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_scatter(pair: str, horizon: int) -> pd.DataFrame:
    return data_layer.score_return_scatter(pair, horizon)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_decomposition(pair: str, horizons: tuple[int, ...]) -> dict:
    return decompose_pair(pair, horizons=horizons)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_rolling_ic(pair: str, horizon: int, window: int) -> pd.DataFrame:
    return rolling_ic(pair, horizon=horizon, window=window)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_calendar(pair: str, horizon: int, period: str) -> list:
    return backtest_by_calendar_period(
        pair, horizon=horizon, period=cast("str", period)  # type: ignore[arg-type]
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_vol_regimes(pair: str, horizon: int) -> list:
    return backtest_by_volatility_regime(pair, horizon=horizon)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_weighter_comparison(
    pair: str, horizon: int, weighters: tuple[str, ...], n_splits: int,
) -> list:
    return compare_weighters(
        pair, horizon=horizon, weighters=weighters, n_splits=n_splits,
    )


@st.cache_data(ttl=60, show_spinner=False)
def _cached_markov(pair: str, horizon: int, n_states: int):  # noqa: ANN202
    return build_markov_analysis(pair, horizon=horizon, n_states=n_states)


# -- Header ------------------------------------------------------------------
st.title("FOREX-Z — Backtest")
st.caption(
    "Pouvoir prédictif des scores macro sur les rendements FX."
)
st.write("")  # espace


# -- Sidebar : sélecteurs globaux --------------------------------------------
with st.sidebar:
    st.markdown("### Paramètres")
    horizon = st.selectbox(
        "Horizon (jours)",
        options=list(DEFAULT_HORIZONS),
        index=1,
        help="Nombre de jours de trading entre l'émission du signal et le rendement mesuré.",
    )
    pair_options = sorted(PAIRS.keys())
    selected_pair = st.selectbox(
        "Paire (pour les onglets détail)",
        options=pair_options,
        index=pair_options.index("EURUSD") if "EURUSD" in pair_options else 0,
    )
    st.markdown("---")
    st.markdown(
        "**Rappel :** un IC > 0.05 sur un grand N est encourageant. "
        "Les résultats sur quelques dizaines d'obs ne sont pas "
        "significatifs."
    )


# -- Calcul en amont (une fois, mis en cache) --------------------------------
with st.spinner("Chargement des résultats..."):
    results = _cached_run_backtest(tuple(DEFAULT_HORIZONS))

overview_df = data_layer.overview_frame(results, horizon=horizon)


# -- Tabs --------------------------------------------------------------------
tab_overview, tab_pair, tab_decomp, tab_regimes, tab_model = st.tabs(
    ["Overview", "Pair detail", "Décomposition", "Régimes", "Modèle"]
)


# -- Tab 1 : Overview --------------------------------------------------------
with tab_overview:
    if overview_df.empty:
        st.info(
            "Aucune paire n'a assez de données pour être backtestée à cet "
            "horizon. Lancez d'abord le pipeline d'ingestion puis "
            "`python -m analytics --update-prices`."
        )
    else:
        n_pairs = len(overview_df)
        best_ic = overview_df["ic_spearman"].max()
        mean_hit = overview_df["hit_rate"].mean()
        best_sharpe = overview_df["sharpe"].max()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Paires analysées", f"{n_pairs}")
        c2.metric("Meilleur IC", f"{best_ic:+.3f}")
        c3.metric("Hit rate moyen", f"{mean_hit:.1%}" if mean_hit == mean_hit else "n/a")
        c4.metric("Meilleur Sharpe", f"{best_sharpe:+.2f}" if best_sharpe == best_sharpe else "n/a")

        st.write("")
        st.markdown("#### Classement des paires par IC")
        st.plotly_chart(plots.plot_pair_ic_bar(overview_df), use_container_width=True)

        st.write("")
        st.markdown("#### Tableau détaillé")
        st.dataframe(
            overview_df.style.format({
                "ic_spearman": "{:+.3f}",
                "hit_rate": "{:.1%}",
                "cumulative_return": "{:+.2%}",
                "sharpe": "{:+.2f}",
                "max_drawdown": "{:.2%}",
            }),
            use_container_width=True,
            hide_index=True,
        )


# -- Tab 2 : Pair detail -----------------------------------------------------
with tab_pair:
    st.markdown(f"### {selected_pair} — horizon {horizon} jours")

    pair_metrics = results.get(selected_pair, {}).get(horizon)
    if pair_metrics is None:
        st.info(
            f"Pas assez de données pour `{selected_pair}` à l'horizon {horizon}j."
        )
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("N", f"{pair_metrics.n_samples}")
        c2.metric("IC Spearman", f"{pair_metrics.ic_spearman:+.3f}")
        c3.metric(
            "Hit rate",
            f"{pair_metrics.hit_rate:.1%}" if pair_metrics.hit_rate == pair_metrics.hit_rate else "n/a",
        )
        c4.metric(
            "Sharpe",
            f"{pair_metrics.sharpe:+.2f}" if pair_metrics.sharpe == pair_metrics.sharpe else "n/a",
        )
        c5.metric("Max DD", f"{pair_metrics.max_drawdown:.2%}")

        st.write("")
        col_left, col_right = st.columns([1.5, 1])
        with col_left:
            st.markdown("#### Courbe d'équity (stratégie long/short)")
            eq = _cached_equity_curve(selected_pair, horizon)
            st.plotly_chart(plots.plot_equity_curve(eq), use_container_width=True)
        with col_right:
            st.markdown("#### Score vs rendement forward")
            sc = _cached_scatter(selected_pair, horizon)
            st.plotly_chart(plots.plot_score_return_scatter(sc), use_container_width=True)


# -- Tab 3 : Décomposition ---------------------------------------------------
with tab_decomp:
    st.markdown(f"### Décomposition — {selected_pair}, horizon {horizon}j")
    st.caption(
        "Chaque indicateur est backtesté seul : on voit ceux qui portent "
        "le signal et ceux qui ajoutent du bruit."
    )

    pair_decomp = _cached_decomposition(selected_pair, tuple(DEFAULT_HORIZONS))
    if not pair_decomp:
        st.info(
            f"Pas assez de données pour décomposer `{selected_pair}` "
            f"à l'horizon {horizon}j."
        )
    else:
        # Table par indicateur
        rows = []
        for indicator, by_h in pair_decomp.items():
            m = by_h.get(horizon)
            if m is None:
                continue
            rows.append({
                "indicator": indicator,
                "n": m.n_samples,
                "ic_spearman": m.ic_spearman,
                "hit_rate": m.hit_rate,
                "sharpe": m.sharpe,
            })
        per_indicator = (
            pd.DataFrame(rows)
            .sort_values("ic_spearman", ascending=False, na_position="last")
            if rows else pd.DataFrame()
        )

        if per_indicator.empty:
            st.info("Aucun indicateur n'a assez de données à cet horizon.")
        else:
            st.plotly_chart(
                plots.plot_period_bars(
                    per_indicator.assign(period=per_indicator["indicator"]),
                    column="ic_spearman",
                    label_column="period",
                ),
                use_container_width=True,
            )
            st.dataframe(
                per_indicator.style.format({
                    "ic_spearman": "{:+.3f}",
                    "hit_rate": "{:.1%}",
                    "sharpe": "{:+.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )


# -- Tab 4 : Régimes ---------------------------------------------------------
with tab_regimes:
    st.markdown(f"### Régimes — {selected_pair}, horizon {horizon}j")

    left, right = st.columns([1, 1])

    # -- IC glissant
    with left:
        st.markdown("#### IC glissant")
        st.caption("IC sur une fenêtre de 60 observations récentes.")
        rolling = _cached_rolling_ic(selected_pair, horizon, window=60)
        st.plotly_chart(plots.plot_rolling_ic(rolling), use_container_width=True)

    # -- Par année
    with right:
        st.markdown("#### IC par année")
        calendar_metrics = _cached_calendar(selected_pair, horizon, "year")
        cal_df = data_layer.calendar_period_frame(calendar_metrics)
        st.plotly_chart(
            plots.plot_period_bars(cal_df, column="ic_spearman",
                                   label_column="period"),
            use_container_width=True,
        )

    st.write("")
    st.markdown("#### IC par régime de volatilité (terciles)")
    st.caption(
        "Les observations sont segmentées selon la vol réalisée 20j du "
        "sous-jacent. Permet de voir si le signal résiste aux régimes "
        "agités."
    )
    vol_metrics = _cached_vol_regimes(selected_pair, horizon)
    vol_df = data_layer.volatility_regime_frame(vol_metrics)
    if vol_df.empty:
        st.info("Pas assez d'observations pour 3 régimes de volatilité.")
    else:
        st.plotly_chart(
            plots.plot_period_bars(vol_df, column="ic_spearman",
                                   label_column="regime"),
            use_container_width=True,
        )
        st.dataframe(
            vol_df.style.format({
                "ic_spearman": "{:+.3f}",
                "hit_rate": "{:.1%}",
                "cumulative_return": "{:+.2%}",
                "sharpe": "{:+.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )


# -- Tab 5 : Modèle ----------------------------------------------------------
with tab_model:
    st.markdown(f"### Modèle — {selected_pair}, horizon {horizon}j")
    st.caption(
        "Compare différents pondérateurs d'indicateurs en walk-forward "
        "(train expanding window). Le gap IS − OOS indique l'overfit : "
        "plus il est grand, moins le modèle se tient out-of-sample."
    )

    st.markdown("#### Pondérateurs")
    model_results = _cached_weighter_comparison(
        selected_pair, horizon, tuple(WEIGHTERS.keys()), n_splits=5,
    )

    if not model_results:
        st.info(
            f"Pas assez de données pour évaluer `{selected_pair}` à "
            f"l'horizon {horizon}j (besoin d'au moins 30 observations "
            "alignées avec des indicateurs en DB)."
        )
    else:
        comparison_df = data_layer.weighter_comparison_frame(model_results)
        weights_df = data_layer.weights_frame(model_results)

        best_oos = comparison_df["ic_oos"].max()
        best_row = comparison_df.loc[comparison_df["ic_oos"].idxmax()]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Meilleur IC OOS", f"{best_oos:+.3f}")
        c2.metric("Pondérateur gagnant", str(best_row["weighter"]))
        c3.metric(
            "Sharpe OOS",
            f"{best_row['sharpe_oos']:+.2f}"
            if best_row["sharpe_oos"] == best_row["sharpe_oos"] else "n/a",
        )
        c4.metric("N observations", f"{int(best_row['n_samples'])}")

        st.write("")
        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.markdown("##### IC in-sample vs out-of-sample")
            st.plotly_chart(
                plots.plot_ic_is_vs_oos(comparison_df),
                use_container_width=True,
            )
        with col_r:
            st.markdown("##### Poids appris par indicateur")
            st.plotly_chart(
                plots.plot_weights_heatmap(weights_df),
                use_container_width=True,
            )

        st.markdown("##### Tableau détaillé")
        st.dataframe(
            comparison_df.style.format({
                "ic_is": "{:+.3f}",
                "ic_oos": "{:+.3f}",
                "hit_rate_oos": "{:.1%}",
                "cumulative_return_oos": "{:+.2%}",
                "sharpe_oos": "{:+.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.write("")
    st.markdown("#### Analyse de Markov sur les états du score")
    st.caption(
        "Discrétise le score en 3 quantiles (low / mid / high) et mesure "
        "la matrice de transition entre états successifs, ainsi que le "
        "rendement forward moyen par état. Une matrice quasi-identité "
        "indique de la persistance (régime clustering) ; un gradient "
        "marqué de rendements par état indique un vrai signal non-linéaire."
    )

    markov = _cached_markov(selected_pair, horizon, 3)
    if markov is None:
        st.info(
            f"Pas assez de données pour l'analyse Markov "
            f"(`{selected_pair}`, horizon {horizon}j)."
        )
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("N observations", f"{markov.n_samples}")
        c2.metric(
            "IC conditionnel",
            f"{markov.conditional_ic:+.3f}"
            if markov.conditional_ic == markov.conditional_ic else "n/a",
        )
        best_state_idx = int(
            max(range(markov.n_states), key=lambda i: markov.state_returns[i])
        )
        c3.metric(
            "État le plus rentable",
            f"{markov.state_labels[best_state_idx]} "
            f"({markov.state_returns[best_state_idx]:+.2%})",
        )

        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.markdown("##### Matrice de transition")
            st.plotly_chart(
                plots.plot_markov_transition(
                    data_layer.markov_transition_frame(markov)
                ),
                use_container_width=True,
            )
        with col_r:
            st.markdown("##### Rendement moyen par état")
            st.plotly_chart(
                plots.plot_markov_state_returns(
                    data_layer.markov_state_frame(markov)
                ),
                use_container_width=True,
            )

        state_df = data_layer.markov_state_frame(markov)
        st.dataframe(
            state_df.style.format({
                "mean_forward_return": "{:+.3%}",
                "hit_rate": "{:.1%}",
            }),
            use_container_width=True,
            hide_index=True,
        )
