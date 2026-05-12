# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade over ~250ms
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **See session change %** — each watchlist row shows the % change since the first price observed in the current browser session (resets on page reload)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~250ms via CSS transitions (shorter than the simulator tick interval so the flash visibly resets between updates)
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere. The server emits a delta only when the price cache version advances (see §6).
- **AI integration**: LiteLLM → OpenRouter (Cerebras for fast inference), with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start.sh              # Launch Docker container (macOS/Linux, bash)
│   ├── stop.sh               # Stop Docker container (macOS/Linux, bash)
│   ├── start.ps1             # Launch Docker container (Windows PowerShell)
│   └── stop.ps1              # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false

# Optional: Comma-separated list of tickers used to seed a fresh database
# Default if unset: AAPL,GOOGL,MSFT,AMZN,TSLA,NVDA,META,JPM,V,NFLX
DEFAULT_WATCHLIST=
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- If `DEFAULT_WATCHLIST` is set, its comma-separated tickers are used to seed the watchlist on first-run initialization. Only affects an empty database; existing watchlists are not overwritten.
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

### Conventions

- All timestamps are stored and transmitted as ISO 8601 UTC strings (e.g., `2026-05-12T14:30:00Z`). The frontend formats to the browser's local timezone for display.
- All monetary values are in USD. No multi-currency support.

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, and timestamp for each ticker
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- **Version-based change detection**: the price cache maintains a monotonic version counter that advances every time a price is written. The SSE handler tracks the version it last sent to each client and only emits events when the cache version advances. Clients receive deltas, not a fixed-cadence broadcast.
- Effective push rate matches the upstream source (simulator ~500ms per tick; Massive every 15s on free tier). When prices don't change, no events are sent.
- Each SSE event contains ticker, price, previous price, timestamp (UTC), and change direction
- After reconnect there is no replay/backfill — the client may miss intermediate ticks across the gap. This is accepted (a missed flash is harmless; sparklines show a small gap).
- Client handles reconnection automatically (EventSource has built-in retry)

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

Single-user model: no `user_id` columns. All `id` columns are `INTEGER PRIMARY KEY AUTOINCREMENT` (smaller, faster, no generation code). All timestamps are ISO 8601 UTC.

**users_profile** — Singleton row holding user state (cash balance). Enforced as singleton by `CHECK (id = 1)`.
- `id` INTEGER PRIMARY KEY CHECK (id = 1)
- `cash_balance` REAL NOT NULL DEFAULT 10000.0
- `created_at` TEXT NOT NULL

**watchlist** — Tickers the user is watching
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `ticker` TEXT NOT NULL UNIQUE
- `added_at` TEXT NOT NULL

**positions** — Current holdings (one row per ticker)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `ticker` TEXT NOT NULL UNIQUE
- `quantity` REAL NOT NULL (fractional shares supported)
- `avg_cost` REAL NOT NULL
- `updated_at` TEXT NOT NULL

