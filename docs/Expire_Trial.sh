#!/usr/bin/env bash
# QA / staff: force-expire the standalone trial clock (macOS / Linux).
# Run from the Easy-Books docs folder:
#   bash docs/Expire_Trial.sh
# Charges ~/.easy-books (or $EB_DATA_DIR), never backend/. Books and source
# are not deleted. Type EXPIRE to confirm.
#
# Do NOT run with `sh docs/Expire_Trial.sh` — this script needs bash.

if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script requires bash. Run:  bash docs/Expire_Trial.sh" >&2
  exit 1
fi

set -euo pipefail

echo "============================================================"
echo "             EASY BOOKS - FORCE EXPIRE TRIAL"
echo "============================================================"
echo
echo "This locks the copy as if the 15-day trial had already ended."
echo "Your source folder and books are not deleted."
echo "If a license file is present the copy stays unlocked."
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$REPO_ROOT/backend/scripts/expire_trial.py" ]; then
  echo "[ERROR] backend/scripts/expire_trial.py not found."
  echo "        This script must live in <Easy-Books>/docs/"
  echo "        Current folder: $SCRIPT_DIR"
  echo
  exit 1
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

ROOT="$REPO_ROOT"
if [ -f "$ROOT/portable/apply-env.sh" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/portable/apply-env.sh"
fi
export EB_DATA_DIR="${EB_DATA_DIR:-$HOME/.easy-books}"

echo "Type EXPIRE to continue:"
if [ -t 0 ]; then
  IFS= read -r CONFIRM || true
  echo
else
  IFS= read -r CONFIRM || true
fi

if [ "${CONFIRM:-}" != "EXPIRE" ]; then
  echo
  echo "[ERROR] Not expired (type EXPIRE exactly)."
  echo
  exit 1
fi

cd "$REPO_ROOT/backend" || {
  echo "[ERROR] Cannot open $REPO_ROOT/backend."
  exit 1
}
export PYTHONPATH=.

rc=0
if command -v uv >/dev/null 2>&1; then
  uv run python -m scripts.expire_trial --yes "$@" || rc=$?
elif [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m scripts.expire_trial --yes "$@" || rc=$?
elif command -v python3 >/dev/null 2>&1; then
  python3 -m scripts.expire_trial --yes "$@" || rc=$?
elif command -v python >/dev/null 2>&1; then
  python -m scripts.expire_trial --yes "$@" || rc=$?
else
  echo "[ERROR] uv / Python not found. Install Easy-Books first (./install-and-run.sh)."
  exit 1
fi

echo
if [ "$rc" -ne 0 ]; then
  echo "[ERROR] Trial was not force-expired."
  echo
  exit 1
fi

echo "Refresh the login page (or restart Easy-Books) to see Trial ended."
echo
exit 0
