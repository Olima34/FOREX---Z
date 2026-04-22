"""Tests pour `country_indicator.data_changed`."""

from __future__ import annotations

from economic_data.scripts.country_indicator import data_changed


def _result(actual=0.5, previous=0.4, consensus=0.45, forecast=0.4):
    return {
        "actual": actual,
        "previous": previous,
        "consensus": consensus,
        "forecast": forecast,
    }


def test_no_previous_row_means_change():
    assert data_changed(None, _result()) is True


def test_identical_values_means_no_change():
    latest = _result()
    assert data_changed(latest, _result()) is False


def test_changed_actual_detected():
    latest = _result(actual=0.5)
    assert data_changed(latest, _result(actual=0.6)) is True


def test_empty_result_does_not_overwrite_valid_latest():
    """Une ligne entièrement None ne doit pas écraser une ligne valide."""
    latest = _result()
    empty = {"actual": None, "previous": None, "consensus": None, "forecast": None}
    assert data_changed(latest, empty) is False


def test_first_real_value_after_none_is_change():
    latest = {"actual": None, "previous": None, "consensus": None, "forecast": None}
    assert data_changed(latest, _result()) is True
