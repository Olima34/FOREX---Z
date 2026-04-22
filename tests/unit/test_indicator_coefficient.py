"""Tests pour `_get_indicator_coefficient`."""

from __future__ import annotations

from maths_stats.z_score_calculation import _get_indicator_coefficient
from utils.parametres import DEFAULT_INDICATOR_COEFFICIENT, INDICATOR_COEFFICIENTS


def test_direct_lookup():
    assert _get_indicator_coefficient("gdp-growth") == INDICATOR_COEFFICIENTS["gdp-growth"]


def test_underscore_to_dash_fallback():
    assert _get_indicator_coefficient("gdp_growth") == INDICATOR_COEFFICIENTS["gdp-growth"]


def test_unknown_indicator_returns_default():
    assert _get_indicator_coefficient("some-unknown-indicator") == DEFAULT_INDICATOR_COEFFICIENT
