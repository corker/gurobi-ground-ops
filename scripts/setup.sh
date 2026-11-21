#!/usr/bin/env bash
# Install everything ground-ops needs: Python and its packages, the UI's packages, and the observability image.
set -euo pipefail
cd "$(dirname "$0")/.."

need() {
  command -v "$1" >/dev/null || { echo "setup: $1 is missing; install it from $2" >&2; exit 1; }
}
need uv https://docs.astral.sh/uv/
need npm https://nodejs.org/
need docker https://docs.docker.com/get-started/get-docker/
docker info >/dev/null 2>&1 || { echo "setup: Docker isn't running; start it and try again" >&2; exit 1; }

uv sync
(cd ui && npm ci)
docker compose pull
echo "setup: done; scripts/start.sh starts everything"
