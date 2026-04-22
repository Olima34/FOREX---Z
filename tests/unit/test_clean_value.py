"""Tests pour `country_indicator.clean_value` — parsing des valeurs TE."""

from __future__ import annotations

import pytest

from economic_data.scripts.country_indicator import clean_value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.5%", 1.5),
        ("-0.3%", -0.3),
        ("$1.5B", 1.5e9),
        ("2M", 2e6),
        ("500K", 500e3),
        ("€1,234.56", 1234.56),
        ("1,000", 1000.0),
        ("0", 0.0),
    ],
)
def test_clean_value_parses_common_formats(raw, expected):
    assert clean_value(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", float("nan"), 42, object()])
def test_clean_value_rejects_non_string_or_unparseable(raw):
    assert clean_value(raw) is None


def test_clean_value_strips_currency_symbols():
    assert clean_value("CHF1.25") == pytest.approx(1.25)
    assert clean_value("¥100") == pytest.approx(100.0)
