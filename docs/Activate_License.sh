#!/usr/bin/env bash
# Field tool: activate a signed Easy-Books install license (macOS / Linux).
# Paste the EB1.… token issued by Easy-Books. The private signing seed is
# NOT in this file. Run from the Easy-Books docs folder:
#   bash docs/Activate_License.sh
# Writes ~/.easy-books/.easy-books-license (or $EB_DATA_DIR). Source folder
# and books are never deleted.
#
# Do NOT run with `sh docs/Activate_License.sh` — this script needs bash.

if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script requires bash. Run:  bash docs/Activate_License.sh" >&2
  exit 1
fi

set -euo pipefail

unset EB_LICENSE_TOKEN 2>/dev/null || true
cleanup() { unset EB_LICENSE_TOKEN 2>/dev/null || true; }
trap cleanup EXIT

echo "============================================================"
echo "             EASY BOOKS - ACTIVATE LICENSE"
echo "============================================================"
echo
echo "This unlocks this installation with a signed license token."
echo "Stop Easy-Books first. Your source folder and books are not deleted."
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$REPO_ROOT/backend/scripts/activate_license.py" ]; then
  echo "[ERROR] backend/scripts/activate_license.py not found."
  echo "        This script must live in <Easy-Books>/docs/"
  echo "        Current folder: $SCRIPT_DIR"
  echo
  exit 1
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# Same data dir as install-and-run.sh. Without this, Python defaults to
# backend/ and the running copy (which uses ~/.easy-books) stays locked.
ROOT="$REPO_ROOT"
if [ -f "$ROOT/portable/apply-env.sh" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/portable/apply-env.sh"
fi
export EB_DATA_DIR="${EB_DATA_DIR:-$HOME/.easy-books}"

echo "Paste the license token (EB1.…):"
if [ -t 0 ]; then
  IFS= read -r EB_LICENSE_TOKEN || true
else
  IFS= read -r EB_LICENSE_TOKEN || true
fi

if [ -z "${EB_LICENSE_TOKEN:-}" ]; then
  echo
  echo "[ERROR] License token is required."
  echo
  exit 1
fi
export EB_LICENSE_TOKEN

cd "$REPO_ROOT/backend" || {
  echo "[ERROR] Cannot open $REPO_ROOT/backend."
  exit 1
}
export PYTHONPATH=.

rc=0
if command -v uv >/dev/null 2>&1; then
  uv run python -m scripts.activate_license "$@" || rc=$?
elif [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m scripts.activate_license "$@" || rc=$?
elif command -v python3 >/dev/null 2>&1; then
  python3 -m scripts.activate_license "$@" || rc=$?
elif command -v python >/dev/null 2>&1; then
  python -m scripts.activate_license "$@" || rc=$?
else
  echo "[ERROR] uv / Python not found. Install Easy-Books first (./install-and-run.sh)."
  exit 1
fi

unset EB_LICENSE_TOKEN
echo
if [ "$rc" -ne 0 ]; then
  echo "[ERROR] License was not activated. Check the token and that"
  echo "        Easy-Books is installed (uv / Python in backend)."
  echo
  exit 1
fi

echo "Restart Easy-Books (./install-and-run.sh or the desktop app)"
echo "for the license to take effect."
echo
exit 0
