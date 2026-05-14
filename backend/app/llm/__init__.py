"""LLM integration package for FinAlly.

Implements the chat assistant per PLAN §9: structured-output prompting,
mock-mode keyword parsing, server-side validation, executor wiring to the
shared portfolio / watchlist services, and a per-process rate limiter.

Public API is intentionally small — routes import the submodules directly
(`client`, `executor`, `mock`, `prompt`, `rate_limit`, `schema`).
"""

from __future__ import annotations

from .schema import LLMResponse, TradeAction, WatchlistChange

__all__ = ["LLMResponse", "TradeAction", "WatchlistChange"]
