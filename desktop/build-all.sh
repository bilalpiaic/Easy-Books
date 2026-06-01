#!/usr/bin/env bash
# Build the Easy-Books desktop installer on macOS or Linux.
#
# Produces:  macOS → desktop/dist/Easy-Books-<version>.dmg
#            Linux → desktop/dist/Easy-Books-<version>.AppImage
#
# Prereqs: uv (+Python 3.12) and Node.js. The FIRST run also downloads a
# portable Node + Electron and can take several minutes.
#
# macOS signing/notarization needs APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD,
# APPLE_TEAM_ID + a Developer ID Application cert in the keychain; otherwise the
# build is unsigned (Gatekeeper will warn on first open).
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "[1/3] Staging resources (PyInstaller backend + Next.js build + portable Node)..."
./scripts/prepare-resources.sh
cd "$ROOT"

echo "[2/3] Installing desktop (Electron) dependencies..."
npm install

echo "[3/3] Building the installer (electron-builder)..."
npm run dist

echo "Done. Installer(s) in $ROOT/dist:"
ls -1 "$ROOT/dist" 2>/dev/null | grep -E '\.(dmg|AppImage|deb)$' || true
