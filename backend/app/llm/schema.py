"""Pydantic models for the LLM structured response (PLAN §9).

The LLM is asked to return JSON matching `LLMResponse`. We *never* trust raw
output: every response is validated through `LLMResponse.model_validate_json`
before any side-effect (trade or watchlist mutation) is attempted.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TradeAction(BaseModel):
    """One trade the assistant wants to execute on the user's behalf."""

    model_config = ConfigDict(extra="ignore")

    ticker: str = Field(..., min_length=1, max_length=16)
    side: Literal["buy", "sell"]
    quantity: float

    @field_validator("ticker")
    @classmethod
    def _upper_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("quantity")
    @classmethod
    def _finite_positive(cls, value: float) -> float:
        # NaN/inf and non-positive quantities are rejected at the service
        # layer too, but catching them in the schema gives a cleaner error.
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("quantity must be a finite number")
        if value <= 0:
            raise ValueError("quantity must be positive")
        return float(value)


class WatchlistChange(BaseModel):
    """One add/remove operation against the watchlist."""

    model_config = ConfigDict(extra="ignore")

    ticker: str = Field(..., min_length=1, max_length=16)
    action: Literal["add", "remove"]

    @field_validator("ticker")
    @classmethod
    def _upper_ticker(cls, value: str) -> str:
        return value.strip().upper()


class LLMResponse(BaseModel):
    """Top-level structured response from the LLM (PLAN §9).

    `message` is mandatory — the conversational reply shown to the user.
    `trades` and `watchlist_changes` default to empty lists so a pure-chat
    reply parses cleanly without needing them.
    """

    model_config = ConfigDict(extra="ignore")

    message: str
    trades: list[TradeAction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


__all__ = ["TradeAction", "WatchlistChange", "LLMResponse"]
