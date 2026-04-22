import glob
import json
import os
import sqlite3

DB_PATH = "database/forex_data.db"

def connect_db():
    return sqlite3.connect(DB_PATH)

def migrate_country_indicators():
    print("⏳ Migration des indicateurs économiques...")
    conn = connect_db()
    cursor = conn.cursor()
    count = 0

    # Chercher tous les fichiers JSON dans les sous-dossiers de pays
    paths = glob.glob("economic_data/json/indicator_country/*/*.json")

    for path in paths:
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for row in data:
                        cursor.execute('''
                            INSERT INTO country_indicators 
                            (country, indicator, reference, actual, consensus, forecast, previous, date_release, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row.get('country'),
                            row.get('indicator'),
                            row.get('reference'),
                            row.get('actual'),
                            row.get('consensus'),
                            row.get('forecast'),
                            row.get('previous'),
                            row.get('date'), # Dans ton JSON c'était 'date'
                            row.get('timestamp')
                        ))
                        count += 1
        except Exception as e:
            print(f"⚠️ Erreur sur {path} : {e}")

    conn.commit()
    conn.close()
    print(f"✅ {count} indicateurs importés avec succès.")

def migrate_cot_sentiment():
    print("⏳ Migration du sentiment COT...")
    conn = connect_db()
    cursor = conn.cursor()
    count = 0

    cot_path = "sentiment/json/cot.json"
    if os.path.exists(cot_path):
        with open(cot_path, encoding='utf-8') as f:
            data = json.load(f)
            # Le COT est un dictionnaire avec les paires comme clés
            for key, value in data.items():
                if key != '_metadata' and isinstance(value, dict):
                    cursor.execute('''
                        INSERT INTO cot_sentiment (pair, pair_sentiment)
                        VALUES (?, ?)
                    ''', (
                        value.get('pair', key),
                        value.get('pair_sentiment')
                    ))
                    count += 1

    conn.commit()
    conn.close()
    print(f"✅ {count} données COT importées avec succès.")

def migrate_carry():
    print("⏳ Migration du Carry Trade...")
    conn = connect_db()
    cursor = conn.cursor()
    count = 0

    carry_path = "economic_data/json/carry.json"
    if os.path.exists(carry_path):
        with open(carry_path, encoding='utf-8') as f:
            data = json.load(f)
            for pair_list in data.values():
                if isinstance(pair_list, list):
                    for row in pair_list:
                        cursor.execute('''
                            INSERT INTO carry_trade 
                            (pair, base_country, quote_country, base_actual, quote_actual, carry_value, base_interest_rate_id, quote_interest_rate_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row.get('pair'),
                            row.get('base_country'),
                            row.get('quote_country'),
                            row.get('base_actual'),
                            row.get('quote_actual'),
                            row.get('carry'),
                            row.get('base_interest_rate_id'),
                            row.get('quote_interest_rate_id')
                        ))
                        count += 1

    conn.commit()
    conn.close()
    print(f"✅ {count} données de Carry Trade importées.")

def migrate_total_scores():
    print("⏳ Migration des scores totaux...")
    conn = connect_db()
    cursor = conn.cursor()
    count = 0

    scores_path = "economic_data/json/pair_total_score.json"
    if os.path.exists(scores_path):
        with open(scores_path, encoding='utf-8') as f:
            data = json.load(f)
            for pair_list in data.values():
                if isinstance(pair_list, list):
                    for row in pair_list:
                        # Les scores et IDs sont déjà des strings JSON selon ton script actuel
                        cursor.execute('''
                            INSERT INTO pair_total_scores 
                            (pair, total_score, indicator_scores_json, indicator_ids_json)
                            VALUES (?, ?, ?, ?)
                        ''', (
                            row.get('pair'),
                            row.get('total_score'),
                            row.get('indicator_scores'),
                            row.get('indicator_ids')
                        ))
                        count += 1

    conn.commit()
    conn.close()
    print(f"✅ {count} scores totaux importés.")

if __name__ == "__main__":
    print("🚀 Début de la migration des JSON vers SQLite...\n")
    migrate_country_indicators()
    migrate_cot_sentiment()
    migrate_carry()
    migrate_total_scores()
    print("\n🎉 Migration terminée avec succès !")
