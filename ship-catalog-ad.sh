#!/usr/bin/env bash
# Easy-Books — rebuild and pack the catalog advertisement explorer.
#
# Double-click is not typical on Unix; run from the repo root:
#   ./ship-catalog-ad.sh
#   bash ship-catalog-ad.sh --refresh   # also regenerate catalog-index.json via vitest
#   bash ship-catalog-ad.sh --open      # open the HTML after packing
#   bash ship-catalog-ad.sh --print-paths
#
# Override the project folder with EB_ROOT if this script is copied elsewhere.
# Do NOT run with `sh ship-catalog-ad.sh` — this script needs bash.
set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
  echo "✖ ship-catalog-ad.sh requires bash. Run:  bash ship-catalog-ad.sh" >&2
  exit 1
fi

REFRESH=0
OPEN=0
SKIP_PACK=0
PRINT_PATHS=0
for arg in "$@"; do
  case "$arg" in
    --refresh) REFRESH=1 ;;
    --open) OPEN=1 ;;
    --skip-pack) SKIP_PACK=1 ;;
    --print-paths) PRINT_PATHS=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "✖ unknown flag: $arg  (try --help)" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${EB_ROOT:-$SCRIPT_DIR}"
ROOT="$(cd "$ROOT" && pwd)"

# ── Project + required file locations (all relative to ROOT) ─────────────────
MARKETING="$ROOT/docs/marketing"
FRONTEND="$ROOT/frontend"
PUBLIC="$FRONTEND/public"
SHOTS="$PUBLIC/catalog"

BUILD_PY="$MARKETING/build_catalog_ad.py"
PACK_PY="$MARKETING/pack_catalog_ad.py"
SHIP_DOC="$MARKETING/CATALOG_AD_SHIP.md"
INDEX_DOCS="$MARKETING/catalog-index.json"
INDEX_PUBLIC="$SHOTS/index.json"
HTML_DOCS="$MARKETING/catalog-advertisement.html"
HTML_PUBLIC="$PUBLIC/catalog-advertisement.html"
ZIP_OUT="$MARKETING/dist/easy-books-catalog-explorer.zip"
CREATIVE="$MARKETING/slides/12-cta.png"
VITEST_SPEC="$FRONTEND/src/lib/__tests__/workflowCatalog.test.ts"

HOSTED="${FRONTEND_ORIGIN:-http://127.0.0.1:3000}/catalog-advertisement.html"

die()  { printf "\n\033[1;31m✖ %s\033[0m\n" "$*" >&2; exit 1; }
log()  { printf "\n\033[1;33m▶ %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m✓ %s\033[0m\n" "$*"; }

print_paths() {
  cat <<EOF
Easy-Books catalog advertisement — locations
============================================
Project root (EB_ROOT)     $ROOT
Shipping spec              $SHIP_DOC
Build HTML                 $BUILD_PY
Pack zip                   $PACK_PY
Catalog JSON (preferred)   $INDEX_DOCS
Catalog JSON (fallback)    $INDEX_PUBLIC
Explorer HTML (docs)       $HTML_DOCS
Explorer HTML (public)     $HTML_PUBLIC
Snapshots (JPEGs)          $SHOTS
Ad creative (slide)        $CREATIVE
Offline zip (gitignored)   $ZIP_OUT
Hosted click-out URL       $HOSTED
Vitest (refresh index)     $VITEST_SPEC

Ads / email / chat: send the hosted URL, not the HTML file.
Booth / USB: unzip the zip and double-click catalog-advertisement.html.
EOF
}

print_paths

[ -d "$ROOT/frontend" ] && [ -d "$MARKETING" ] || die "Not an Easy-Books checkout. Expected frontend/ and docs/marketing/ under $ROOT (set EB_ROOT)."
[ -f "$BUILD_PY" ] || die "missing $BUILD_PY"
[ -f "$PACK_PY" ] || die "missing $PACK_PY"
[ -d "$SHOTS" ] || die "missing snapshot folder $SHOTS"
JPG_COUNT="$(find "$SHOTS" -maxdepth 1 -name '*.jpg' | wc -l | tr -d ' ')"
[ "$JPG_COUNT" -ge 50 ] || die "expected catalog JPEGs in $SHOTS, found $JPG_COUNT"

if [ "$PRINT_PATHS" -eq 1 ]; then
  ok "$JPG_COUNT snapshots on disk"
  exit 0
fi

find_python() {
  if command -v python3 >/dev/null 2>&1; then command -v python3; return; fi
  if command -v python >/dev/null 2>&1; then command -v python; return; fi
  die "python3 is required (stdlib only — json, pathlib, zipfile)."
}
PY="$(find_python)"

refresh_index() {
  command -v npm >/dev/null 2>&1 || die "npm is required for --refresh (catalog-index.json)."
  [ -d "$FRONTEND/node_modules" ] || die "frontend/node_modules missing — run npm install in frontend/ first."
  log "Refreshing catalog-index.json (vitest)…"
  ( cd "$FRONTEND" && npm test -- src/lib/__tests__/workflowCatalog.test.ts )
}

if [ "$REFRESH" -eq 1 ]; then
  refresh_index
fi

if [ ! -f "$INDEX_DOCS" ] && [ ! -f "$INDEX_PUBLIC" ]; then
  log "catalog-index.json missing — generating it…"
  refresh_index
fi

[ -f "$INDEX_DOCS" ] || [ -f "$INDEX_PUBLIC" ] || die "no catalog JSON at $INDEX_DOCS or $INDEX_PUBLIC"

log "Building explorer HTML…"
"$PY" "$BUILD_PY"
[ -f "$HTML_DOCS" ] && [ -f "$HTML_PUBLIC" ] || die "build did not write $HTML_DOCS and $HTML_PUBLIC"
ok "HTML → $HTML_DOCS"
ok "HTML → $HTML_PUBLIC  (served as /catalog-advertisement.html)"

if [ "$SKIP_PACK" -eq 0 ]; then
  log "Packing offline zip (USB / booth)…"
  "$PY" "$PACK_PY"
  [ -f "$ZIP_OUT" ] || die "packer did not write $ZIP_OUT"
  ok "zip  → $ZIP_OUT"
fi

echo ""
echo "Ship for ads:  $HOSTED"
echo "Do not attach the HTML. Spec: $SHIP_DOC"

if [ "$OPEN" -eq 1 ]; then
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$HTML_PUBLIC" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$HTML_PUBLIC"
  else
    echo "Open this file in a browser: $HTML_PUBLIC"
  fi
fi
