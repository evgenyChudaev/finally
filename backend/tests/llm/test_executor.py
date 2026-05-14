"""Tests for `app.llm.executor.execute_actions`.

We use the real service layer + a tmp SQLite DB so we exercise the same
trade validation path as manual REST trades.
"""

from __future__ import annotations

import pytest

from app.db import positions_repo, watchlist_repo
from app.llm.executor import execute_actions
from app.llm.schema import LLMResponse, TradeAction, WatchlistChange


@pytest.mark.asyncio
async def test_single_trade_executes(price_cache, data_source):
    response = LLMResponse(
        message="ok",
        trades=[TradeAction(ticker="AAPL", side="buy", quantity=2)],
    )
    trades, watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert errors == []
    assert watchlist == []
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"
    assert trades[0]["side"] == "buy"
    assert trades[0]["quantity"] == 2
    # Position now exists in the DB.
    assert positions_repo.get_position("AAPL").quantity == 2


@pytest.mark.asyncio
async def test_order_preserved(price_cache, data_source):
    response = LLMResponse(
        message="ok",
        trades=[
            TradeAction(ticker="AAPL", side="buy", quantity=1),
            TradeAction(ticker="MSFT", side="buy", quantity=1),
            TradeAction(ticker="TSLA", side="buy", quantity=1),
        ],
    )
    trades, _watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert errors == []
    assert [t["ticker"] for t in trades] == ["AAPL", "MSFT", "TSLA"]


@pytest.mark.asyncio
async def test_failure_captured_per_action(price_cache, data_source):
    # First trade is impossible (insufficient cash), second is fine.
    response = LLMResponse(
        message="ok",
        trades=[
            TradeAction(ticker="NVDA", side="buy", quantity=100),  # ~$80k
            TradeAction(ticker="AAPL", side="buy", quantity=1),
        ],
    )
    trades, _watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert len(trades) == 1
    assert trades[0]["ticker"] == "AAPL"
    assert len(errors) == 1
    err = errors[0]
    assert err["code"] == "INSUFFICIENT_CASH"
    assert err["action"]["type"] == "trade"
    assert err["action"]["ticker"] == "NVDA"


@pytest.mark.asyncio
async def test_success_after_failure(price_cache, data_source):
    """A sell that goes through after an oversized buy is rejected."""
    # Set up: buy 1 AAPL so we can sell it later.
    response_setup = LLMResponse(
        message="setup",
        trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
    )
    await execute_actions(response_setup, price_cache, data_source)

    # Now: oversized buy fails, sell succeeds.
    response = LLMResponse(
        message="ok",
        trades=[
            TradeAction(ticker="NVDA", side="buy", quantity=999),  # too expensive
            TradeAction(ticker="AAPL", side="sell", quantity=1),
        ],
    )
    trades, _watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert len(trades) == 1
    assert trades[0]["side"] == "sell"
    assert trades[0]["ticker"] == "AAPL"
    assert len(errors) == 1
    assert errors[0]["code"] == "INSUFFICIENT_CASH"


@pytest.mark.asyncio
async def test_watchlist_add_executes(price_cache, data_source):
    response = LLMResponse(
        message="ok",
        watchlist_changes=[WatchlistChange(ticker="META", action="add")],
    )
    _trades, watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert errors == []
    assert watchlist == [{"ticker": "META", "action": "add"}]
    assert watchlist_repo.has_ticker("META")


@pytest.mark.asyncio
async def test_watchlist_remove_executes(price_cache, data_source):
    # AAPL is in the test seed watchlist (see tmp_db fixture) so we can
    # remove it without pre-adding.
    response = LLMResponse(
        message="ok",
        watchlist_changes=[WatchlistChange(ticker="AAPL", action="remove")],
    )
    _trades, watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert errors == []
    assert watchlist == [{"ticker": "AAPL", "action": "remove"}]
    assert not watchlist_repo.has_ticker("AAPL")


@pytest.mark.asyncio
async def test_unknown_watchlist_add_captured(price_cache, data_source):
    response = LLMResponse(
        message="ok",
        watchlist_changes=[WatchlistChange(ticker="ZZZZ", action="add")],
    )
    _trades, watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert watchlist == []
    assert len(errors) == 1
    assert errors[0]["code"] == "UNKNOWN_TICKER"
    assert errors[0]["action"]["type"] == "watchlist_change"


@pytest.mark.asyncio
async def test_trades_run_before_watchlist(price_cache, data_source):
    response = LLMResponse(
        message="ok",
        trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
        watchlist_changes=[WatchlistChange(ticker="META", action="add")],
    )
    trades, watchlist, errors = await execute_actions(
        response, price_cache, data_source
    )
    assert errors == []
    assert len(trades) == 1
    assert len(watchlist) == 1
