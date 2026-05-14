"""Health-check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from ..schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe for Docker / load balancers.

    Always returns `{"status": "ok"}` with HTTP 200 as long as the process
    is running and the app object has been mounted.
    """
    return HealthResponse(status="ok")
