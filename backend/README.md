# FinAlly Backend

FastAPI backend for the FinAlly AI Trading Workstation.

## Structure

- `app/` - Application code
  - `market/` - Market data subsystem
    - `models.py` - PriceUpdate dataclass
    - `cache.py` - Thread-safe price cache
    - `interface.py` - MarketDataSource abstract interface
    - `simulator.py` - GBM-based market simulator
    - `massive_client.py` - Massive/Polygon.io API client
    - `factory.py` - Data source factory
    - `stream.py` - SSE streaming endpoint
    - `seed_prices.py` - Default ticker prices and parameters

- `tests/` - Unit and integration tests
  - `market/` - Market data tests

## Running Tests

```bash
# Install dependencies
uv sync --dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/market/test_simulator.py

# Run with verbose output
uv run pytest -v
```

## Environment Variables

- `MASSIVE_API_KEY` - Optional. If set, use real market data from Massive API. If not set, use the built-in simulator.

## Market Data Demos

Two standalone scripts exercise the `app.market` subsystem end-to-end — useful
for smoke-testing the backend without bringing up the full FastAPI app.

```bash
# Rich live dashboard (full-screen, scrolls back on exit).
# Best in a regular terminal.
uv run market_data_demo.py

# Scrolling text demo (no alternate-screen mode).
# Best inside VS Code (integrated terminal OR Debug Console).
uv run market_data_demo_vscode.py
```

The VS Code demo prints a banner, snapshot, and tick-by-tick updates as
ordinary stdout lines, so it works identically under `uv run`, `python -m`,
and F5 / "Run Python File" in VS Code.

### Running from VS Code (F5 / Run & Debug)

1. Open the repo root in VS Code.
2. Command Palette → **Python: Select Interpreter** → pick the one under
   `backend/.venv/`.
3. Open `backend/market_data_demo_vscode.py` and press **F5**.

For one-click access from the **Run and Debug** panel, drop the following
into `.vscode/launch.json` at the repo root (the directory does not yet
exist — create it if needed):

```jsonc
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Market Data Demo",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/backend/market_data_demo_vscode.py",
            "cwd": "${workspaceFolder}/backend",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env",
            "python": "${workspaceFolder}/backend/.venv/bin/python"
        },
        {
            "name": "Python: Market Data Demo (Rich dashboard)",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/backend/market_data_demo.py",
            "cwd": "${workspaceFolder}/backend",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env",
            "python": "${workspaceFolder}/backend/.venv/bin/python"
        }
    ]
}
```

## Development

```bash
# Install dependencies
uv sync --dev

# Run linter
uv run ruff check .

# Format code
uv run ruff format .
```
