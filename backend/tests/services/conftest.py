"""Reuse the routes-test fixtures for service-level tests."""

from __future__ import annotations

# Import the route-test fixtures so service tests get tmp_db + price_cache
# + data_source without duplicating setup. pytest collects fixtures from any
# conftest in the path; this conftest just re-exports.
from tests.routes.conftest import (  # noqa: F401 - fixture re-export
    DEFAULT_TEST_PRICES,
    FakeDataSource,
    data_source,
    price_cache,
    tmp_db,
)
