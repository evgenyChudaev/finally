-- FinAlly SQLite schema.
-- All ids: INTEGER PRIMARY KEY AUTOINCREMENT.
-- All timestamps: TEXT, ISO 8601 UTC (e.g. "2026-05-12T14:30:00.123456Z").
-- Single-user model: no user_id columns.

CREATE TABLE IF NOT EXISTS users_profile (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    cash_balance  REAL    NOT NULL DEFAULT 10000.0,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker    TEXT    NOT NULL UNIQUE,
    added_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT    NOT NULL UNIQUE,
    quantity    REAL    NOT NULL,
    avg_cost    REAL    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT    NOT NULL,
    side         TEXT    NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity     REAL    NOT NULL,
    price        REAL    NOT NULL,
    executed_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_executed_at
    ON trades (executed_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    total_value  REAL    NOT NULL,
    recorded_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_recorded_at
    ON portfolio_snapshots (recorded_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role        TEXT    NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT    NOT NULL,
    actions     TEXT,
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
    ON chat_messages (created_at DESC);
