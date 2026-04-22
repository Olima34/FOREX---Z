"""
Tests pour `pair_indicator_score.calculate_indicator_score`.

Le score est testé SANS pondération z-score (country=None) pour isoler la
logique de comparaison actual vs reference.
"""

from __future__ import annotations

from economic_data.scripts.pair_indicator_score import calculate_indicator_score


def test_actual_above_consensus_returns_positive():
    assert calculate_indicator_score(1.2, 1.0, None, "gdp-growth") == 1


def test_actual_below_consensus_returns_negative():
    assert calculate_indicator_score(0.8, 1.0, None, "gdp-growth") == -1


def test_actual_equal_to_consensus_returns_zero():
    assert calculate_indicator_score(1.0, 1.0, None, "gdp-growth") == 0


def test_none_actual_returns_zero():
    assert calculate_indicator_score(None, 1.0, None, "gdp-growth") == 0


def test_none_consensus_falls_back_to_forecast():
    # consensus None -> on utilise forecast. actual > forecast -> 1.
    assert calculate_indicator_score(1.5, None, 1.2, "gdp-growth") == 1


def test_no_reference_at_all_returns_zero():
    assert calculate_indicator_score(1.5, None, None, "gdp-growth") == 0


def test_bad_indicator_flips_the_sign():
    """`unemployment-rate` est un 'bad indicator' : hausse = négatif."""
    # actual 6.0 > consensus 5.5 -> brut +1 -> flipped à -1
    assert calculate_indicator_score(6.0, 5.5, None, "unemployment-rate") == -1
    # actual 5.0 < consensus 5.5 -> brut -1 -> flipped à +1
    assert calculate_indicator_score(5.0, 5.5, None, "unemployment-rate") == 1
