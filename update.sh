#!/usr/bin/env bash
# Easy-Books — update to the latest version.
# Your data (database + uploads) lives in $EB_DATA_DIR (default ~/.easy-books),
# OUTSIDE this folder, so it is never touched by the update. install-and-run.sh
# runs `alembic upgrade head` on launch, migrating your data forward safely.
set -euo pipefail
cd "$(dirname "$0")"
echo "Updating Easy-Books — your data in ${EB_DATA_DIR:-$HOME/.easy-books} is left untouched."
# uv sync (run by install-and-run.sh on every launch) can rewrite backend/uv.lock
# even with no dependency changes; discard that drift before pulling so a fresh
# upstream lockfile bump can't block the fast-forward (#138).
git checkout -- backend/uv.lock 2>/dev/null || true

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

git pull --ff-only
exec ./install-and-run.sh --rebuild
