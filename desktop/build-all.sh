#!/usr/bin/env bash
# Build the Easy-Books desktop installer on macOS or Linux.
#
# Usage:  ./desktop/build-all.sh                  (full build)
#         ./desktop/build-all.sh --skip-staging   (fast repackage; reuse resources)
#
# Finds Node itself (system -> portable ./.node -> download), so npm need not be
# on your PATH. macOS signing/notarization needs APPLE_ID/.../Developer ID cert.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
REPO_ROOT="$(cd .. && pwd)"
SKIP_STAGING=0
[ "${1:-}" = "--skip-staging" ] && SKIP_STAGING=1

# Ensure Node/npm on PATH (system -> portable ./.node -> download).
if ! command -v npm >/dev/null 2>&1; then
  NODE_DIR="$REPO_ROOT/.node"
  if [ ! -x "$NODE_DIR/bin/node" ]; then
    nv="20.18.1"
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"; [ "$os" = darwin ] && plat=darwin || plat=linux
    arch="$(uname -m)"; case "$arch" in x86_64|amd64) arch=x64;; aarch64|arm64) arch=arm64;; esac
    mkdir -p "$NODE_DIR"
    curl -fsSL "https://nodejs.org/dist/v$nv/node-v$nv-$plat-$arch.tar.gz" | tar -xz -C "$NODE_DIR" --strip-components=1
  fi
  export PATH="$NODE_DIR/bin:$PATH"
fi

# Stop a running instance so the build can overwrite its output.
for port in 8000 3000; do
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  [ -n "$pids" ] && kill $pids 2>/dev/null || true
done

if [ "$SKIP_STAGING" -eq 0 ]; then
  echo "[1/3] Staging resources (PyInstaller backend + Next.js build + portable Node)..."
  ./scripts/prepare-resources.sh
  cd "$ROOT"
else
  [ -f "$ROOT/resources/frontend/server.js" ] || { echo "ERROR: --skip-staging but resources are not staged; run without it once."; exit 1; }
  echo "[1/3] --skip-staging: reusing existing desktop/resources."
fi

echo "[2/3] Installing desktop (Electron) dependencies..."
npm install

echo "[3/3] Building the installer (electron-builder)..."
npm run dist

echo "Done. Output in $ROOT/dist:"
ls -1 "$ROOT/dist" 2>/dev/null | grep -E '\.(dmg|AppImage|deb)$' || true
