"""Portfolio snapshots repository (P&L chart data points)."""

from __future__ import annotations

from dataclasses import dataclass

from .database import get_connection, utc_now_iso


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A single point on the P&L chart."""

    id: int
    total_value: float
    recorded_at: str


def record_snapshot(total_value: float) -> Snapshot:
    """Record a portfolio total-value snapshot at the current time.

    Per the plan (§7, decision #20) these are written event-driven — once at
    app startup and once after each trade. There is no periodic background
    snapshot writer.
    """
    if total_value < 0:
        raise ValueError(f"total_value must be non-negative, got {total_value}")

    now = utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO portfolio_snapshots (total_value, recorded_at) VALUES (?, ?)",
            (float(total_value), now),
        )
        new_id = int(cursor.lastrowid)
    return Snapshot(id=new_id, total_value=float(total_value), recorded_at=now)


def list_snapshots(limit: int = 500) -> list[Snapshot]:
    """Return snapshots in chronological (oldest first) order.

    The P&L chart expects ascending timestamps, so we sort ASC here. The
    `limit` parameter is applied after the sort so the most recent N points
    are returned in chronological order — useful when the table grows large.
    """
    if limit <= 0:
        return []
    with get_connection() as conn:
        # Take the latest N rows then re-order ascending for the chart.
        rows = conn.execute(
            """
            SELECT id, total_value, recorded_at FROM (
                SELECT id, total_value, recorded_at
                FROM portfolio_snapshots
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
            ) ORDER BY recorded_at ASC, id ASC
            """,
            (int(limit),),
        ).fetchall()
    return [
        Snapshot(id=r["id"], total_value=r["total_value"], recorded_at=r["recorded_at"])
        for r in rows
    ]
