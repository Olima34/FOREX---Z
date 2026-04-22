"""
Thème visuel du dashboard : palette, styles plotly, CSS custom.

Design principles (épuré, moderne) :
- Palette minimale : 1 accent, 2 nuances de gris, 1 "danger" rouge doux.
- Beaucoup de whitespace : padding généreux, pas de bordures lourdes.
- Typo sans-serif system (Inter via fallback).
- Plots plotly avec fond transparent → s'intègrent au fond Streamlit.
- Gradients IC : vert froid (corrélation positive) → rouge doux (négative).
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# -- Palette ----------------------------------------------------------------

COLORS = {
    "bg": "#FAFAFA",
    "surface": "#FFFFFF",
    "text": "#1A1A1A",
    "muted": "#6B7280",
    "accent": "#2563EB",       # bleu calme
    "accent_soft": "#DBEAFE",
    "positive": "#059669",     # vert froid
    "negative": "#DC2626",     # rouge doux
    "neutral": "#9CA3AF",
    "grid": "#E5E7EB",
}

# -- Thème plotly -----------------------------------------------------------

PLOTLY_TEMPLATE = "forex_z"


def _register_plotly_template() -> None:
    """Enregistre un template plotly adapté au thème — à appeler une fois."""
    layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
              "color": COLORS["text"], "size": 13},
        colorway=[COLORS["accent"], COLORS["positive"], COLORS["negative"],
                  COLORS["neutral"], COLORS["muted"]],
        xaxis={"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"],
               "showline": False, "ticks": "outside",
               "tickcolor": COLORS["grid"]},
        yaxis={"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"],
               "showline": False, "ticks": "outside",
               "tickcolor": COLORS["grid"]},
        margin={"l": 48, "r": 24, "t": 32, "b": 40},
        hoverlabel={"bgcolor": COLORS["surface"], "bordercolor": COLORS["grid"],
                    "font": {"color": COLORS["text"]}},
        legend={"bgcolor": "rgba(0,0,0,0)", "bordercolor": COLORS["grid"]},
    )
    pio.templates[PLOTLY_TEMPLATE] = go.layout.Template(layout=layout)
    pio.templates.default = PLOTLY_TEMPLATE


# -- CSS custom pour Streamlit ----------------------------------------------

CUSTOM_CSS = """
<style>
/* Background + typo de base */
.stApp {
    background-color: #FAFAFA;
}
html, body, [class*="css"]  {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
/* Cache les décorations par défaut */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Titre principal plus aéré */
h1 {
    font-weight: 600;
    letter-spacing: -0.02em;
    color: #1A1A1A;
    margin-bottom: 0.2rem;
}
h2, h3 {
    font-weight: 600;
    color: #1A1A1A;
    letter-spacing: -0.01em;
}

/* Metric cards plus sobres */
[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    padding: 1rem 1.25rem;
    border-radius: 10px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02);
}
[data-testid="stMetricLabel"] {
    color: #6B7280;
    font-size: 0.80rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}
[data-testid="stMetricValue"] {
    color: #1A1A1A;
    font-weight: 600;
    font-size: 1.65rem;
}

/* Tabs plus propres */
.stTabs [data-baseweb="tab-list"] {
    gap: 2rem;
    border-bottom: 1px solid #E5E7EB;
}
.stTabs [data-baseweb="tab"] {
    padding: 0.5rem 0;
    color: #6B7280;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    color: #2563EB;
}

/* Sidebar plus aérée */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}

/* Dataframes compactes */
[data-testid="stDataFrame"] {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
}
</style>
"""


def apply_theme() -> None:
    """À appeler en haut de `app.py` : enregistre plotly + injecte le CSS."""
    import streamlit as st

    _register_plotly_template()
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def color_for_value(value: float, *, positive_is_good: bool = True) -> str:
    """Renvoie une couleur selon le signe d'une valeur (IC, Sharpe, ...)."""
    if value != value:  # nan
        return COLORS["muted"]
    if value == 0:
        return COLORS["neutral"]
    if (value > 0) == positive_is_good:
        return COLORS["positive"]
    return COLORS["negative"]
