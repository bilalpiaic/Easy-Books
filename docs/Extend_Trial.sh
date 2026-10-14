#!/usr/bin/env bash
# Field tool: grant another 15-day standalone trial window (macOS / Linux).
# The password is NOT stored in this file. It is checked (SHA-256) by
# backend/scripts/extend_trial.py. Run from the Easy-Books docs folder:
#   bash docs/Extend_Trial.sh
# Source folder and ~/.easy-books books are never deleted.
#
# Do NOT run with `sh docs/Extend_Trial.sh` — this script needs bash.

if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script requires bash. Run:  bash docs/Extend_Trial.sh" >&2
  exit 1
fi

set -euo pipefail

unset EB_EXTEND_TRIAL_PASSWORD 2>/dev/null || true
cleanup() { unset EB_EXTEND_TRIAL_PASSWORD 2>/dev/null || true; }
trap cleanup EXIT

echo "============================================================"
echo "             EASY BOOKS - EXTEND TRIAL (15 days)"
echo "============================================================"
echo
echo "This restarts the trial clock from today. Stop Easy-Books first."
echo "Your source folder and books are not deleted."
echo "A field password is required (typing is hidden)."
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$REPO_ROOT/backend/scripts/extend_trial.py" ]; then
  echo "[ERROR] backend/scripts/extend_trial.py not found."
  echo "        This script must live in <Easy-Books>/docs/"
  echo "        Current folder: $SCRIPT_DIR"
  echo
  exit 1
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

echo "Enter the extend-trial password:"
if [ -t 0 ]; then
  # Hidden prompt on a real terminal (same idea as the Windows .bat).
  IFS= read -r -s -p "Password: " EB_EXTEND_TRIAL_PASSWORD || true
  echo
else
  IFS= read -r EB_EXTEND_TRIAL_PASSWORD || true
fi

if [ -z "${EB_EXTEND_TRIAL_PASSWORD:-}" ]; then
  echo
  echo "[ERROR] Password is required."
  echo
  exit 1
fi
export EB_EXTEND_TRIAL_PASSWORD

cd "$REPO_ROOT/backend" || {
  echo "[ERROR] Cannot open $REPO_ROOT/backend."
  exit 1
}
export PYTHONPATH=.

rc=0
if command -v uv >/dev/null 2>&1; then
  uv run python -m scripts.extend_trial "$@" || rc=$?
elif [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m scripts.extend_trial "$@" || rc=$?
elif command -v python3 >/dev/null 2>&1; then
  python3 -m scripts.extend_trial "$@" || rc=$?
elif command -v python >/dev/null 2>&1; then
  python -m scripts.extend_trial "$@" || rc=$?
else
  echo "[ERROR] uv / Python not found. Install Easy-Books first (./install-and-run.sh)."
  exit 1
fi

unset EB_EXTEND_TRIAL_PASSWORD
echo
if [ "$rc" -ne 0 ]; then
  echo "[ERROR] Trial was not extended. Check the password and that"
  echo "        Easy-Books is installed (uv / Python in backend)."
  echo
  exit 1
fi

echo "Restart Easy-Books (./install-and-run.sh or the desktop app)"
echo "for the new 15-day window to take effect."
echo
exit 0
