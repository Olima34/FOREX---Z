import os
import sqlite3

# Chemin vers notre future base de données
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "forex_data.db")

def create_database():
    """Crée la base de données SQLite et les tables nécessaires."""

    # S'assurer que le dossier existe
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        print(f"📁 Dossier {DB_DIR} créé.")

    # Se connecter à la base (cela crée le fichier s'il n'existe pas)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🏗️ Création des tables en cours...")

    # 1. Table pour les indicateurs économiques des pays
    cursor.execute('''
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
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 2. Table pour le sentiment COT
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cot_sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT NOT NULL,
        pair_sentiment REAL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 3. Table pour le calcul du Carry Trade
    cursor.execute('''
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
    )
    ''')

    # 4. Table pour les scores totaux des paires
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pair_total_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT NOT NULL,
        total_score REAL NOT NULL,
        indicator_scores_json TEXT,  -- On stocke le dictionnaire en texte JSON pour simplifier
        indicator_ids_json TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 5. Table pour l'historique des prix FX (alimentée par le module analytics)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS fx_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT NOT NULL,
        date TEXT NOT NULL,
        close REAL NOT NULL,
        UNIQUE(pair, date)
    )
    ''')

    # Valider et fermer la connexion
    conn.commit()
    conn.close()

    print(f"✅ Base de données initialisée avec succès dans : {DB_PATH}")

if __name__ == "__main__":
    create_database()
