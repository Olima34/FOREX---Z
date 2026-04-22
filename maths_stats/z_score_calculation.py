"""
Calcule les z-scores de "surprise" (actual - consensus) pour chaque couple
(pays, indicateur) à partir de l'historique stocké en DB.

La table `z_scores` contient un seul enregistrement par couple (clé primaire
composite country+indicator) — on utilise UPSERT pour la tenir à jour.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import INDICATOR_COEFFICIENTS
from utils.gestion_db import execute_read_query, execute_write_query
from utils.logger import get_logger
from utils.parametres import DEFAULT_INDICATOR_COEFFICIENT

logger = get_logger("Z_SCORES")

execute_write_query(
    """
    CREATE TABLE IF NOT EXISTS z_scores (
        country TEXT,
        indicator TEXT,
        z_score REAL,
        latest_surprise REAL,
        historical_mean REAL,
        historical_std REAL,
        historical_count INTEGER,
        latest_actual REAL,
        latest_consensus REAL,
        latest_forecast REAL,
        latest_release_ts INTEGER,
        indicator_reference TEXT,
        calculation_timestamp INTEGER,
        PRIMARY KEY (country, indicator)
    )
    """
)


def update_z_scores() -> bool:
    logger.info("Calcul des z-scores depuis la DB...")

    all_data = execute_read_query("SELECT * FROM country_indicators ORDER BY timestamp ASC")

    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in all_data:
        grouped.setdefault((row["country"], row["indicator"]), []).append(row)

    successful = 0
    calc_timestamp = int(time.time())

    for (country, indicator), data in grouped.items():
        if len(data) < 3:
            continue

        surprises = []
        for point in data:
            actual = point.get("actual")
            expected = point.get("consensus") if point.get("consensus") is not None else point.get("forecast")
            if expected is not None and actual is not None:
                surprises.append(actual - expected)

        if len(surprises) < 3:
            continue

        historical_surprises = surprises[:-1]
        latest_surprise = surprises[-1]
        latest_point = data[-1]

        if len(historical_surprises) < 2:
            continue

        mean_surprise = float(np.mean(historical_surprises))
        std_surprise = float(np.std(historical_surprises, ddof=1))

        if std_surprise == 0:
            continue

        z_score = (latest_surprise - mean_surprise) / std_surprise

        upsert = """
            INSERT INTO z_scores (
                country, indicator, z_score, latest_surprise, historical_mean,
                historical_std, historical_count, latest_actual, latest_consensus,
                latest_forecast, latest_release_ts, indicator_reference, calculation_timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(country, indicator) DO UPDATE SET
                z_score=excluded.z_score,
                latest_surprise=excluded.latest_surprise,
                historical_mean=excluded.historical_mean,
                historical_std=excluded.historical_std,
                historical_count=excluded.historical_count,
                latest_actual=excluded.latest_actual,
                latest_consensus=excluded.latest_consensus,
                latest_forecast=excluded.latest_forecast,
                latest_release_ts=excluded.latest_release_ts,
                indicator_reference=excluded.indicator_reference,
                calculation_timestamp=excluded.calculation_timestamp
        """
        execute_write_query(
            upsert,
            (
                country, indicator, round(z_score, 4), round(latest_surprise, 4),
                round(mean_surprise, 4), round(std_surprise, 4), len(historical_surprises),
                latest_point.get("actual"), latest_point.get("consensus"),
                latest_point.get("forecast"), latest_point.get("date_release"),
                latest_point.get("reference", ""), calc_timestamp,
            ),
        )
        successful += 1

    logger.info("Calcul des z-scores terminé : %d indicateurs mis à jour.", successful)
    return True


def get_z_scores_timestamp() -> int | None:
    query = "SELECT MAX(calculation_timestamp) as last_calc FROM z_scores"
    results = execute_read_query(query)
    return results[0]["last_calc"] if results and results[0]["last_calc"] else None


def _get_indicator_coefficient(indicator: str) -> float:
    return (
        INDICATOR_COEFFICIENTS.get(indicator)
        or INDICATOR_COEFFICIENTS.get(indicator.replace("_", "-"))
        or INDICATOR_COEFFICIENTS.get(indicator.replace("-", "_"))
        or DEFAULT_INDICATOR_COEFFICIENT
    )


def get_z_score_data(country: str, indicator: str) -> tuple[float | None, float]:
    query = "SELECT z_score FROM z_scores WHERE country = ? AND indicator = ?"
    results = execute_read_query(query, (country, indicator))

    if not results or results[0]["z_score"] is None:
        return None, 1.0

    z_score = results[0]["z_score"]
    coefficient = _get_indicator_coefficient(indicator)
    factor = round(1.0 + abs(z_score) * coefficient, 4)
    return z_score, factor


def get_z_score(country: str, indicator: str) -> float | None:
    z_score, _ = get_z_score_data(country, indicator)
    return z_score


def get_z_score_factor(country: str, indicator: str) -> float:
    _, factor = get_z_score_data(country, indicator)
    return factor


if __name__ == "__main__":
    update_z_scores()
