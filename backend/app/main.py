"""FinAlly FastAPI application.

This module exposes the ASGI application object as a module-level `app` for
uvicorn / docker (`uvicorn app.main:app`). The `create_app()` factory does
all the wiring so tests can mint an isolated instance with a tmp DB and a
prefilled price cache.

Startup:
    1. Configure logging.
    2. Lazily initialize the SQLite database (creates tables + seeds if
       empty).
    3. Build the `PriceCache` and a `MarketDataSource` (simulator unless
       `MASSIVE_API_KEY` is set).
    4. Start the source against the union of the current watchlist tickers
       and the default seed (so a fresh DB still has live prices).
    5. Wait briefly for the first prices, then record an initial
       `portfolio_snapshots` row anchoring the P&L chart.

Shutdown:
    Stop the data source. The SQLite connections are closed eagerly by the
    repos' context manager so there is nothing to clean up there.

Routes:
    /api/health, /api/portfolio/*, /api/watchlist/*, /api/stream/prices.
    The chat endpoints are owned by the LLM team — they're optional here.

Static assets:
    If `app/static/` exists (populated by the Docker build copying the
    Next.js export), it's mounted as the root site with a SPA catch-all so
    non-`/api/*` paths fall back to `index.html`.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .db.database import DEFAULT_WATCHLIST_TICKERS, _watchlist_from_env
from .errors import ApiError, api_error_handler, validation_error_handler
from .logging_config import configure_logging
from .market import PriceCache, create_market_data_source, create_stream_router
from .routes import chat as chat_routes
from .routes import health as health_routes
from .routes import portfolio as portfolio_routes
from .routes import watchlist as watchlist_routes
from .services import portfolio_service

logger = logging.getLogger(__name__)

# How long startup will wait for the first batch of prices before recording
# the initial snapshot. The simulator usually delivers in well under a
# second; the Massive client may take a poll interval.
_STARTUP_PRICE_TIMEOUT = 3.0
_STARTUP_PRICE_POLL = 0.05

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _initial_tickers() -> list[str]:
    """Tickers the data source should track at startup.

    The union of:
    - whatever is on the watchlist in the DB right now, and
    - the configured default seed (so a brand-new DB has price data even
      before the first watchlist read).
    """
    from .db import watchlist_repo  # local import to avoid cycles

    seed = list(_watchlist_from_env()) or list(DEFAULT_WATCHLIST_TICKERS)
    watched = [row.ticker for row in watchlist_repo.list_tickers()]
    combined: list[str] = []
    seen: set[str] = set()
    for ticker in [*watched, *seed]:
        upper = ticker.strip().upper()
        if upper and upper not in seen:
            seen.add(upper)
            combined.append(upper)
    return combined


async def _await_first_prices(cache: PriceCache, tickers: list[str]) -> None:
    """Wait up to `_STARTUP_PRICE_TIMEOUT` for any price to land.

    We don't require every ticker to have ticked — just at least one, so the
    initial portfolio snapshot reflects a reasonable starting point. If
    nothing arrives in time (e.g. an offline Massive API) we record the
    snapshot anyway using cash + cost-basis fallback.
    """
    if not tickers:
        return
    elapsed = 0.0
    while elapsed < _STARTUP_PRICE_TIMEOUT:
        if cache.version > 0:
            return
        await asyncio.sleep(_STARTUP_PRICE_POLL)
        elapsed += _STARTUP_PRICE_POLL


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Async context manager driving startup + shutdown."""
    configure_logging()
    logger.info("app.start")

    db.init_db()

    # Reuse the cache created eagerly in `create_app()` so the SSE router can
    # be registered before the static catch-all. Fall back to a fresh cache
    # for backwards compatibility (e.g. tests that bypass `create_app`).
    # NOTE: `PriceCache` defines `__len__`, so an empty cache is falsy under
    # boolean coercion — use an explicit `is None` check, not `or`.
    pre_existing = getattr(app.state, "price_cache", None)
    cache = pre_existing if pre_existing is not None else PriceCache()
    source = create_market_data_source(cache)

    tickers = _initial_tickers()
    logger.info("market.start tickers=%s", ",".join(tickers))
    await source.start(tickers)
    await _await_first_prices(cache, tickers)

    # Anchor the P&L chart's left edge. Tolerate failures so a misconfigured
    # DB volume doesn't break the whole app — startup will surface the real
    # error elsewhere if there is one.
    try:
        total_value = portfolio_service.compute_total_value(cache)
        from .db import snapshots_repo  # local import to avoid cycles

        snapshots_repo.record_snapshot(total_value)
        logger.info("portfolio.snapshot.initial total_value=%.2f", total_value)
    except Exception as exc:  # noqa: BLE001 - keep app running
        logger.warning("portfolio.snapshot.initial failed: %s", exc)

    app.state.price_cache = cache
    app.state.market_source = source

    try:
        yield
    finally:
        logger.info("app.shutdown")
        try:
            await source.stop()
        except Exception as exc:  # noqa: BLE001 - shutdown should not raise
            logger.warning("market.stop failed: %s", exc)


def create_app() -> FastAPI:
    """Build and wire the FastAPI application."""
    # Allow tests / scripts that bypass lifespan to still pick up logging
    # config (e.g. running uvicorn against an alternate ASGI app).
    configure_logging()

    app = FastAPI(
        title="FinAlly",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # Error envelope: every ApiError / validation failure → {detail, code}.
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # Default exception handler — log and emit our envelope so the frontend
    # has something predictable to render.
    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("api.unhandled %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "internal server error",
                "code": "INTERNAL_ERROR",
            },
        )

    # API routers.
    app.include_router(health_routes.router)
    app.include_router(portfolio_routes.router)
    app.include_router(watchlist_routes.router)
    app.include_router(chat_routes.router)

    # Create the PriceCache eagerly and register the SSE stream router BEFORE
    # the static catch-all below. FastAPI matches routes in registration
    # order, so if the catch-all is registered first it shadows /api/stream/*.
    # `_lifespan` reuses this cache via `app.state.price_cache`.
    cache = PriceCache()
    app.state.price_cache = cache
    app.include_router(create_stream_router(cache))

    # Optional static frontend export.
    if STATIC_DIR.is_dir():
        # Mount the assets directory so /_next/* and other build paths
        # resolve. We deliberately mount at a sub-path that won't collide
        # with /api/*; the SPA root + arbitrary routes fall through to the
        # catch-all below.
        next_dir = STATIC_DIR / "_next"
        if next_dir.is_dir():
            app.mount(
                "/_next",
                StaticFiles(directory=str(next_dir)),
                name="next_assets",
            )

        index_html = STATIC_DIR / "index.html"

        @app.get("/", include_in_schema=False)
        async def _index() -> FileResponse:  # pragma: no cover - trivial
            return FileResponse(str(index_html))

        # SPA catch-all: serve static files when they exist, otherwise
        # fall back to index.html. Excludes /api/* via path order
        # (routers are registered first and match longer prefixes).
        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa(full_path: str):  # pragma: no cover - file serving
            if full_path.startswith("api/"):
                # Defensive: should already be handled by /api routers.
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "not found", "code": "NOT_FOUND"},
                )
            candidate = STATIC_DIR / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            # SPA fallback.
            if index_html.is_file():
                return FileResponse(str(index_html))
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "not found", "code": "NOT_FOUND"},
            )

    return app


# Module-level ASGI app for uvicorn / docker.
app = create_app()


__all__ = ["app", "create_app"]
