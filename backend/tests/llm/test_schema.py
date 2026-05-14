"""Tests for `app.llm.schema` (Pydantic structured-output models)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.schema import LLMResponse, TradeAction, WatchlistChange


def test_full_response_parses():
    raw = (
        '{"message": "ok", '
        '"trades": [{"ticker": "aapl", "side": "buy", "quantity": 3}], '
        '"watchlist_changes": [{"ticker": "msft", "action": "add"}]}'
    )
    parsed = LLMResponse.model_validate_json(raw)
    assert parsed.message == "ok"
    assert len(parsed.trades) == 1
    assert parsed.trades[0].ticker == "AAPL"  # normalized
    assert parsed.trades[0].side == "buy"
    assert parsed.trades[0].quantity == 3
    assert parsed.watchlist_changes[0].ticker == "MSFT"
    assert parsed.watchlist_changes[0].action == "add"


def test_message_only_parses_with_empty_defaults():
    raw = '{"message": "hello"}'
    parsed = LLMResponse.model_validate_json(raw)
    assert parsed.message == "hello"
    assert parsed.trades == []
    assert parsed.watchlist_changes == []


def test_malformed_json_raises_validation_error():
    with pytest.raises(ValidationError):
        LLMResponse.model_validate_json("{not really json")


def test_missing_message_field_raises():
    with pytest.raises(ValidationError):
        LLMResponse.model_validate_json('{"trades": []}')


def test_invalid_side_raises():
    with pytest.raises(ValidationError):
        TradeAction(ticker="AAPL", side="hold", quantity=1)  # type: ignore[arg-type]


def test_non_positive_quantity_raises():
    with pytest.raises(ValidationError):
        TradeAction(ticker="AAPL", side="buy", quantity=0)


def test_inf_quantity_raises():
    with pytest.raises(ValidationError):
        TradeAction(ticker="AAPL", side="buy", quantity=float("inf"))


def test_extra_fields_are_ignored():
    raw = (
        '{"message": "hi", "trades": [], "watchlist_changes": [], '
        '"extra": "ignored"}'
    )
    parsed = LLMResponse.model_validate_json(raw)
    assert parsed.message == "hi"


def test_invalid_watchlist_action_raises():
    with pytest.raises(ValidationError):
        WatchlistChange(ticker="AAPL", action="toggle")  # type: ignore[arg-type]


def test_ticker_normalized_to_upper():
    action = TradeAction(ticker="  aapl ", side="buy", quantity=1)
    assert action.ticker == "AAPL"
    change = WatchlistChange(ticker="msft", action="add")
    assert change.ticker == "MSFT"
