# FinAlly Frontend

Next.js 14 (App Router) + TypeScript + Tailwind. Built as a static export so the
FastAPI backend can serve it directly on port 8000.

## Develop

```bash
cd frontend
npm install
npm run dev          # serves on http://localhost:3000
```

`next.config.js` rewrites `/api/*` to `http://localhost:8000/api/*` in dev so
the frontend talks to a locally running FastAPI backend. Override with
`BACKEND_URL=http://other-host:8000 npm run dev`.

## Build (static export)

```bash
npm run build
# Static files end up in ./out
```

The Docker multi-stage build copies `frontend/out/` into
`backend/app/static/` so FastAPI serves it from the same origin in production —
no CORS needed.

## Smoke tests

```bash
npm test
```

Tests live under `__tests__/` and use React Testing Library with `ts-jest`.
Coverage is intentionally light — flash behavior, trade-bar error surfacing,
chat panel render of mock history.

## Stack

- Next.js 14 App Router, `output: 'export'`
- TypeScript strict mode
- Tailwind CSS with custom dark palette (bg `#0d1117`, accent `#ecad0a`, blue
  `#209dd7`, purple `#753991`)
- `lightweight-charts` for the main price chart and P&L area chart
- Hand-rolled SVG sparklines for watchlist rows
- `EventSource` for the SSE price stream
