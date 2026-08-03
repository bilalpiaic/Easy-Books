#!/usr/bin/env bash
# Easy-Books — update to the latest version.
# Your data (database + uploads) lives in $EB_DATA_DIR (default ~/.easy-books),
# OUTSIDE this folder, so it is never touched by the update. install-and-run.sh
# runs `alembic upgrade head` on launch, migrating your data forward safely.
#
# Usage (Debian / Ubuntu / macOS):
#   ./update.sh
#   bash update.sh          # if the file lost +x
# Do NOT run with `sh update.sh` — this script needs bash.
set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
  echo "✖ update.sh requires bash. Run:  bash update.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "Updating Easy-Books — your data in ${EB_DATA_DIR:-$HOME/.easy-books} is left untouched."

if [ ! -d .git ]; then
  echo "✖ This folder is not a git checkout (no .git). Clone from GitHub, or update manually:" >&2
  echo "    https://github.com/bilalpiaic/Easy-Books" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "✖ git is required. On Debian/Ubuntu:  sudo apt-get install -y git" >&2
  exit 1
fi

# Installer / tool churn that must not block `git pull --ff-only` (#138 + Debian):
#   • uv sync can rewrite backend/uv.lock (platform resolution drift)
#   • next build used to overwrite tracked frontend/public/version.json
# These files are machine-generated; discarding local edits is always safe —
# the next install regenerates them.
discard_installer_drift() {
  git checkout -- backend/uv.lock frontend/public/version.json 2>/dev/null || true
}

discard_installer_drift

# Local-only frontend sources are still typechecked by `next build` and will
# abort the update even when git pull is clean. FloatingStack was a phone-side
# experiment that never shipped upstream (TS: `c !== false`).
if [ -f frontend/src/components/mobile/FloatingStack.tsx ]; then
  echo "⚠ Removing local-only frontend/src/components/mobile (breaks next build)."
  rm -rf frontend/src/components/mobile
fi
layout="frontend/src/app/(dashboard)/layout.tsx"
if [ -f "$layout" ] && grep -q FloatingStack "$layout" 2>/dev/null; then
  echo "⚠ Restoring layout.tsx (local FloatingStack import)."
  git checkout -- "$layout" 2>/dev/null || true
fi

# Prefer tracking branch when configured; fall back to origin/main.
git fetch --quiet origin 2>/dev/null || true

if ! git pull --ff-only; then
  echo "" >&2
  echo "✖ git pull --ff-only failed — local files are blocking the update." >&2
  echo "  Working tree:" >&2
  git status -sb >&2 || true
  echo "" >&2
  echo "  Safe fixes for a script install (no local commits you care about):" >&2
  echo "    git checkout -- backend/uv.lock frontend/public/version.json" >&2
  echo "    git fetch origin && git reset --hard origin/main" >&2
  echo "    bash update.sh" >&2
  echo "" >&2
  echo "  Your data in ${EB_DATA_DIR:-$HOME/.easy-books} is never touched by these commands." >&2
  exit 1
fi

# Re-discard in case the pull brought an older update.sh that still left drift
# from a concurrent installer write (race on long builds — belt and braces).
discard_installer_drift

# Always invoke via bash so a missing +x bit on install-and-run.sh cannot fail
# the update on a fresh Debian clone.
exec bash "$ROOT/install-and-run.sh" --rebuild
