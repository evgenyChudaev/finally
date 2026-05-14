"""Watchlist repository."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .database import get_connection, utc_now_iso


@dataclass(frozen=True, slots=True)
class WatchlistEntry:
    """One row of the watchlist table."""

    id: int
    ticker: str
    added_at: str


def _normalize(ticker: str) -> str:
    return ticker.strip().upper()


def list_tickers() -> list[WatchlistEntry]:
    """Return all watchlist entries in insertion order (oldest first)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, ticker, added_at FROM watchlist ORDER BY id ASC"
        ).fetchall()
    return [
        WatchlistEntry(id=r["id"], ticker=r["ticker"], added_at=r["added_at"]) for r in rows
    ]


def has_ticker(ticker: str) -> bool:
    """Return True if the ticker is on the watchlist."""
    normalized = _normalize(ticker)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM watchlist WHERE ticker = ? LIMIT 1", (normalized,)
        ).fetchone()
    return row is not None


def add_ticker(ticker: str) -> WatchlistEntry:
    """Add a ticker to the watchlist.

    Raises `ValueError` if the ticker is empty, or `KeyError` with the
    normalized ticker if it is already on the watchlist (maps cleanly to the
    `TICKER_ALREADY_WATCHED` API error).
    """
    normalized = _normalize(ticker)
    if not normalized:
        raise ValueError("ticker cannot be empty")

    now = utc_now_iso()
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO watchlist (ticker, added_at) VALUES (?, ?)",
                (normalized, now),
            )
        except sqlite3.IntegrityError as exc:
            raise KeyError(normalized) from exc
        new_id = cursor.lastrowid
    return WatchlistEntry(id=int(new_id), ticker=normalized, added_at=now)


def remove_ticker(ticker: str) -> bool:
    """Remove a ticker from the watchlist.

    Returns True if a row was deleted, False if the ticker was not on the
    list. Callers translate False into the `TICKER_NOT_WATCHED` 404.
    """
    normalized = _normalize(ticker)
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE ticker = ?", (normalized,)
        )
        return cursor.rowcount > 0
