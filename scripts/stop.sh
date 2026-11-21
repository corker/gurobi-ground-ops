#!/usr/bin/env bash
# Stop what start.sh started: the app, then the observability stack, whose telemetry goes with it.
set -euo pipefail
cd "$(dirname "$0")/.."

if pkill -f "ground-ops serve"; then
  echo "stop: stopped the app"
else
  echo "stop: the app wasn't running"
fi
docker compose down
