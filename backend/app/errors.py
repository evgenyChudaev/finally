"""Consistent error envelope for the FinAlly API.

Every error response follows the `{detail, code}` shape from PLAN §8. Routes
raise `ApiError` which is converted to a JSON response by an exception
handler installed in `app.main`.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Canonical error codes from PLAN §8.
INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
INSUFFICIENT_SHARES = "INSUFFICIENT_SHARES"
UNKNOWN_TICKER = "UNKNOWN_TICKER"
INVALID_QUANTITY = "INVALID_QUANTITY"
TICKER_ALREADY_WATCHED = "TICKER_ALREADY_WATCHED"
TICKER_NOT_WATCHED = "TICKER_NOT_WATCHED"
RATE_LIMITED = "RATE_LIMITED"
LLM_ERROR = "LLM_ERROR"
VALIDATION_ERROR = "VALIDATION_ERROR"


class ApiError(HTTPException):
    """HTTPException variant that carries our `code` alongside `detail`.

    FastAPI's default behavior wraps `detail` in `{"detail": ...}` for the
    JSON body. We install an exception handler that flattens that into
    `{"detail": str, "code": str}` instead.
    """

    def __init__(self, *, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    """Convert an `ApiError` into the canonical `{detail, code}` JSON body."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Map Pydantic validation failures to our envelope.

    FastAPI normally returns 422 with a verbose body; we keep the body simple
    so the frontend can switch on a single code.
    """
    # Use the first error message for the user-facing detail; the structured
    # list is available in logs if you re-raise.
    first = exc.errors()[0] if exc.errors() else {"msg": "invalid request"}
    location = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    msg = first.get("msg", "invalid request")
    detail = f"{location}: {msg}" if location else msg
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail, "code": VALIDATION_ERROR},
    )
