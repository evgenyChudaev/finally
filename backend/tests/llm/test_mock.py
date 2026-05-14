"""Tests for `app.llm.mock.mock_response` (PLAN §9 Mock Mode keyword table)."""

from __future__ import annotations

import pytest

from app.llm.mock import mock_response


def test_buy_pattern_emits_trade():
    response = mock_response("buy 5 AAPL")
    assert len(response.trades) == 1
    trade = response.trades[0]
    assert trade.ticker == "AAPL"
    assert trade.side == "buy"
    assert trade.quantity == 5
    assert response.watchlist_changes == []
    assert "Buying 5 AAPL" in response.message


def test_sell_pattern_emits_trade():
    response = mock_response("sell 2 MSFT")
    assert len(response.trades) == 1
    trade = response.trades[0]
    assert trade.side == "sell"
    assert trade.ticker == "MSFT"
    assert trade.quantity == 2
    assert "Selling 2 MSFT" in response.message


def test_fractional_quantity_supported():
    response = mock_response("buy 0.5 NVDA")
    assert response.trades[0].quantity == pytest.approx(0.5)


@pytest.mark.parametrize(
    "message",
    [
        "BUY 3 AAPL",
        "Buy 3 aapl",
        "please bUy 3 AaPl now",
    ],
)
def test_case_insensitive_buy(message: str):
    response = mock_response(message)
    assert len(response.trades) == 1
    assert response.trades[0].ticker == "AAPL"
    assert response.trades[0].side == "buy"


def test_add_watchlist():
    response = mock_response("add PYPL")
    assert response.trades == []
    assert len(response.watchlist_changes) == 1
    change = response.watchlist_changes[0]
    assert change.ticker == "PYPL"
    assert change.action == "add"
    assert "Added PYPL" in response.message


def test_remove_watchlist():
    response = mock_response("Remove TSLA from my watchlist please")
    assert len(response.watchlist_changes) == 1
    assert response.watchlist_changes[0].ticker == "TSLA"
    assert response.watchlist_changes[0].action == "remove"


def test_fallthrough_default():
    response = mock_response("hello there, can you summarize my portfolio?")
    assert response.trades == []
    assert response.watchlist_changes == []
    assert "Mock LLM response" in response.message


def test_empty_message_returns_default():
    response = mock_response("")
    assert response.trades == []
    assert response.watchlist_changes == []


def test_multiple_actions_in_one_message():
    response = mock_response("buy 1 AAPL and sell 2 MSFT")
    assert len(response.trades) == 2
    sides = sorted(t.side for t in response.trades)
    assert sides == ["buy", "sell"]


def test_buy_does_not_double_as_watchlist_add():
    # The "5 AAPL" span overlaps with an unintended "add AAPL" — make sure
    # we don't double-count it.
    response = mock_response("buy 5 AAPL")
    assert response.watchlist_changes == []


def test_zero_quantity_ignored():
    response = mock_response("buy 0 AAPL")
    assert response.trades == []
    # Falls through to default since no actions captured.
    assert "Mock LLM response" in response.message
