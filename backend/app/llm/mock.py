"""Deterministic mock LLM responses (PLAN §9 Mock Mode).

When `LLM_MOCK=true` the chat route uses `mock_response` instead of calling
OpenRouter. The mock implements the keyword table from PLAN §9:

| Pattern (case-insensitive)        | Effect                                       |
| --------------------------------- | -------------------------------------------- |
| `buy <N> <TICKER>`                | one TradeAction: side="buy"                  |
| `sell <N> <TICKER>`               | one TradeAction: side="sell"                 |
| `add <TICKER>` (to watchlist)     | one WatchlistChange: action="add"            |
| `remove <TICKER>` (from list)     | one WatchlistChange: action="remove"         |
| (anything else)                   | canned default message, no actions           |

Mock output flows through the same executor + validation path as real
output, so E2E tests exercise the full chat pipeline.
"""

from __future__ import annotations

import re

from .schema import LLMResponse, TradeAction, WatchlistChange

# Quantity may be int or float (e.g. "buy 0.5 AAPL"). Ticker is 1-6 uppercase
# letters (typical US equity range); we match case-insensitively and upper-case
# in the Pydantic validator.
_TRADE_RE = re.compile(
    r"\b(?P<side>buy|sell)\s+(?P<qty>\d+(?:\.\d+)?)\s+(?P<ticker>[A-Z]{1,6})\b",
    re.IGNORECASE,
)
_WATCHLIST_RE = re.compile(
    r"\b(?P<action>add|remove)\s+(?P<ticker>[A-Z]{1,6})\b",
    re.IGNORECASE,
)

_DEFAULT_MESSAGE = (
    "Mock LLM response. Try 'buy 5 AAPL' or ask for analysis."
)


def mock_response(user_message: str) -> LLMResponse:
    """Return a deterministic `LLMResponse` for the given user message.

    Matching is exhaustive: every trade pattern in the message generates a
    `TradeAction`, every watchlist pattern generates a `WatchlistChange`.
    Trades take precedence over watchlist matches when text overlaps —
    e.g. "buy 5 AAPL" is parsed as a trade, not as a watchlist add.
    """
    if not user_message:
        return LLMResponse(message=_DEFAULT_MESSAGE)

    trades: list[TradeAction] = []
    consumed_spans: list[tuple[int, int]] = []

    for match in _TRADE_RE.finditer(user_message):
        side = match.group("side").lower()
        ticker = match.group("ticker").upper()
        try:
            qty = float(match.group("qty"))
        except ValueError:  # pragma: no cover - regex guarantees float-parsable
            continue
        if qty <= 0:
            continue
        trades.append(
            TradeAction(ticker=ticker, side=side, quantity=qty)
        )
        consumed_spans.append(match.span())

    watchlist_changes: list[WatchlistChange] = []
    for match in _WATCHLIST_RE.finditer(user_message):
        # Skip matches that overlap with a parsed trade (e.g. the "5 AAPL"
        # in "buy 5 AAPL" should not also fire a watchlist add for AAPL).
        start, end = match.span()
        if any(start < ce and end > cs for cs, ce in consumed_spans):
            continue
        action = match.group("action").lower()
        ticker = match.group("ticker").upper()
        watchlist_changes.append(
            WatchlistChange(ticker=ticker, action=action)
        )

    if trades or watchlist_changes:
        message_parts: list[str] = []
        for trade in trades:
            verb = "Buying" if trade.side == "buy" else "Selling"
            qty_str = _qty_str(trade.quantity)
            message_parts.append(f"{verb} {qty_str} {trade.ticker}.")
        for change in watchlist_changes:
            if change.action == "add":
                message_parts.append(f"Added {change.ticker} to your watchlist.")
            else:
                message_parts.append(
                    f"Removed {change.ticker} from your watchlist."
                )
        return LLMResponse(
            message=" ".join(message_parts),
            trades=trades,
            watchlist_changes=watchlist_changes,
        )

    return LLMResponse(message=_DEFAULT_MESSAGE)


def _qty_str(qty: float) -> str:
    """Render `qty` without a trailing `.0` for whole-number quantities."""
    if qty == int(qty):
        return str(int(qty))
    return f"{qty:g}"


__all__ = ["mock_response"]
