"""Portfolio HTTP route tests."""

from __future__ import annotations

import pytest

from app.db import positions_repo
from app.errors import (
    INSUFFICIENT_CASH,
    INSUFFICIENT_SHARES,
    INVALID_QUANTITY,
    UNKNOWN_TICKER,
    VALIDATION_ERROR,
)


def test_get_portfolio_empty(client):
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == pytest.approx(10_000.0)
    assert body["total_value"] == pytest.approx(10_000.0)
    assert body["positions"] == []


def test_post_trade_buy_happy_path(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 3},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["side"] == "buy"
    assert body["quantity"] == 3
    assert body["price"] == pytest.approx(190.0)

    # Confirm the portfolio reflects the trade.
    after = client.get("/api/portfolio").json()
    assert after["cash_balance"] == pytest.approx(10_000.0 - 3 * 190.0)
    assert len(after["positions"]) == 1
    assert after["positions"][0]["ticker"] == "AAPL"


def test_post_trade_sell_full_removes_position(client):
    client.post(
        "/api/portfolio/trade",
        json={"ticker": "MSFT", "side": "buy", "quantity": 2},
    )
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "MSFT", "side": "sell", "quantity": 2},
    )
    assert response.status_code == 200
    assert positions_repo.get_position("MSFT") is None


def test_post_trade_invalid_quantity(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 0},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == INVALID_QUANTITY


def test_post_trade_unknown_ticker(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "ZZZZ", "side": "buy", "quantity": 1},
    )
    assert response.status_code == 400
    assert response.json()["code"] == UNKNOWN_TICKER


def test_post_trade_insufficient_cash(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "NVDA", "side": "buy", "quantity": 100},
    )
    assert response.status_code == 400
    assert response.json()["code"] == INSUFFICIENT_CASH


def test_post_trade_insufficient_shares(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "sell", "quantity": 1},
    )
    assert response.status_code == 400
    assert response.json()["code"] == INSUFFICIENT_SHARES


def test_post_trade_validation_error_missing_field(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1},  # missing side
    )
    assert response.status_code == 422
    assert response.json()["code"] == VALIDATION_ERROR


def test_post_trade_validation_error_bad_side(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "borrow", "quantity": 1},
    )
    assert response.status_code == 422
    assert response.json()["code"] == VALIDATION_ERROR


def test_get_history_after_trade(client):
    client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1},
    )
    response = client.get("/api/portfolio/history")
    assert response.status_code == 200
    snapshots = response.json()["snapshots"]
    # We don't run the app lifespan in tests, so there's no startup-anchor
    # snapshot; only the trade snapshot exists.
    assert len(snapshots) == 1
    assert snapshots[0]["total_value"] == pytest.approx(10_000.0, abs=0.01)


def test_get_trades_returns_recent_first(client):
    client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1},
    )
    client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "sell", "quantity": 1},
    )
    response = client.get("/api/portfolio/trades")
    assert response.status_code == 200
    trades = response.json()["trades"]
    assert len(trades) == 2
    assert trades[0]["side"] == "sell"
    assert trades[1]["side"] == "buy"


def test_get_trades_limit_param(client):
    client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1},
    )
    client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1},
    )
    response = client.get("/api/portfolio/trades?limit=1")
    assert response.status_code == 200
    assert len(response.json()["trades"]) == 1
