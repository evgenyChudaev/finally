"""Tests for positions_repo."""

from __future__ import annotations

import pytest

from app.db.positions_repo import (
    delete_position,
    get_position,
    list_positions,
    upsert_position,
)


class TestUpsertPosition:
    def test_insert(self, db_path):
        pos = upsert_position("AAPL", 10.0, 190.0)
        assert pos.ticker == "AAPL"
        assert pos.quantity == 10.0
        assert pos.avg_cost == 190.0
        assert pos.id > 0

    def test_update_keeps_single_row(self, db_path):
        upsert_position("AAPL", 10.0, 190.0)
        pos2 = upsert_position("AAPL", 20.0, 195.0)
        assert pos2.quantity == 20.0
        assert pos2.avg_cost == 195.0
        all_positions = list_positions()
        assert len(all_positions) == 1

    def test_normalizes_ticker(self, db_path):
        pos = upsert_position("  aapl  ", 5.0, 100.0)
        assert pos.ticker == "AAPL"

    def test_rejects_empty_ticker(self, db_path):
        with pytest.raises(ValueError):
            upsert_position("", 5.0, 100.0)

    def test_rejects_negative_quantity(self, db_path):
        with pytest.raises(ValueError):
            upsert_position("AAPL", -1.0, 100.0)

    def test_rejects_negative_avg_cost(self, db_path):
        with pytest.raises(ValueError):
            upsert_position("AAPL", 1.0, -100.0)

    def test_zero_quantity_allowed(self, db_path):
        # Zero is legal — callers can choose to call delete_position instead,
        # but a closed position with quantity 0 is not a logic error here.
        pos = upsert_position("AAPL", 0.0, 0.0)
        assert pos.quantity == 0.0


class TestGetPosition:
    def test_missing_returns_none(self, db_path):
        assert get_position("AAPL") is None

    def test_get(self, db_path):
        upsert_position("AAPL", 10.0, 190.0)
        pos = get_position("AAPL")
        assert pos is not None
        assert pos.quantity == 10.0

    def test_get_case_insensitive(self, db_path):
        upsert_position("AAPL", 10.0, 190.0)
        assert get_position("aapl") is not None


class TestListPositions:
    def test_empty(self, db_path):
        assert list_positions() == []

    def test_sorted_by_ticker(self, db_path):
        upsert_position("MSFT", 5.0, 400.0)
        upsert_position("AAPL", 10.0, 190.0)
        upsert_position("GOOGL", 2.0, 175.0)
        positions = list_positions()
        assert [p.ticker for p in positions] == ["AAPL", "GOOGL", "MSFT"]


class TestDeletePosition:
    def test_delete(self, db_path):
        upsert_position("AAPL", 10.0, 190.0)
        assert delete_position("AAPL") is True
        assert get_position("AAPL") is None

    def test_delete_missing(self, db_path):
        assert delete_position("AAPL") is False

    def test_delete_normalizes(self, db_path):
        upsert_position("AAPL", 10.0, 190.0)
        assert delete_position("aapl") is True
