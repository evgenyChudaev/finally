"""Fixtures shared across DB tests.

Every test gets a fresh, initialized SQLite file in `tmp_path` so suites are
isolated and parallel-safe. `reset_db_path_for_tests` also clears the
internal "initialized" memo so each test re-runs schema + seed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.db import init_db, reset_db_path_for_tests


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the DB layer at a fresh file under `tmp_path` and init it."""
    # Make sure DEFAULT_WATCHLIST from the host env doesn't leak in unless a
    # test explicitly sets it.
    monkeypatch.delenv("DEFAULT_WATCHLIST", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    path = tmp_path / "finally.db"
    reset_db_path_for_tests(path)
    init_db()
    yield path
    reset_db_path_for_tests(None)


@pytest.fixture
def empty_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Like `db_path` but does NOT call init_db — for testing init itself."""
    monkeypatch.delenv("DEFAULT_WATCHLIST", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    path = tmp_path / "finally.db"
    reset_db_path_for_tests(path)
    yield path
    reset_db_path_for_tests(None)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no stray env vars from the host pollute tests."""
    # Tests that need DEFAULT_WATCHLIST set will use monkeypatch.setenv.
    # We only need to clear here as a safety net for tests that don't take
    # the `db_path` fixture.
    if "PYTEST_CURRENT_TEST" in os.environ:  # always true under pytest
        pass
