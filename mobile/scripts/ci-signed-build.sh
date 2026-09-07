#!/usr/bin/env bash
# Capacitor signed-build scaffolding (#307).
# Always syncs the wrapper. Produces a release AAB only when Android keystore
# secrets AND a local Android SDK are present. Missing secrets is success —
# this is scaffolding, not a claim that Play/App Store signing is configured.
set -euo pipefail
cd "$(dirname "$0")/.."

npm ci
if [ ! -d android ]; then npx cap add android; fi
if [ ! -d ios ]; then npx cap add ios || echo "ios template skipped (non-mac is fine)"; fi
npx cap sync

if [ -z "${ANDROID_KEYSTORE_BASE64:-}" ]; then
  echo "ANDROID_KEYSTORE_BASE64 not set — Capacitor sync only. Not a signed Play upload."
  exit 0
fi

if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
  echo "Android SDK not installed on this runner — cannot bundleRelease. Sync succeeded."
  exit 0
fi

mkdir -p /tmp/eb-keystore
echo "$ANDROID_KEYSTORE_BASE64" | base64 -d > /tmp/eb-keystore/release.jks
export ANDROID_KEYSTORE_FILE=/tmp/eb-keystore/release.jks
cd android
./gradlew bundleRelease
echo "AAB written under android/app/build/outputs/bundle/release/"
