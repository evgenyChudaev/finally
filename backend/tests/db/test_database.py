"""Tests for the database init / connection plumbing."""

from __future__ import annotations

import sqlite3

import pytest

from app.db import get_connection, init_db
from app.db.database import (
    DEFAULT_CASH_BALANCE,
    DEFAULT_WATCHLIST_TICKERS,
    _watchlist_from_env,
    utc_now_iso,
)


class TestUtcNowIso:
    def test_format_ends_with_z(self):
        ts = utc_now_iso()
        assert ts.endswith("Z")
        assert "+00:00" not in ts

    def test_round_trip_parses(self):
        from datetime import datetime

        ts = utc_now_iso()
        # Strip Z, add UTC offset, parse.
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None


class TestInitDb:
    def test_init_creates_tables(self, empty_db_path):
        init_db()
        with get_connection() as conn:
            names = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        for table in (
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        ):
            assert table in names, f"missing table {table}"

    def test_init_creates_indices(self, empty_db_path):
        init_db()
        with get_connection() as conn:
            names = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
        assert "idx_trades_executed_at" in names
        assert "idx_chat_messages_created_at" in names

    def test_init_seeds_default_profile(self, empty_db_path):
        init_db()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, cash_balance, created_at FROM users_profile"
            ).fetchone()
        assert row is not None
        assert row["id"] == 1
        assert row["cash_balance"] == DEFAULT_CASH_BALANCE
        assert row["created_at"].endswith("Z")

    def test_init_seeds_default_watchlist(self, empty_db_path):
        init_db()
        with get_connection() as conn:
            rows = conn.execute("SELECT ticker FROM watchlist ORDER BY id").fetchall()
        tickers = [r["ticker"] for r in rows]
        assert tickers == list(DEFAULT_WATCHLIST_TICKERS)

    def test_init_is_idempotent(self, empty_db_path):
        init_db()
        init_db()
        init_db()
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM watchlist").fetchone()["n"]
            profile_count = conn.execute(
                "SELECT COUNT(*) AS n FROM users_profile"
            ).fetchone()["n"]
        assert count == len(DEFAULT_WATCHLIST_TICKERS)
        assert profile_count == 1

    def test_init_preserves_existing_data(self, empty_db_path):
        # First init, then mutate state, then init again -> mutation survives.
        init_db()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO watchlist (ticker, added_at) VALUES (?, ?)",
                ("PYPL", utc_now_iso()),
            )
            conn.execute("UPDATE users_profile SET cash_balance = 12345.67 WHERE id = 1")
        init_db()
        with get_connection() as conn:
            cash = conn.execute(
                "SELECT cash_balance FROM users_profile"
            ).fetchone()["cash_balance"]
            tickers = {r["ticker"] for r in conn.execute("SELECT ticker FROM watchlist")}
        assert cash == 12345.67
        assert "PYPL" in tickers

    def test_default_watchlist_env_override(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DEFAULT_WATCHLIST", "spy, qqq, dia ,, AAPL")
        init_db()
        with get_connection() as conn:
            rows = conn.execute("SELECT ticker FROM watchlist ORDER BY id").fetchall()
        tickers = [r["ticker"] for r in rows]
        assert tickers == ["SPY", "QQQ", "DIA", "AAPL"]

    def test_default_watchlist_env_empty_falls_back(self, empty_db_path, monkeypatch):
        monkeypatch.setenv("DEFAULT_WATCHLIST", "   ")
        init_db()
        with get_connection() as conn:
            rows = conn.execute("SELECT ticker FROM watchlist ORDER BY id").fetchall()
        assert [r["ticker"] for r in rows] == list(DEFAULT_WATCHLIST_TICKERS)

    def test_watchlist_from_env_dedupes(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_WATCHLIST", "AAPL,aapl,MSFT,AAPL")
        assert _watchlist_from_env() == ["AAPL", "MSFT"]


class TestSingletonProfile:
    def test_cannot_insert_second_profile_row(self, db_path):
        with pytest.raises(sqlite3.IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO users_profile (id, cash_balance, created_at) "
                    "VALUES (2, 100.0, ?)",
                    (utc_now_iso(),),
                )


class TestConnection:
    def test_foreign_keys_on(self, db_path):
        with get_connection() as conn:
            result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

    def test_row_factory_yields_mapping_access(self, db_path):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = 1"
            ).fetchone()
        assert row["cash_balance"] == DEFAULT_CASH_BALANCE

    def test_rollback_on_exception(self, db_path):
        with pytest.raises(RuntimeError):
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO watchlist (ticker, added_at) VALUES (?, ?)",
                    ("ROLLBACK_TEST", utc_now_iso()),
                )
                raise RuntimeError("boom")
        # The row should not be present after the rollback.
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS n FROM watchlist WHERE ticker = 'ROLLBACK_TEST'"
            ).fetchone()["n"]
        assert count == 0


class TestDbPath:
    def test_env_var_override(self, tmp_path, monkeypatch):
        from app.db import reset_db_path_for_tests
        from app.db.database import get_db_path

        reset_db_path_for_tests(None)  # clear any test override
        custom = tmp_path / "custom.db"
        monkeypatch.setenv("DB_PATH", str(custom))
        resolved = get_db_path()
        assert resolved == custom.resolve()
        assert custom.parent.exists()

    def test_default_path_contains_db_dir(self, monkeypatch):
        from app.db import reset_db_path_for_tests
        from app.db.database import get_db_path

        reset_db_path_for_tests(None)
        monkeypatch.delenv("DB_PATH", raising=False)
        resolved = get_db_path()
        assert resolved.name == "finally.db"
        assert resolved.parent.name == "db"
