# FinAlly E2E Tests

Playwright end-to-end tests for the FinAlly AI Trading Workstation.

## Prerequisites

- Docker (the `finally:latest` image must be built — see `scripts/start.sh --build`)
- Node 20+
- npm

## Quickstart

```bash
# From the project root, build the app image first
docker build -t finally:latest .

# Then, from this directory
cd test
npm install
npx playwright install chromium

# Bring up the test stack (LLM_MOCK=true, ephemeral DB)
docker compose -f docker-compose.test.yml up -d

# Wait for the app to be healthy, then run tests
npm test

# Tear down
docker compose -f docker-compose.test.yml down -v
```

## What gets tested

| Spec | Covers |
|---|---|
| `fresh-start.spec.ts` | Default 10-ticker watchlist renders, $10,000 cash, green connection dot, live price updates via SSE within 3s. |
| `watchlist-crud.spec.ts` | Add a known ticker, remove it; API error codes `UNKNOWN_TICKER`, `TICKER_ALREADY_WATCHED`. |
| `trade-flow.spec.ts` | Buy/sell flow updates cash + positions; API error codes `INSUFFICIENT_CASH`, `INSUFFICIENT_SHARES`, `INVALID_QUANTITY`, `UNKNOWN_TICKER`. |
| `chat-mock.spec.ts` | `LLM_MOCK=true` keyword table: `buy N TICKER`, `add TICKER`, `remove TICKER`, fall-through. Verifies trade auto-execution, error badges, chat history rehydration. |
| `sse-resilience.spec.ts` | Best-effort: blocking the SSE endpoint flips the connection dot; restoring it brings it back to green. Soft-skips if route interception is flaky. |
| `portfolio-viz.spec.ts` | After a trade, heatmap renders a tile for the new position; P&L history has snapshots. |

## Configuration

- `FINALLY_BASE_URL` — default `http://localhost:8000`.
- `FINALLY_CONTAINER_NAME` — default `finally-e2e` (used by `hardReset()`).

## Notes

- Tests run **serially** (`workers: 1`, `fullyParallel: false`) because they share backend state.
- Each `describe` block calls `hardReset()` from `fixtures/freshDb.ts` to restart the container and get a clean tmpfs DB. If Docker isn't available (local dev), it gracefully degrades to a soft state-reset via the API.
- Retries: 1.
- Selectors are forgiving — they prefer `data-testid` but fall back to text/role queries so the frontend implementation has flexibility.
