"""Tests pour `cot.calculate_cot_net_change` et `_parse_sqlite_timestamp`."""

from __future__ import annotations

from datetime import datetime

import pytest

from sentiment.scripts.cot import _parse_sqlite_timestamp, calculate_cot_net_change


def test_net_change_positive_when_longs_gain_share():
    row = {
        "Noncommercial_Positions_Long_All": 110.0,
        "Noncommercial_Positions_Short_All": 90.0,
        "Change_in_Noncommercial_Long_All": 10.0,
        "Change_in_Noncommercial_Short_All": -10.0,
    }
    # avant : long=100 short=100 -> 50%. Maintenant : long=110 short=90 -> 55%.
    assert calculate_cot_net_change(row) == pytest.approx(5.0)


def test_net_change_negative_when_shorts_gain_share():
    row = {
        "Noncommercial_Positions_Long_All": 90.0,
        "Noncommercial_Positions_Short_All": 110.0,
        "Change_in_Noncommercial_Long_All": -10.0,
        "Change_in_Noncommercial_Short_All": 10.0,
    }
    assert calculate_cot_net_change(row) == pytest.approx(-5.0)


def test_net_change_zero_when_no_change():
    row = {
        "Noncommercial_Positions_Long_All": 100.0,
        "Noncommercial_Positions_Short_All": 100.0,
        "Change_in_Noncommercial_Long_All": 0.0,
        "Change_in_Noncommercial_Short_All": 0.0,
    }
    assert calculate_cot_net_change(row) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "value",
    [
        "2026-04-22 15:30:00",  # format SQLite classique
        "2026-04-22T15:30:00",  # ISO
    ],
)
def test_parse_sqlite_timestamp_accepts_both_formats(value):
    assert _parse_sqlite_timestamp(value) == datetime(2026, 4, 22, 15, 30, 0)


def test_parse_sqlite_timestamp_returns_none_on_garbage():
    assert _parse_sqlite_timestamp("not-a-date") is None
