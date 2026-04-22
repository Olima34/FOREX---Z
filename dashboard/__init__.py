"""
Dashboard Streamlit pour l'exploration interactive du backtest FOREX-Z.

Architecture en 3 couches :

- `data.py`   : fonctions pures qui préparent les DataFrames destinés
                à l'affichage. Testables sans Streamlit.
- `theme.py`  : palette de couleurs, styles plotly, CSS custom.
- `app.py`    : UI Streamlit — consomme `data` et `theme`. Lancer via
                `streamlit run dashboard/app.py`.
"""
