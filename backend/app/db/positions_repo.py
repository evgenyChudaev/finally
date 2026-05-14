"""Positions repository (one row per ticker held)."""

from __future__ import annotations

from dataclasses import dataclass

from .database import get_connection, utc_now_iso


@dataclass(frozen=True, slots=True)
class Position:
    """A held position in a single ticker."""

    id: int
    ticker: str
    quantity: float
    avg_cost: float
    updated_at: str


def _row_to_position(row) -> Position:
    return Position(
        id=row["id"],
        ticker=row["ticker"],
        quantity=row["quantity"],
        avg_cost=row["avg_cost"],
        updated_at=row["updated_at"],
    )


def list_positions() -> list[Position]:
    """Return every held position, sorted by ticker."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, ticker, quantity, avg_cost, updated_at "
            "FROM positions ORDER BY ticker ASC"
        ).fetchall()
    return [_row_to_position(r) for r in rows]


def get_position(ticker: str) -> Position | None:
    """Return the position for a ticker, or None if not held."""
    normalized = ticker.strip().upper()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, ticker, quantity, avg_cost, updated_at "
            "FROM positions WHERE ticker = ?",
            (normalized,),
        ).fetchone()
    return _row_to_position(row) if row is not None else None


def upsert_position(ticker: str, quantity: float, avg_cost: float) -> Position:
    """Insert or replace the row for a ticker.

    The caller is responsible for computing the post-trade `quantity` and
    `avg_cost` (e.g. weighted average for buys, unchanged for sells). This
    repo function just persists the result.

    Raises `ValueError` if `quantity` is negative — a zero/negative balance
    is logically a `delete_position`, not an upsert.
    """
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker cannot be empty")
    if quantity < 0:
        raise ValueError(f"quantity must be non-negative, got {quantity}")
    if avg_cost < 0:
        raise ValueError(f"avg_cost must be non-negative, got {avg_cost}")

    now = utc_now_iso()
    with get_connection() as conn:
        # SQLite's UPSERT keeps a single row per ticker thanks to the UNIQUE
        # constraint and lets us return the resulting row's id either way.
        conn.execute(
            """
            INSERT INTO positions (ticker, quantity, avg_cost, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                quantity   = excluded.quantity,
                avg_cost   = excluded.avg_cost,
                updated_at = excluded.updated_at
            """,
            (normalized, float(quantity), float(avg_cost), now),
        )
        row = conn.execute(
            "SELECT id, ticker, quantity, avg_cost, updated_at "
            "FROM positions WHERE ticker = ?",
            (normalized,),
        ).fetchone()
    return _row_to_position(row)


def delete_position(ticker: str) -> bool:
    """Delete a position. Returns True if a row was removed."""
    normalized = ticker.strip().upper()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM positions WHERE ticker = ?", (normalized,))
        return cursor.rowcount > 0
