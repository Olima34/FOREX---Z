"""Tests du formatteur de rapport de backtest."""

from __future__ import annotations

from analytics.scripts.backtest import BacktestMetrics
from analytics.scripts.report import format_backtest_report


def test_report_is_empty_message_when_no_results():
    text = format_backtest_report({})
    assert "Aucune paire" in text


def test_report_contains_pair_and_horizon_rows():
    results = {
        "EURUSD": {
            1: BacktestMetrics(
                pair="EURUSD",
                horizon_days=1,
                n_samples=42,
                ic_spearman=0.12,
                hit_rate=0.58,
                cumulative_return=0.035,
                sharpe=0.7,
                max_drawdown=-0.08,
            ),
            5: BacktestMetrics(
                pair="EURUSD",
                horizon_days=5,
                n_samples=40,
                ic_spearman=0.04,
                hit_rate=0.51,
                cumulative_return=0.01,
                sharpe=0.15,
                max_drawdown=-0.12,
            ),
        }
    }
    text = format_backtest_report(results)
    assert "## EURUSD" in text
    assert "| 1j" in text or " 1j " in text
    assert " 5j" in text
    assert "42" in text  # n_samples ligne 1
    # Les pourcentages sont bien formatés (avec signe).
    assert "+3.50%" in text or "+3.50 %" in text or "+0.035" in text or "+3.5" in text


def test_report_handles_nan_values():
    # Sur un échantillon trop petit, certaines métriques sont NaN : doit rendre "n/a".
    results = {
        "EURUSD": {
            1: BacktestMetrics(
                pair="EURUSD",
                horizon_days=1,
                n_samples=3,
                ic_spearman=float("nan"),
                hit_rate=float("nan"),
                cumulative_return=0.0,
                sharpe=float("nan"),
                max_drawdown=0.0,
            )
        }
    }
    text = format_backtest_report(results)
    assert "n/a" in text
