"""
Ingestion et lecture des prix FX historiques.

On télécharge les cours via yfinance puis on les stocke dans la table
`fx_prices` (UNIQUE sur `(pair, date)` → réingestion idempotente).

Le point d'entrée HTTP `_download_prices` est volontairement minimaliste
et isolé : les tests le monkey-patchent sans avoir à mocker yfinance.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pandas as pd

from config import PAIRS
from utils.gestion_db import execute_read_query, get_connection
from utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = get_logger("FX_PRICES")

# Conversion paire projet → ticker yfinance.
# yfinance utilise `EURUSD=X`, `GBPUSD=X`, etc.
PAIR_TO_YF_TICKER: dict[str, str] = {pair: f"{pair}=X" for pair in PAIRS}

DEFAULT_HISTORY_DAYS = 365 * 5  # 5 ans d'historique par défaut


def _ensure_schema() -> None:
    """Crée la table `fx_prices` si elle n'existe pas.

    Rend le module tolérant aux bases héritées d'avant l'introduction du
    module analytics — aucun besoin de relancer manuellement `init_db.py`.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fx_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                date TEXT NOT NULL,
                close REAL NOT NULL,
                UNIQUE(pair, date)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _download_prices(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Télécharge les cours via yfinance et normalise le DataFrame.

    Retourne un DataFrame à deux colonnes : `date` (str YYYY-MM-DD) et
    `close` (float). DataFrame vide si yfinance ne renvoie rien.

    Ce wrapper est le seul point du module qui touche le réseau.
    Les tests remplacent cette fonction pour injecter des données
    synthétiques sans dépendance à yfinance.
    """
    import yfinance as yf

    raw = yf.download(
        ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        progress=False,
        auto_adjust=True,
    )
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["date", "close"])

    # Depuis yfinance 0.2.x, les colonnes peuvent être un MultiIndex
    # même pour un seul ticker. On aplatit pour un accès uniforme.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    if "Close" not in raw.columns:
        logger.warning("Colonne Close absente pour %s", ticker)
        return pd.DataFrame(columns=["date", "close"])

    df = raw.reset_index()[["Date", "Close"]].rename(columns={"Date": "date", "Close": "close"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["close"])
    return df


def update_prices_for_pair(
    pair: str,
    history_days: int = DEFAULT_HISTORY_DAYS,
) -> int:
    """Télécharge et upsert les prix pour une paire. Retourne # lignes écrites."""
    if pair not in PAIR_TO_YF_TICKER:
        logger.error("Paire inconnue : %s", pair)
        return 0

    _ensure_schema()

    end = date.today()
    start = end - timedelta(days=history_days)
    ticker = PAIR_TO_YF_TICKER[pair]

    try:
        df = _download_prices(ticker, start, end)
    except Exception:
        logger.exception("Échec téléchargement prix %s (%s)", pair, ticker)
        return 0

    if df.empty:
        logger.warning("Aucune donnée de prix pour %s", pair)
        return 0

    rows = [(pair, str(row.date), float(row.close)) for row in df.itertuples(index=False)]
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO fx_prices (pair, date, close) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        inserted = conn.total_changes
    finally:
        conn.close()

    logger.info("Paire %s : %d nouvelles lignes de prix (sur %d téléchargées)",
                pair, inserted, len(rows))
    return inserted


def update_all_prices(history_days: int = DEFAULT_HISTORY_DAYS) -> int:
    """Met à jour les prix de toutes les paires connues."""
    total = 0
    for pair in PAIRS:
        total += update_prices_for_pair(pair, history_days=history_days)
    return total


def get_prices(pair: str) -> pd.DataFrame:
    """Retourne l'historique des prix d'une paire en DataFrame trié par date."""
    _ensure_schema()
    rows = execute_read_query(
        "SELECT date, close FROM fx_prices WHERE pair = ? ORDER BY date",
        (pair,),
    )
    if not rows:
        return pd.DataFrame(columns=["date", "close"])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["close"] = df["close"].astype(float)
    return df.sort_values("date").reset_index(drop=True)
