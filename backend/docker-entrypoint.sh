#!/bin/sh
set -e

# Ensure the data directory exists (local_config.py also does this, but belt-and-suspenders)
mkdir -p "${EB_DATA_DIR:-/data}"

echo "[startup] Running Alembic migrations..."
uv run alembic upgrade head

echo "[startup] Seeding demo data (skips if any user already exists)..."
uv run python -m scripts.autoseed_demo || echo "[startup] Demo seed skipped or non-fatal error"

echo "[startup] Starting API server..."
exec uv run uvicorn main:app --host 0.0.0.0 --port 8000
