"""
Fixtures globales pour la suite de tests.

`temp_db` crée une base SQLite jetable et la substitue à la DB réelle en
monkey-patchant `utils.gestion_db.DB_PATH`. Comme tous les scripts du
projet appellent `get_connection()` (qui lit `DB_PATH` au runtime), ce
patch suffit à isoler complètement les tests de la DB de production.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures_data"


def _apply_schema(conn: sqlite3.Connection) -> None:
    """Crée toutes les tables du projet sur la connexion fournie."""
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS country_indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            indicator TEXT NOT NULL,
            reference TEXT,
            actual REAL,
            consensus REAL,
            forecast REAL,
            previous REAL,
            date_release TEXT,
            next_update_ts INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cot_sentiment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            pair_sentiment REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS carry_trade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            base_country TEXT NOT NULL,
            quote_country TEXT NOT NULL,
            base_actual REAL,
            quote_actual REAL,
            carry_value REAL,
            base_interest_rate_id INTEGER,
            quote_interest_rate_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pair_total_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            total_score REAL NOT NULL,
            indicator_scores_json TEXT,
            indicator_ids_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

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
        );

        CREATE TABLE IF NOT EXISTS fx_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL NOT NULL,
            UNIQUE(pair, date)
        );

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
        );
        """
    )
    conn.commit()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """
    Crée une DB SQLite vide avec le schéma complet du projet et
    redirige `utils.gestion_db.DB_PATH` vers elle.

    Yielde le chemin de la DB (Path) — les tests qui veulent insérer
    des données peuvent appeler les helpers du projet directement.
    """
    db_path = tmp_path / "test_forex.db"

    conn = sqlite3.connect(db_path)
    _apply_schema(conn)
    conn.close()

    import utils.gestion_db as gestion_db

    monkeypatch.setattr(gestion_db, "DB_PATH", db_path)
    yield db_path


@pytest.fixture
def fixtures_dir() -> Path:
    """Répertoire des fichiers HTML/CSV utilisés par les tests HTTP."""
    return FIXTURES_DIR
