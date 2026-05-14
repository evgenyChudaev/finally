"""Shared fixtures for route + service tests.

Each test gets:
- a tmp SQLite database, initialized with the default schema (no
  watchlist seed beyond an explicit list of test tickers),
- a `PriceCache` pre-filled with deterministic prices,
- a `FakeDataSource` that records add/remove calls and seeds the cache,
- a FastAPI app instance (built fresh, not the module-level one) with the
  fixtures bolted onto `app.state` so route tests can use TestClient
  directly without invoking the real lifespan / simulator.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app import errors as app_errors
from app import schemas
from app.db import database, reset_db_path_for_tests
from app.market import MarketDataSource, PriceCache
from app.routes import health as health_routes
from app.routes import portfolio as portfolio_routes
from app.routes import watchlist as watchlist_routes

# Deterministic prices used across the route tests.
DEFAULT_TEST_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 150.00,
    "MSFT": 400.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
}


class FakeDataSource(MarketDataSource):
    """In-memory MarketDataSource for tests.

    On `start`, seeds every ticker in `known_prices` into the cache. On
    `add_ticker`, seeds the price if known; otherwise behaves as a no-op
    (so the watchlist service times out and returns UNKNOWN_TICKER).
    """

    def __init__(self, cache: PriceCache, known_prices: dict[str, float]):
        self.cache = cache
        self.known_prices = dict(known_prices)
        self.added: list[str] = []
        self.removed: list[str] = []
        self.tickers: list[str] = []

    async def start(self, tickers: list[str]) -> None:
        self.tickers = list(tickers)
        for ticker in tickers:
            price = self.known_prices.get(ticker.upper())
            if price is not None:
                self.cache.update(ticker.upper(), price)

    async def stop(self) -> None:
        return None

    async def add_ticker(self, ticker: str) -> None:
        upper = ticker.upper()
        self.added.append(upper)
        if upper not in self.tickers:
            self.tickers.append(upper)
        price = self.known_prices.get(upper)
        if price is not None:
            self.cache.update(upper, price)

    async def remove_ticker(self, ticker: str) -> None:
        upper = ticker.upper()
        self.removed.append(upper)
        if upper in self.tickers:
            self.tickers.remove(upper)
        self.cache.remove(upper)

    def get_tickers(self) -> list[str]:
        return list(self.tickers)


def _build_test_app(cache: PriceCache, source: MarketDataSource) -> FastAPI:
    """Construct a FastAPI app without invoking the real lifespan.

    We deliberately avoid `create_app()` because that defines a lifespan
    handler that would replace our pre-built cache. The test app mirrors
    the production wiring minus the background simulator startup.
    """
    app = FastAPI()

    app.add_exception_handler(app_errors.ApiError, app_errors.api_error_handler)
    app.add_exception_handler(
        RequestValidationError, app_errors.validation_error_handler
    )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        # Tests should never trip this; surface as 500 if they do.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "code": "INTERNAL_ERROR"},
        )

    app.include_router(health_routes.router)
    app.include_router(portfolio_routes.router)
    app.include_router(watchlist_routes.router)

    app.state.price_cache = cache
    app.state.market_source = source
    return app


@pytest.fixture
def tmp_db(tmp_path, monkeypatch) -> Iterator[None]:
    """Point the DB layer at a fresh SQLite file under `tmp_path`.

    The override is cleared on teardown so the next test gets a clean slate.
    """
    db_path = tmp_path / "finally.db"
    # Clear DEFAULT_WATCHLIST so seed only includes the bare singleton row,
    # which we then explicitly populate per-test via the `watchlist` fixture.
    monkeypatch.delenv("DEFAULT_WATCHLIST", raising=False)
    monkeypatch.setenv("DEFAULT_WATCHLIST", ",".join(DEFAULT_TEST_PRICES.keys()))
    reset_db_path_for_tests(db_path)
    try:
        database.init_db()
        yield
    finally:
        reset_db_path_for_tests(None)


@pytest.fixture
def price_cache(tmp_db) -> PriceCache:
    """A PriceCache pre-filled with the deterministic test prices."""
    cache = PriceCache()
    for ticker, price in DEFAULT_TEST_PRICES.items():
        cache.update(ticker, price)
    return cache


@pytest.fixture
def data_source(price_cache: PriceCache) -> FakeDataSource:
    """A FakeDataSource that knows about the default test tickers + a few extra
    candidates that can be added at runtime."""
    return FakeDataSource(
        price_cache,
        known_prices={
            **DEFAULT_TEST_PRICES,
            "META": 350.00,
            "AMZN": 180.00,
            "NFLX": 600.00,
        },
    )


@pytest.fixture
def app(price_cache: PriceCache, data_source: FakeDataSource) -> FastAPI:
    """A FastAPI app wired to the test cache + fake data source."""
    return _build_test_app(price_cache, data_source)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """A FastAPI TestClient. Lifespan is not invoked — we don't need it."""
    # Using a no-op lifespan via `raise_app_exceptions=True` keeps tracebacks.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def schema_module():
    """Convenience handle to the schemas module for type assertions."""
    return schemas
