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
# Rebuild when forced, when there's no build yet, OR when the code has moved on
# since the last build (so a git pull / update always recompiles the UI — a
# stale bundle must never hide new features).
HEAD_COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
BUILT_COMMIT="$(cat frontend/.next/.built-commit 2>/dev/null || true)"
# Read the app version from frontend/package.json so the UI version badge shows
# the correct release string, not the fallback "dev".
APP_VERSION="$(uv run python3 -c "import json; print(json.load(open('frontend/package.json'))['version'],end='')" 2>/dev/null || echo "dev")"
if [ "${1:-}" = "--rebuild" ] || [ ! -f frontend/.next/standalone/server.js ] \
   || { [ -n "$HEAD_COMMIT" ] && [ "$HEAD_COMMIT" != "$BUILT_COMMIT" ]; }; then
  log "Building the app (first run or update can take a few minutes)…"
  BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ( cd frontend && npm install && \
    NEXT_PUBLIC_APP_VERSION="$APP_VERSION" \
    NEXT_PUBLIC_GIT_COMMIT="${HEAD_COMMIT:-dev}" \
    NEXT_PUBLIC_BUILD_DATE="$BUILD_DATE" \
    npx next build )
  # Write version.json so the running server can self-report its build identity.
  # UpdateModal fetches /version.json to detect when update.sh has already
  # rebuilt the server (commit differs from the page's baked-in GIT_COMMIT).
  printf '{"version":"%s","commit":"%s","built":"%s"}\n' \
    "$APP_VERSION" "${HEAD_COMMIT:-dev}" "$BUILD_DATE" \
    > frontend/public/version.json
  # Next 'standalone' does not copy these — required for the server to serve them.
  cp -r frontend/.next/static  frontend/.next/standalone/.next/static
  cp -r frontend/public        frontend/.next/standalone/public
  [ -n "$HEAD_COMMIT" ] && echo "$HEAD_COMMIT" > frontend/.next/.built-commit
fi

# ── 5. Launch (both servers, localhost only) ──────────────────────────────────
export EB_DATA_DIR="${EB_DATA_DIR:-$HOME/.easy-books}"
export FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:3000,http://127.0.0.1:3000}"  # allow both hosts so the browser is not CORS-blocked
export SEED_DEMO="${SEED_DEMO:-true}"       # auto-load full demo data on first install; set SEED_DEMO=false for a clean install
export APP_ENV="${APP_ENV:-local}"
mkdir -p "$EB_DATA_DIR"

# Free ports from any previous run so the fresh backend binds — and so no stale
# process holds the SQLite file lock when we migrate next.
for port in 8000 3000; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null || true
done

# Migrate the user's DB forward so updates apply new columns (not just tables).
# Fail loud rather than start the app on a half-migrated schema.
# Auto-backup before any migration so users can roll back by restoring the file.
log "Checking for pending database migrations…"
PENDING="$( cd backend && PYTHONPATH=. uv run alembic check 2>&1 )" && HAS_PENDING=0 || HAS_PENDING=1
if [ "$HAS_PENDING" = "1" ]; then
  BACKUP_DIR="$EB_DATA_DIR/backups"
  mkdir -p "$BACKUP_DIR"
  STAMP="$(date +%Y%m%d_%H%M%S)"
  for db_file in "$EB_DATA_DIR"/*.db; do
    [ -f "$db_file" ] && cp "$db_file" "$BACKUP_DIR/$(basename "$db_file" .db)_$STAMP.bak" && \
      log "  Backed up $(basename "$db_file") → backups/$(basename "$db_file" .db)_$STAMP.bak"
  done
fi
log "Applying database migrations…"
( cd backend && PYTHONPATH=. uv run alembic upgrade head ) \
  || die "Database migration failed — restore from $EB_DATA_DIR/backups/ if needed. See the error above."

# First-run demo data: load the 5 fully-populated demo companies so the demo
# logins work immediately. Idempotent (skips once present); skipped entirely
# when SEED_DEMO=false. ~20-30s on first install only.
log "Loading demo data (first run only; set SEED_DEMO=false to skip)…"
( cd backend && PYTHONPATH=. uv run python -m scripts.autoseed_demo ) \
  || echo "  (demo seeding skipped/failed — non-fatal; the app still starts)"

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
