"""
Logger centralisé du projet FOREX-Z.

Chaque module appelle `get_logger("NOM_MODULE")` et obtient un logger qui écrit
simultanément dans la console et dans `logs/forex_bot.log` (avec rotation).

Le niveau de log peut être surchargé via la variable d'environnement
`FOREX_LOG_LEVEL` (ex: DEBUG, INFO, WARNING).
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "forex_bot.log"

_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _resolve_level(env_var: str, default: str) -> int:
    value = os.environ.get(env_var, default).upper()
    if value not in _LEVELS:
        value = default
    return getattr(logging, value)


def get_logger(nom_module: str) -> logging.Logger:
    """
    Retourne un logger configuré (console + fichier avec rotation).

    - Console : niveau contrôlé par FOREX_LOG_LEVEL (défaut INFO).
    - Fichier : niveau contrôlé par FOREX_FILE_LOG_LEVEL (défaut DEBUG),
      rotation à 5 MB, 5 fichiers d'historique.
    """
    logger = logging.getLogger(nom_module)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(_resolve_level("FOREX_LOG_LEVEL", "INFO"))
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(_resolve_level("FOREX_FILE_LOG_LEVEL", "DEBUG"))
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger
