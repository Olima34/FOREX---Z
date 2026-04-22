"""
CLI du module analytics.

Utilisation :
    python -m analytics                       # backtest toutes les paires
    python -m analytics --pair EURUSD         # backtest une paire
    python -m analytics --update-prices       # (ré)ingère les prix avant
    python -m analytics --horizons 1 5 20     # horizons custom (jours)
"""

from __future__ import annotations

import argparse
import sys

from analytics.scripts.backtest import DEFAULT_HORIZONS, run_backtest
from analytics.scripts.prices import update_all_prices, update_prices_for_pair
from analytics.scripts.report import format_backtest_report
from config import PAIRS
from utils.logger import get_logger

logger = get_logger("ANALYTICS_CLI")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m analytics",
        description="Backtest des scores macro FOREX-Z vs prix FX historiques.",
    )
    p.add_argument(
        "--pair",
        action="append",
        default=None,
        help="Paire à analyser (peut être répété). Par défaut, toutes.",
    )
    p.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=list(DEFAULT_HORIZONS),
        help="Horizons en jours de trading. Défaut : 1 5 20.",
    )
    p.add_argument(
        "--update-prices",
        action="store_true",
        help="Télécharge/actualise les prix FX via yfinance avant le backtest.",
    )
    p.add_argument(
        "--history-days",
        type=int,
        default=365 * 5,
        help="Nombre de jours d'historique à télécharger (défaut : 5 ans).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    pairs = args.pair if args.pair else None

    if args.update_prices:
        if pairs is None:
            logger.info("Mise à jour des prix pour toutes les paires...")
            n = update_all_prices(history_days=args.history_days)
        else:
            n = 0
            for pair in pairs:
                if pair not in PAIRS:
                    logger.error("Paire inconnue : %s", pair)
                    continue
                n += update_prices_for_pair(pair, history_days=args.history_days)
        logger.info("Prix mis à jour : %d nouvelles lignes", n)

    results = run_backtest(pairs=pairs, horizons=tuple(args.horizons))
    print(format_backtest_report(results))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