**trades** — Trade history (append-only log)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `ticker` TEXT NOT NULL
- `side` TEXT NOT NULL CHECK (side IN ('buy', 'sell'))
- `quantity` REAL NOT NULL (fractional shares supported)
- `price` REAL NOT NULL
- `executed_at` TEXT NOT NULL
- Index on `executed_at DESC` for history queries

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded **immediately after each trade execution** and **once at app startup** (to anchor the chart's left edge). No periodic background task — the chart is event-driven and reflects every cash-changing event accurately.
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `total_value` REAL NOT NULL
- `recorded_at` TEXT NOT NULL

**chat_messages** — Conversation history with LLM (append-only)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `role` TEXT NOT NULL CHECK (role IN ('user', 'assistant'))
- `content` TEXT NOT NULL
- `actions` TEXT (JSON — trades executed and watchlist changes made by the assistant; NULL for user messages)
- `created_at` TEXT NOT NULL
- Index on `created_at DESC` for windowed reads
- The LLM only reads the most recent 20 rows as context (see §9). The table is never truncated by the app — it serves as a complete audit log.

### Default Seed Data

- One row in `users_profile`: `id=1`, `cash_balance=10000.0`, `created_at=<now UTC>`
- Watchlist seed: `DEFAULT_WATCHLIST` env var if set, otherwise the built-in default — AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Conventions

- All request and response bodies are JSON.
- Successful responses use 2xx status codes and return the documented body shape.
- Errors return a consistent envelope and an appropriate status code:

  ```json
  {"detail": "Insufficient cash for trade", "code": "INSUFFICIENT_CASH"}
  ```

  Defined error codes: `INSUFFICIENT_CASH`, `INSUFFICIENT_SHARES`, `UNKNOWN_TICKER`, `INVALID_QUANTITY`, `TICKER_ALREADY_WATCHED`, `TICKER_NOT_WATCHED`, `RATE_LIMITED`, `LLM_ERROR`, `VALIDATION_ERROR`. The frontend may show the `detail` text and switch on `code` for behavior.

- A ticker is **unknown** if it has no entry in the price cache (simulator's seed set, or a previously fetched Massive symbol). Unknown tickers are rejected with 400 `UNKNOWN_TICKER` rather than auto-seeded.

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates. Event payload: `{ticker, price, previous_price, timestamp, direction}` where `direction ∈ {"up", "down", "flat"}`. |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Returns `{cash_balance, total_value, positions: [{ticker, quantity, avg_cost, current_price, unrealized_pl, pct_change}, ...]}` |
| POST | `/api/portfolio/trade` | Body: `{ticker, side, quantity}` (`side ∈ {"buy", "sell"}`, `quantity > 0`). Returns the executed trade: `{id, ticker, side, quantity, price, executed_at}`. Errors: 400 `INSUFFICIENT_CASH`, 400 `INSUFFICIENT_SHARES`, 400 `UNKNOWN_TICKER`, 400 `INVALID_QUANTITY`. |
| GET | `/api/portfolio/history` | Query: `?limit=N` (default 500). Returns `{snapshots: [{total_value, recorded_at}, ...]}` ordered by `recorded_at ASC` for the P&L chart. |
| GET | `/api/portfolio/trades` | Query: `?limit=N` (default 100). Returns `{trades: [{id, ticker, side, quantity, price, executed_at}, ...]}` ordered by `executed_at DESC`. |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Returns `{tickers: [{ticker, current_price, previous_price, direction, added_at}, ...]}` |
| POST | `/api/watchlist` | Body: `{ticker}`. Validates the ticker is known to the data source. Errors: 400 `UNKNOWN_TICKER`, 409 `TICKER_ALREADY_WATCHED`. Returns the created entry. |
| DELETE | `/api/watchlist/{ticker}` | Removes a ticker. Error: 404 `TICKER_NOT_WATCHED`. |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Body: `{message: string}`. Returns `{message, trades: [...], watchlist_changes: [...], errors: [{action, code, detail}]}`. Rate-limited to 10 requests/minute per process — over-limit returns 429 `RATE_LIMITED`. |
| GET | `/api/chat/history` | Query: `?limit=N` (default 50). Returns `{messages: [{id, role, content, actions, created_at}, ...]}` ordered by `created_at ASC` so the frontend can render the panel directly. Used to rehydrate the chat panel on page load. |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment). Returns `{status: "ok"}` with 200. |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use cerebras-inference skill to use LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. Structured Outputs should be used to interpret the results.

There is an OPENROUTER_API_KEY in the .env file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Applies a per-process rate limit of **10 requests/minute** on `/api/chat`. Over-limit returns 429 `RATE_LIMITED` and is not forwarded to the LLM. The bucket is a simple in-memory counter — it resets on process restart.
2. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value).
3. Loads the **20 most recent rows** from `chat_messages` (ordered by `created_at DESC`, then reversed for chronological order) as conversation history. The bound keeps token cost predictable; older messages are not pruned from the table (it remains a full audit log) but they are not sent to the LLM.
4. Constructs a prompt with a system message, portfolio context, the 20-message window, and the user's new message.
5. Calls the LLM via LiteLLM → OpenRouter, requesting structured output, using the cerebras-inference skill.
6. Parses the complete structured JSON response.
7. Auto-executes trades and watchlist changes in the order returned (see *Partial-failure semantics* below).
8. Stores the user message and the assistant message (with the JSON `actions` field summarizing what executed and what failed) in `chat_messages`.
9. Returns the complete JSON response to the frontend (no token-by-token streaming — Cerebras inference is fast enough that a loading indicator is sufficient).

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

### Partial-failure semantics

The LLM may return multiple trades and/or watchlist changes in one response. The backend executes them **in the order returned, skipping failures** (best-effort):

- Each trade and watchlist change is attempted independently via the same code path as the manual REST endpoints.
- Successful actions are recorded; failed actions are captured as `{action, code, detail}` entries in the response's `errors` array.
- A later trade may succeed even after an earlier one fails (e.g., a sell that goes through after an oversized buy is rejected).
- The assistant message stored in `chat_messages` includes both the executed actions and the failures in its `actions` JSON, so chat history retrieval can render the final outcome accurately.
- The response shape is `{message, trades: [...executed...], watchlist_changes: [...executed...], errors: [...failures...]}`.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### Structured Output Mechanism

