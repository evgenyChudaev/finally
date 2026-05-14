"""Tests for profile_repo."""

from __future__ import annotations

import pytest

from app.db import get_connection
from app.db.database import DEFAULT_CASH_BALANCE
from app.db.profile_repo import get_profile, set_cash, update_cash


class TestGetProfile:
    def test_returns_seeded_profile(self, db_path):
        profile = get_profile()
        assert profile.id == 1
        assert profile.cash_balance == DEFAULT_CASH_BALANCE
        assert profile.created_at.endswith("Z")

    def test_recreates_missing_row(self, db_path):
        # Pathological: delete the singleton, then expect get_profile to
        # reinsert it with defaults.
        with get_connection() as conn:
            conn.execute("DELETE FROM users_profile")
        profile = get_profile()
        assert profile.cash_balance == DEFAULT_CASH_BALANCE


class TestUpdateCash:
    def test_positive_delta(self, db_path):
        new = update_cash(500.0)
        assert new == DEFAULT_CASH_BALANCE + 500.0
        assert get_profile().cash_balance == new

    def test_negative_delta(self, db_path):
        new = update_cash(-2500.0)
        assert new == DEFAULT_CASH_BALANCE - 2500.0

    def test_rejects_negative_balance(self, db_path):
        with pytest.raises(ValueError):
            update_cash(-(DEFAULT_CASH_BALANCE + 1))
        # Balance unchanged after the rejected attempt.
        assert get_profile().cash_balance == DEFAULT_CASH_BALANCE

    def test_zero_delta(self, db_path):
        new = update_cash(0.0)
        assert new == DEFAULT_CASH_BALANCE


class TestSetCash:
    def test_set_cash(self, db_path):
        assert set_cash(42.5) == 42.5
        assert get_profile().cash_balance == 42.5

    def test_rejects_negative(self, db_path):
        with pytest.raises(ValueError):
            set_cash(-1.0)
