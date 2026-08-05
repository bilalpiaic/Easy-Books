#!/usr/bin/env bash
# One-shot Vercel deploy for Easy-Books cloud stack.
#
# Architecture:
#   Frontend  → Vercel (Next.js)     — ROOT: frontend/
#   Backend   → Vercel (FastAPI)     — ROOT: backend/
#   Database  → Neon Postgres        — DATABASE_URL on the backend project
#
# Neon hosts Postgres only (not the FastAPI process). The API runs on Vercel
# and talks to Neon via DATABASE_URL.
#
# Prerequisites:
#   npm i -g vercel
#   vercel login
#   A Neon project with a pooled connection string
#
# Usage:
#   ./scripts/deploy-cloud.sh              # interactive first-time link + deploy
#   ./scripts/deploy-cloud.sh --prod       # production deploy (both projects)
#   ./scripts/deploy-cloud.sh --backend    # backend only
#   ./scripts/deploy-cloud.sh --frontend   # frontend only
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROD=0
DO_BACKEND=1
DO_FRONTEND=1

for arg in "$@"; do
  case "$arg" in
    --prod) PROD=1 ;;
    --backend) DO_FRONTEND=0 ;;
    --frontend) DO_BACKEND=0 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown flag: $arg" >&2
      exit 1
      ;;
  esac
done

if ! command -v vercel >/dev/null 2>&1; then
  echo "Vercel CLI not found. Install with: npm i -g vercel" >&2
  exit 1
fi

deploy_dir() {
  local dir="$1"
  local name="$2"
  echo ""
  echo "═══ Deploying $name from $dir ═══"
  cd "$dir"
  if [[ "$PROD" -eq 1 ]]; then
    vercel --prod --yes
  else
    vercel --yes
  fi
}

if [[ "$DO_BACKEND" -eq 1 ]]; then
  deploy_dir "$ROOT/backend" "backend (FastAPI → Neon)"
  cat <<'EOF'

Next — set backend env vars (once) if you have not already:

  cd backend
  vercel env add DATABASE_URL production     # Neon pooled connection string
  vercel env add JWT_SECRET_KEY production   # openssl rand -hex 32
  vercel env add FRONTEND_ORIGIN production  # https://<frontend>.vercel.app
  vercel env add APP_ENV production
  # optional:
  vercel env add SEED_ADMIN_EMAIL production
  vercel env add SEED_ADMIN_PASSWORD production
  vercel env add SEED_COMPANY_NAME production

Then re-run:  ./scripts/deploy-cloud.sh --prod --backend

EOF
fi

if [[ "$DO_FRONTEND" -eq 1 ]]; then
  deploy_dir "$ROOT/frontend" "frontend (Next.js)"
  cat <<'EOF'

Next — set frontend env var (once) if you have not already:

  cd frontend
  vercel env add NEXT_PUBLIC_API_URL production   # https://<backend>.vercel.app

Then re-run:  ./scripts/deploy-cloud.sh --prod --frontend

EOF
fi

echo "Done. See DEPLOYMENT.md for Neon setup, CORS wiring, and smoke tests."
