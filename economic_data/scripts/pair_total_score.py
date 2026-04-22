"""
Agrège les scores par indicateur de chaque paire et y ajoute la composante COT
pour produire un score total unique par paire.

total = Σ scores_indicateurs + sentiment_COT * exp(|sentiment| * factor)
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import INDICATORS, PAIRS
from economic_data.scripts import pair_indicator_score
from utils.gestion_db import execute_read_query, execute_write_query, get_cot_sentiment
from utils.logger import get_logger
from utils.parametres import COT_EXPONENTIAL_FACTOR

logger = get_logger("PAIR_TOTAL_SCORE")


def get_cot_sentiment_score(pair: str) -> float:
    """Renvoie le sentiment COT de la paire, pondéré exponentiellement."""
    cot_data = get_cot_sentiment(pair)
    if not cot_data:
        logger.debug("Pas de données COT pour %s", pair)
        return 0.0

    sentiment = cot_data["pair_sentiment"]
    weight = math.exp(abs(sentiment) * COT_EXPONENTIAL_FACTOR)
    return sentiment * weight


def get_indicator_scores_and_ids(pair: str) -> tuple[dict, dict]:
    indicator_scores: dict[str, float | None] = {}
    indicator_ids: dict[str, int | None] = {}

    for indicator in INDICATORS:
        latest_data = pair_indicator_score.get_latest(pair, indicator)
        if latest_data:
            indicator_scores[indicator] = latest_data["pair_score"]
            indicator_ids[indicator] = latest_data["id"]
        else:
            indicator_scores[indicator] = None
            indicator_ids[indicator] = None

    return indicator_scores, indicator_ids


def calculate_pair_total_score(pair: str) -> dict:
    indicator_scores, indicator_ids = get_indicator_scores_and_ids(pair)

    economic_total = sum(s for s in indicator_scores.values() if s is not None)
    cot_influence = get_cot_sentiment_score(pair)

    return {
        "total_score": economic_total + cot_influence,
        "indicator_scores": indicator_scores,
        "indicator_ids": indicator_ids,
    }


def scores_changed(pair: str, last_scores: dict | None) -> bool:
    if not last_scores:
        return True

    current_scores, _ = get_indicator_scores_and_ids(pair)

    for indicator in INDICATORS:
        current = current_scores.get(indicator)
        last = last_scores.get(indicator)

        if current is None and last is None:
            continue
        if current is None or last is None:
            return True
        if abs(current - last) > 0.0001:
            return True

    return False


def get_latest(pair: str) -> dict | None:
    query = "SELECT * FROM pair_total_scores WHERE pair = ? ORDER BY timestamp DESC, id DESC LIMIT 1"
    results = execute_read_query(query, (pair,))
    return results[0] if results else None


def get_due() -> list[str]:
    due: list[str] = []
    for pair in PAIRS:
        row = get_latest(pair)

        if row:
            try:
                last_scores = json.loads(row["indicator_scores_json"]) if row["indicator_scores_json"] else {}
            except (json.JSONDecodeError, TypeError):
                last_scores = {}

            if scores_changed(pair, last_scores):
                due.append(pair)
        else:
            due.append(pair)
    return due


def update_due() -> int:
    due = get_due()

    if not due:
        logger.info("Aucun pair_total_score à recalculer.")
        return 0

    updated_due = 0

    for pair in due:
        logger.info("[CALCULATE] total_score %s", pair)
        result = calculate_pair_total_score(pair)

        query = """
            INSERT INTO pair_total_scores
            (pair, total_score, indicator_scores_json, indicator_ids_json)
            VALUES (?, ?, ?, ?)
        """
        execute_write_query(
            query,
            (
                pair,
                result["total_score"],
                json.dumps(result["indicator_scores"]),
                json.dumps(result["indicator_ids"]),
            ),
        )
        logger.info("[OK] %s total_score=%.4f", pair, result["total_score"])
        updated_due += 1

    logger.info("Total pair_total_score mis à jour : %d", updated_due)
    return updated_due


if __name__ == "__main__":
    update_due()