Use OpenAI-style JSON schema enforcement (`response_format={"type": "json_schema", "json_schema": {...}}`) where the route supports it. If `openrouter/openai/gpt-oss-120b` via Cerebras does not accept `json_schema` at runtime, fall back to `response_format={"type": "json_object"}` plus a system-prompt instruction to match the schema, and validate the parsed JSON server-side against a Pydantic model before executing any actions. Either way, the backend must treat the LLM output as untrusted: malformed JSON → return a generic message to the user and log the raw response; valid JSON with no `trades`/`watchlist_changes` → treat as a pure-conversation reply.

### LLM Mock Mode

When `LLM_MOCK=true`, the backend bypasses OpenRouter and returns deterministic responses driven by simple keyword matching on the user message. This enables fast, free, reproducible E2E tests; development without an API key; and CI/CD pipelines.

Mock behavior (case-insensitive):

| User message contains... | Mock response |
|---|---|
| `buy <N> <TICKER>` (e.g., "buy 5 AAPL") | `message: "Buying N TICKER for you."`, one trade: `{ticker, side: "buy", quantity: N}` |
| `sell <N> <TICKER>` | `message: "Selling N TICKER."`, one trade: `{ticker, side: "sell", quantity: N}` |
| `add <TICKER>` to watchlist | `message: "Added TICKER to your watchlist."`, one watchlist change: `{ticker, action: "add"}` |
| `remove <TICKER>` from watchlist | one watchlist change: `{ticker, action: "remove"}` |
| (anything else) | `message: "Mock LLM response. Try 'buy 5 AAPL' or ask for analysis."`, no actions |

Mock responses go through the same validation and partial-failure logic as real LLM responses, so E2E tests exercise the full execution path.

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), **session change %** (vs. the first price observed in this browser session — resets on reload), and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, sourced from `GET /api/portfolio/history` (`portfolio_snapshots` rows). Points are event-driven (one per trade plus an app-start anchor) rather than evenly spaced.
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill. On `UNKNOWN_TICKER` from the API, show inline validation error.
- **AI chat panel** — docked/collapsible sidebar. Rehydrated on load via `GET /api/chat/history`. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions, watchlist changes, and partial-failure errors shown inline as confirmations.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`. Surface a yellow "reconnecting" status when `readyState === CONNECTING` and red when an `error` event closes the connection.
- **Charting**: use **Lightweight Charts** (canvas-based) for the main price chart and the P&L chart — it handles streaming updates efficiently. For sparklines, either Lightweight Charts in a compact preset or hand-rolled SVG polylines is fine; both perform well at sparkline scale.
- Price flash effect: on receiving a new price, briefly apply a CSS class with a background color transition that fades over ~250ms, then remove it. The 250ms duration is shorter than the simulator's ~500ms tick so consecutive ticks produce distinct flashes rather than a constant glow.
- Session change % is computed entirely client-side: on first SSE event for each ticker, store its price as that ticker's session baseline; render `(current - baseline) / baseline * 100`.
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a **bind mount** of the project's `db/` directory:

```bash
docker run -v "$(pwd)/db:/app/db" -p 8000:8000 --env-file .env finally
```

On Windows PowerShell:

```powershell
docker run -v "${PWD}/db:/app/db" -p 8000:8000 --env-file .env finally
```

The `db/` directory in the project root maps to `/app/db` in the container. The backend writes `finally.db` to this path. A bind mount (rather than a named volume) is used so the SQLite file is visible on the host — students can inspect, back up, or delete it with normal file tools.

### Start/Stop Scripts

**`scripts/start.sh`** (macOS/Linux, bash):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the bind-mount volume, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop.sh`** (macOS/Linux, bash):
- Stops and removes the running container
- Does NOT delete the `db/` directory (data persists)

