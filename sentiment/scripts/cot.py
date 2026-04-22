"""
Récupère le rapport hebdomadaire COT (Commitments of Traders) de la CFTC
et en déduit un score de sentiment par paire.

La CFTC publie chaque vendredi à 15:30 ET (≈ 21:30 Paris). On ne déclenche
le fetch qu'après cette échéance, ou si aucune donnée n'a encore été
enregistrée.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from io import StringIO

import pandas as pd
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import COT_COLUMNS, COT_NAMES, COT_PAIRS
from utils.gestion_db import execute_read_query, execute_write_query, get_cot_sentiment
from utils.logger import get_logger
from utils.parametres import HTTP_TIMEOUT

logger = get_logger("COT")

COT_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"

COT_POSITION_COLUMNS = [
    "Noncommercial_Positions_Long_All",
    "Noncommercial_Positions_Short_All",
    "Change_in_Noncommercial_Long_All",
    "Change_in_Noncommercial_Short_All",
]


def fetch() -> pd.DataFrame | None:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(COT_URL, headers=headers, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        logger.exception("Erreur HTTP lors du fetch COT")
        return None

    try:
        df = pd.read_csv(StringIO(response.text), names=COT_COLUMNS)
        df = df[df["Market_and_Exchange_Names"].isin(COT_NAMES)]
        for column in COT_POSITION_COLUMNS:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        return df[["Market_and_Exchange_Names", *COT_POSITION_COLUMNS]]
    except (ValueError, KeyError):
        logger.exception("Erreur de parsing du CSV COT")
        return None


def calculate_cot_net_change(row) -> float:
    long_pos = row["Noncommercial_Positions_Long_All"]
    short_pos = row["Noncommercial_Positions_Short_All"]
    long_change = row["Change_in_Noncommercial_Long_All"]
    short_change = row["Change_in_Noncommercial_Short_All"]

    current_pct = long_pos / (long_pos + short_pos) * 100
    prev_pct = (long_pos - long_change) / (
        (long_pos - long_change) + (short_pos - short_change)
    ) * 100
    return current_pct - prev_pct


def calculate_pair_cot(pair: str, df: pd.DataFrame) -> dict:
    base_country, quote_country = COT_PAIRS[pair]
    base_data = df[df["Market_and_Exchange_Names"] == base_country].iloc[0]
    quote_data = df[df["Market_and_Exchange_Names"] == quote_country].iloc[0]

    base_net_change = calculate_cot_net_change(base_data)
    quote_net_change = calculate_cot_net_change(quote_data)
    pair_sentiment = float(base_net_change - quote_net_change)

    logger.info("[OK] COT %s = %.4f", pair, pair_sentiment)
    return {"pair": pair, "pair_sentiment": pair_sentiment}


def get_latest(pair: str) -> dict | None:
    return get_cot_sentiment(pair)


def get_last_update_time() -> str | None:
    query = "SELECT timestamp FROM cot_sentiment ORDER BY timestamp DESC LIMIT 1"
    results = execute_read_query(query)
    if results and results[0]["timestamp"]:
        return results[0]["timestamp"]
    return None


def _parse_sqlite_timestamp(value: str) -> datetime | None:
    """Parse un timestamp SQLite (`YYYY-MM-DD HH:MM:SS` ou ISO)."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def should_update_cot() -> bool:
    """Vrai si on est passé la dernière publication COT sans l'avoir ingérée."""
    now = datetime.now()
    last_update = get_last_update_time()

    if not last_update:
        logger.info("Aucune donnée COT en base, mise à jour initiale requise")
        return True

    last_update_dt = _parse_sqlite_timestamp(last_update)
    if not last_update_dt:
        logger.warning("Timestamp COT illisible (%s), on force la maj", last_update)
        return True

    days_since_friday = (now.weekday() - 4) % 7
    current_friday = now
    if days_since_friday != 0:
        current_friday = now - timedelta(days=days_since_friday)
    elif now.hour < 21 or (now.hour == 21 and now.minute < 31):
        current_friday = now - timedelta(days=7)

    target = current_friday.replace(hour=21, minute=31, second=0, microsecond=0)

    if last_update_dt < target:
        logger.info("Données COT obsolètes. Dernière maj : %s, cible : %s", last_update_dt, target)
        return True

    logger.info(
        "Données COT à jour. Dernière maj : %s, prochaine cible : %s",
        last_update_dt, target + timedelta(days=7),
    )
    return False


def update() -> int:
    if not should_update_cot():
        return 0

    df = fetch()
    if df is None:
        logger.error("Fetch COT a échoué — aucune maj effectuée")
        return 0

    updated_count = 0

    for pair in COT_PAIRS:
        logger.info("[CALCULATE] sentiment COT %s", pair)
        try:
            result = calculate_pair_cot(pair, df)
        except (IndexError, ValueError):
            logger.exception("Erreur de calcul COT pour %s", pair)
            continue

        execute_write_query(
            "INSERT INTO cot_sentiment (pair, pair_sentiment) VALUES (?, ?)",
            (result["pair"], result["pair_sentiment"]),
        )
        updated_count += 1

    logger.info("Total sentiment COT mis à jour : %d", updated_count)
    return updated_count


if __name__ == "__main__":
    update()
