"""
Calcule le différentiel de taux d'intérêt (carry) pour chaque paire de devises.

carry(pair) = interest_rate(base) - interest_rate(quote)
"""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import PAIRS
from utils.gestion_db import execute_read_query, execute_write_query, get_latest_indicator
from utils.logger import get_logger

logger = get_logger("CARRY")


def get_latest_carry(pair: str) -> dict | None:
    query = "SELECT * FROM carry_trade WHERE pair = ? ORDER BY timestamp DESC, id DESC LIMIT 1"
    results = execute_read_query(query, (pair,))
    return results[0] if results else None


def calculate_pair_carry(pair: str) -> dict | None:
    base_country, quote_country = PAIRS[pair]

    base_data = get_latest_indicator(base_country, "interest-rate")
    quote_data = get_latest_indicator(quote_country, "interest-rate")

    if not base_data or not quote_data:
        missing = []
        if not base_data:
            missing.append(f"{base_country} interest-rate")
        if not quote_data:
            missing.append(f"{quote_country} interest-rate")
        logger.debug("Données manquantes pour %s : %s", pair, ", ".join(missing))
        return None

    base_actual = base_data["actual"]
    quote_actual = quote_data["actual"]

    if base_actual is None:
        logger.info("%s actual rate None, en attente de publication (%s)", base_country, pair)
        return None

    if quote_actual is None:
        logger.info("%s actual rate None, en attente de publication (%s)", quote_country, pair)
        return None

    return {
        "pair": pair,
        "base_country": base_country,
        "quote_country": quote_country,
        "base_actual": base_actual,
        "quote_actual": quote_actual,
        "carry_value": base_actual - quote_actual,
        "base_interest_rate_id": base_data["id"],
        "quote_interest_rate_id": quote_data["id"],
    }


def id_changed(country: str, last_id: int) -> bool:
    data = get_latest_indicator(country, "interest-rate")
    if not data:
        return False
    return data["id"] != last_id


def value_changed(country: str, last_value) -> bool:
    data = get_latest_indicator(country, "interest-rate")
    if not data:
        return False
    return data["actual"] != last_value


def get_due() -> list[tuple[str, str, str]]:
    due: list[tuple[str, str, str]] = []
    for pair in PAIRS:
        base_country, quote_country = PAIRS[pair]
        row = get_latest_carry(pair)

        if row:
            base_id_updated = id_changed(base_country, row["base_interest_rate_id"])
            quote_id_updated = id_changed(quote_country, row["quote_interest_rate_id"])
            base_value_updated = value_changed(base_country, row["base_actual"])
            quote_value_updated = value_changed(quote_country, row["quote_actual"])

            if (base_id_updated and base_value_updated) or (quote_id_updated and quote_value_updated):
                due.append((pair, base_country, quote_country))
        else:
            due.append((pair, base_country, quote_country))
    return due


def update_due() -> int:
    due = get_due()

    if not due:
        logger.info("Aucun carry à recalculer.")
        return 0

    updated_due = 0

    for pair, base_country, quote_country in due:
        logger.info("[CALCULATE] carry %s (%s vs %s)", pair, base_country, quote_country)
        result = calculate_pair_carry(pair)

        if not result:
            logger.warning("Carry non calculé pour %s", pair)
            continue

        query = """
            INSERT INTO carry_trade
            (pair, base_country, quote_country, base_actual, quote_actual,
             carry_value, base_interest_rate_id, quote_interest_rate_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        execute_write_query(
            query,
            (
                result["pair"], result["base_country"], result["quote_country"],
                result["base_actual"], result["quote_actual"], result["carry_value"],
                result["base_interest_rate_id"], result["quote_interest_rate_id"],
            ),
        )
        logger.info("[OK] %s carry=%s", pair, result["carry_value"])
        updated_due += 1

    logger.info("Total carry mis à jour : %d", updated_due)
    return updated_due


if __name__ == "__main__":
    update_due()
