"""Unit tests for the watchlist service."""

from __future__ import annotations

import pytest

from app.db import watchlist_repo
from app.errors import (
    TICKER_ALREADY_WATCHED,
    TICKER_NOT_WATCHED,
    UNKNOWN_TICKER,
    ApiError,
)
from app.services import portfolio_service, watchlist_service


async def test_add_known_ticker_already_in_cache(price_cache, data_source):
    """Tickers already in the cache should add immediately without polling."""
    # Pre-seed only added rows: drop any seed AAPL entry so we can add it.
    watchlist_repo.remove_ticker("AAPL")
    entry = await watchlist_service.add(price_cache, data_source, "aapl")
    assert entry.ticker == "AAPL"
    assert watchlist_repo.has_ticker("AAPL")


async def test_add_unknown_ticker_returns_400(price_cache, data_source):
    with pytest.raises(ApiError) as exc:
        await watchlist_service.add(price_cache, data_source, "ZZZZ")
    assert exc.value.code == UNKNOWN_TICKER
    # Source.add_ticker was called once but no price arrived in time.
    assert "ZZZZ" in data_source.added


async def test_add_already_watched_returns_409(price_cache, data_source):
    # The default seed includes AAPL — adding again must conflict.
    assert watchlist_repo.has_ticker("AAPL")
    with pytest.raises(ApiError) as exc:
        await watchlist_service.add(price_cache, data_source, "AAPL")
    assert exc.value.code == TICKER_ALREADY_WATCHED
    assert exc.value.status_code == 409


async def test_add_uppercases_input(price_cache, data_source):
    watchlist_repo.remove_ticker("MSFT")
    entry = await watchlist_service.add(price_cache, data_source, "msft")
    assert entry.ticker == "MSFT"


async def test_add_new_ticker_via_source(price_cache, data_source):
    """A ticker the source knows but the cache doesn't yet: source.add_ticker
    runs, the fake seeds the cache, and the watchlist row is persisted."""
    # NFLX is in the fake data source but not in the prefilled cache.
    assert price_cache.get_price("NFLX") is None
    entry = await watchlist_service.add(price_cache, data_source, "NFLX")
    assert entry.ticker == "NFLX"
    assert price_cache.get_price("NFLX") == pytest.approx(600.0)


async def test_remove_unknown_ticker_returns_404(price_cache, data_source):
    with pytest.raises(ApiError) as exc:
        await watchlist_service.remove(price_cache, data_source, "ZZZZ")
    assert exc.value.code == TICKER_NOT_WATCHED
    assert exc.value.status_code == 404


async def test_remove_drops_db_row_and_stops_polling(price_cache, data_source):
    # No position on NVDA — removing should also stop the source.
    await watchlist_service.remove(price_cache, data_source, "NVDA")
    assert not watchlist_repo.has_ticker("NVDA")
    assert "NVDA" in data_source.removed
    assert price_cache.get_price("NVDA") is None


async def test_remove_keeps_polling_if_position_exists(price_cache, data_source):
    """If we still hold the ticker, we keep tracking it for valuation."""
    portfolio_service.execute_trade(price_cache, "AAPL", "buy", 1)
    await watchlist_service.remove(price_cache, data_source, "AAPL")
    assert not watchlist_repo.has_ticker("AAPL")
    assert "AAPL" not in data_source.removed
    # Cache must still have AAPL so the position can be valued.
    assert price_cache.get_price("AAPL") is not None
