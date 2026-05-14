"""Database layer for FinAlly.

Public API:
    get_db_path        - Resolve the SQLite file path
    get_connection     - Context manager yielding a sqlite3.Connection
    init_db            - Lazy initialization (create tables, seed defaults)
    reset_db_path_for_tests - Test helper to override the DB path

Repositories:
    profile_repo
    watchlist_repo
    positions_repo
    trades_repo
    snapshots_repo
    chat_repo
"""

from .database import (
    get_connection,
    get_db_path,
    init_db,
    reset_db_path_for_tests,
)

__all__ = [
    "get_connection",
    "get_db_path",
    "init_db",
    "reset_db_path_for_tests",
]
