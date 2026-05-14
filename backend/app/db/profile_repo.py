"""User profile repository (singleton row at id=1)."""

from __future__ import annotations

from dataclasses import dataclass

from .database import DEFAULT_CASH_BALANCE, get_connection, utc_now_iso


@dataclass(frozen=True, slots=True)
class Profile:
    """Singleton user profile row."""

    id: int
    cash_balance: float
    created_at: str


def get_profile() -> Profile:
    """Return the singleton profile row.

    If the row is missing (defensive — `init_db` should have inserted it),
    one is created on the fly with the default cash balance.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, cash_balance, created_at FROM users_profile WHERE id = 1"
        ).fetchone()

        if row is None:
            now = utc_now_iso()
            conn.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) "
                "VALUES (1, ?, ?)",
                (DEFAULT_CASH_BALANCE, now),
            )
            return Profile(id=1, cash_balance=DEFAULT_CASH_BALANCE, created_at=now)

        return Profile(
            id=row["id"],
            cash_balance=row["cash_balance"],
            created_at=row["created_at"],
        )


def update_cash(delta: float) -> float:
    """Apply a signed delta to the cash balance atomically.

    Returns the new balance. Raises `ValueError` if the resulting balance
    would be negative — callers should validate `INSUFFICIENT_CASH` before
    invoking this, but the guard keeps the invariant defensible.
    """
    with get_connection() as conn:
        # Lock the row by reading inside a single transaction (sqlite serializes
        # writes anyway, but doing the read+write in one connection prevents
        # interleaving with other writers).
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("users_profile row is missing; did init_db() run?")

        current = float(row["cash_balance"])
        new_balance = current + float(delta)
        if new_balance < 0:
            raise ValueError(
                f"cash balance cannot go negative (current={current}, delta={delta})"
            )

        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = 1",
            (new_balance,),
        )
        return new_balance


def set_cash(value: float) -> float:
    """Replace the cash balance outright.

    Used by tests and admin reset paths; production trade flow should use
    `update_cash` for atomic deltas.
    """
    if value < 0:
        raise ValueError("cash balance cannot be negative")
    with get_connection() as conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = 1",
            (float(value),),
        )
    return float(value)
