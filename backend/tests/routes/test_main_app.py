"""Lightweight smoke tests for the FastAPI app factory.

We don't run the full lifespan (which starts the GBM simulator); instead
we verify that the module imports cleanly, exposes the expected ASGI
attribute, and that the basic routing is wired.
"""

from __future__ import annotations


def test_app_factory_creates_fastapi_instance():
    from fastapi import FastAPI

    from app.main import app, create_app

    assert isinstance(app, FastAPI)
    rebuilt = create_app()
    assert isinstance(rebuilt, FastAPI)


def test_routes_registered():
    from app.main import app

    paths = {route.path for route in app.routes if hasattr(route, "path")}
    # Core API surface — chat endpoints owned by a different task, so we
    # don't assert on those.
    assert "/api/health" in paths
    assert "/api/portfolio" in paths
    assert "/api/portfolio/trade" in paths
    assert "/api/portfolio/history" in paths
    assert "/api/portfolio/trades" in paths
    assert "/api/watchlist" in paths
