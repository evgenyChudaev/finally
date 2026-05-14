"""End-to-end chat route tests against the FastAPI TestClient with `LLM_MOCK=true`.

These exercise the full chat pipeline — rate limiter, mock LLM, executor,
persistence, history rehydration — without ever calling OpenRouter.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.errors import RATE_LIMITED
from app.llm.rate_limit import chat_rate_limiter
from app.routes import chat as chat_routes


@pytest.fixture(autouse=True)
def _enable_mock_and_reset_limiter(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    chat_rate_limiter.reset()
    yield
    chat_rate_limiter.reset()


@pytest.fixture
def chat_client(client: TestClient, app) -> TestClient:
    """The shared `client` fixture, but with the chat router mounted."""
    app.include_router(chat_routes.router)
    return client


def test_post_chat_trade_executes(chat_client):
    response = chat_client.post("/api/chat", json={"message": "buy 3 AAPL"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Buying 3 AAPL" in body["message"]
    assert len(body["trades"]) == 1
    assert body["trades"][0]["ticker"] == "AAPL"
    assert body["trades"][0]["side"] == "buy"
    assert body["errors"] == []

    # Trade visible in /api/portfolio.
    portfolio = chat_client.get("/api/portfolio").json()
    assert any(
        p["ticker"] == "AAPL" and p["quantity"] == 3 for p in portfolio["positions"]
    )


def test_post_chat_watchlist_add(chat_client):
    response = chat_client.post("/api/chat", json={"message": "add META"})
    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"] == [{"ticker": "META", "action": "add"}]
    assert body["errors"] == []

    watchlist = chat_client.get("/api/watchlist").json()
    assert any(t["ticker"] == "META" for t in watchlist["tickers"])


def test_post_chat_default_message(chat_client):
    response = chat_client.post("/api/chat", json={"message": "hi"})
    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == []
    assert body["watchlist_changes"] == []
    assert "Mock LLM response" in body["message"]


def test_chat_history_rehydrates(chat_client):
    chat_client.post("/api/chat", json={"message": "buy 1 AAPL"})
    chat_client.post("/api/chat", json={"message": "hello"})

    response = chat_client.get("/api/chat/history")
    assert response.status_code == 200
    messages = response.json()["messages"]
    # 2 user messages + 2 assistant messages, chronological.
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "buy 1 AAPL"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["actions"] is not None
    assert len(messages[1]["actions"]["trades"]) == 1
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "hello"
    assert messages[3]["role"] == "assistant"
    assert messages[3]["actions"]["trades"] == []


def test_chat_history_limit(chat_client):
    for i in range(3):
        chat_client.post("/api/chat", json={"message": f"hello {i}"})
    response = chat_client.get("/api/chat/history?limit=2")
    assert response.status_code == 200
    assert len(response.json()["messages"]) == 2


def test_chat_validation_empty_message(chat_client):
    response = chat_client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_chat_rate_limit(chat_client):
    # Burn through the 10/min budget.
    for _ in range(10):
        r = chat_client.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 200, r.text
    blocked = chat_client.post("/api/chat", json={"message": "hi"})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == RATE_LIMITED


def test_chat_records_partial_failure(chat_client):
    # 999 NVDA is way past the $10k cash budget; expect a failure entry but
    # the chat row still persists.
    response = chat_client.post(
        "/api/chat", json={"message": "buy 999 NVDA"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == []
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == "INSUFFICIENT_CASH"

    # Assistant turn captured the failure in the persisted actions JSON.
    history = chat_client.get("/api/chat/history").json()["messages"]
    assistant_row = next(m for m in history if m["role"] == "assistant")
    assert assistant_row["actions"]["errors"][0]["code"] == "INSUFFICIENT_CASH"


def test_chat_mixed_actions_in_one_message(chat_client):
    response = chat_client.post(
        "/api/chat", json={"message": "buy 1 AAPL and add META"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["trades"]) == 1
    assert body["trades"][0]["ticker"] == "AAPL"
    assert body["watchlist_changes"] == [{"ticker": "META", "action": "add"}]
    assert body["errors"] == []
