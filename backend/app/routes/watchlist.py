"""Watchlist routes: list / add / remove."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from ..db import watchlist_repo
from ..schemas import (
    WatchlistAddRequest,
    WatchlistResponse,
    WatchlistTickerResponse,
)
from ..services import watchlist_service

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(request: Request) -> WatchlistResponse:
    """Return the watchlist enriched with the latest cached prices."""
    cache = request.app.state.price_cache
    rows = watchlist_repo.list_tickers()
    out: list[WatchlistTickerResponse] = []
    for row in rows:
        snapshot = cache.get(row.ticker)
        out.append(
            WatchlistTickerResponse(
                ticker=row.ticker,
                current_price=snapshot.price if snapshot else None,
                previous_price=snapshot.previous_price if snapshot else None,
                direction=snapshot.direction if snapshot else "flat",
                added_at=row.added_at,
            )
        )
    return WatchlistResponse(tickers=out)


@router.post(
    "",
    response_model=WatchlistTickerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_watchlist(
    request: Request, body: WatchlistAddRequest
) -> WatchlistTickerResponse:
    """Add a ticker to the watchlist, coordinating with the data source."""
    cache = request.app.state.price_cache
    source = request.app.state.market_source
    entry = await watchlist_service.add(cache, source, body.ticker)
    snapshot = cache.get(entry.ticker)
    return WatchlistTickerResponse(
        ticker=entry.ticker,
        current_price=snapshot.price if snapshot else None,
        previous_price=snapshot.previous_price if snapshot else None,
        direction=snapshot.direction if snapshot else "flat",
        added_at=entry.added_at,
    )


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(request: Request, ticker: str) -> None:
    """Remove a ticker from the watchlist.

    Returns 204 No Content on success, 404 with `TICKER_NOT_WATCHED` if the
    ticker isn't on the list.
    """
    cache = request.app.state.price_cache
    source = request.app.state.market_source
    await watchlist_service.remove(cache, source, ticker)
