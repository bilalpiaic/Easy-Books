#!/usr/bin/env bash
# Start the FastAPI backend and the Next.js frontend together.
# Ctrl-C (or any signal) stops both. If either process exits, the other is
# stopped as well so you don't end up with a half-running app.

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_PY="$BACKEND_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "error: backend venv not found at $VENV_PY" >&2
  echo "create it with: python -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "error: frontend dependencies missing. run 'npm install' in $FRONTEND_DIR" >&2
  exit 1
fi

# Pre-flight: make sure the ports we want are free. Without this, uvicorn or
# next-dev would fail seconds after the script claims it started everything,
# which is confusing. We report the holder PID + command so it's easy to act on.
check_port() {
  local port="$1" label="$2" holder
  holder="$(ss -tlnp "sport = :$port" 2>/dev/null | awk 'NR>1' | head -n1)"
  if [[ -n "$holder" ]]; then
    echo "error: port $port (for $label) is already in use:" >&2
    echo "  $holder" >&2
    echo "free it with: fuser -k ${port}/tcp   (or kill the PID listed above)" >&2
    return 1
  fi
}

PORT_CONFLICT=0
check_port 8000 backend  || PORT_CONFLICT=1
check_port 3000 frontend || PORT_CONFLICT=1
[[ $PORT_CONFLICT -eq 1 ]] && exit 1

# Prefix each line of a stream with a colored tag so the two log streams
# are easy to tell apart in the combined output.
prefix() {
  local tag="$1" color="$2" line
  while IFS= read -r line; do
    printf '\033[%sm[%s]\033[0m %s\n' "$color" "$tag" "$line"
  done
}

# Seed demo data (idempotent — safe every run; skips rows that already exist).
echo "seeding demo data..."
if (
  cd "$BACKEND_DIR"
  PYTHONPATH=. "$VENV_PY" -m scripts.seed_demo
) 2>&1 | prefix "seed" "33"; then
  echo "demo data ready."
else
  echo "warning: demo seed reported errors (non-fatal — server still starting)" >&2
fi

# Resolve a Linux node binary — the Windows node/npm on PATH causes CMD.EXE to
# be invoked inside WSL2, which fails with "UNC paths are not supported".
NODE_BIN="$(command -v node 2>/dev/null)"
if [[ -z "$NODE_BIN" || "$NODE_BIN" == /mnt/c/* ]]; then
  # Fall back to the VSCode Server node if the PATH node is a Windows binary.
  NODE_BIN="$(find /home -maxdepth 6 -path '*/.vscode-server/*/node' -type f 2>/dev/null | head -n1)"
fi
if [[ -z "$NODE_BIN" ]]; then
  echo "error: no Linux node binary found. Install Node.js inside WSL2." >&2
  exit 1
fi
NEXT_BIN="$FRONTEND_DIR/node_modules/next/dist/bin/next"

BACK_PID=""
FRONT_PID=""

cleanup() {
  trap - INT TERM EXIT
  echo
  echo "stopping..."
  [[ -n "$BACK_PID"  ]] && kill -TERM "$BACK_PID"  2>/dev/null || true
  [[ -n "$FRONT_PID" ]] && kill -TERM "$FRONT_PID" 2>/dev/null || true
  # Give them a moment to shut down gracefully, then SIGKILL stragglers.
  sleep 1
  [[ -n "$BACK_PID"  ]] && kill -KILL "$BACK_PID"  2>/dev/null || true
  [[ -n "$FRONT_PID" ]] && kill -KILL "$FRONT_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM EXIT

# Backend: uvicorn via main.py (binds to localhost:8000, reload on).
(
  cd "$BACKEND_DIR"
  exec "$VENV_PY" main.py
) > >(prefix "backend"  "36") 2> >(prefix "backend"  "36" >&2) &
BACK_PID=$!

# Frontend: Next.js dev server on port 3000.
(
  cd "$FRONTEND_DIR"
  exec "$NODE_BIN" "$NEXT_BIN" dev
) > >(prefix "frontend" "35") 2> >(prefix "frontend" "35" >&2) &
FRONT_PID=$!

echo "backend  pid=$BACK_PID  -> http://localhost:8000  (docs: /docs)"
echo "frontend pid=$FRONT_PID -> http://localhost:3000"
echo "press Ctrl-C to stop both."

# Wait until either child exits, then cleanup() takes over via the EXIT trap.
wait -n "$BACK_PID" "$FRONT_PID"
EXITED=$?
echo "one process exited (status $EXITED), shutting down the other..."
