#!/usr/bin/env bash
# Easy-Books — update to the latest version.
# Your data (database + uploads) lives in $EB_DATA_DIR (default ~/.easy-books),
# OUTSIDE this folder, so it is never touched by the update. install-and-run.sh
# runs `alembic upgrade head` on launch, migrating your data forward safely.
set -euo pipefail
cd "$(dirname "$0")"
echo "Updating Easy-Books — your data in ${EB_DATA_DIR:-$HOME/.easy-books} is left untouched."
git pull --ff-only
exec ./install-and-run.sh --rebuild
