"""LiteLLM client targeting OpenRouter with Cerebras inference (PLAN §9).

We follow the `cerebras-inference` skill recipe:

    from litellm import completion
    MODEL = "openrouter/openai/gpt-oss-120b"
    EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

Two structured-output strategies are attempted, in order:

1. `response_format=LLMResponse` — LiteLLM's Pydantic shortcut, which
   translates into an OpenAI-style `json_schema` payload. This is the
   strongest guarantee on routes that support it.
2. Fallback: `response_format={"type": "json_object"}` + the schema baked
   into the system prompt + server-side Pydantic validation. Used when
   strategy 1 raises (some Cerebras-routed models reject schema mode).

Either way, the caller receives an already-validated `LLMResponse`. Raw
text and provider errors are surfaced as `LLMClientError` so the route can
emit a generic message and log the failure.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .schema import LLMResponse

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY: dict[str, Any] = {"provider": {"order": ["cerebras"]}}

# How hard the model should think before replying. "low" is appropriate for
# fast conversational responses; the skill recipe uses the same value.
REASONING_EFFORT = "low"


class LLMClientError(RuntimeError):
    """Raised when the LLM call fails or returns un-parseable output."""


def complete(
    system_prompt: str,
    context_block: str,
    history: list[dict[str, str]],
    user_message: str,
) -> LLMResponse:
    """Call the LLM and return a validated `LLMResponse`.

    `history` is a list of `{role, content}` dicts in chronological order,
    excluding the brand-new `user_message` (which is appended last). It is
    expected to be pre-bounded to the last 20 rows by the caller per
    PLAN §9.

    Raises `LLMClientError` for any provider / parsing failure. The caller
    is responsible for turning that into a graceful user-facing reply and
    persisting the LLM_ERROR row.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise LLMClientError("OPENROUTER_API_KEY is not set")

    try:
        # Import lazily so test envs without litellm installed can still
        # import the module to reach the mock path.
        from litellm import completion  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001 - import-time failure
        raise LLMClientError(f"litellm import failed: {exc}") from exc

    messages = _build_messages(system_prompt, context_block, history, user_message)

    # ---- Strategy 1: json_schema via LiteLLM's Pydantic shortcut. -----------
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=LLMResponse,
            reasoning_effort=REASONING_EFFORT,
            extra_body=EXTRA_BODY,
        )
        raw = _extract_content(response)
        return _parse_or_raise(raw)
    except LLMClientError:
        # _parse_or_raise wants us to keep its error — re-raise to outer.
        raise
    except Exception as exc:  # noqa: BLE001 - try fallback
        logger.warning(
            "llm.schema-mode-failed err=%s; falling back to json_object", exc
        )

    # ---- Strategy 2: json_object + Pydantic validation. ---------------------
    try:
        response = completion(
            model=MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            reasoning_effort=REASONING_EFFORT,
            extra_body=EXTRA_BODY,
        )
    except Exception as exc:  # noqa: BLE001 - final failure
        raise LLMClientError(f"LLM provider error: {exc}") from exc

    raw = _extract_content(response)
    return _parse_or_raise(raw)


def _build_messages(
    system_prompt: str,
    context_block: str,
    history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    """Compose the LiteLLM `messages` array."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": context_block},
    ]
    for row in history:
        role = row.get("role")
        content = row.get("content")
        if role not in ("user", "assistant") or not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _extract_content(response: Any) -> str:
    """Pull the text content out of a LiteLLM response object."""
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError, KeyError, TypeError) as exc:
        raise LLMClientError(
            f"unexpected LLM response shape: {type(response).__name__}"
        ) from exc


def _parse_or_raise(raw: str) -> LLMResponse:
    """Validate `raw` as `LLMResponse`. Treat malformed output as fatal."""
    if not raw:
        raise LLMClientError("empty LLM response")
    try:
        return LLMResponse.model_validate_json(raw)
    except Exception as first_err:  # noqa: BLE001 - try one more tactic
        # Some models wrap JSON in code fences or prefix it with a sentence.
        # Try to extract the first {...} object before giving up.
        snippet = _extract_json_object(raw)
        if snippet is None:
            logger.warning("llm.parse-failed raw=%r err=%s", raw[:500], first_err)
            raise LLMClientError(
                f"LLM response was not valid JSON: {first_err}"
            ) from first_err
        try:
            return LLMResponse.model_validate_json(snippet)
        except Exception as exc:  # noqa: BLE001 - give up
            logger.warning("llm.parse-failed-snippet raw=%r err=%s", raw[:500], exc)
            raise LLMClientError(
                f"LLM response was not valid JSON: {exc}"
            ) from exc


def _extract_json_object(raw: str) -> str | None:
    """Return the first balanced `{...}` substring in `raw`, or None."""
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                snippet = raw[start : i + 1]
                # Quick sanity check that it parses as JSON at all.
                try:
                    json.loads(snippet)
                except json.JSONDecodeError:
                    return None
                return snippet
    return None


__all__ = ["complete", "LLMClientError", "MODEL", "EXTRA_BODY"]
