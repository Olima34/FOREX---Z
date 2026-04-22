"""
Calcule un score par (paire, indicateur) à partir des données stockées en DB.

Pour chaque pays, on compare `actual` à la référence (consensus → forecast).
Le signe de la surprise est pondéré par le z-score historique de l'indicateur,
puis on soustrait le score du pays quote au score du pays base.
"""

from __future__ import annotations

import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import BAD_INDICATORS, INDICATORS, PAIRS
from maths_stats.z_score_calculation import get_z_score_factor, get_z_scores_timestamp
from utils.gestion_db import execute_read_query, execute_write_query, get_latest_indicator
from utils.logger import get_logger

logger = get_logger("PAIR_INDICATOR_SCORE")

# Création idempotente de la table (au cas où init_db.py n'a pas été lancé).
execute_write_query(
    """
    CREATE TABLE IF NOT EXISTS pair_indicator_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT,
        indicator TEXT,
        base_country TEXT,
        quote_country TEXT,
        base_actual REAL,
        base_consensus REAL,
        base_forecast REAL,
        quote_actual REAL,
        quote_consensus REAL,
        quote_forecast REAL,
        base_score REAL,
        quote_score REAL,
        pair_score REAL,
        base_indicator_id INTEGER,
        quote_indicator_id INTEGER,
        base_z_factor REAL,
        quote_z_factor REAL,
        calculation_timestamp INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
)


def calculate_indicator_score(
    actual: float | None,
    consensus: float | None,
    forecast: float | None,
    indicator: str,
    country: str | None = None,
) -> float:
    if actual is None:
        return 0

    reference_value = consensus if consensus is not None else forecast
    if reference_value is None:
        return 0

    score: float
    if actual > reference_value:
        score = 1.0
    elif actual < reference_value:
        score = -1.0
    else:
        score = 0.0

    # Certains indicateurs sont "inversés" : une hausse du chômage est négative.
    if indicator in BAD_INDICATORS:
        score *= -1

    if country:
        score *= get_z_score_factor(country, indicator)

    return round(score, 4)


def calculate_pair_indicator_score(pair: str, indicator: str) -> dict | None:
    base_country, quote_country = PAIRS[pair]

    base_data = get_latest_indicator(base_country, indicator)
    quote_data = get_latest_indicator(quote_country, indicator)

    if not base_data or not quote_data:
        return None

    base_score = calculate_indicator_score(
        base_data["actual"], base_data["consensus"], base_data["forecast"], indicator, base_country
    )
    quote_score = calculate_indicator_score(
        quote_data["actual"], quote_data["consensus"], quote_data["forecast"], indicator, quote_country
    )

    return {
        "base_actual": base_data["actual"],
        "base_consensus": base_data["consensus"],
        "base_forecast": base_data["forecast"],
        "quote_actual": quote_data["actual"],
        "quote_consensus": quote_data["consensus"],
        "quote_forecast": quote_data["forecast"],
        "base_score": base_score,
        "quote_score": quote_score,
        "pair_score": base_score - quote_score,
        "base_indicator_id": base_data["id"],
        "quote_indicator_id": quote_data["id"],
        "base_z_factor": get_z_score_factor(base_country, indicator),
        "quote_z_factor": get_z_score_factor(quote_country, indicator),
    }


def id_changed(country: str, indicator: str, last_id: int) -> bool:
    latest_data = get_latest_indicator(country, indicator)
    if not latest_data:
        return False
    return latest_data["id"] != last_id


def get_latest(pair: str, indicator: str) -> dict | None:
    query = (
        "SELECT * FROM pair_indicator_scores "
        "WHERE pair = ? AND indicator = ? "
        "ORDER BY timestamp DESC, id DESC LIMIT 1"
    )
    results = execute_read_query(query, (pair, indicator))
    return results[0] if results else None


def get_due() -> list[tuple[str, str, str, str]]:
    due: list[tuple[str, str, str, str]] = []
    z_scores_timestamp = get_z_scores_timestamp()

    for pair in PAIRS:
        base_country, quote_country = PAIRS[pair]
        for indicator in INDICATORS:
            row = get_latest(pair, indicator)

            if row:
                base_updated = id_changed(base_country, indicator, row["base_indicator_id"])
                quote_updated = id_changed(quote_country, indicator, row["quote_indicator_id"])

                z_scores_updated = False
                if z_scores_timestamp and row.get("calculation_timestamp"):
                    current_base_z = get_z_score_factor(base_country, indicator)
                    current_quote_z = get_z_score_factor(quote_country, indicator)
                    stored_base_z = row.get("base_z_factor", 1.0)
                    stored_quote_z = row.get("quote_z_factor", 1.0)
                    z_scores_updated = (
                        abs(current_base_z - stored_base_z) > 0.0001
                        or abs(current_quote_z - stored_quote_z) > 0.0001
                    )

                if base_updated or quote_updated or z_scores_updated:
                    due.append((pair, indicator, base_country, quote_country))
            else:
                due.append((pair, indicator, base_country, quote_country))
    return due


def update_due() -> int:
    due = get_due()

    if not due:
        logger.info("Aucun pair_indicator_score à recalculer.")
        return 0

    updated_due = 0

    for pair, indicator, base_country, quote_country in due:
        logger.info("[CALCULATE] %s - %s", pair, indicator)
        result = calculate_pair_indicator_score(pair, indicator)

        if not result:
            logger.warning("Score non calculé pour %s - %s", pair, indicator)
            continue

        calc_ts = get_z_scores_timestamp() or int(time.time())

        query = """
            INSERT INTO pair_indicator_scores
            (pair, indicator, base_country, quote_country, base_actual, base_consensus,
             base_forecast, quote_actual, quote_consensus, quote_forecast, base_score,
             quote_score, pair_score, base_indicator_id, quote_indicator_id,
             base_z_factor, quote_z_factor, calculation_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_write_query(
            query,
            (
                pair, indicator, base_country, quote_country,
                result["base_actual"], result["base_consensus"], result["base_forecast"],
                result["quote_actual"], result["quote_consensus"], result["quote_forecast"],
                result["base_score"], result["quote_score"], result["pair_score"],
                result["base_indicator_id"], result["quote_indicator_id"],
                result["base_z_factor"], result["quote_z_factor"], calc_ts,
            ),
        )
        logger.info(
            "[OK] %s/%s base=%s quote=%s pair=%s",
            pair, indicator,
            result["base_score"], result["quote_score"], result["pair_score"],
        )
        updated_due += 1

    logger.info("Total pair_indicator_score mis à jour : %d", updated_due)
    return updated_due


if __name__ == "__main__":
    update_due()
