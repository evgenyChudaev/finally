"""Chat routes: POST /api/chat and GET /api/chat/history (PLAN §8/§9).

The POST endpoint orchestrates a full chat turn:

1. Per-process rate limit (10 req/min).
2. Persist the user message.
3. Build portfolio + watchlist context.
4. Pull the last 20 chat rows for conversation history.
5. Call the LLM (or the mock when `LLM_MOCK=true`).
6. Validate + execute returned actions (best-effort, partial failures
   captured in `errors`).
7. Persist the assistant row with an `actions` JSON capturing executed
   trades, watchlist changes, and any errors.
8. Return the same payload to the frontend.

The GET endpoint returns recent history in chronological order so the chat
panel can rehydrate on page load.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ..db import chat_repo, watchlist_repo
from ..errors import LLM_ERROR, RATE_LIMITED, ApiError
from ..llm import client as llm_client
from ..llm import executor as llm_executor
from ..llm import mock as llm_mock
from ..llm import prompt as llm_prompt
from ..llm.rate_limit import chat_rate_limiter
from ..llm.schema import LLMResponse
from ..services import portfolio_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_GENERIC_LLM_ERROR_MESSAGE = (
    "Sorry, I couldn't reach the model just now. Please try again."
)


class ChatRequest(BaseModel):
    """`POST /api/chat` request body."""

    model_config = ConfigDict(extra="ignore")

    message: str = Field(..., min_length=1)


class ChatMessageResponse(BaseModel):
    """One row of `GET /api/chat/history`."""

    id: int
    role: Literal["user", "assistant"]
    content: str
    actions: dict[str, Any] | None = None
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]


def _llm_mock_enabled() -> bool:
    """Read `LLM_MOCK` at request time so tests can flip it via env."""
    raw = os.environ.get("LLM_MOCK", "")
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _load_recent_history_for_llm(limit: int = 20) -> list[dict[str, str]]:
    """Pull the last `limit` chat rows in chronological order for the prompt."""
    rows = chat_repo.recent_messages(limit=limit)
    return [{"role": row.role, "content": row.content} for row in rows]


def _build_watchlist_for_context(cache) -> list[dict[str, Any]]:
    """Snapshot the watchlist + cache prices for the per-turn context block."""
    entries = watchlist_repo.list_tickers()
    out: list[dict[str, Any]] = []
    for entry in entries:
        price = cache.get_price(entry.ticker)
        out.append({"ticker": entry.ticker, "current_price": price})
    return out


@router.post("")
async def post_chat(request: Request, body: ChatRequest) -> dict[str, Any]:
    """Run one chat turn: persist user msg, call LLM, execute, persist asst msg."""
    # ---- Rate limit (10/min/process). --------------------------------------
    if not chat_rate_limiter.try_acquire():
        raise ApiError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code=RATE_LIMITED,
            detail="too many chat requests; try again shortly",
        )

    user_message = body.message.strip()
    if not user_message:
        # ChatRequest already enforces min_length=1 but the trim guards
        # against pure-whitespace bodies that slip through.
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            detail="message cannot be empty",
        )

    cache = request.app.state.price_cache
    source = request.app.state.market_source

    # Persist the user turn first so the conversation log is consistent even
    # if the LLM call below fails mid-flight.
    chat_repo.append_message("user", user_message)

    # Build the prompt context.
    summary = portfolio_service.summarize(cache)
    watchlist = _build_watchlist_for_context(cache)
    context_block = llm_prompt.build_context_block(
        summary, watchlist, summary.total_value
    )
    history = _load_recent_history_for_llm(limit=20)
    # `recent_messages` includes the user row we just persisted; drop it so
    # the LLM sees the new message exactly once (it is also passed
    # separately as the final `user_message` to keep history shapes clean).
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    # ---- LLM call (or mock). -----------------------------------------------
    llm_response: LLMResponse
    llm_call_error: dict[str, Any] | None = None

    if _llm_mock_enabled():
        llm_response = llm_mock.mock_response(user_message)
    else:
        try:
            llm_response = llm_client.complete(
                llm_prompt.build_system_prompt(),
                context_block,
                history,
                user_message,
            )
        except llm_client.LLMClientError as exc:
            logger.warning("chat.llm-error err=%s", exc)
            llm_response = LLMResponse(
                message=_GENERIC_LLM_ERROR_MESSAGE,
            )
            llm_call_error = {
                "action": None,
                "code": LLM_ERROR,
                "detail": str(exc),
            }

    # ---- Execute actions (skipping when the LLM call itself failed). -------
    executed_trades: list[dict[str, Any]]
    executed_watchlist: list[dict[str, Any]]
    action_errors: list[dict[str, Any]]
    if llm_call_error is None:
        (
            executed_trades,
            executed_watchlist,
            action_errors,
        ) = await llm_executor.execute_actions(llm_response, cache, source)
    else:
        executed_trades = []
        executed_watchlist = []
        action_errors = []

    errors: list[dict[str, Any]] = []
    if llm_call_error is not None:
        errors.append(llm_call_error)
    errors.extend(action_errors)

    # ---- Persist the assistant turn. ---------------------------------------
    actions_payload: dict[str, Any] = {
        "trades": executed_trades,
        "watchlist_changes": executed_watchlist,
        "errors": errors,
    }
    chat_repo.append_message(
        "assistant",
        llm_response.message,
        actions=actions_payload,
    )

    return {
        "message": llm_response.message,
        "trades": executed_trades,
        "watchlist_changes": executed_watchlist,
        "errors": errors,
    }


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    limit: int = Query(default=50, ge=1, le=500),
) -> ChatHistoryResponse:
    """Return up to `limit` recent chat messages in chronological order."""
    rows = chat_repo.recent_messages(limit=limit)
    return ChatHistoryResponse(
        messages=[
            ChatMessageResponse(
                id=row.id,
                role=row.role,
                content=row.content,
                actions=row.actions,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )
