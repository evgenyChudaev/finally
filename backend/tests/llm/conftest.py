"""Reuse the routes-test fixtures for LLM-layer tests."""

from __future__ import annotations

# Import the route-test fixtures so LLM tests get tmp_db + price_cache +
# data_source without duplicating setup.
from tests.routes.conftest import (  # noqa: F401 - fixture re-export
    DEFAULT_TEST_PRICES,
    FakeDataSource,
    app,
    client,
    data_source,
    price_cache,
    tmp_db,
)
