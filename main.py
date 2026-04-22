"""
FOREX-Z — boucle d'exécution principale.

Enchaîne les étapes de collecte et de scoring dans un cycle horaire :
1. Indicateurs macro par pays (Trading Economics)
2. Sentiment COT (CFTC)
3. Carry trade (différentiel de taux)
4. Score par (paire, indicateur)
5. Score total par paire (incluant la composante COT)
"""

from economic_data.scripts.carry import update_due as update_carry
from economic_data.scripts.country_indicator import update_due as update_country_indicator
from economic_data.scripts.pair_indicator_score import update_due as update_pair_score
from economic_data.scripts.pair_total_score import update_due as update_pair_total_score
from sentiment.scripts.cot import update as update_cot
from utils.logger import get_logger
from utils.ui import economic_data_loop_with_ui

logger = get_logger("MAIN")


def main() -> None:
    logger.info("=" * 60)
    logger.info("FOREX-Z — STARTING")
    logger.info("=" * 60)

    update_functions = [
        (update_country_indicator, "Country Indicators"),
        (update_cot, "COT Sentiment Analysis"),
        (update_carry, "Carry Calculations"),
        (update_pair_score, "Pair Indicator Scores"),
        (update_pair_total_score, "Pair Total Scores"),
    ]

    try:
        economic_data_loop_with_ui(update_functions)
        logger.info("Boucle principale terminée proprement.")
    except Exception:
        logger.exception("CRASH FATAL dans main.py")


if __name__ == "__main__":
    main()
