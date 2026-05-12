# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as the capstone project for an agentic AI coding course.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — treemap heatmap, P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js static export (TypeScript + Tailwind), served by FastAPI
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite, bind-mounted, lazily initialized and seeded
- **AI**: LiteLLM → OpenRouter (`openai/gpt-oss-120b` via Cerebras) with structured outputs
- **Market data**: Built-in GBM simulator (default) or Massive/Polygon REST polling (optional)

See [`planning/PLAN.md`](planning/PLAN.md) for the full specification.

## Quick Start

```bash
cp .env.example .env          # then add your OPENROUTER_API_KEY
./scripts/start.sh            # macOS/Linux
# or
./scripts/start.ps1           # Windows PowerShell
```

Open <http://localhost:8000>. To stop, run the matching `stop` script.

The SQLite database is bind-mounted at `./db/finally.db` and persists across restarts.

### Manual Docker

```bash
docker build -t finally .
docker run -v "$(pwd)/db:/app/db" -p 8000:8000 --env-file .env finally
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | Massive/Polygon key for real market data; omit to use the simulator |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |
| `DEFAULT_WATCHLIST` | No | Comma-separated tickers to seed a fresh database |

## Project Structure

```
finally/
├── frontend/    # Next.js static export
├── backend/     # FastAPI uv project (incl. db/ schema + seed)
├── planning/    # Project documentation and agent contracts
├── test/        # Playwright E2E tests
├── db/          # SQLite bind-mount target (runtime)
└── scripts/     # start/stop helpers (.sh and .ps1)
```

## Testing

- Backend unit tests: `pytest` inside `backend/`
- Frontend unit tests: `npm test` inside `frontend/`
- E2E: Playwright via `test/docker-compose.test.yml` (runs with `LLM_MOCK=true`)

## Try the Market Data Subsystem in Isolation

Two standalone demos in `backend/` exercise the market data pipeline without
spinning up the full app — handy if you just want to confirm the simulator
and price cache work in your environment:

```bash
cd backend
uv sync --extra dev

# Full-screen Rich dashboard (best in a regular terminal).
uv run market_data_demo.py

# Scrolling, plain-stdout demo (best inside VS Code).
uv run market_data_demo_vscode.py
```

See [`backend/README.md`](backend/README.md#market-data-demos) for the matching
VS Code `launch.json` snippet (F5 → "Python: Market Data Demo").

## License

See [LICENSE](LICENSE).
