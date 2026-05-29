#!/usr/bin/env bash
#
# Easy-Books bootstrap (macOS / Linux) — clone (or update) the repo, then
# install everything and run. The only manual step a new user takes.
#
# One-liner (nothing pre-downloaded):
#   curl -fsSL https://raw.githubusercontent.com/bilalpiaic/Easy-Books/main/bootstrap.sh | bash
#
# Or download this file and run:  ./bootstrap.sh [install-dir]
# Install location: 1st arg, else $EB_INSTALL_DIR, else ~/Easy-Books.
set -euo pipefail

REPO="https://github.com/bilalpiaic/Easy-Books.git"
ZIP="https://github.com/bilalpiaic/Easy-Books/archive/refs/heads/main.zip"
DEST="${1:-${EB_INSTALL_DIR:-$HOME/Easy-Books}}"

log() { printf "\n\033[1;33m▶ %s\033[0m\n" "$*"; }
die() { printf "\n\033[1;31m✖ %s\033[0m\n" "$*" >&2; exit 1; }

log "Easy-Books will be installed in: $DEST"

if command -v git >/dev/null 2>&1; then
  if [ -d "$DEST/.git" ]; then
    log "Updating existing copy (git pull)…"
    git -C "$DEST" pull --ff-only || true
  elif [ -e "$DEST" ]; then
    log "Folder already exists and is not a git repo — using it as-is."
  else
    log "Cloning $REPO …"
    git clone --depth 1 "$REPO" "$DEST"
  fi
else
  # No git — download the source archive instead (still one command for the user).
  if [ ! -e "$DEST" ]; then
    command -v curl >/dev/null 2>&1 || die "Need either git or curl installed."
    command -v unzip >/dev/null 2>&1 || die "git not found and 'unzip' is unavailable — install git or unzip."
    log "git not found — downloading source archive…"
    tmp="$(mktemp -d)"
    curl -fsSL "$ZIP" -o "$tmp/eb.zip" || die "Download failed — check your internet connection."
    ( cd "$tmp" && unzip -q eb.zip )
    mv "$tmp/Easy-Books-main" "$DEST"
    rm -rf "$tmp"
  fi
fi

[ -f "$DEST/install-and-run.sh" ] || die "install-and-run.sh not found in $DEST."
cd "$DEST"
chmod +x install-and-run.sh 2>/dev/null || true
log "Launching the installer…"
exec ./install-and-run.sh "${@:2}"
