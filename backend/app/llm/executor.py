"""Execute the actions returned by the LLM (PLAN §9).

The executor iterates `trades` then `watchlist_changes` in order, calling
into the same service functions that back the REST endpoints — so the
validation rules and snapshot bookkeeping are identical to manual trades.

Best-effort semantics: a failure in one action is captured into the
`errors` list but does NOT abort the remaining actions. A later sell may
succeed after an earlier oversized buy is rejected.
"""

from __future__ import annotations

import logging
from typing import Any

from ..db import trades_repo
from ..errors import ApiError
from ..market import MarketDataSource, PriceCache
from ..services import portfolio_service, watchlist_service
from .schema import LLMResponse, TradeAction, WatchlistChange

logger = logging.getLogger(__name__)


async def execute_actions(
    response: LLMResponse,
    cache: PriceCache,
    source: MarketDataSource,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Execute every trade and watchlist change in `response`.

    Returns `(executed_trades, executed_watchlist_changes, errors)`.

    - `executed_trades`: persisted `Trade` rows serialized as dicts.
    - `executed_watchlist_changes`: `{ticker, action}` entries that
      succeeded — the action's terminal state.
    - `errors`: `{action, code, detail}` entries describing failures. The
      `action` field is the original LLM-supplied dict so the frontend can
      render a meaningful "couldn't execute X" message.
    """
    executed_trades: list[dict] = []
    executed_watchlist: list[dict] = []
    errors: list[dict] = []

    for trade in response.trades:
        try:
            persisted = portfolio_service.execute_trade(
                cache=cache,
                ticker=trade.ticker,
                side=trade.side,
                quantity=trade.quantity,
            )
            executed_trades.append(_trade_to_dict(persisted))
        except ApiError as exc:
            logger.info(
                "llm.trade.failed ticker=%s side=%s qty=%s code=%s detail=%s",
                trade.ticker,
                trade.side,
                trade.quantity,
                exc.code,
                exc.detail,
            )
            errors.append(
                {
                    "action": _trade_action_dict(trade),
                    "code": exc.code,
                    "detail": str(exc.detail),
                }
            )
        except Exception as exc:  # noqa: BLE001 - bug-safety net
            logger.exception("llm.trade.unhandled ticker=%s", trade.ticker)
            errors.append(
                {
                    "action": _trade_action_dict(trade),
                    "code": "LLM_ERROR",
                    "detail": f"unhandled error: {exc}",
                }
            )

    for change in response.watchlist_changes:
        try:
            if change.action == "add":
                entry = await watchlist_service.add(cache, source, change.ticker)
                executed_watchlist.append(
                    {"ticker": entry.ticker, "action": "add"}
                )
            else:
                await watchlist_service.remove(cache, source, change.ticker)
                executed_watchlist.append(
                    {"ticker": change.ticker, "action": "remove"}
                )
        except ApiError as exc:
            logger.info(
                "llm.watchlist.failed ticker=%s action=%s code=%s detail=%s",
                change.ticker,
                change.action,
                exc.code,
                exc.detail,
            )
            errors.append(
                {
                    "action": _watchlist_change_dict(change),
                    "code": exc.code,
                    "detail": str(exc.detail),
                }
            )
        except Exception as exc:  # noqa: BLE001 - bug-safety net
            logger.exception(
                "llm.watchlist.unhandled ticker=%s action=%s",
                change.ticker,
                change.action,
            )
            errors.append(
                {
                    "action": _watchlist_change_dict(change),
                    "code": "LLM_ERROR",
                    "detail": f"unhandled error: {exc}",
                }
            )

    return executed_trades, executed_watchlist, errors


def _trade_to_dict(trade: trades_repo.Trade) -> dict[str, Any]:
    return {
        "id": trade.id,
        "ticker": trade.ticker,
        "side": trade.side,
        "quantity": trade.quantity,
        "price": trade.price,
        "executed_at": trade.executed_at,
    }


def _trade_action_dict(action: TradeAction) -> dict[str, Any]:
    return {
        "type": "trade",
        "ticker": action.ticker,
        "side": action.side,
        "quantity": action.quantity,
    }


def _watchlist_change_dict(change: WatchlistChange) -> dict[str, Any]:
    return {
        "type": "watchlist_change",
        "ticker": change.ticker,
        "action": change.action,
    }


__all__ = ["execute_actions"]
