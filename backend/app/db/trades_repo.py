"""Trades repository (append-only log)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .database import get_connection, utc_now_iso

Side = Literal["buy", "sell"]


@dataclass(frozen=True, slots=True)
class Trade:
    """One row of the trades table."""

    id: int
    ticker: str
    side: Side
    quantity: float
    price: float
    executed_at: str


def _row_to_trade(row) -> Trade:
    return Trade(
        id=row["id"],
        ticker=row["ticker"],
        side=row["side"],
        quantity=row["quantity"],
        price=row["price"],
        executed_at=row["executed_at"],
    )


def record_trade(ticker: str, side: str, quantity: float, price: float) -> Trade:
    """Append a trade row and return it.

    Raises `ValueError` for invalid inputs (empty ticker, bad side, non-positive
    quantity, negative price). Higher-level trade execution must have already
    enforced cash/share availability — this function is a thin persistence
    helper.
    """
    normalized = ticker.strip().upper()
    if not normalized:
        raise ValueError("ticker cannot be empty")
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")
    if price < 0:
        raise ValueError(f"price must be non-negative, got {price}")

    now = utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO trades (ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (normalized, side, float(quantity), float(price), now),
        )
        new_id = int(cursor.lastrowid)
    return Trade(
        id=new_id,
        ticker=normalized,
        side=side,  # type: ignore[arg-type]
        quantity=float(quantity),
        price=float(price),
        executed_at=now,
    )


def list_trades(limit: int = 100) -> list[Trade]:
    """Return the most recent trades, newest first."""
    if limit <= 0:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, ticker, side, quantity, price, executed_at "
            "FROM trades ORDER BY executed_at DESC, id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [_row_to_trade(r) for r in rows]
