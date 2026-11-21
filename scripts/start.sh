#!/usr/bin/env bash
# Start the observability stack, build the UI, serve the app and open it. Ctrl-C stops the app; the stack keeps
# running (docker compose down stops it).
set -euo pipefail
cd "$(dirname "$0")/.."

URL=http://127.0.0.1:8000
[ -d ui/node_modules ] || { echo "start: the UI's packages are missing; run scripts/setup.sh first" >&2; exit 1; }
if curl -s -o /dev/null "$URL"; then
  echo "start: something is already listening on $URL; stop it first" >&2
  exit 1
fi

docker compose up --wait
(cd ui && npm run build)

open_when_ready() {
  for _ in $(seq 60); do
    if curl -s -o /dev/null "$URL"; then
      if command -v open >/dev/null; then open "$URL"; else xdg-open "$URL"; fi
      return
    fi
    sleep 0.5
  done
  echo "start: the app didn't answer at $URL within 30 s" >&2
}
open_when_ready &

echo "start: the UI is at $URL and Grafana at http://localhost:3000; Ctrl-C stops the app"
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
exec uv run ground-ops serve
