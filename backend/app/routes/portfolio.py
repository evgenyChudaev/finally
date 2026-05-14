"""Portfolio routes: snapshot, trade, history, and trade log."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..db import snapshots_repo, trades_repo
from ..schemas import (
    HistoryResponse,
    PortfolioResponse,
    PositionResponse,
    SnapshotResponse,
    TradeRequest,
    TradeResponse,
    TradesResponse,
)
from ..services import portfolio_service

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(request: Request) -> PortfolioResponse:
    """Return cash, total value, and the live valuation of every position."""
    cache = request.app.state.price_cache
    summary = portfolio_service.summarize(cache)
    return PortfolioResponse(
        cash_balance=summary.cash_balance,
        total_value=summary.total_value,
        positions=[PositionResponse(**row) for row in summary.positions],
    )


@router.post("/trade", response_model=TradeResponse)
async def post_trade(request: Request, body: TradeRequest) -> TradeResponse:
    """Execute a market order at the current cache price.

    Validation failures bubble up as `ApiError` with one of the canonical
    codes from PLAN §8 (`INVALID_QUANTITY`, `UNKNOWN_TICKER`,
    `INSUFFICIENT_CASH`, `INSUFFICIENT_SHARES`).
    """
    cache = request.app.state.price_cache
    trade = portfolio_service.execute_trade(
        cache=cache,
        ticker=body.ticker,
        side=body.side,
        quantity=body.quantity,
    )
    return TradeResponse(
        id=trade.id,
        ticker=trade.ticker,
        side=trade.side,
        quantity=trade.quantity,
        price=trade.price,
        executed_at=trade.executed_at,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    limit: int = Query(default=500, ge=1, le=10_000),
) -> HistoryResponse:
    """Return P&L snapshots in chronological order (oldest → newest)."""
    rows = snapshots_repo.list_snapshots(limit=limit)
    return HistoryResponse(
        snapshots=[
            SnapshotResponse(total_value=row.total_value, recorded_at=row.recorded_at)
            for row in rows
        ]
    )


@router.get("/trades", response_model=TradesResponse)
async def get_trades(
    limit: int = Query(default=100, ge=1, le=1_000),
) -> TradesResponse:
    """Return recent trades, newest first."""
    rows = trades_repo.list_trades(limit=limit)
    return TradesResponse(
        trades=[
            TradeResponse(
                id=row.id,
                ticker=row.ticker,
                side=row.side,
                quantity=row.quantity,
                price=row.price,
                executed_at=row.executed_at,
            )
            for row in rows
        ]
    )
