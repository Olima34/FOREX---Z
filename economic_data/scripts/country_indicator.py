"""
Récupère les indicateurs macro-économiques depuis Trading Economics et les
stocke dans la table `country_indicators` de SQLite.

Pour chaque (pays, indicateur), on ne ré-insère une ligne que si les valeurs
actual/consensus/forecast/previous ont changé. Le champ `next_update_ts`
permet d'éviter de re-scraper une page dont la prochaine publication est
encore dans le futur.
"""

from __future__ import annotations

import os
import sys
import time
from io import StringIO

import pandas as pd
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import COUNTRIES, SYMBOLS, UNITS
from maths_stats.z_score_calculation import update_z_scores
from utils.gestion_db import execute_write_query, get_connection, get_latest_indicator
from utils.logger import get_logger
from utils.parametres import HTTP_TIMEOUT

logger = get_logger("COUNTRY_INDICATOR")


def _ensure_schema() -> None:
    """Ajoute la colonne `next_update_ts` si elle manque (migration idempotente)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(country_indicators)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "next_update_ts" not in columns:
            cursor.execute("ALTER TABLE country_indicators ADD COLUMN next_update_ts INTEGER")
            conn.commit()
            logger.info("Colonne next_update_ts ajoutée à country_indicators")
        else:
            logger.debug("Colonne next_update_ts déjà présente")
    finally:
        conn.close()


_ensure_schema()


def clean_value(value) -> float | None:
    """Convertit une valeur texte (ex: '1.25%', '$1.5B') en float."""
    if pd.isna(value) or not isinstance(value, str):
        return None

    value = value.strip()
    for symbol in SYMBOLS:
        value = value.replace(symbol, "").strip()

    if value and value[-1] in UNITS:
        try:
            return float(value[:-1]) * UNITS[value[-1]]
        except ValueError:
            return None

    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def fetch(country: str, indicator: str, reference: str) -> dict | None:
    """Scrape la page Trading Economics correspondante et renvoie la dernière publication."""
    url = f"https://tradingeconomics.com/{country}/{indicator}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        response.raise_for_status()

        df = pd.read_html(StringIO(response.text))[0]
        df = df[df["Reference"] == reference]
        df["dt"] = pd.to_datetime(
            df["Calendar"] + " " + df["GMT"],
            format="%Y-%m-%d %I:%M %p",
            errors="coerce",
            utc=True,
        )

        now = pd.Timestamp.now(tz="UTC")
        past = df[df["dt"] <= now]
        future = df[df["dt"] > now]

        result = {
            "country": country,
            "indicator": indicator,
            "reference": reference,
            "release_ts": int(past["dt"].iloc[-1].timestamp()) if not past.empty else None,
            "actual": clean_value(past["Actual"].iloc[-1]) if not past.empty else None,
            "previous": clean_value(past["Previous"].iloc[-1]) if not past.empty else None,
            "consensus": clean_value(past["Consensus"].iloc[-1]) if not past.empty else None,
            "forecast": clean_value(past["TEForecast"].iloc[-1]) if not past.empty else None,
            "next_update_ts": int(future["dt"].iloc[0].timestamp()) if not future.empty else None,
        }
        time.sleep(1)  # rate-limit courtois envers Trading Economics
        return result

    except requests.exceptions.RequestException:
        logger.exception("Erreur HTTP lors du fetch %s/%s", country, indicator)
        return None
    except (ValueError, KeyError, IndexError):
        logger.exception("Erreur de parsing pour %s/%s (format HTML inattendu ?)", country, indicator)
        return None


def data_changed(latest: dict | None, result: dict) -> bool:
    """Renvoie True si au moins une des valeurs clés diffère de la dernière ligne."""
    if not latest:
        return True

    key_fields = ["actual", "previous", "consensus", "forecast"]
    latest_values = tuple(latest.get(field) for field in key_fields)
    result_values = tuple(result.get(field) for field in key_fields)

    # Ne pas écraser une ligne valide par une ligne entièrement vide (pb de scraping).
    if any(v is not None for v in latest_values) and all(v is None for v in result_values):
        return False

    return latest_values != result_values


def get_latest(country: str, indicator: str) -> dict | None:
    return get_latest_indicator(country, indicator)


def get_due() -> list[tuple[str, str, str]]:
    """Liste les (pays, indicateur, reference) qui ont besoin d'être rafraîchis."""
    due: list[tuple[str, str, str]] = []
    now_ts = pd.Timestamp.now(tz="UTC").timestamp()

    for country in COUNTRIES:
        for indicator, reference in COUNTRIES[country].items():
            row = get_latest(country, indicator)
            if row:
                next_update_ts = row.get("next_update_ts")
                if not next_update_ts or next_update_ts < now_ts:
                    due.append((country, indicator, reference))
            else:
                due.append((country, indicator, reference))
    return due


def update_due() -> int:
    due = get_due()

    if not due:
        logger.info("Aucun country_indicator à mettre à jour.")
        return 0

    updated_due = 0

    for country, indicator, reference in due:
        logger.info("[FETCH] %s - %s (%s)", country, indicator, reference)
        result = fetch(country, indicator, reference)

        if not result:
            logger.warning("Impossible de récupérer %s - %s", country, indicator)
            continue

        latest = get_latest(country, indicator)

        if data_changed(latest, result):
            query = """
                INSERT INTO country_indicators
                (country, indicator, reference, actual, consensus, forecast, previous,
                 date_release, next_update_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            execute_write_query(
                query,
                (
                    result["country"], result["indicator"], result["reference"],
                    result["actual"], result["consensus"], result["forecast"], result["previous"],
                    result.get("release_ts"), result.get("next_update_ts"),
                ),
            )
            logger.info(
                "[OK] %s/%s maj : actual=%s consensus=%s forecast=%s",
                country, indicator,
                result["actual"], result["consensus"], result["forecast"],
            )
            updated_due += 1

        elif result["next_update_ts"] and latest and result["next_update_ts"] != latest.get("next_update_ts"):
            execute_write_query(
                "UPDATE country_indicators SET next_update_ts = ? WHERE id = ?",
                (result["next_update_ts"], latest["id"]),
            )
            logger.info("[UPDATE] next_update_ts=%s pour %s/%s", result["next_update_ts"], country, indicator)
        else:
            logger.debug("[SKIP] Pas de changement pour %s/%s", country, indicator)

    if updated_due > 0:
        logger.info("[Z-SCORES] Données économiques modifiées, recalcul des z-scores...")
        update_z_scores()
    else:
        logger.info("[Z-SCORES] Aucune maj économique, z-scores inchangés")

    logger.info("Total mis à jour : %d country_indicator", updated_due)
    return updated_due


if __name__ == "__main__":
    update_due()
