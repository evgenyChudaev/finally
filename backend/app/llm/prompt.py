"""Prompt construction for the FinAlly chat assistant (PLAN §9).

Two helpers:

- `build_system_prompt()` — static system message framing the model as
  "FinAlly, an AI trading assistant" and pinning the structured-JSON output
  schema.
- `build_context_block(portfolio_summary, watchlist, total_value)` — a
  per-turn context block summarizing the user's current state. Inserted as
  a system-role message right after the static system prompt so the model
  sees it before the chat history.

The structured-output JSON shape is documented inline because the
non-schema fallback in `client.py` relies on the model honoring it from
the prompt alone.
"""

from __future__ import annotations

from typing import Any

_SYSTEM_PROMPT = (
    "You are FinAlly, an AI trading assistant embedded in the user's "
    "simulated trading workstation. You can analyze the user's portfolio, "
    "suggest trades with concise, data-driven reasoning, execute trades on "
    "the user's behalf, and manage their watchlist.\n"
    "\n"
    "Behavior rules:\n"
    "- Be concise and direct. Lead with the answer, then the rationale.\n"
    "- When the user asks you to trade or modify the watchlist, include "
    "the corresponding entries in the structured response — do NOT ask for "
    "confirmation. This is a simulated environment.\n"
    "- Only propose trades the user can afford and sells for shares the "
    "user actually holds. The backend will reject impossible trades.\n"
    "- All tickers must be uppercase US equity symbols (e.g. AAPL, MSFT).\n"
    "- Always reply with a single JSON object matching this exact schema:\n"
    "  {\n"
    '    "message": "<your conversational reply>",\n'
    '    "trades": [ {"ticker": "AAPL", "side": "buy"|"sell", '
    '"quantity": <number>} ],\n'
    '    "watchlist_changes": [ {"ticker": "AAPL", '
    '"action": "add"|"remove"} ]\n'
    "  }\n"
    "- `trades` and `watchlist_changes` MUST be arrays; use [] when there "
    "are none. Never return anything other than valid JSON."
)


def build_system_prompt() -> str:
    """Return the static system prompt used for every chat turn."""
    return _SYSTEM_PROMPT


def build_context_block(
    portfolio_summary: Any,
    watchlist: list[dict],
    total_value: float,
) -> str:
    """Build the per-turn portfolio + watchlist context block.

    `portfolio_summary` accepts either a `PortfolioSummary` dataclass or a
    plain dict with the same shape (`cash_balance`, `positions`) — letting
    tests pass simple dicts.
    """
    cash = _attr(portfolio_summary, "cash_balance")
    positions = _attr(portfolio_summary, "positions") or []

    lines: list[str] = []
    lines.append("Current portfolio snapshot:")
    lines.append(f"- Cash: ${_money(cash)}")
    lines.append(f"- Total value: ${_money(total_value)}")
    if positions:
        lines.append("- Positions:")
        for pos in positions:
            ticker = _attr(pos, "ticker")
            qty = _attr(pos, "quantity")
            avg = _attr(pos, "avg_cost")
            price = _attr(pos, "current_price")
            pl = _attr(pos, "unrealized_pl")
            pct = _attr(pos, "pct_change")
            lines.append(
                f"  - {ticker}: qty={qty}, avg_cost=${_money(avg)}, "
                f"price=${_money(price)}, "
                f"unrealized_pl=${_money(pl)} ({_money(pct)}%)"
            )
    else:
        lines.append("- Positions: none")

    if watchlist:
        lines.append("- Watchlist (live prices):")
        for entry in watchlist:
            ticker = _attr(entry, "ticker")
            price = _attr(entry, "current_price")
            lines.append(f"  - {ticker}: ${_money(price)}")
    else:
        lines.append("- Watchlist: empty")

    return "\n".join(lines)


def _attr(obj: Any, name: str) -> Any:
    """Read `name` from either a mapping or an attribute on a dataclass."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _money(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


__all__ = ["build_system_prompt", "build_context_block"]
