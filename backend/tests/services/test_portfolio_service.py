"""Unit tests for the portfolio service.

These cover the validation matrix from PLAN §8 plus the happy-path
mechanics that the LLM executor (Task #3) will rely on. The service is
exercised directly so the tests don't depend on the HTTP layer.
"""

from __future__ import annotations

import pytest

from app.db import positions_repo, profile_repo, snapshots_repo, trades_repo
from app.errors import (
    INSUFFICIENT_CASH,
    INSUFFICIENT_SHARES,
    INVALID_QUANTITY,
    UNKNOWN_TICKER,
    ApiError,
)
from app.services import portfolio_service


def test_summarize_empty_portfolio(price_cache):
    """Brand-new profile: $10k cash, no positions, total == cash."""
    summary = portfolio_service.summarize(price_cache)
    assert summary.cash_balance == pytest.approx(10_000.0)
    assert summary.total_value == pytest.approx(10_000.0)
    assert summary.positions == []


def test_execute_buy_creates_position_and_decreases_cash(price_cache):
    trade = portfolio_service.execute_trade(price_cache, "AAPL", "buy", 10)
    assert trade.side == "buy"
    assert trade.quantity == 10
    assert trade.price == pytest.approx(190.0)

    profile = profile_repo.get_profile()
    assert profile.cash_balance == pytest.approx(10_000.0 - 10 * 190.0)

    pos = positions_repo.get_position("AAPL")
    assert pos is not None
    assert pos.quantity == 10
    assert pos.avg_cost == pytest.approx(190.0)


def test_execute_buy_uses_weighted_avg_cost(price_cache):
    """Adding to a position recomputes avg_cost as a weighted average."""
    portfolio_service.execute_trade(price_cache, "AAPL", "buy", 10)
    # Move the market and add again — service uses cache price for both
    # cost and avg_cost computation.
    price_cache.update("AAPL", 200.0)
    portfolio_service.execute_trade(price_cache, "AAPL", "buy", 10)

    pos = positions_repo.get_position("AAPL")
    assert pos is not None
    assert pos.quantity == 20
    assert pos.avg_cost == pytest.approx((190.0 + 200.0) / 2)


def test_execute_sell_partial_keeps_avg_cost(price_cache):
    portfolio_service.execute_trade(price_cache, "MSFT", "buy", 5)
    portfolio_service.execute_trade(price_cache, "MSFT", "sell", 2)

    pos = positions_repo.get_position("MSFT")
    assert pos is not None
    assert pos.quantity == 3
    assert pos.avg_cost == pytest.approx(400.0)


def test_execute_sell_full_deletes_position(price_cache):
    portfolio_service.execute_trade(price_cache, "GOOGL", "buy", 4)
    portfolio_service.execute_trade(price_cache, "GOOGL", "sell", 4)
    assert positions_repo.get_position("GOOGL") is None


def test_invalid_quantity_zero(price_cache):
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "AAPL", "buy", 0)
    assert exc.value.code == INVALID_QUANTITY
    assert exc.value.status_code == 400


def test_invalid_quantity_negative(price_cache):
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "AAPL", "buy", -5)
    assert exc.value.code == INVALID_QUANTITY


def test_invalid_quantity_nan(price_cache):
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "AAPL", "buy", float("nan"))
    assert exc.value.code == INVALID_QUANTITY


def test_unknown_ticker_rejected(price_cache):
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "ZZZZ", "buy", 1)
    assert exc.value.code == UNKNOWN_TICKER
    assert exc.value.status_code == 400


def test_insufficient_cash(price_cache):
    # We can't afford 100 AAPL @ $190 with $10k cash.
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "AAPL", "buy", 100)
    assert exc.value.code == INSUFFICIENT_CASH


def test_insufficient_shares_no_position(price_cache):
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "AAPL", "sell", 1)
    assert exc.value.code == INSUFFICIENT_SHARES


def test_insufficient_shares_partial_holding(price_cache):
    portfolio_service.execute_trade(price_cache, "AAPL", "buy", 2)
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "AAPL", "sell", 5)
    assert exc.value.code == INSUFFICIENT_SHARES


def test_trade_records_snapshot(price_cache):
    initial = snapshots_repo.list_snapshots()
    portfolio_service.execute_trade(price_cache, "AAPL", "buy", 1)
    after = snapshots_repo.list_snapshots()
    assert len(after) == len(initial) + 1
    # Total value after a fair-price buy should equal the previous balance:
    # cash drops by price * qty, position gains the same market value.
    assert after[-1].total_value == pytest.approx(10_000.0, abs=0.01)


def test_summarize_with_position_uses_cache_price(price_cache):
    portfolio_service.execute_trade(price_cache, "TSLA", "buy", 4)
    price_cache.update("TSLA", 300.0)
    summary = portfolio_service.summarize(price_cache)
    assert len(summary.positions) == 1
    row = summary.positions[0]
    assert row["ticker"] == "TSLA"
    assert row["current_price"] == 300.0
    # bought 4 @ 250, now @ 300 → $200 unrealized P&L, +20% pct change.
    assert row["unrealized_pl"] == pytest.approx(200.0, abs=0.01)
    assert row["pct_change"] == pytest.approx(20.0, abs=0.001)


def test_summarize_falls_back_to_avg_cost_when_no_price(price_cache):
    portfolio_service.execute_trade(price_cache, "TSLA", "buy", 4)
    price_cache.remove("TSLA")  # simulate stale cache
    summary = portfolio_service.summarize(price_cache)
    row = summary.positions[0]
    assert row["current_price"] == pytest.approx(250.0)  # avg_cost fallback
    assert row["unrealized_pl"] == pytest.approx(0.0)


def test_trades_appear_in_log(price_cache):
    portfolio_service.execute_trade(price_cache, "AAPL", "buy", 1)
    portfolio_service.execute_trade(price_cache, "AAPL", "sell", 1)
    trades = trades_repo.list_trades()
    assert len(trades) == 2
    # Newest first.
    assert trades[0].side == "sell"
    assert trades[1].side == "buy"


def test_bad_side_rejected(price_cache):
    with pytest.raises(ApiError) as exc:
        portfolio_service.execute_trade(price_cache, "AAPL", "borrow", 1)
    assert exc.value.code == INVALID_QUANTITY
