# Market Data Backend — Detailed Design

Implementation-ready design for the FinAlly market data subsystem. Covers the unified `MarketDataSource` interface, the in-memory `PriceCache`, the GBM simulator, the Massive (Polygon.io) REST poller, the SSE streaming endpoint, and FastAPI lifecycle integration.

Everything in this document lives under `backend/app/market/`. This design reflects what is actually shipped (see `MARKET_DATA_SUMMARY.md`) and incorporates the fixes from the original code review.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [File Layout](#2-file-layout)
3. [Data Model — `models.py`](#3-data-model--modelspy)
4. [Price Cache — `cache.py`](#4-price-cache--cachepy)
5. [Abstract Interface — `interface.py`](#5-abstract-interface--interfacepy)
6. [Seed Prices & Parameters — `seed_prices.py`](#6-seed-prices--parameters--seed_pricespy)
7. [GBM Simulator — `simulator.py`](#7-gbm-simulator--simulatorpy)
8. [Massive Client — `massive_client.py`](#8-massive-client--massive_clientpy)
9. [Factory — `factory.py`](#9-factory--factorypy)
10. [SSE Streaming Endpoint — `stream.py`](#10-sse-streaming-endpoint--streampy)
11. [FastAPI Lifecycle Integration](#11-fastapi-lifecycle-integration)
12. [Watchlist Coordination](#12-watchlist-coordination)
13. [Testing Strategy](#13-testing-strategy)
14. [Error Handling & Edge Cases](#14-error-handling--edge-cases)
15. [Configuration Summary](#15-configuration-summary)

---

## 1. Architecture Overview

```
                ┌───────────────────────────────┐
                │      MarketDataSource (ABC)   │
                └───────────────┬───────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
   ┌──────────────────────┐         ┌──────────────────────────┐
   │ SimulatorDataSource  │         │   MassiveDataSource      │
   │   (GBM, ~500ms tick) │         │  (REST poll, ~15s)       │
   └──────────┬───────────┘         └────────────┬─────────────┘
              │                                   │
              └──────────────┬────────────────────┘
                             ▼
                    ┌──────────────────┐
                    │   PriceCache     │  ◀── thread-safe, version-counter
                    └────────┬─────────┘
                             │
       ┌─────────────────────┼──────────────────────┐
       ▼                     ▼                      ▼
  SSE /api/stream/prices   Portfolio valuation    Trade execution
```

**Strategy pattern.** Both data sources implement the same ABC. Downstream code (SSE, REST routes, LLM tool calls) is source-agnostic and reads only from the `PriceCache`.

**Push, don't pull.** Data sources are producers — they write into the cache on their own schedule. Consumers never call the source for prices; they read from the cache. This decouples upstream timing (500ms simulator tick vs. 15s Massive poll) from downstream consumers.

**Version-based SSE deltas.** The cache maintains a monotonic version counter, advanced on every write. The SSE handler skips emit when the version hasn't changed — clients receive deltas only, not a fixed-cadence broadcast.

---

## 2. File Layout

```
backend/app/market/
├── __init__.py            # Re-exports the public API
├── models.py              # PriceUpdate dataclass
├── cache.py               # PriceCache (thread-safe, versioned)
├── interface.py           # MarketDataSource ABC
├── seed_prices.py         # SEED_PRICES, TICKER_PARAMS, correlation constants
├── simulator.py           # GBMSimulator + SimulatorDataSource
├── massive_client.py      # MassiveDataSource (REST poller)
├── factory.py             # create_market_data_source()
└── stream.py              # create_stream_router() — SSE endpoint
```

`__init__.py` exposes the public surface so other modules import from `app.market` without reaching into submodules:

```python
from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .stream import create_stream_router

__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

---

## 3. Data Model — `models.py`

`PriceUpdate` is the only data type that escapes the market layer. Frozen and slotted for safety and memory efficiency.

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PriceUpdate:
    """Immutable snapshot of a ticker's price at one moment."""

    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def change(self) -> float:
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        if self.price > self.previous_price:
            return "up"
        if self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

**Design notes**
- `frozen=True` — safe to share across async tasks; no defensive copying.
- `slots=True` — small memory win, helpful since we create many of these.
- Derived properties (`change`, `direction`, `change_percent`) — can't drift out of sync with `price`/`previous_price`.

---

## 4. Price Cache — `cache.py`

The cache is the single source of truth for live prices. Producers write, consumers read. Thread-safe via `threading.Lock` (not `asyncio.Lock`) because the Massive client's synchronous methods run inside `asyncio.to_thread()`.

```python
from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory store of the latest price per ticker."""

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Bumped on every write

    def update(
        self,
        ticker: str,
        price: float,
        timestamp: float | None = None,
    ) -> PriceUpdate:
        """Record a price; auto-derives previous_price from prior value."""
        with self._lock:
            ts = timestamp if timestamp is not None else time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def get_all(self) -> dict[str, PriceUpdate]:
        with self._lock:
            return dict(self._prices)

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)
            self._version += 1  # Removal is a change too

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: str) -> bool:
        with self._lock:
            return ticker in self._prices
```

**Why the version counter?** The SSE handler polls the cache on a short interval. Without versioning, it would re-serialize and resend the entire snapshot every poll, even when nothing changed (e.g., between Massive's 15s polls). With the counter, the handler skips sends when `cache.version == last_sent_version`.

**Why `threading.Lock`?** The Massive client is synchronous; it runs in a real OS thread via `asyncio.to_thread()`. An `asyncio.Lock` would not protect against that. `threading.Lock` works correctly from both sync threads and the async event loop.

**Lock the version read.** Even though reading a Python `int` is atomic under the GIL, locking is consistent with the rest of the class and is forward-compatible with no-GIL Python builds.

---

## 5. Abstract Interface — `interface.py`

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Producer that writes price updates into a shared PriceCache.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL"])
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        await source.stop()
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing updates. Call exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task. Idempotent."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the active set; no-op if already present."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the active set and from the cache."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the currently tracked tickers."""
```

The contract is intentionally minimal. The source pushes into a cache injected at construction; the interface doesn't expose any read methods because consumers should always read from the cache.

---

## 6. Seed Prices & Parameters — `seed_prices.py`

Pure data, no logic. Shared by the simulator and useful as fallback display values before the first Massive poll lands.

```python
"""Seed prices and per-ticker GBM parameters for the simulator."""

SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00,
    "GOOGL": 175.00,
    "MSFT": 420.00,
    "AMZN": 185.00,
    "TSLA": 250.00,
    "NVDA": 800.00,
    "META": 500.00,
    "JPM": 195.00,
    "V": 280.00,
    "NFLX": 600.00,
}

# Annualized drift (mu) and volatility (sigma) per ticker.
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},   # High vol
    "NVDA":  {"sigma": 0.40, "mu": 0.08},   # High vol, strong drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},
    "V":     {"sigma": 0.17, "mu": 0.04},
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}

CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR    = 0.6   # Tech stocks move together
INTRA_FINANCE_CORR = 0.5   # Finance stocks move together
CROSS_GROUP_CORR   = 0.3   # Different sectors or anything else
TSLA_CORR          = 0.3   # TSLA does its own thing
```

(Reviewer's note: an earlier draft defined an unused `DEFAULT_CORR` constant alongside `CROSS_GROUP_CORR`. They were redundant; the code now uses `CROSS_GROUP_CORR` as the catch-all.)

---

## 7. GBM Simulator — `simulator.py`

Two classes in one module:

- `GBMSimulator` — pure math engine, stateful, advances one step at a time.
- `SimulatorDataSource` — `MarketDataSource` implementation that wraps the simulator in an async loop and writes to the cache.

### 7.1 The Math

Geometric Brownian Motion: prices evolve continuously, stay positive, and exhibit the log-normal distribution observed in real markets.

```
S(t+dt) = S(t) · exp( (μ − σ²/2)·dt + σ·√dt · Z )
```

- `μ` annualized drift; `σ` annualized volatility.
- `dt` time step as a fraction of a trading year.
- `Z` correlated standard normal (correlation injected via Cholesky).

For 500 ms ticks across ~252 trading days × 6.5 hours/day:

```
dt = 0.5 / (252 · 6.5 · 3600) ≈ 8.48 × 10⁻⁸
```

The tiny `dt` produces sub-cent per-tick moves that accumulate naturally — about right for intraday realism.

### 7.2 Correlation via Cholesky

Real stocks move together within sectors. We build a pairwise correlation matrix `C` and compute `L = cholesky(C)`. Then correlated draws are obtained from independent ones:

```
Z_correlated = L · Z_independent
```

For valid correlation structures, Cholesky exists (positive semi-definite) and is fast — O(n³), trivially fast for n < 50 tickers.

### 7.3 `GBMSimulator`

```python
from __future__ import annotations

import logging
import math
import random

import numpy as np

from .seed_prices import (
    CORRELATION_GROUPS,
    CROSS_GROUP_CORR,
    DEFAULT_PARAMS,
    INTRA_FINANCE_CORR,
    INTRA_TECH_CORR,
    SEED_PRICES,
    TICKER_PARAMS,
    TSLA_CORR,
)

logger = logging.getLogger(__name__)


class GBMSimulator:
    """Correlated GBM price-path generator."""

    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # ~8.48e-8

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = 0.001,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    # ----- public API -----

    def step(self) -> dict[str, float]:
        """Advance all tickers one tick. Returns {ticker: rounded_price}."""
        n = len(self._tickers)
        if n == 0:
            return {}

        z_ind = np.random.standard_normal(n)
        z = self._cholesky @ z_ind if self._cholesky is not None else z_ind

        result: dict[str, float] = {}
        sqrt_dt = math.sqrt(self._dt)
        for i, ticker in enumerate(self._tickers):
            p = self._params[ticker]
            mu, sigma = p["mu"], p["sigma"]
            drift = (mu - 0.5 * sigma ** 2) * self._dt
            diffusion = sigma * sqrt_dt * float(z[i])
            self._prices[ticker] *= math.exp(drift + diffusion)

            # Random shock event (~0.1% per tick per ticker → ~one every 50s
            # across 10 tickers at 2 ticks/s — enough to keep the dashboard alive).
            if random.random() < self._event_prob:
                magnitude = random.uniform(0.02, 0.05)
                sign = random.choice([-1, 1])
                self._prices[ticker] *= 1.0 + magnitude * sign
                logger.debug(
                    "Shock on %s: %.1f%% %s",
                    ticker, magnitude * 100, "up" if sign > 0 else "down",
                )

            result[ticker] = round(self._prices[ticker], 2)

        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        """Public accessor — avoids reaching into the private list from outside."""
        return list(self._tickers)

    # ----- internals -----

    def _add_ticker_internal(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = rho
                corr[j, i] = rho
        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech = CORRELATION_GROUPS["tech"]
        finance = CORRELATION_GROUPS["finance"]

        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### 7.4 `SimulatorDataSource`

```python
import asyncio

from .cache import PriceCache
from .interface import MarketDataSource


class SimulatorDataSource(MarketDataSource):
    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._sim = GBMSimulator(
            tickers=tickers,
            event_probability=self._event_prob,
        )
        # Seed the cache with initial prices so the SSE stream has data
        # to send on its very first poll — no blank-screen delay.
        for ticker in tickers:
            price = self._sim.get_price(ticker)
            if price is not None:
                self._cache.update(ticker, price)

        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")
        logger.info("Simulator started with %d tickers", len(tickers))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Simulator stopped")

    async def add_ticker(self, ticker: str) -> None:
        if not self._sim:
            return
        self._sim.add_ticker(ticker)
        price = self._sim.get_price(ticker)
        if price is not None:
            self._cache.update(ticker, price)  # Seed immediately
        logger.info("Simulator: added %s", ticker)

    async def remove_ticker(self, ticker: str) -> None:
        if self._sim:
            self._sim.remove_ticker(ticker)
        self._cache.remove(ticker)
        logger.info("Simulator: removed %s", ticker)

    def get_tickers(self) -> list[str]:
        return self._sim.get_tickers() if self._sim else []

    async def _run_loop(self) -> None:
        while True:
            try:
                if self._sim:
                    prices = self._sim.step()
                    for ticker, price in prices.items():
                        self._cache.update(ticker, price)
            except Exception:
                logger.exception("Simulator step failed")
            await asyncio.sleep(self._interval)
```

**Key behaviors**
- **Seed-on-start** — the cache has data before the loop ticks, so the SSE first frame is non-empty.
- **Per-tick exception isolation** — a bad step is logged and the loop continues.
- **Graceful cancellation** — `stop()` cancels the task and awaits it, swallowing `CancelledError`.

---

## 8. Massive Client — `massive_client.py`

REST polling against the Massive (Polygon.io) snapshot endpoint, which returns prices for every requested ticker in a single API call — critical for staying under the free tier's 5 req/min cap.

### 8.1 Why polling, not WebSocket?

- Works on every tier (free includes REST; WebSocket is paid-only).
- Trivial to implement and reason about.
- The 15s polling cadence is fine for the FinAlly UX — the simulator path is what gives the "fast and alive" demo feel; the Massive path is opt-in for users who want real prices.

### 8.2 Implementation

```python
from __future__ import annotations

import asyncio
import logging
from typing import Any

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


class MassiveDataSource(MarketDataSource):
    """REST poller against Massive's snapshot endpoint."""

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,  # Free tier safe default
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: list[str] = []
        self._client: Any = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = [t.upper().strip() for t in tickers]
        # Immediate first poll so the cache has data right away.
        await self._poll_once()
        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(self._tickers), self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        t = ticker.upper().strip()
        if t not in self._tickers:
            self._tickers.append(t)
            logger.info("Massive: %s queued (next poll)", t)

    async def remove_ticker(self, ticker: str) -> None:
        t = ticker.upper().strip()
        self._tickers = [x for x in self._tickers if x != t]
        self._cache.remove(t)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # ----- internals -----

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        if not self._tickers or not self._client:
            return
        try:
            snapshots = await asyncio.to_thread(self._fetch_snapshots)
        except Exception as e:
            # 401, 429, network — log and try again on next interval.
            logger.error("Massive poll failed: %s", e)
            return

        processed = 0
        for snap in snapshots:
            try:
                price = snap.last_trade.price
                timestamp = snap.last_trade.timestamp / 1000.0  # ms → s
                self._cache.update(
                    ticker=snap.ticker,
                    price=price,
                    timestamp=timestamp,
                )
                processed += 1
            except (AttributeError, TypeError) as e:
                logger.warning(
                    "Skipping malformed snapshot for %s: %s",
                    getattr(snap, "ticker", "???"), e,
                )
        logger.debug(
            "Massive poll: updated %d/%d", processed, len(self._tickers),
        )

    def _fetch_snapshots(self) -> list:
        """Synchronous call to the Massive REST API; runs in a thread."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=self._tickers,
        )
```

### 8.3 Error-handling table

| Failure | Behavior |
|---|---|
| 401 Unauthorized | Logged at ERROR; poller keeps running so the user can fix `.env` + restart. |
| 429 Rate Limited | Logged at ERROR; retry next interval. Use a higher `poll_interval` if persistent. |
| Network timeout | Logged at ERROR; retry next interval. |
| Malformed single snapshot | Logged at WARNING; remaining tickers in the batch still processed. |
| All snapshots fail | Cache retains last known prices — better than blanking the UI. |

### 8.4 Import strategy

`massive` is declared a core dependency in `pyproject.toml`, so we import it at module top-level (no lazy imports). This eliminates the test-mocking fragility that an earlier lazy-import design introduced — `patch("app.market.massive_client.RESTClient")` resolves cleanly because `RESTClient` is a real module-level name.

---

## 9. Factory — `factory.py`

The factory picks the implementation based on `MASSIVE_API_KEY`. Per-implementation imports happen inside the branch so simulator-only deployments don't pay for unused work.

```python
from __future__ import annotations

import logging
import os

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """Return the configured data source (unstarted)."""
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()

    if api_key:
        from .massive_client import MassiveDataSource
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)

    from .simulator import SimulatorDataSource
    logger.info("Market data source: GBM Simulator")
    return SimulatorDataSource(price_cache=price_cache)
```

---

## 10. SSE Streaming Endpoint — `stream.py`

The SSE endpoint pushes price events to connected browser clients via `EventSource`. Two important details:

1. **Version-gated emit** — only emits when the cache version advances. No version change → no event.
2. **Per-request router** — `create_stream_router()` creates a fresh `APIRouter` per call, not a module-level singleton. This avoids accidental double-registration in tests.

```python
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

logger = logging.getLogger(__name__)


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter(prefix="/api/stream", tags=["streaming"])

    @router.get("/prices")
    async def stream_prices(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    price_cache: PriceCache,
    request: Request,
    poll_interval: float = 0.25,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames whenever the cache version advances."""
    yield "retry: 1000\n\n"  # Browser auto-reconnect after 1s

    last_version = -1
    client = request.client.host if request.client else "unknown"
    logger.info("SSE connected: %s", client)

    try:
        while True:
            if await request.is_disconnected():
                break

            current = price_cache.version
            if current != last_version:
                last_version = current
                snapshot = price_cache.get_all()
                if snapshot:
                    payload = {t: u.to_dict() for t, u in snapshot.items()}
                    yield f"data: {json.dumps(payload)}\n\n"

            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("SSE disconnected: %s", client)
```

### Wire format

```
retry: 1000

data: {"AAPL":{"ticker":"AAPL","price":190.50,"previous_price":190.42,
       "timestamp":1707580800.5,"change":0.08,"change_percent":0.042,
       "direction":"up"}, "GOOGL":{...}}
```

### Client usage

```javascript
const es = new EventSource('/api/stream/prices');
es.onmessage = (e) => {
  const prices = JSON.parse(e.data);
  for (const [ticker, u] of Object.entries(prices)) {
    updateTicker(ticker, u);  // CSS flash, sparkline append, etc.
  }
};
es.onerror = () => setConnectionStatus('reconnecting');
```

---

## 11. FastAPI Lifecycle Integration

The market data system is wired into the FastAPI `lifespan` context manager, so it starts with the app and stops cleanly on shutdown.

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.market import (
    PriceCache,
    MarketDataSource,
    create_market_data_source,
    create_stream_router,
)
from app.db import load_watchlist_tickers  # reads from SQLite


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- STARTUP ----
    price_cache = PriceCache()
    source: MarketDataSource = create_market_data_source(price_cache)

    initial_tickers = await load_watchlist_tickers()
    await source.start(initial_tickers)

    app.state.price_cache = price_cache
    app.state.market_source = source
    app.include_router(create_stream_router(price_cache))

    yield  # App is running

    # ---- SHUTDOWN ----
    await source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)


def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache

def get_market_source(request: Request) -> MarketDataSource:
    return request.app.state.market_source
```

### Using the cache from a route

```python
@router.post("/api/portfolio/trade")
async def execute_trade(
    body: TradeRequest,
    cache: PriceCache = Depends(get_price_cache),
):
    price = cache.get_price(body.ticker)
    if price is None:
        raise HTTPException(400, detail={
            "detail": f"Unknown ticker {body.ticker}",
            "code": "UNKNOWN_TICKER",
        })
    # ... fill at `price` ...
```

---

## 12. Watchlist Coordination

Adding or removing a watchlist entry must be reflected in the data source so the cache tracks the right set of tickers.

```python
@router.post("/api/watchlist")
async def add_to_watchlist(
    body: WatchlistAdd,
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
):
    ticker = body.ticker.upper().strip()
    # Validate unknown-ticker policy: the source must recognize it.
    # Simulator accepts any string; Massive will fail-silently on next poll.
    await db.insert_watchlist(ticker)
    await source.add_ticker(ticker)
    return {
        "ticker": ticker,
        "current_price": cache.get_price(ticker),
    }


@router.delete("/api/watchlist/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    source: MarketDataSource = Depends(get_market_source),
):
    await db.delete_watchlist(ticker)
    # Edge case: keep streaming the price if the user still holds a position,
    # so portfolio valuation stays accurate.
    if not await db.has_open_position(ticker):
        await source.remove_ticker(ticker)
    return {"status": "ok"}
```

### Add flows side-by-side

| Step | Simulator | Massive |
|---|---|---|
| 1. Append to internal ticker list | yes | yes |
| 2. Seed initial price | yes (random or `SEED_PRICES`) | no — populated on next poll |
| 3. Update cache | yes (immediately) | yes (next poll cycle) |
| 4. Rebuild Cholesky | yes | n/a |

---

## 13. Testing Strategy

The test suite that ships with the implementation has 73 tests across 6 modules; overall coverage is 84%. The high-value tests are summarized here.

### 13.1 `PriceCache`

```python
def test_first_update_is_flat():
    cache = PriceCache()
    u = cache.update("AAPL", 190.50)
    assert u.direction == "flat"
    assert u.previous_price == 190.50

def test_direction_up_and_down():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    assert cache.update("AAPL", 191.0).direction == "up"
    assert cache.update("AAPL", 190.5).direction == "down"

def test_version_increments_on_write_and_remove():
    cache = PriceCache()
    v0 = cache.version
    cache.update("AAPL", 190.0)
    cache.update("GOOGL", 175.0)
    assert cache.version == v0 + 2
    cache.remove("AAPL")
    assert cache.version == v0 + 3
```

### 13.2 `GBMSimulator`

```python
def test_prices_remain_positive():
    sim = GBMSimulator(tickers=["TSLA"])  # High volatility ticker
    for _ in range(10_000):
        assert sim.step()["TSLA"] > 0

def test_cholesky_full_default_basket():
    """Verify the correlation matrix is PSD for the full default watchlist."""
    tickers = list(SEED_PRICES.keys())  # 10 tickers
    sim = GBMSimulator(tickers=tickers)
    assert sim._cholesky is not None
    # Cholesky succeeded → matrix is positive definite.

def test_add_and_remove_ticker_keep_cholesky_consistent():
    sim = GBMSimulator(tickers=["AAPL"])
    assert sim._cholesky is None  # n <= 1
    sim.add_ticker("GOOGL")
    assert sim._cholesky.shape == (2, 2)
    sim.remove_ticker("GOOGL")
    assert sim._cholesky is None
```

### 13.3 `SimulatorDataSource` (async integration)

```python
@pytest.mark.asyncio
async def test_start_seeds_cache_before_loop_runs():
    cache = PriceCache()
    src = SimulatorDataSource(cache, update_interval=10.0)  # Long interval
    await src.start(["AAPL", "GOOGL"])
    # Even before the first tick fires, cache must contain seeded prices.
    assert cache.get_price("AAPL") == SEED_PRICES["AAPL"]
    assert cache.get_price("GOOGL") == SEED_PRICES["GOOGL"]
    await src.stop()
```

### 13.4 `MassiveDataSource` (mocked)

```python
def _snap(ticker, price, ts_ms):
    s = MagicMock()
    s.ticker = ticker
    s.last_trade.price = price
    s.last_trade.timestamp = ts_ms
    return s

@pytest.mark.asyncio
async def test_poll_updates_cache(monkeypatch):
    cache = PriceCache()
    src = MassiveDataSource(api_key="k", price_cache=cache, poll_interval=60.0)
    src._client = MagicMock()  # Avoid creating a real RESTClient
    src._tickers = ["AAPL", "GOOGL"]
    monkeypatch.setattr(
        src, "_fetch_snapshots",
        lambda: [_snap("AAPL", 190.50, 1_707_580_800_000),
                 _snap("GOOGL", 175.25, 1_707_580_800_000)],
    )
    await src._poll_once()
    assert cache.get_price("AAPL") == 190.50
    assert cache.get_price("GOOGL") == 175.25

@pytest.mark.asyncio
async def test_api_error_does_not_crash(monkeypatch):
    cache = PriceCache()
    src = MassiveDataSource(api_key="k", price_cache=cache, poll_interval=60.0)
    src._client = MagicMock()
    src._tickers = ["AAPL"]
    monkeypatch.setattr(src, "_fetch_snapshots",
                       lambda: (_ for _ in ()).throw(Exception("network")))
    await src._poll_once()  # Must not raise
    assert cache.get_price("AAPL") is None
```

### 13.5 Factory

```python
def test_factory_returns_simulator_without_key(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    src = create_market_data_source(PriceCache())
    assert type(src).__name__ == "SimulatorDataSource"

def test_factory_returns_massive_with_key(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "abc")
    src = create_market_data_source(PriceCache())
    assert type(src).__name__ == "MassiveDataSource"
```

### 13.6 SSE smoke test

A full SSE integration test requires an ASGI test client. A minimal sanity check:

```python
@pytest.mark.asyncio
async def test_sse_emits_on_version_change(monkeypatch):
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    app = FastAPI()
    app.include_router(create_stream_router(cache))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app)) as ac:
        async with ac.stream("GET", "http://t/api/stream/prices") as resp:
            chunks = []
            async for line in resp.aiter_lines():
                chunks.append(line)
                if line.startswith("data:"):
                    break
            assert any("AAPL" in c for c in chunks)
```

---

## 14. Error Handling & Edge Cases

### 14.1 Empty watchlist on startup
Both sources accept an empty initial list. The simulator's `step()` returns `{}`; the Massive poller skips its API call. SSE emits nothing until a ticker is added.

### 14.2 Trade before first price
The Simulator path seeds the cache in `start()` and `add_ticker()` so this can't happen. The Massive path has a brief window between `add_ticker()` and the next successful poll; routes must check for `None` and return `400 UNKNOWN_TICKER` per the API contract in `PLAN.md §8`.

### 14.3 Invalid Massive key
First poll fails with 401; the poller logs and keeps running. The user fixes `.env` and restarts the container.

### 14.4 SSE reconnection
The `retry: 1000` directive tells the browser to reconnect after 1s. There is **no replay/backfill** across the gap (accepted per `PLAN.md §6` decision 27).

### 14.5 Concurrent cache writes
`threading.Lock` serializes writes. With ~10 tickers at 2 ticks/sec, lock contention is negligible. The critical section is a dict assignment.

### 14.6 Floating-point precision
Prices are `round(..., 2)` in both the simulator and the cache. GBM is multiplicative via `exp(...)` — always positive, numerically stable.

---

## 15. Configuration Summary

| Parameter | Where | Default | Description |
|---|---|---|---|
| `MASSIVE_API_KEY` | env | unset | Switches factory to `MassiveDataSource` |
| `LOG_LEVEL` | env | `INFO` | Set to `DEBUG` for verbose logging |
| `update_interval` | `SimulatorDataSource.__init__` | `0.5 s` | Simulator tick rate |
| `event_probability` | `GBMSimulator.__init__` | `0.001` | Random-shock chance per ticker per tick |
| `dt` | `GBMSimulator.__init__` | `~8.48e-8` | GBM time step (fraction of a trading year) |
| `poll_interval` | `MassiveDataSource.__init__` | `15.0 s` | REST poll interval (free-tier safe) |
| SSE poll | `_generate_events` | `0.25 s` | How often the SSE loop checks the cache version |
| SSE retry | `_generate_events` | `1000 ms` | Browser `EventSource` reconnect delay |

### Defaults at a glance

- Simulator effectively pushes ~2 events/sec into the cache → SSE clients receive ~2 events/sec.
- Massive (free tier) pushes 1 event every 15s → SSE clients receive 1 event every 15s.
- In both cases, SSE only emits when the cache version actually advanced, so idle periods produce no traffic.

---

## Appendix A — Public API Cheat Sheet

```python
from app.market import (
    PriceUpdate,
    PriceCache,
    MarketDataSource,
    create_market_data_source,
    create_stream_router,
)

# Wire it up
cache = PriceCache()
source = create_market_data_source(cache)
await source.start(["AAPL", "GOOGL", "MSFT"])

# Read prices
update = cache.get("AAPL")         # PriceUpdate | None
price = cache.get_price("AAPL")    # float | None
all_prices = cache.get_all()       # dict[str, PriceUpdate]

# Manage tickers
await source.add_ticker("TSLA")
await source.remove_ticker("GOOGL")

# Shutdown
await source.stop()
```

## Appendix B — Demo

A Rich terminal dashboard demonstrating the full subsystem is available at `backend/market_data_demo.py`:

```bash
cd backend
uv run market_data_demo.py
```

It shows ten tickers with sparklines, color-coded direction arrows, and an event log of notable moves — useful for sanity-checking the simulator and verifying the cache + source plumbing without booting the full app.
