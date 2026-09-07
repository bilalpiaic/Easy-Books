#!/usr/bin/env bash
#
# Easy-Books — cloud-folder / portable launcher.
#
# Consumer cloud storage cannot keep a backend "always running". This script
# runs FastAPI + Next.js on THIS computer and points SQLite at a folder that
# can live on OneDrive, Google Drive, or any other synced drive.
#
# Daily use (after one install-and-run):
#   ./launch-cloud.sh              # start whatever is down, then open the UI
#   ./launch-cloud.sh --open       # frontend only: open the browser (backend must already be up)
#   ./launch-cloud.sh --backend    # keep the API running (use with OS login items)
#   ./launch-cloud.sh --stop       # stop local servers started by this launcher
#
# First-time: copy easy-books-portable.env.example → easy-books-portable.env
# and run ./install-and-run.sh once so deps and the Next.js standalone build exist.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
. "$ROOT/portable/apply-env.sh"

export EB_PORTABLE="${EB_PORTABLE:-1}"
export EB_CLOUD_SAFE_SQLITE="${EB_CLOUD_SAFE_SQLITE:-true}"
export EB_INSTANCE_LOCK="${EB_INSTANCE_LOCK:-true}"
export EB_DATA_DIR="${EB_DATA_DIR:-$ROOT/data}"
export FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:3000,http://127.0.0.1:3000}"
export APP_ENV="${APP_ENV:-local}"
export SEED_DEMO="${SEED_DEMO:-false}"
export PATH="$HOME/.local/bin:$ROOT/.node/bin:$PATH"

MODE="up"
case "${1:-}" in
  --open|-o) MODE="open" ;;
  --backend|-b) MODE="backend" ;;
  --stop) MODE="stop" ;;
  --help|-h)
    sed -n '2,18p' "$0"
    exit 0
    ;;
esac

RUN_DIR="$ROOT/.run"
mkdir -p "$EB_DATA_DIR" "$RUN_DIR"

api_up() { curl -sf --max-time 2 http://127.0.0.1:8000/api/version >/dev/null 2>&1; }
ui_up()  { curl -sf --max-time 2 -o /dev/null http://127.0.0.1:3000/login >/dev/null 2>&1 || \
           curl -sf --max-time 2 -o /dev/null http://127.0.0.1:3000/ >/dev/null 2>&1; }

open_ui() {
  ( command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:3000/login >/dev/null 2>&1 ) \
    || ( command -v open >/dev/null && open http://127.0.0.1:3000/login ) \
    || echo "Open http://127.0.0.1:3000/login in your browser."
}

stop_pidfile() {
  local f="$1"
  if [ -f "$f" ]; then
    local pid
    pid="$(cat "$f" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$f"
  fi
}

if [ "$MODE" = "stop" ]; then
  stop_pidfile "$RUN_DIR/backend.pid"
  stop_pidfile "$RUN_DIR/frontend.pid"
  echo "Stopped Easy-Books local servers (data folder left untouched: $EB_DATA_DIR)"
  exit 0
fi

if [ "$MODE" = "open" ]; then
  if ! api_up; then
    echo "Backend is not running on http://127.0.0.1:8000." >&2
    echo "Start it with:  ./launch-cloud.sh --backend" >&2
    echo "Or start both:  ./launch-cloud.sh" >&2
    exit 1
  fi
  if ! ui_up; then
    echo "Frontend is not running. Starting it…"
    MODE="frontend-only"
  else
    open_ui
    echo "Opened http://127.0.0.1:3000  (API already running; data: $EB_DATA_DIR)"
    exit 0
  fi
fi

NODE_BIN="$(command -v node || true)"
if [ -z "$NODE_BIN" ] && [ -x "$ROOT/.node/bin/node" ]; then
  NODE_BIN="$ROOT/.node/bin/node"
fi

start_backend() {
  if api_up; then
    echo "Backend already running on :8000"
    return 0
  fi
  if [ ! -d "$ROOT/backend" ]; then
    echo "Missing backend/ — run this from the Easy-Books folder." >&2
    exit 1
  fi
  echo "Starting backend (data: $EB_DATA_DIR)…"
  (
    cd "$ROOT/backend"
    PYTHONPATH=. uv run python -m uvicorn main:app --host 127.0.0.1 --port 8000 \
      >>"$RUN_DIR/backend.log" 2>&1
  ) &
  echo $! > "$RUN_DIR/backend.pid"
  local ready=0
  for _ in $(seq 1 60); do
    if api_up; then ready=1; break; fi
    sleep 1
  done
  if [ "$ready" != "1" ]; then
    echo "Backend failed to start. Last log:" >&2
    tail -n 40 "$RUN_DIR/backend.log" >&2 || true
    exit 1
  fi
}

start_frontend() {
  if ui_up; then
    echo "Frontend already running on :3000"
    return 0
  fi
  if [ -z "$NODE_BIN" ]; then
    echo "Node.js not found. Run ./install-and-run.sh once first." >&2
    exit 1
  fi
  if [ ! -f "$ROOT/frontend/.next/standalone/server.js" ]; then
    echo "Frontend is not built. Run ./install-and-run.sh once first." >&2
    exit 1
  fi
  echo "Starting frontend…"
  (
    cd "$ROOT/frontend"
    PORT=3000 HOSTNAME=127.0.0.1 "$NODE_BIN" .next/standalone/server.js \
      >>"$RUN_DIR/frontend.log" 2>&1
  ) &
  echo $! > "$RUN_DIR/frontend.pid"
  for _ in $(seq 1 30); do
    if ui_up; then break; fi
    sleep 1
  done
}

if [ "$MODE" = "backend" ]; then
  start_backend
  echo "API is running at http://127.0.0.1:8000  — leave this machine on."
  echo "Open the UI with ./launch-cloud.sh --open  (or start the frontend too with ./launch-cloud.sh)"
  exit 0
fi

if [ "${MODE}" = "frontend-only" ]; then
  start_frontend
  open_ui
  echo "Opened http://127.0.0.1:3000"
  exit 0
fi

start_backend
start_frontend
open_ui
echo "Easy-Books is running at http://127.0.0.1:3000"
echo "Data folder: $EB_DATA_DIR"
echo "Stop with: ./launch-cloud.sh --stop"
