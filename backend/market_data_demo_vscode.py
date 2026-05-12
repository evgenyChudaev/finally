"""FinAlly Market Data Demo — VS Code friendly.

A scrolling, plain-stdout demo that exercises every public piece of the
``app.market`` subsystem. Designed to be runnable in any environment,
including VS Code's integrated terminal and Debug Console — no alternate
screen, no curses, no terminal trickery.

How to run
==========

From the ``backend`` directory:

    uv run market_data_demo_vscode.py

Or from VS Code:

    1. Open this repository folder in VS Code.
    2. Make sure the Python interpreter is the uv-managed virtual env at
       ``backend/.venv/bin/python`` (Command Palette → "Python: Select
       Interpreter" → pick the one under ``backend/.venv``).
    3. Open this file and press F5 (or use the bundled launch config
       ``Python: Market Data Demo`` from the Run & Debug panel).

What it demonstrates
====================

    1. Factory selects simulator (default) or Massive API (if
       ``MASSIVE_API_KEY`` is set).
    2. Source lifecycle: ``start`` -> ticks -> ``stop``.
    3. ``PriceCache``: ``get_all``, ``get``, ``get_price``, ``__contains__``
       and the monotonic ``version`` counter used for SSE change detection.
    4. ``PriceUpdate`` properties: ``change``, ``change_percent``,
       ``direction``.
    5. Dynamic watchlist: ``add_ticker`` / ``remove_ticker``.
    6. Graceful shutdown with ``stop()``.

The demo runs for about 30 seconds and exits cleanly. Press ``Ctrl+C`` at
any time to stop early.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Make ``app.market`` importable when the script is launched directly from
# VS Code (the Run/Debug runner does not necessarily set ``cwd`` to backend/).
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.market import (  # noqa: E402  (sys.path tweak must happen first)
    PriceCache,
    PriceUpdate,
    create_market_data_source,
)

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

INITIAL_TICKERS: list[str] = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
]

# Number of cache-version bumps to wait for in each "watch" phase.
TICKS_PER_PHASE = 4

# Hard ceiling per watch phase, so the demo never hangs if the data source
# stalls (e.g., Massive API rate limit). With the simulator (~500ms ticks),
# four ticks complete in ~2s; with Massive on the free tier (~15s polls),
# four ticks take ~60s — both within this ceiling.
WATCH_TIMEOUT_SECONDS = 90.0

# Polling interval for watching the cache version. Short enough to feel
# responsive against the simulator's ~500ms tick.
POLL_INTERVAL_SECONDS = 0.25

BANNER = "=" * 72
RULE = "-" * 72


# ----------------------------------------------------------------------------
# Output helpers
# ----------------------------------------------------------------------------


def section(title: str) -> None:
    """Print a clearly delimited section header to stdout."""
    print()
    print(BANNER)
    print(f"  {title}")
    print(BANNER, flush=True)


def subsection(title: str) -> None:
    print()
    print(f"-- {title}")
    print(RULE, flush=True)


def format_update(update: PriceUpdate) -> str:
    """One-line, fixed-width rendering of a PriceUpdate for tabular output."""
    arrow = {"up": "^", "down": "v", "flat": "-"}[update.direction]
    return (
        f"{update.ticker:>6s}  ${update.price:>10,.2f}  "
        f"{arrow}  {update.change:+9.4f}  ({update.change_percent:+8.4f}%)"
    )


def print_snapshot(cache: PriceCache, header: str | None = None) -> None:
    """Dump the cache's current state, one ticker per line."""
    if header:
        print(f"\n{header} (cache version = {cache.version})")
    snapshot = cache.get_all()
    if not snapshot:
        print("   (cache is empty)")
        return
    for ticker in sorted(snapshot):
        print(f"   {format_update(snapshot[ticker])}")
    sys.stdout.flush()


# ----------------------------------------------------------------------------
# Demo phases
# ----------------------------------------------------------------------------


async def wait_for_ticks(cache: PriceCache, ticks: int, label: str) -> int:
    """Wait until the cache's version counter has advanced by `ticks`.

    Returns the number of ticks actually observed (which may be < `ticks` if
    the timeout fires — the simulator should never trigger that, but the
    Massive client on a free-tier rate limit might).
    """
    start_version = cache.version
    target = start_version + ticks
    deadline = time.monotonic() + WATCH_TIMEOUT_SECONDS
    last_reported = start_version

    while cache.version < target and time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        if cache.version > last_reported:
            seen = cache.version - start_version
            print_snapshot(cache, f"{label}: cache bump #{seen}")
            last_reported = cache.version

    observed = cache.version - start_version
    if observed < ticks:
        print(
            f"   [warn] only observed {observed}/{ticks} cache bumps within "
            f"{WATCH_TIMEOUT_SECONDS:.0f}s — continuing."
        )
    return observed


