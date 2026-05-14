"""Watchlist HTTP route tests."""

from __future__ import annotations

from app.db import watchlist_repo
from app.errors import (
    TICKER_ALREADY_WATCHED,
    TICKER_NOT_WATCHED,
    UNKNOWN_TICKER,
    VALIDATION_ERROR,
)


def test_get_watchlist_returns_seeded_tickers(client):
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    body = response.json()
    tickers = {row["ticker"] for row in body["tickers"]}
    # The conftest seeds the watchlist with the deterministic test ticker
    # set so each entry has live cache prices.
    assert "AAPL" in tickers
    for row in body["tickers"]:
        if row["ticker"] in {"AAPL", "MSFT", "TSLA"}:
            assert row["current_price"] is not None
            assert row["direction"] in {"up", "down", "flat"}


def test_post_watchlist_happy_path(client):
    # Remove AAPL from the watchlist so we can re-add it.
    watchlist_repo.remove_ticker("AAPL")
    response = client.post("/api/watchlist", json={"ticker": "aapl"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["current_price"] is not None


def test_post_watchlist_unknown_ticker(client):
    response = client.post("/api/watchlist", json={"ticker": "ZZZZ"})
    assert response.status_code == 400
    assert response.json()["code"] == UNKNOWN_TICKER


def test_post_watchlist_duplicate(client):
    # AAPL is already in the seed list.
    response = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert response.status_code == 409
    assert response.json()["code"] == TICKER_ALREADY_WATCHED


def test_post_watchlist_missing_body(client):
    response = client.post("/api/watchlist", json={})
    assert response.status_code == 422
    assert response.json()["code"] == VALIDATION_ERROR


def test_delete_watchlist_happy_path(client):
    response = client.delete("/api/watchlist/NVDA")
    assert response.status_code == 204
    assert not watchlist_repo.has_ticker("NVDA")


def test_delete_watchlist_unknown(client):
    response = client.delete("/api/watchlist/ZZZZ")
    assert response.status_code == 404
    assert response.json()["code"] == TICKER_NOT_WATCHED
