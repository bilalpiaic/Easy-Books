#!/usr/bin/env bash
# Launch Easy-Books locally (on-premise): both servers bound to 127.0.0.1.
#
# Prereqs (one-time):
#   backend:  cd backend && uv sync
#   frontend: cd frontend && npm install && npx next build
#             then copy static assets into the standalone bundle:
#             cp -r frontend/.next/static frontend/.next/standalone/.next/static
#             cp -r frontend/public      frontend/.next/standalone/public
#
# Data (SQLite db, uploads, per-install secret) lives under $EB_DATA_DIR.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export EB_DATA_DIR="${EB_DATA_DIR:-$HOME/.easy-books}"
export SEED_DEMO="${SEED_DEMO:-false}"     # packaged installs boot empty
export APP_ENV="${APP_ENV:-local}"
mkdir -p "$EB_DATA_DIR"

PATH="$HOME/.local/bin:$PATH"

# Backend (FastAPI) on 127.0.0.1:8000
( cd "$ROOT/backend" && PYTHONPATH=. uv run uvicorn main:app --host 127.0.0.1 --port 8000 ) &
BACK=$!

# Frontend (Next.js standalone) on 127.0.0.1:3000
( cd "$ROOT/frontend" && PORT=3000 HOSTNAME=127.0.0.1 node .next/standalone/server.js ) &
FRONT=$!

trap 'kill $BACK $FRONT 2>/dev/null || true' EXIT INT TERM
sleep 2
( command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:3000 ) \
  || ( command -v open >/dev/null && open http://127.0.0.1:3000 ) \
  || echo "Open http://127.0.0.1:3000 in your browser."
wait
