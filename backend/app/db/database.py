"""SQLite connection management and lazy initialization for FinAlly."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# Built-in default watchlist when DEFAULT_WATCHLIST is unset.
DEFAULT_WATCHLIST_TICKERS: tuple[str, ...] = (
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
)

# Default cash balance for a fresh users_profile row.
DEFAULT_CASH_BALANCE: float = 10000.0

# Module-level test override for the database path. Production callers should
# not set this; tests use `reset_db_path_for_tests` to point at a tmp file.
_db_path_override: Path | None = None

# Tracks whether init_db() has already run for a given DB path. Lazy init only
# needs to do its full work on first call; subsequent calls remain idempotent
# but skip the schema/seed checks for speed.
_init_lock = threading.Lock()
_initialized_paths: set[Path] = set()

# SQL DDL is loaded once from schema.sql alongside this module.
_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string ending in 'Z'."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_db_path() -> Path:
    """Resolve the SQLite database file path.

    Resolution order:
        1. `reset_db_path_for_tests` override (test-only).
        2. `DB_PATH` environment variable.
        3. `<project-root>/db/finally.db` where project root is the directory
           containing the `backend/` package.

    The parent directory is created if it does not exist.
    """
    if _db_path_override is not None:
        path = _db_path_override
    else:
        env_value = os.environ.get("DB_PATH", "").strip()
        if env_value:
            path = Path(env_value).expanduser().resolve()
        else:
            # backend/app/db/database.py -> project root is three parents up
            # from this file.
            project_root = Path(__file__).resolve().parents[3]
            path = project_root / "db" / "finally.db"

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def reset_db_path_for_tests(path: Path | str | None) -> None:
    """Override the database path. Tests only.

    Pass `None` to clear the override and revert to env/default resolution.
    Also resets the "initialized" memo so a new DB at the same path goes
    through schema + seed again.
    """
    global _db_path_override
    _db_path_override = Path(path).expanduser().resolve() if path is not None else None
    with _init_lock:
        _initialized_paths.clear()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with foreign keys on and Row factory.

    The connection commits on successful exit and rolls back on exception,
    then is always closed. Callers may still wrap multiple statements in an
    explicit transaction via `conn.execute("BEGIN")` if they need stricter
    isolation, but the default behavior is suitable for the simple
    single-user read/write patterns in this app.
    """
    path = get_db_path()
    conn = sqlite3.connect(
        str(path),
        detect_types=sqlite3.PARSE_DECLTYPES,
        isolation_level="DEFERRED",
    )
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _load_schema_sql() -> str:
    """Read schema DDL from the bundled schema.sql file."""
    return _SCHEMA_PATH.read_text(encoding="utf-8")


def _watchlist_from_env() -> list[str]:
    """Parse the DEFAULT_WATCHLIST env var, falling back to the built-in list.

    Empty/whitespace entries are dropped; tickers are uppercased and
    deduplicated while preserving order.
    """
    raw = os.environ.get("DEFAULT_WATCHLIST", "").strip()
    if not raw:
        return list(DEFAULT_WATCHLIST_TICKERS)

    seen: set[str] = set()
    result: list[str] = []
    for piece in raw.split(","):
        ticker = piece.strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            result.append(ticker)
    return result or list(DEFAULT_WATCHLIST_TICKERS)


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    """Insert the singleton profile row and default watchlist if absent.

    The function is safe to call on a partially-seeded DB: each insert uses
    INSERT OR IGNORE, so existing rows are preserved.
    """
    now = utc_now_iso()

    conn.execute(
        "INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) "
        "VALUES (1, ?, ?)",
        (DEFAULT_CASH_BALANCE, now),
    )

    cursor = conn.execute("SELECT COUNT(*) AS n FROM watchlist")
    row = cursor.fetchone()
    if row["n"] == 0:
        tickers = _watchlist_from_env()
        conn.executemany(
            "INSERT OR IGNORE INTO watchlist (ticker, added_at) VALUES (?, ?)",
            [(t, now) for t in tickers],
        )
        logger.info("db.seed.watchlist count=%d tickers=%s", len(tickers), ",".join(tickers))


def init_db() -> Path:
    """Create tables (if missing) and seed default data (if empty).

    Idempotent: safe to call from app startup or lazily before the first
    request. Returns the path to the database file.
    """
    path = get_db_path()
    with _init_lock:
        if path in _initialized_paths:
            return path

        schema_sql = _load_schema_sql()
        with get_connection() as conn:
            conn.executescript(schema_sql)
            _seed_if_empty(conn)

        _initialized_paths.add(path)
        logger.info("db.init path=%s", path)
        return path
