"""Tests for watchlist_repo."""

from __future__ import annotations

import pytest

from app.db.database import DEFAULT_WATCHLIST_TICKERS
from app.db.watchlist_repo import (
    add_ticker,
    has_ticker,
    list_tickers,
    remove_ticker,
)


class TestListTickers:
    def test_returns_seeded(self, db_path):
        entries = list_tickers()
        tickers = [e.ticker for e in entries]
        assert tickers == list(DEFAULT_WATCHLIST_TICKERS)
        # Insertion order is preserved (ascending id).
        ids = [e.id for e in entries]
        assert ids == sorted(ids)


class TestHasTicker:
    def test_yes(self, db_path):
        assert has_ticker("AAPL")
        assert has_ticker("aapl")  # case-insensitive

    def test_no(self, db_path):
        assert not has_ticker("PYPL")


class TestAddTicker:
    def test_add(self, db_path):
        entry = add_ticker("PYPL")
        assert entry.ticker == "PYPL"
        assert entry.added_at.endswith("Z")
        assert has_ticker("PYPL")

    def test_add_normalizes(self, db_path):
        entry = add_ticker("  pypl  ")
        assert entry.ticker == "PYPL"

    def test_duplicate_raises_keyerror(self, db_path):
        with pytest.raises(KeyError) as exc:
            add_ticker("AAPL")
        assert exc.value.args[0] == "AAPL"

    def test_empty_raises_valueerror(self, db_path):
        with pytest.raises(ValueError):
            add_ticker("   ")


class TestRemoveTicker:
    def test_remove_existing(self, db_path):
        assert remove_ticker("AAPL") is True
        assert not has_ticker("AAPL")

    def test_remove_normalizes(self, db_path):
        assert remove_ticker("aapl") is True
        assert not has_ticker("AAPL")

    def test_remove_missing(self, db_path):
        assert remove_ticker("ZZZZ") is False
