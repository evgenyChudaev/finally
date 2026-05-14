"""Portfolio service: trade execution + valuation.

The service layer wraps the repo functions with the validation rules from
PLAN §8 and exposes a clean Python API that both HTTP routes and the LLM
executor can call. All error cases raise `ApiError` with the canonical code
documented in `app.errors`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import status

from ..db import positions_repo, profile_repo, snapshots_repo, trades_repo
from ..errors import (
    INSUFFICIENT_CASH,
    INSUFFICIENT_SHARES,
    INVALID_QUANTITY,
    UNKNOWN_TICKER,
    ApiError,
)
from ..market import PriceCache

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    """Aggregated portfolio view returned by `summarize`."""

    cash_balance: float
    total_value: float
    positions: list[dict]


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def summarize(cache: PriceCache) -> PortfolioSummary:
    """Build the `GET /api/portfolio` payload.

    Reads the singleton profile, all held positions, and overlays the
    current price from the cache. If the cache has no price for a ticker
    (e.g. cold start before the simulator has ticked) we fall back to the
    average cost — that yields a zero P&L for that row rather than a crash.
    """
    profile = profile_repo.get_profile()
    held = positions_repo.list_positions()

    positions_out: list[dict] = []
    holdings_value = 0.0
    for pos in held:
        current = cache.get_price(pos.ticker)
        current_price = current if current is not None else pos.avg_cost
        cost_basis = pos.avg_cost * pos.quantity
        market_value = current_price * pos.quantity
        unrealized_pl = market_value - cost_basis
        pct_change = (
            (current_price - pos.avg_cost) / pos.avg_cost * 100.0
            if pos.avg_cost > 0
            else 0.0
        )
        holdings_value += market_value
        positions_out.append(
            {
                "ticker": pos.ticker,
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "current_price": current_price,
                "unrealized_pl": round(unrealized_pl, 4),
                "pct_change": round(pct_change, 4),
            }
        )

    total_value = profile.cash_balance + holdings_value
    return PortfolioSummary(
        cash_balance=profile.cash_balance,
        total_value=round(total_value, 4),
        positions=positions_out,
    )


def compute_total_value(cache: PriceCache) -> float:
    """Cash + market value of holdings (using cache prices, avg_cost fallback)."""
    return summarize(cache).total_value


def execute_trade(
    cache: PriceCache, ticker: str, side: str, quantity: float
) -> trades_repo.Trade:
    """Validate and execute a market order at the cache's current price.

    Returns the persisted `Trade` row on success. Raises `ApiError` with a
    canonical code on validation failure. After a successful trade we also
    record a `portfolio_snapshots` row so the P&L chart picks it up.

    The function is callable from both the REST route and the LLM executor
    — they share this code path so partial-failure semantics in chat use
    exactly the same validation as manual trades.
    """
    if side not in ("buy", "sell"):
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=INVALID_QUANTITY,
            detail=f"invalid side '{side}'; expected 'buy' or 'sell'",
        )
    try:
        qty = float(quantity)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=INVALID_QUANTITY,
            detail=f"quantity must be a number, got {quantity!r}",
        ) from exc
    if not (qty > 0):
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=INVALID_QUANTITY,
            detail="quantity must be positive",
        )
    # Guard against NaN / inf that survive the > 0 check above.
    if qty != qty or qty in (float("inf"), float("-inf")):  # NaN/inf check
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=INVALID_QUANTITY,
            detail="quantity must be a finite number",
        )

    normalized = _normalize_ticker(ticker)
    if not normalized:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=UNKNOWN_TICKER,
            detail="ticker is required",
        )

    price = cache.get_price(normalized)
    if price is None:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=UNKNOWN_TICKER,
            detail=f"unknown ticker '{normalized}'",
        )

    current_position = positions_repo.get_position(normalized)
    profile = profile_repo.get_profile()

    if side == "buy":
        cost = price * qty
        if cost > profile.cash_balance + 1e-9:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=INSUFFICIENT_CASH,
                detail=(
                    f"insufficient cash: need ${cost:.2f}, "
                    f"have ${profile.cash_balance:.2f}"
                ),
            )

        # Weighted-average cost basis. For a brand-new position the
        # existing cost basis is zero so this reduces to the new price.
        if current_position is None:
            new_quantity = qty
            new_avg_cost = price
        else:
            existing_basis = current_position.avg_cost * current_position.quantity
            new_quantity = current_position.quantity + qty
            new_avg_cost = (existing_basis + cost) / new_quantity

        # Mutate cash first so a downstream failure on positions still leaves
        # us with the trade un-recorded and cash intact (positions upsert is
        # itself a single statement so failures here are unlikely).
        profile_repo.update_cash(-cost)
        positions_repo.upsert_position(normalized, new_quantity, new_avg_cost)

    else:  # sell
        if current_position is None or current_position.quantity + 1e-9 < qty:
            held = current_position.quantity if current_position else 0.0
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code=INSUFFICIENT_SHARES,
                detail=(
                    f"insufficient shares: trying to sell {qty} {normalized}, "
                    f"hold {held}"
                ),
            )
        proceeds = price * qty
        remaining = current_position.quantity - qty
        # Avg cost is unchanged on a sell; if we're fully out, drop the row.
        if remaining <= 1e-9:
            positions_repo.delete_position(normalized)
        else:
            positions_repo.upsert_position(
                normalized, remaining, current_position.avg_cost
            )
        profile_repo.update_cash(proceeds)

    trade = trades_repo.record_trade(normalized, side, qty, price)

    # Anchor a new P&L data point right after the trade.
    total_value = compute_total_value(cache)
    snapshots_repo.record_snapshot(total_value)

    logger.info(
        "trade.executed side=%s ticker=%s qty=%s price=%.4f total_value=%.2f",
        side,
        normalized,
        qty,
        price,
        total_value,
    )
    return trade
