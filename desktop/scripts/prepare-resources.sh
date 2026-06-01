#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RES="$ROOT/desktop/resources"; NODE_VERSION="20.18.1"
rm -rf "$RES"; mkdir -p "$RES"

# Ensure Node/npm is on PATH for the frontend build. Prefer system node; else
# reuse the portable ./.node that install-and-run.sh sets up; else fetch it.
if ! command -v npm >/dev/null 2>&1; then
  NODE_DIR="$ROOT/.node"
  if [ ! -x "$NODE_DIR/bin/node" ]; then
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"; [ "$os" = darwin ] && plat=darwin || plat=linux
    arch="$(uname -m)"; case "$arch" in x86_64|amd64) arch=x64;; aarch64|arm64) arch=arm64;; esac
    mkdir -p "$NODE_DIR"
    curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-$plat-$arch.tar.gz" | tar -xz -C "$NODE_DIR" --strip-components=1
  fi
  export PATH="$NODE_DIR/bin:$PATH"
fi
# Backend binary
( cd "$ROOT/backend" && uv run pyinstaller easybooks-backend.spec )
cp -r "$ROOT/backend/dist/easybooks-backend" "$RES/backend"
# Frontend standalone
( cd "$ROOT/frontend" && npm install && npx next build )
cp -r "$ROOT/frontend/.next/static"  "$ROOT/frontend/.next/standalone/.next/static"
cp -r "$ROOT/frontend/public"        "$ROOT/frontend/.next/standalone/public"
mkdir -p "$RES/frontend"; cp -r "$ROOT/frontend/.next/standalone/." "$RES/frontend/"
# Portable Node
os="$(uname -s|tr '[:upper:]' '[:lower:]')"; [ "$os" = darwin ] && plat=darwin || plat=linux
arch="$(uname -m)"; case "$arch" in x86_64|amd64) arch=x64;; arm64|aarch64) arch=arm64;; esac
curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-$plat-$arch.tar.gz" \
  | tar -xz -C "$RES" && mv "$RES/node-v$NODE_VERSION-$plat-$arch" "$RES/node"
echo "Staged → $RES"
