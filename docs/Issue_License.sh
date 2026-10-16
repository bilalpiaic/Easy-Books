#!/usr/bin/env bash
# STAFF ONLY — generate an EB1 license token for one client.
# Run this on the field-staff laptop / office checkout, NOT on the client's
# Easy-Books folder. The signing seed is NOT stored in this file.
#   bash docs/Issue_License.sh
# Repeat for any other client with that client's install ID + owner email.

if [ -z "${BASH_VERSION:-}" ]; then
  echo "This script requires bash. Run:  bash docs/Issue_License.sh" >&2
  exit 1
fi

set -euo pipefail

cleanup() { :; }
trap cleanup EXIT

echo "============================================================"
echo "             EASY BOOKS - ISSUE LICENSE (staff)"
echo "============================================================"
echo
echo "Generate a token on THIS machine for one client."
echo "Do not run this inside a customer's Easy-Books copy."
echo "You need that client's Install ID (UUID) and owner email."
echo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$REPO_ROOT/backend/scripts/issue_license.py" ]; then
  echo "[ERROR] backend/scripts/issue_license.py not found."
  echo "        Run this from staff's Easy-Books docs/ folder."
  echo "        Current folder: $SCRIPT_DIR"
  echo
  exit 1
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if [ -z "${EB_LICENSE_SIGNING_SEED:-}" ]; then
  echo "[ERROR] Set EB_LICENSE_SIGNING_SEED on this staff machine first."
  echo "        The seed is not stored in this script."
  echo
  exit 1
fi

echo "Client install ID (UUID from their lock screen):"
IFS= read -r INSTALL_ID || true
echo "Owner email on that install:"
IFS= read -r OWNER_EMAIL || true

if [ -z "${INSTALL_ID:-}" ] || [ -z "${OWNER_EMAIL:-}" ]; then
  echo
  echo "[ERROR] Install ID and owner email are required."
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
  uv run python -m scripts.issue_license --install-id "$INSTALL_ID" --email "$OWNER_EMAIL" "$@" || rc=$?
elif [ -x ".venv/bin/python" ]; then
  .venv/bin/python -m scripts.issue_license --install-id "$INSTALL_ID" --email "$OWNER_EMAIL" "$@" || rc=$?
elif command -v python3 >/dev/null 2>&1; then
  python3 -m scripts.issue_license --install-id "$INSTALL_ID" --email "$OWNER_EMAIL" "$@" || rc=$?
elif command -v python >/dev/null 2>&1; then
  python -m scripts.issue_license --install-id "$INSTALL_ID" --email "$OWNER_EMAIL" "$@" || rc=$?
else
  echo "[ERROR] uv / Python not found. Use a staff Easy-Books checkout that can run backend scripts."
  exit 1
fi

echo
if [ "$rc" -ne 0 ]; then
  echo "[ERROR] Token was not issued. Check the seed, install ID, and email."
  echo
  exit 1
fi

echo "Send that EB1.… line to the client (or paste it on their lock screen)."
echo "It only unlocks the install ID you typed. Repeat for the next client."
echo
exit 0