**`scripts/start.ps1`** / **`scripts/stop.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Decisions Log

Records resolutions for plan-review items so downstream agents don't re-litigate them. Each entry: the question, the decision, and where it lives in the plan.

### 13.1 Resolved — incorporated into the plan body

| # | Decision | Lives in |
|---|---|---|
| 1 | SSE uses **version-based change detection** (not fixed-cadence broadcast). Clients receive deltas only when the cache version advances. | §3, §6 |
| 2 | Charting: **Lightweight Charts** (canvas) for main price chart and P&L chart. Sparklines may use Lightweight Charts or hand-rolled SVG. Recharts (SVG) is not used. | §10 |
| 3 | Docker volume is a **bind mount** (`-v "$(pwd)/db:/app/db"`), not a named volume — so the SQLite file is visible on the host. | §11 |
| 4 | Price flash fades over **~250ms** (shorter than the ~500ms simulator tick). Consecutive ticks produce distinct flashes. | §2, §10 |
| 5 | Scripts are named `start.sh`/`stop.sh` (bash) and `start.ps1`/`stop.ps1` (PowerShell). No `_mac` suffix. | §4, §11 |
| 6 | Error responses use a consistent `{detail, code}` envelope with defined codes (`INSUFFICIENT_CASH`, `UNKNOWN_TICKER`, etc.). | §8 |
| 7 | `POST /api/chat` body is `{message: string}`. | §8 |
| 8 | **Added `GET /api/chat/history?limit=N`** — chat panel rehydrates on page load. | §8, §10 |
| 9 | **Added `GET /api/portfolio/trades?limit=N`** — recent trades available to the UI. | §8 |
| 10 | Unknown tickers on `POST /api/watchlist` and `POST /api/portfolio/trade` are **rejected with 400 `UNKNOWN_TICKER`** (no auto-seeding). | §8 |
| 11 | Watchlist shows **session change %** (anchored to first price observed in the browser session). Computed client-side; no schema or backend changes. The label is "session change %", not "daily change %". | §2, §10 |
| 12 | LLM context window: **last 20 messages** from `chat_messages`, ordered chronologically. Older rows remain in the table as an audit log but are not sent to the model. | §9 |
| 13 | Multi-action LLM responses execute **in order, skipping failures** (best-effort). Failures returned as `errors: [{action, code, detail}, ...]`. | §9 |
| 14 | `/api/chat` is rate-limited to **10 requests/minute** per process (in-memory bucket). Over-limit → 429 `RATE_LIMITED`. | §8, §9 |
| 15 | Mock mode (`LLM_MOCK=true`) uses **keyword-triggered** responses: `buy/sell <N> <TICKER>` and `add/remove <TICKER>` map to deterministic trades and watchlist changes, exercising the full execution path in E2E tests. | §9 |
| 16 | Structured output: prefer `response_format={"type": "json_schema", ...}`. Fall back to `json_object` + Pydantic server-side validation if the route doesn't accept schema mode. Verify at implementation time. | §9 |
| 17 | **Dropped `user_id`** from every table. Single-user only. Future multi-user support, if ever needed, will require a migration regardless. | §7 |
| 18 | Primary keys are **`INTEGER PRIMARY KEY AUTOINCREMENT`**, not TEXT UUIDs. | §7 |
| 19 | `users_profile` is a **singleton row** enforced by `CHECK (id = 1)`. | §7 |
| 20 | **Dropped the 30s `portfolio_snapshots` background task.** Snapshots are recorded only after each trade and once at app startup (anchors the P&L chart's left edge). | §7 |
| 24 | Logging: stdout, leveled text (use Python `logging` with a uvicorn-style format). Docker captures it. | §13.3 — note below |
| 25 | All timestamps stored and transmitted as ISO 8601 **UTC**. Frontend renders in the browser's local TZ. | §5 |
| 26 | All monetary values are **USD**. No multi-currency support. | §5 |
| 27 | SSE gap handling: no replay/backfill after reconnect — accepted (missed flashes are harmless; sparklines show a small gap). | §6 |
| 28 | Watchlist seed configurable via `DEFAULT_WATCHLIST` env var (comma-separated). Only affects an empty database. | §5, §7 |

### 13.2 Items intentionally not adopted

| # | Item | Reason kept |
|---|---|---|
| 21 | "Bound `chat_messages` growth (prune to last N)". | Table is now read with `LIMIT 20` for the LLM, and the new `GET /api/chat/history` also bounds reads. The table itself stays unbounded as an audit log. No pruning needed. |
| 22 | "Drop the change % field." | Superseded by decision #11: keep the field, anchor to session. |
| 23 | "Defer the main chart for v1." | The main price chart is part of the Bloomberg-feel UX and stays in v1. |

### 13.3 Logging convention (decision #24 detail)

- Use Python's standard `logging` module configured at app startup. Default level `INFO`; `DEBUG` if `LOG_LEVEL=debug` env var is set.
- Format: `<ISO UTC timestamp> <level> <logger> <message>`. Single-line, plain text — Docker captures stdout, no JSON wrapping needed for this scale.
- Log: app start/stop, DB init, data source selection (simulator vs. Massive), each trade execution, each LLM call (with token counts if available), SSE connect/disconnect, and all errors with stack traces.
