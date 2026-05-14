# syntax=docker/dockerfile:1.7
#
# FinAlly — multi-stage build.
#
# Stage 1 (frontend-builder): node:20-slim
#   - Installs npm deps and runs `npm run build`.
#   - Next.js is configured with `output: 'export'`, so the build emits
#     a fully static site under `frontend/out/`.
#
# Stage 2 (runtime): python:3.12-slim
#   - Installs `uv` via pip (predictable, no curl required).
#   - Syncs the backend project from the committed `uv.lock` (no dev deps).
#   - Copies the static frontend export from stage 1 into
#     `backend/app/static/` — FastAPI serves it from there.
#   - Runs uvicorn binding 0.0.0.0:8000.
#
# The SQLite database lives at /app/db/finally.db (overridable via
# `DB_PATH`); mount the host's `./db` directory there for persistence.

############################
# Stage 1 — frontend build #
############################
FROM node:20-slim AS frontend-builder

WORKDIR /build

# Install deps first (better layer caching). If a lockfile is present we
# use `npm ci`; otherwise fall back to `npm install`.
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Now copy the rest of the frontend source and build.
COPY frontend/ ./
RUN npm run build

# Sanity check: the static export must exist.
RUN test -d /build/out || (echo "frontend build did not produce /build/out — check next.config.js output:'export'" && exit 1)


###############################
# Stage 2 — Python runtime    #
###############################
FROM python:3.12-slim AS runtime

# System hardening + minimal runtime deps. `curl` is handy for the
# `HEALTHCHECK` below; everything else stays small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv from PyPI (predictable; no network curl pipe).
RUN pip install --no-cache-dir uv

# Don't write .pyc files; flush stdout immediately so docker logs are live.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    DB_PATH=/app/db/finally.db

WORKDIR /app/backend

# Install Python deps first so the lockfile layer caches.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Now bring in the application source and finish the install.
COPY backend/ ./
RUN uv sync --frozen --no-dev

# Copy the built static frontend into the location FastAPI expects.
COPY --from=frontend-builder /build/out/ /app/backend/app/static/

# Ensure the bind-mount target exists even if the host doesn't pre-create
# it; the volume mount will shadow this at runtime.
RUN mkdir -p /app/db

EXPOSE 8000

# Lightweight container-level health check hitting /api/health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

# Use uv to launch uvicorn so we pick up the synced environment.
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
