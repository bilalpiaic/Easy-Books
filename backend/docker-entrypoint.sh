#!/bin/sh
set -e

# Ensure the data directory exists (local_config.py also does this, but belt-and-suspenders)
mkdir -p "${EB_DATA_DIR:-/data}"

# #424 — APP_ROLE=api|migrate|worker. `arq …` is a worker command, not a role name.
CMD0="${1:-}"
ROLE="${APP_ROLE:-}"

if [ "$CMD0" = "migrate" ]; then
  ROLE=migrate
  shift
elif [ "$CMD0" = "api" ]; then
  ROLE=api
  shift
elif [ "$CMD0" = "worker" ]; then
  ROLE=worker
  shift
elif [ "$CMD0" = "arq" ]; then
  ROLE=worker
fi

run_migrations() {
  echo "[startup] Running Alembic migrations..."
  uv run alembic upgrade head
  echo "[startup] Seeding demo data (skips if any user already exists)..."
  uv run python -m scripts.autoseed_demo || echo "[startup] Demo seed skipped or non-fatal error"
}

should_migrate() {
  case "${RUN_MIGRATIONS:-}" in
    1|true|yes|on) return 0 ;;
    0|false|no|off) return 1 ;;
  esac
  case "$ROLE" in
    migrate) return 0 ;;
    worker) return 1 ;;
    api)
      # Explicit APP_ROLE=api (SaaS replicas) skips DDL. Compose/desktop leave
      # APP_ROLE unset and still migrate on API start.
      if [ -n "${APP_ROLE:-}" ]; then
        return 1
      fi
      return 0
      ;;
    *) return 0 ;;
  esac
}

if [ "$ROLE" = "migrate" ]; then
  run_migrations
  echo "[startup] Migrate role finished."
  exit 0
fi

if should_migrate; then
  run_migrations
fi

if [ "$ROLE" = "worker" ]; then
  if [ "$CMD0" = "arq" ]; then
    echo "[startup] Starting ARQ worker..."
    exec uv run "$@"
  fi
  echo "[startup] Starting ARQ worker..."
  exec uv run arq worker.WorkerSettings
fi

if [ -n "$CMD0" ] && [ "$CMD0" != "api" ]; then
  exec uv run "$@"
fi

echo "[startup] Starting API server..."
exec uv run python -m uvicorn main:app --host 0.0.0.0 --port 8000
