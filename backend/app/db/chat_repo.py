"""Chat-message repository (append-only conversation log)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from .database import get_connection, utc_now_iso

Role = Literal["user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One row of the chat_messages table."""

    id: int
    role: Role
    content: str
    actions: dict[str, Any] | None
    created_at: str


def _row_to_message(row) -> ChatMessage:
    raw_actions = row["actions"]
    parsed: dict[str, Any] | None
    if raw_actions is None:
        parsed = None
    else:
        try:
            parsed = json.loads(raw_actions)
        except json.JSONDecodeError:
            # Defensive: if a hand-edited row has bad JSON we surface the raw
            # string rather than crashing the chat panel.
            parsed = {"_raw": raw_actions}
    return ChatMessage(
        id=row["id"],
        role=row["role"],
        content=row["content"],
        actions=parsed,
        created_at=row["created_at"],
    )


def append_message(
    role: str,
    content: str,
    actions: dict[str, Any] | None = None,
) -> ChatMessage:
    """Append a chat message and return the persisted row.

    `actions` is serialized to JSON for `assistant` messages that include
    executed trades / watchlist changes / errors. User messages and
    plain-conversation assistant messages may pass `None`.

    Raises `ValueError` for invalid role or empty content.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"role must be 'user' or 'assistant', got {role!r}")
    if not content:
        raise ValueError("content cannot be empty")

    actions_json = None if actions is None else json.dumps(actions, default=str)
    now = utc_now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO chat_messages (role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?)",
            (role, content, actions_json, now),
        )
        new_id = int(cursor.lastrowid)
    return ChatMessage(
        id=new_id,
        role=role,  # type: ignore[arg-type]
        content=content,
        actions=actions,
        created_at=now,
    )


def recent_messages(limit: int = 20) -> list[ChatMessage]:
    """Return up to `limit` most-recent messages in chronological order.

    The query takes the newest `limit` rows by `created_at DESC` (uses the
    index on `created_at`), then re-orders ascending so the LLM and the UI
    see the natural conversation flow.
    """
    if limit <= 0:
        return []
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, actions, created_at FROM (
                SELECT id, role, content, actions, created_at
                FROM chat_messages
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            ) ORDER BY created_at ASC, id ASC
            """,
            (int(limit),),
        ).fetchall()
    return [_row_to_message(r) for r in rows]
