"""Watchlist service: add / remove tickers with data-source coordination.

The service tries to make the data source aware of every watched ticker so
the price cache stays populated. On `add`, if the cache already has the
ticker we accept it immediately; otherwise we ask the data source to begin
tracking it and wait briefly for the first price to land before committing
the DB write. On `remove`, we only stop tracking a ticker if no other
references (positions, other watchlist rows) still need it.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import status

from ..db import positions_repo, watchlist_repo
from ..errors import (
    TICKER_ALREADY_WATCHED,
    TICKER_NOT_WATCHED,
    UNKNOWN_TICKER,
    ApiError,
)
from ..market import MarketDataSource, PriceCache

logger = logging.getLogger(__name__)

# Total time to wait for the data source to deliver a first price after a
# new ticker is added. Polled at a small granularity below.
_PRICE_WAIT_SECONDS = 3.0
_PRICE_POLL_INTERVAL = 0.1


def _normalize(ticker: str) -> str:
    return ticker.strip().upper()


async def add(
    cache: PriceCache,
    source: MarketDataSource,
    ticker: str,
) -> watchlist_repo.WatchlistEntry:
    """Validate a candidate ticker, ask the data source to track it, and
    persist a new watchlist row.

    Raises `ApiError` with `TICKER_ALREADY_WATCHED` (409) if the ticker is
    already on the list, or `UNKNOWN_TICKER` (400) if the data source
    cannot deliver a price within ~3 seconds.
    """
    normalized = _normalize(ticker)
    if not normalized:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=UNKNOWN_TICKER,
            detail="ticker is required",
        )

    if watchlist_repo.has_ticker(normalized):
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=TICKER_ALREADY_WATCHED,
            detail=f"{normalized} is already on the watchlist",
        )

    # Fast path: cache already has the ticker (simulator seed or prior add).
    if cache.get_price(normalized) is None:
        # Ask the data source to start tracking. The simulator validates the
        # ticker against its seed list and silently no-ops on unknowns; the
        # Massive client makes a real REST call. Either way, success here
        # means "polling has begun", not "we have a price yet".
        try:
            await source.add_ticker(normalized)
        except Exception as exc:  # noqa: BLE001 - propagate as 400
            logger.warning(
                "watchlist.add source-error ticker=%s err=%s", normalized, exc
            )
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=UNKNOWN_TICKER,
                detail=f"unknown ticker '{normalized}'",
            ) from exc

        # Poll briefly for a price to land in the cache.
        waited = 0.0
        while waited < _PRICE_WAIT_SECONDS:
            if cache.get_price(normalized) is not None:
                break
            await asyncio.sleep(_PRICE_POLL_INTERVAL)
            waited += _PRICE_POLL_INTERVAL

        if cache.get_price(normalized) is None:
            # Best-effort cleanup so we don't leave the source polling a
            # ticker we're not going to record.
            try:
                await source.remove_ticker(normalized)
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=UNKNOWN_TICKER,
                detail=f"unknown ticker '{normalized}'",
            )

    entry = watchlist_repo.add_ticker(normalized)
    logger.info("watchlist.added ticker=%s", normalized)
    return entry


async def remove(
    cache: PriceCache,
    source: MarketDataSource,
    ticker: str,
) -> None:
    """Remove a ticker from the watchlist.

    Raises `ApiError` with `TICKER_NOT_WATCHED` (404) if the ticker isn't
    on the list. After the DB delete we only ask the data source to stop
    tracking the ticker if no held position references it; otherwise we
    keep the price cache populated for valuation.
    """
    normalized = _normalize(ticker)
    if not watchlist_repo.remove_ticker(normalized):
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=TICKER_NOT_WATCHED,
            detail=f"{normalized} is not on the watchlist",
        )

    # Stop polling iff nothing else needs the ticker's price. A held position
    # always needs it for valuation; a watchlist entry obviously does too.
    if positions_repo.get_position(normalized) is None and not watchlist_repo.has_ticker(
        normalized
    ):
        try:
            await source.remove_ticker(normalized)
        except Exception as exc:  # noqa: BLE001 - log and move on
            logger.warning(
                "watchlist.remove source-stop-failed ticker=%s err=%s",
                normalized,
                exc,
            )
        # Also drop the cache entry so a future re-add starts cleanly.
        cache.remove(normalized)

    logger.info("watchlist.removed ticker=%s", normalized)
