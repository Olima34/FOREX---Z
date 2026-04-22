"""
Fin wrapper autour de `sqlite3` pour le projet FOREX-Z.

- Chemin absolu vers la base (indépendant du CWD).
- `row_factory = sqlite3.Row` pour exposer les résultats sous forme de dict.
- Les erreurs sont loguées (stacktrace complète) puis retournées comme
  `[]` / `None` pour que le pipeline continue de tourner.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger("DB_MANAGER")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "forex_data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def execute_read_query(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        logger.exception("Erreur de lecture DB | Requête: %s", query)
        return []
    finally:
        conn.close()


def execute_write_query(query: str, params: tuple = ()) -> int | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        logger.exception("Erreur d'écriture DB | Requête: %s", query)
        return None
    finally:
        conn.close()


def get_latest_indicator(country: str, indicator: str) -> dict[str, Any] | None:
    # Tri par `id DESC` en tie-breaker : deux INSERTs sur la même seconde
    # partagent `CURRENT_TIMESTAMP` mais ont forcément des id distincts.
    query = (
        "SELECT * FROM country_indicators "
        "WHERE country = ? AND indicator = ? "
        "ORDER BY timestamp DESC, id DESC LIMIT 1"
    )
    results = execute_read_query(query, (country, indicator))
    return results[0] if results else None


def get_cot_sentiment(pair: str) -> dict[str, Any] | None:
    query = (
        "SELECT * FROM cot_sentiment "
        "WHERE pair = ? ORDER BY timestamp DESC, id DESC LIMIT 1"
    )
    results = execute_read_query(query, (pair,))
    return results[0] if results else None
