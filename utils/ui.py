"""
Affichage console de la boucle principale + orchestrateur de cycle.

On garde `print()` pour les en-têtes/séparateurs purement visuels (console
uniquement), mais toutes les informations d'état passent par le logger
pour être archivées dans le fichier de log.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime

from utils.logger import get_logger
from utils.parametres import MAIN_LOOP_ERROR_BACKOFF_SECONDS, MAIN_LOOP_INTERVAL_SECONDS

logger = get_logger("UI")


class ForexUI:
    """Mise en forme de la sortie console pour la boucle FOREX."""

    @staticmethod
    def print_cycle_header(cycle_count: int) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n┌─ CYCLE #{cycle_count} - {timestamp} ─┐")

    @staticmethod
    def print_step_header(step_number: int, total_steps: int, step_name: str) -> None:
        print("│")
        print(f"├─ [{step_number}/{total_steps}] {step_name}...")

    @staticmethod
    def print_cycle_completed() -> None:
        print("│")
        print("└─ CYCLE COMPLETED ─────────────────────────────────────┘")

    @staticmethod
    def print_waiting_message() -> None:
        minutes = MAIN_LOOP_INTERVAL_SECONDS // 60
        print(f"\nWAITING — prochaine maj dans {minutes} min (Ctrl+C pour arrêter)")
        print("─" * 60)


def run_economic_cycle(cycle_count: int, update_functions: list[tuple[Callable[[], int], str]]) -> None:
    ui = ForexUI()
    ui.print_cycle_header(cycle_count)
    logger.info("Démarrage du cycle #%d", cycle_count)

    total_steps = len(update_functions)
    for i, (update_func, step_name) in enumerate(update_functions, 1):
        ui.print_step_header(i, total_steps, step_name)
        logger.info("[%d/%d] %s", i, total_steps, step_name)
        try:
            update_func()
        except Exception:
            logger.exception("Étape '%s' a levé une exception", step_name)

    ui.print_cycle_completed()
    logger.info("Cycle #%d terminé", cycle_count)
    ui.print_waiting_message()


def economic_data_loop_with_ui(update_functions: list[tuple[Callable[[], int], str]]) -> None:
    cycle_count = 1

    while True:
        try:
            run_economic_cycle(cycle_count, update_functions)
            time.sleep(MAIN_LOOP_INTERVAL_SECONDS)
            cycle_count += 1
        except KeyboardInterrupt:
            logger.info("Arrêt manuel (Ctrl+C)")
            print("\nShutdown demandé — arrêt propre.")
            break
        except Exception:
            logger.exception("Erreur non gérée dans la boucle principale")
            print(f"\nErreur — nouvelle tentative dans {MAIN_LOOP_ERROR_BACKOFF_SECONDS // 60} min.")
            time.sleep(MAIN_LOOP_ERROR_BACKOFF_SECONDS)
