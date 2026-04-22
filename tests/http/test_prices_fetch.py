"""
Tests pour `analytics.scripts.prices`.

On monkey-patche `_download_prices` plutôt que de mocker yfinance au
niveau HTTP : c'est la frontière d'IO du module et ça évite d'ajouter
yfinance comme dépendance dure à la suite de tests.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from analytics.scripts import prices as prices_mod
from utils.gestion_db import execute_read_query

pytestmark = [pytest.mark.http, pytest.mark.integration]


def _fake_prices_df(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [f"2025-01-{i + 1:02d}" for i in range(n)],
            "close": [1.1 + 0.001 * i for i in range(n)],
        }
    )


def test_update_prices_inserts_rows(temp_db, monkeypatch):
    captured: dict = {}

    def fake_download(ticker: str, start: date, end: date) -> pd.DataFrame:
        captured["ticker"] = ticker
        captured["start"] = start
        captured["end"] = end
        return _fake_prices_df(5)

    monkeypatch.setattr(prices_mod, "_download_prices", fake_download)

    n = prices_mod.update_prices_for_pair("EURUSD", history_days=30)
    assert n == 5
    assert captured["ticker"] == "EURUSD=X"

    rows = execute_read_query("SELECT date, close FROM fx_prices WHERE pair = 'EURUSD'")
    assert len(rows) == 5
    assert rows[0]["date"] == "2025-01-01"
    assert rows[0]["close"] == pytest.approx(1.1)


def test_update_prices_is_idempotent(temp_db, monkeypatch):
    monkeypatch.setattr(prices_mod, "_download_prices", lambda *_a, **_kw: _fake_prices_df(3))

    assert prices_mod.update_prices_for_pair("EURUSD") == 3
    # Deuxième passe : UNIQUE(pair, date) → 0 nouvelle ligne.
    assert prices_mod.update_prices_for_pair("EURUSD") == 0
    rows = execute_read_query("SELECT COUNT(*) AS n FROM fx_prices")
    assert rows[0]["n"] == 3


def test_update_prices_returns_zero_for_unknown_pair(temp_db, monkeypatch):
    # Si le download n'est pas appelé, ça prouve qu'on court-circuite avant.
    monkeypatch.setattr(
        prices_mod, "_download_prices",
        lambda *_a, **_kw: pytest.fail("download should not be called"),
    )
    assert prices_mod.update_prices_for_pair("ZZZXYZ") == 0


def test_update_prices_handles_empty_download(temp_db, monkeypatch):
    monkeypatch.setattr(
        prices_mod, "_download_prices",
        lambda *_a, **_kw: pd.DataFrame(columns=["date", "close"]),
    )
    assert prices_mod.update_prices_for_pair("EURUSD") == 0


def test_update_prices_handles_download_exception(temp_db, monkeypatch):
    def boom(*_a, **_kw):
        raise RuntimeError("yfinance is down")

    monkeypatch.setattr(prices_mod, "_download_prices", boom)
    # On ne veut pas que le pipeline crash : l'erreur est logguée et on renvoie 0.
    assert prices_mod.update_prices_for_pair("EURUSD") == 0


def test_get_prices_returns_sorted_dataframe(temp_db, monkeypatch):
    # On insère volontairement dans le désordre.
    from utils.gestion_db import execute_write_query

    execute_write_query(
        "INSERT INTO fx_prices (pair, date, close) VALUES (?, ?, ?)",
        ("EURUSD", "2025-01-03", 1.103),
    )
    execute_write_query(
        "INSERT INTO fx_prices (pair, date, close) VALUES (?, ?, ?)",
        ("EURUSD", "2025-01-01", 1.101),
    )
    execute_write_query(
        "INSERT INTO fx_prices (pair, date, close) VALUES (?, ?, ?)",
        ("EURUSD", "2025-01-02", 1.102),
    )

    df = prices_mod.get_prices("EURUSD")
    assert len(df) == 3
    assert list(df["close"]) == pytest.approx([1.101, 1.102, 1.103])
    # La colonne date doit être parsée en Timestamp pour permettre merge_asof.
    assert pd.api.types.is_datetime64_any_dtype(df["date"])


def test_get_prices_empty_when_no_data(temp_db):
    df = prices_mod.get_prices("EURUSD")
    assert df.empty
    assert list(df.columns) == ["date", "close"]