async def demo() -> None:
    section("FinAlly - Market Data Subsystem Demo (VS Code edition)")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python:            {sys.version.split()[0]} ({sys.executable})")
    if os.environ.get("MASSIVE_API_KEY", "").strip():
        print("MASSIVE_API_KEY is set: factory will pick MassiveDataSource.")
        print("(Free-tier polling is slow - some phases may take ~60s.)")
    else:
        print("MASSIVE_API_KEY is not set: factory will pick the GBM simulator.")
        print("(Ticks every ~500ms, offline, no network calls.)")

    # ---- 1. Factory ------------------------------------------------------
    section("1. Factory selects a data source")
    cache = PriceCache()
    source = create_market_data_source(cache)
    print(f"Created instance:  {type(source).__name__}")
    print(f"Cache instance:    {type(cache).__name__} (version = {cache.version})")

    # ---- 2. Start the source --------------------------------------------
    section("2. source.start() seeds the cache and begins emitting ticks")
    await source.start(INITIAL_TICKERS)
    print(f"Tracking {len(source.get_tickers())} tickers: {source.get_tickers()}")
    print_snapshot(cache, "Initial snapshot")

    # ---- 3. Observe ticks ----------------------------------------------
    section("3. Watching prices move")
    await wait_for_ticks(cache, TICKS_PER_PHASE, "Tick")

    # ---- 4. Per-ticker queries ------------------------------------------
    section("4. Querying individual tickers")
    for ticker in ("AAPL", "TSLA", "NOSUCH"):
        update = cache.get(ticker)
        price = cache.get_price(ticker)
        present = ticker in cache
        if update is None:
            print(f"  {ticker:>7s}: not in cache (in_cache={present})")
        else:
            print(
                f"  {ticker:>7s}: ${price:,.2f}  "
                f"direction={update.direction:<4s}  "
                f"change={update.change:+.4f}  "
                f"in_cache={present}"
            )

    # ---- 5. Dynamic watchlist ------------------------------------------
    section("5. Dynamic watchlist: add and remove tickers")
    new_ticker = "PYPL"
    subsection(f"Adding {new_ticker}")
    await source.add_ticker(new_ticker)
    print(f"Tracked tickers now: {source.get_tickers()}")
    print(f"{new_ticker} in cache? {new_ticker in cache}")
    new_update = cache.get(new_ticker)
    if new_update is not None:
        print(f"   {format_update(new_update)}")

    drop_ticker = "JPM"
    subsection(f"Removing {drop_ticker}")
    await source.remove_ticker(drop_ticker)
    print(f"Tracked tickers now: {source.get_tickers()}")
    print(f"{drop_ticker} in cache? {drop_ticker in cache}")
    print(f"cache.get_price({drop_ticker!r}) = {cache.get_price(drop_ticker)!r}")

    # ---- 6. Version counter --------------------------------------------
    section("6. Version counter (SSE change-detection contract)")
    v_before = cache.version
    print(f"Version before watching: {v_before}")
    observed = await wait_for_ticks(cache, TICKS_PER_PHASE, "Tick")
    v_after = cache.version
    print(f"\nVersion after:           {v_after}")
    print(f"Delta:                   {v_after - v_before} (observed {observed} bumps)")
    print("The SSE handler uses this counter to emit deltas only on change.")

    # ---- 7. PriceUpdate.to_dict() shape --------------------------------
    section("7. PriceUpdate.to_dict() - the SSE event payload shape")
    sample = cache.get("AAPL")
    if sample is not None:
        for key, val in sample.to_dict().items():
            print(f"  {key:<16s}: {val!r}")

    # ---- 8. Shutdown ---------------------------------------------------
    section("8. Stopping the data source")
    await source.stop()
    print("Stopped. Final cache snapshot:")
    print_snapshot(cache)

    section("Demo complete - market data subsystem looks healthy")


def main() -> int:
    # Friendly log format so the simulator's INFO messages show up clearly.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\nInterrupted by user. Goodbye.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
