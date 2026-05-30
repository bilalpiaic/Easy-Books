#!/usr/bin/env bash
#
# Easy-Books — one-click install & run (macOS / Linux).
#
# Auto-installs everything it needs (no pre-installed Python or Node required):
#   • uv         — self-installs; also provisions Python 3.12 automatically
#   • Node.js    — uses your system Node if present, else downloads a local
#                  portable copy into ./.node (no system install, no admin)
# Then builds the app and launches it at http://127.0.0.1:3000.
#
# Re-run any time. Pass --rebuild to force a fresh frontend build.
# Data (database + uploads + secret) lives in $EB_DATA_DIR (default ~/.easy-books).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
NODE_VERSION="20.18.1"

log()  { printf "\n\033[1;33m▶ %s\033[0m\n" "$*"; }
die()  { printf "\n\033[1;31m✖ %s\033[0m\n" "$*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "curl is required (it ships with macOS and most Linux)."

# ── 1. uv (provides Python 3.12 too) ──────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv (Python toolchain manager)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || die "uv install failed — see https://docs.astral.sh/uv/"

# ── 2. Node.js (system, else local portable download) ─────────────────────────
if command -v node >/dev/null 2>&1; then
  NODE_BIN="$(command -v node)"
else
  NODE_DIR="$ROOT/.node"
  if [ ! -x "$NODE_DIR/bin/node" ]; then
    log "Downloading a local Node.js $NODE_VERSION (no system install)…"
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    [ "$os" = "darwin" ] && plat="darwin" || plat="linux"
    arch="$(uname -m)"; case "$arch" in
      x86_64|amd64) arch="x64";;
      aarch64|arm64) arch="arm64";;
      *) die "Unsupported CPU arch: $arch (install Node 20+ manually, then re-run).";;
    esac
    url="https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-${plat}-${arch}.tar.gz"
    mkdir -p "$NODE_DIR"
    curl -fsSL "$url" | tar -xz -C "$NODE_DIR" --strip-components=1 \
      || die "Node download failed ($url). Check your internet connection."
  fi
  export PATH="$NODE_DIR/bin:$PATH"
  NODE_BIN="$NODE_DIR/bin/node"
fi

# ── 3. Backend dependencies (uv fetches Python 3.12 if missing) ───────────────
log "Installing backend dependencies…"
( cd backend && uv sync )

# ── 4. Frontend build (skipped if already built; --rebuild forces it) ─────────
if [ "${1:-}" = "--rebuild" ] || [ ! -f frontend/.next/standalone/server.js ]; then
  log "Building the app (first run can take a few minutes)…"
  ( cd frontend && npm install && npx next build )
  # Next 'standalone' does not copy these — required for the server to serve them.
  cp -r frontend/.next/static  frontend/.next/standalone/.next/static
  cp -r frontend/public        frontend/.next/standalone/public
fi

# ── 5. Launch (both servers, localhost only) ──────────────────────────────────
export EB_DATA_DIR="${EB_DATA_DIR:-$HOME/.easy-books}"
export SEED_DEMO="${SEED_DEMO:-true}"      # seed demo tenants so the advertised demo logins work (override with SEED_DEMO=false for an empty start)
export APP_ENV="${APP_ENV:-local}"
mkdir -p "$EB_DATA_DIR"

# Free ports from any previous run so the fresh backend (with seeding) binds.
for port in 8000 3000; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null || true
done

log "Starting Easy-Books — data folder: $EB_DATA_DIR"
( cd backend && PYTHONPATH=. uv run uvicorn main:app --host 127.0.0.1 --port 8000 ) &
BACK=$!
( cd frontend && PORT=3000 HOSTNAME=127.0.0.1 "$NODE_BIN" .next/standalone/server.js ) &
FRONT=$!

trap 'kill $BACK $FRONT 2>/dev/null || true' EXIT INT TERM
sleep 3
log "Easy-Books is running at  http://127.0.0.1:3000   (press Ctrl+C to stop)"
( command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:3000 >/dev/null 2>&1 ) \
  || ( command -v open >/dev/null && open http://127.0.0.1:3000 ) \
  || true
wait
