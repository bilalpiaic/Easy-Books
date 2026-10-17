#!/usr/bin/env bash
# Field / staff: remove the signed license from this client PC.
# Run from the Easy-Books docs folder:
#   bash docs/Deactivate_License.sh
# Deletes ~/.easy-books/.easy-books-license (or $EB_DATA_DIR).
# Type DEACTIVATE to confirm. Books and source are not deleted.
#
# Do NOT run with `sh docs/Deactivate_License.sh` — this script needs bash.

if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script requires bash. Run:  bash docs/Deactivate_License.sh" >&2
  exit 1
fi

set -euo pipefail

echo "============================================================"
echo "            EASY BOOKS - DEACTIVATE LICENSE"
echo "============================================================"
echo
echo "This removes the signed license from THIS PC."
echo "Your source folder and books are not deleted."
echo "If the 15-day trial has already ended, the copy will lock again."
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$REPO_ROOT/backend/scripts/deactivate_license.py" ]; then
  echo "[ERROR] backend/scripts/deactivate_license.py not found."
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

echo "Type DEACTIVATE to continue:"
IFS= read -r CONFIRM || true

if [ "${CONFIRM:-}" != "DEACTIVATE" ]; then
  echo
  echo "[ERROR] Not deactivated (type DEACTIVATE exactly)."
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
  uv run python -m scripts.deactivate_license --yes "$@" || rc=$?
elif [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m scripts.deactivate_license --yes "$@" || rc=$?
elif command -v python3 >/dev/null 2>&1; then
  python3 -m scripts.deactivate_license --yes "$@" || rc=$?
elif command -v python >/dev/null 2>&1; then
  python -m scripts.deactivate_license --yes "$@" || rc=$?
else
  echo "[ERROR] uv / Python not found. Install Easy-Books first (./install-and-run.sh)."
  exit 1
fi

echo
if [ "$rc" -ne 0 ]; then
  echo "[ERROR] License was not deactivated."
  echo
  exit 1
fi

echo "Restart Easy-Books. If the trial has ended you will see Trial ended."
echo
exit 0
