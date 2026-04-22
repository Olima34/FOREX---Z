"""
Formatage des résultats de backtest en texte lisible (markdown).

Fonctions pures : on prend un dict de `BacktestMetrics`, on rend une
string. Pas d'IO. Laisse à l'appelant le choix du canal (print, fichier,
logger).
"""

from __future__ import annotations

from analytics.scripts.backtest import BacktestMetrics


def _fmt_pct(x: float) -> str:
    return "n/a" if x != x else f"{x:+.2%}"  # x != x capture NaN


def _fmt_num(x: float, decimals: int = 3) -> str:
    return "n/a" if x != x else f"{x:+.{decimals}f}"


def format_backtest_report(
    results: dict[str, dict[int, BacktestMetrics]],
) -> str:
    """Rend un rapport markdown : une table par paire, une ligne par horizon."""
    if not results:
        return (
            "Aucune paire ne dispose d'assez de données pour être backtestée.\n"
            "Lancez le pipeline d'ingestion, puis `python -m analytics --update-prices`."
        )

    lines: list[str] = []
    lines.append("# Backtest — pouvoir prédictif des scores FOREX-Z")
    lines.append("")
    lines.append(f"{len(results)} paire(s) analysée(s).")
    lines.append("")

    for pair in sorted(results.keys()):
        horizons = results[pair]
        lines.append(f"## {pair}")
        lines.append("")
        lines.append("| Horizon | N    | IC (Spearman) | Hit rate | Cumul.   | Sharpe | Max DD  |")
        lines.append("|---------|------|---------------|----------|----------|--------|---------|")
        for h in sorted(horizons.keys()):
            m = horizons[h]
            lines.append(
                f"| {h:>2}j    | {m.n_samples:>4} "
                f"| {_fmt_num(m.ic_spearman):>13} "
                f"| {_fmt_pct(m.hit_rate):>8} "
                f"| {_fmt_pct(m.cumulative_return):>8} "
                f"| {_fmt_num(m.sharpe, 2):>6} "
                f"| {_fmt_pct(m.max_drawdown):>7} |"
            )
        lines.append("")

    lines.append("## Lecture")
    lines.append("")
    lines.append(
        "- **IC** > 0.05 sur un grand N suggère un signal exploitable ; "
        "proche de 0 = bruit ; négatif = signal contrariant."
    )
    lines.append(
        "- **Hit rate** > 55% sur >100 obs est un bon indice, à confronter à l'IC."
    )
    lines.append(
        "- **Sharpe** est indicatif : pas de frais, pas de slippage, "
        "pas de gestion de capital."
    )
    return "\n".join(lines)
