#!/usr/bin/env bash
# FinAlly — stop script (macOS / Linux).
#
# Stops and removes the "finally" container. Idempotent: returns 0 even
# if nothing was running. The bind-mounted ./db directory is preserved.

set -euo pipefail

NAME="finally"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not on PATH." >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${NAME}$"; then
  echo ">> Stopping ${NAME} ..."
  docker stop "${NAME}" >/dev/null 2>&1 || true
  docker rm "${NAME}" >/dev/null 2>&1 || true
  echo ">> Done. (Database in ./db preserved.)"
else
  echo ">> No ${NAME} container running. Nothing to do."
fi
