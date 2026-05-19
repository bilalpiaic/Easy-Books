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

# Prefix each line of a stream with a colored tag so the two log streams
# are easy to tell apart in the combined output.
prefix() {
  local tag="$1" color="$2" line
  while IFS= read -r line; do
    printf '\033[%sm[%s]\033[0m %s\n' "$color" "$tag" "$line"
  done
}

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
  exec npm run dev --silent
) > >(prefix "frontend" "35") 2> >(prefix "frontend" "35" >&2) &
FRONT_PID=$!

echo "backend  pid=$BACK_PID  -> http://localhost:8000  (docs: /docs)"
echo "frontend pid=$FRONT_PID -> http://localhost:3000"
echo "press Ctrl-C to stop both."

# Wait until either child exits, then cleanup() takes over via the EXIT trap.
wait -n "$BACK_PID" "$FRONT_PID"
EXITED=$?
echo "one process exited (status $EXITED), shutting down the other..."
