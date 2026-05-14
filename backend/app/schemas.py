"""Pydantic request/response models for the FinAlly REST API.

These are deliberately thin: the routes do the work and the schemas just
shape the JSON contract documented in PLAN §8. All models use Pydantic v2.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Side = Literal["buy", "sell"]


class HealthResponse(BaseModel):
    """`GET /api/health` response body."""

    status: Literal["ok"] = "ok"


# --- Portfolio --------------------------------------------------------------


class PositionResponse(BaseModel):
    """One row in the portfolio's positions array."""

    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    unrealized_pl: float
    pct_change: float


class PortfolioResponse(BaseModel):
    """`GET /api/portfolio` response body."""

    cash_balance: float
    total_value: float
    positions: list[PositionResponse]


class TradeRequest(BaseModel):
    """`POST /api/portfolio/trade` request body."""

    model_config = ConfigDict(extra="ignore")

    ticker: str = Field(..., min_length=1, max_length=16)
    side: Side
    quantity: float


class TradeResponse(BaseModel):
    """Persisted trade row returned by `POST /api/portfolio/trade`."""

    id: int
    ticker: str
    side: Side
    quantity: float
    price: float
    executed_at: str


class TradesResponse(BaseModel):
    """`GET /api/portfolio/trades` response body."""

    trades: list[TradeResponse]


class SnapshotResponse(BaseModel):
    """One point on the P&L chart."""

    total_value: float
    recorded_at: str


class HistoryResponse(BaseModel):
    """`GET /api/portfolio/history` response body."""

    snapshots: list[SnapshotResponse]


# --- Watchlist --------------------------------------------------------------


class WatchlistTickerResponse(BaseModel):
    """One row of the watchlist response."""

    ticker: str
    current_price: float | None
    previous_price: float | None
    direction: Literal["up", "down", "flat"]
    added_at: str


class WatchlistResponse(BaseModel):
    """`GET /api/watchlist` response body."""

    tickers: list[WatchlistTickerResponse]


class WatchlistAddRequest(BaseModel):
    """`POST /api/watchlist` request body."""

    model_config = ConfigDict(extra="ignore")

    ticker: str = Field(..., min_length=1, max_length=16)
