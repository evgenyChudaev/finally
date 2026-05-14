#!/usr/bin/env bash
# FinAlly — start script (macOS / Linux).
#
# Usage:
#   ./scripts/start.sh            # build only if image is missing, then run
#   ./scripts/start.sh --build    # force rebuild
#
# Verify the running container:
#   curl -fsS http://localhost:8000/api/health
#   # expected: {"status":"ok"}
#
# Idempotent: safe to run multiple times. If a container named "finally"
# is already running, it is stopped + removed first.

set -euo pipefail

# Resolve repo root (parent of the scripts/ directory) so the script
# works from any cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

IMAGE="finally:latest"
NAME="finally"
PORT="${FINALLY_PORT:-8000}"

FORCE_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --build|-b)
      FORCE_BUILD=1
      ;;
    -h|--help)
      sed -n '2,15p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

if [ ! -f .env ]; then
  echo "ERROR: .env not found in ${REPO_ROOT}." >&2
  echo "       Copy .env.example to .env and add your OPENROUTER_API_KEY." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not on PATH." >&2
  exit 1
fi

# Build if forced, or if the image doesn't exist locally.
if [ "${FORCE_BUILD}" -eq 1 ] || ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo ">> Building ${IMAGE} ..."
  docker build -t "${IMAGE}" .
else
  echo ">> Image ${IMAGE} already exists; skipping build (pass --build to force)."
fi

# Make sure the host bind-mount directory exists.
mkdir -p "${REPO_ROOT}/db"

# Tear down any existing container with the same name (idempotent).
if docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
  echo ">> Removing existing ${NAME} container ..."
  docker rm -f "${NAME}" >/dev/null
fi

echo ">> Starting ${NAME} on port ${PORT} ..."
docker run -d \
  --name "${NAME}" \
  -p "${PORT}:8000" \
  --env-file .env \
  -v "${REPO_ROOT}/db:/app/db" \
  --restart unless-stopped \
  "${IMAGE}" >/dev/null

echo ""
echo "App available at http://localhost:${PORT}"
echo "Logs:  docker logs -f ${NAME}"
echo "Stop:  ./scripts/stop.sh"
echo ""
echo "Verify with:  curl -fsS http://localhost:${PORT}/api/health"
