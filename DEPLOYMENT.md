# Easy-Books — Cloud Deployment Guide

> **This document covers cloud / SaaS deployment (Vercel + Neon Postgres).**
> For on-premise and self-hosted options, see [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md):
> - **Script installer** — one-click, no Docker/Python/Node required
> - **Docker Compose** — team/office LAN server; `docker compose up -d --build`
> - **Desktop (Electron)** — signed Windows `.exe` / macOS `.dmg`

---

## Architecture

```
┌─────────────────────┐       ┌──────────────────────────┐
│  Frontend (Next.js) │──────▶│  Backend (FastAPI)       │
│  Vercel project     │ HTTP  │  Vercel Python function  │
│  Root: frontend/    │       │  Root: backend/          │
└─────────────────────┘       └────────────┬─────────────┘
                                           │ DATABASE_URL
                                           ▼
                                  ┌─────────────────┐
                                  │  Neon Postgres  │
                                  │  (pooled)       │
                                  └─────────────────┘
```

| Layer | Host | Notes |
|---|---|---|
| Frontend | **Vercel** | Next.js 16 app (`frontend/`) |
| Backend API | **Vercel** | FastAPI on `@vercel/python` (`backend/main.py`) |
| Database | **Neon** | Managed Postgres — Neon does **not** run the API process |

Neon is the database. The FastAPI backend still deploys to Vercel and connects to Neon with `DATABASE_URL`.

---

## 0. WHAT WAS PREPARED

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app + serverless-safe lifespan (background loops off on Vercel) |
| `backend/db.py` | Reads `DATABASE_URL`; Neon TLS + `pool_size=1` for serverless |
| `backend/requirements.txt` | pip deps for Vercel Python runtime (includes `psycopg2-binary`) |
| `backend/vercel.json` | Modern `functions` config (`maxDuration: 60`) |
| `backend/pyproject.toml` | `[tool.vercel] entrypoint = "main:app"` |
| `backend/api/index.py` | Legacy entry point (kept for older projects) |
| `backend/.env.vercel.example` | Backend env checklist for Vercel |
| `frontend/vercel.json` | Next.js framework config |
| `frontend/.env.vercel.example` | Frontend env checklist |
| `scripts/deploy-cloud.sh` | One-shot CLI deploy helper |
| `.github/workflows/deploy-vercel.yml` | CI deploy when `DEPLOY_VERCEL=true` |

---

## 1. PREREQUISITES

```bash
npm install -g vercel
vercel login
vercel whoami
```

---

## 2. PROVISION NEON POSTGRES (free tier)

1. Go to **https://neon.tech** → sign up / log in
2. Create project named `easy-books`
3. Region: pick one close to your Vercel region (e.g. `us-east-1`)
4. Copy the **pooled** connection string from the dashboard — looks like:
   ```
   postgresql://user:pass@ep-xxxxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Use the host that contains `-pooler` (serverless-safe). Save this as `DATABASE_URL`.

Alternative: **Vercel Postgres** (Storage tab) — same Neon under the hood; can auto-inject `DATABASE_URL`.

---

## 3. DEPLOY BACKEND

```bash
cd backend
vercel
```

Prompts:
- **Set up and deploy?** Y
- **Link to existing project?** N (first time)
- **Project name?** `easy-books-backend`
- **Directory?** `./`
- **Override settings?** N

Add env vars (see `backend/.env.vercel.example`):

```bash
vercel env add DATABASE_URL production
# Paste the Neon *pooled* connection string

vercel env add JWT_SECRET_KEY production
# Generate with: openssl rand -hex 32

vercel env add FRONTEND_ORIGIN production
# Placeholder OK for now; update after frontend deploy
# e.g. https://easy-books-frontend.vercel.app

vercel env add APP_ENV production

# Optional: seed an admin user on first empty DB
vercel env add SEED_ADMIN_EMAIL production
vercel env add SEED_ADMIN_PASSWORD production
vercel env add SEED_COMPANY_NAME production
```

Promote to production:

```bash
vercel --prod
```

**Verify:**
```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://<backend>.vercel.app/docs
# → 200
```

Or use the helper from the repo root:

```bash
./scripts/deploy-cloud.sh --prod --backend
```

---

## 4. DEPLOY FRONTEND

```bash
cd frontend
vercel
```

Project name: `easy-books-frontend`.

```bash
vercel env add NEXT_PUBLIC_API_URL production
# Value: https://<your-backend>.vercel.app   (from step 3)

vercel --prod
```

---

## 5. UPDATE BACKEND CORS

```bash
cd backend
vercel env rm FRONTEND_ORIGIN production
vercel env add FRONTEND_ORIGIN production
# Value: https://<your-frontend>.vercel.app
vercel --prod
```

`FRONTEND_ORIGIN` accepts a comma-separated list (no trailing slashes) if you have preview + custom domains.

---

## 6. POST-DEPLOY SMOKE TEST

```bash
BACKEND=https://easy-books-backend.vercel.app
FRONTEND=https://easy-books-frontend.vercel.app

# 1. Backend health / docs
curl -i "$BACKEND/docs"

# 2. Frontend serves
curl -I "$FRONTEND/"

# 3. CORS preflight
curl -X OPTIONS \
  -H "Origin: $FRONTEND" \
  -H "Access-Control-Request-Method: POST" \
  "$BACKEND/api/auth/login"

# 4. Login in the browser with SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD
```

---

## 7. CONTINUOUS DEPLOYMENT

### Option A — Vercel Git integration (simplest)

1. Each Vercel project → Settings → Git → connect `bilalpiaic/Easy-Books`
2. **Root Directory** = `backend/` or `frontend/`
3. **Production Branch** = `main`

### Option B — GitHub Actions

1. Create a Vercel token: https://vercel.com/account/tokens
2. After linking projects once via CLI, copy IDs from `.vercel/project.json`
3. Add repository **secrets**:
   - `VERCEL_TOKEN`
   - `VERCEL_ORG_ID`
   - `VERCEL_BACKEND_PROJECT_ID`
   - `VERCEL_FRONTEND_PROJECT_ID`
4. Add repository **variable**: `DEPLOY_VERCEL=true`
5. Push to `main` (or run **Deploy Vercel + Neon** via `workflow_dispatch`)

Env vars still live in the Vercel project dashboards — the workflow only builds/promotes.

---

## 8. ENVIRONMENT VARIABLE REFERENCE

### Backend (`easy-books-backend`)

| Variable | Required | Example |
|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql://…@…-pooler.…neon.tech/neondb?sslmode=require` |
| `JWT_SECRET_KEY` | ✅ | 64-hex from `openssl rand -hex 32` |
| `FRONTEND_ORIGIN` | ✅ | `https://easy-books-frontend.vercel.app` |
| `APP_ENV` | ✅ | `production` |
| `SEED_ADMIN_EMAIL` | optional | `admin@example.com` |
| `SEED_ADMIN_PASSWORD` | optional | Strong password |
| `SEED_COMPANY_NAME` | optional | `My Company` |

### Frontend (`easy-books-frontend`)

| Variable | Required | Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | `https://easy-books-backend.vercel.app` |

---

## 9. TROUBLESHOOTING

### Backend cold-start error: `psycopg2 not found`
`requirements.txt` must include `psycopg2-binary`. Redeploy with `vercel --prod`.

### Frontend can't reach backend (CORS error)
1. `FRONTEND_ORIGIN` must exactly match the frontend URL (no trailing slash)
2. `NEXT_PUBLIC_API_URL` must point at the backend (rebuild frontend after changing it — it is inlined at build time)
3. Logs: `vercel logs --follow` from the backend project dir

### `DATABASE_URL environment variable must be set`
Set the Neon pooled URL on the backend Vercel project and redeploy. On Vercel, SQLite is rejected even if `APP_ENV` is unset.

### Backend cold-start latency (3–5 s first request)
Normal for serverless Python. Subsequent requests on a warm instance are fast.
For always-on latency, host the API on Railway/Fly/Render and keep Neon as the DB.

### Database tables missing on first deploy
Default `SCHEMA_BOOTSTRAP=create_all` runs `SQLModel.metadata.create_all()` on cold start. If the first request times out, retry once. For stricter prod, set `SCHEMA_BOOTSTRAP=alembic` and run `alembic upgrade head` against Neon from CI before traffic.

### PDF generation fails on Vercel
WeasyPrint needs native Pango/Cairo libs that are not on the Vercel Python image. Invoice PDFs degrade gracefully; use Docker/self-host if PDF is critical.

### Background jobs (overdue reminders, webhooks)
Disabled automatically when `VERCEL=1`. Use an external cron (Vercel Cron → authenticated sweep route) or a long-running host + Redis worker (`worker.py` / ARQ) for those features.

---

## 10. SEEDING DEMO DATA (optional)

Demo tenants are created on first DB init when seed paths run. To load rich mock data:

**Option A (API):** log in as a demo user and create records through the public API.

**Option B (dev only):** locally, with `DATABASE_URL` pointed at a *non-production* Neon branch:
```bash
cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo
```
Do **not** run the rich seeder against a live customer database.

---

## 11. ROLLBACK

```bash
vercel ls easy-books-backend
vercel promote <deployment-url>
```

---

## 12. WHAT'S NOT INCLUDED (and why)

| Feature | Status | Why |
|---|---|---|
| Custom domain | Manual | Vercel Dashboard → Domains |
| Email send | Not setup | Needs SMTP / SendGrid |
| File uploads | Limited | Prefer Supabase/S3 (`STORAGE_BACKEND`) — `/uploads` is ephemeral on Vercel |
| Background jobs | Off by default | Serverless request/response only |
| Long-running tasks | Plan limits | Raise `maxDuration` (60s configured); Hobby tier caps apply |

---

## 13. TOTAL COST (free tier)

| Service | Free tier | Sufficient for |
|---|---|---|
| Vercel (frontend) | 100GB bandwidth/mo | A few thousand active users |
| Vercel (backend) | Function invocations | Same (watch cold starts) |
| Neon Postgres | 0.5 GB storage, compute hours | ~5–10 small businesses |

All-in: **$0/month** to get started.

---

## 14. ROUTER ORDERING NOTE

FastAPI matches routes in registration order. Named sub-routes under a resource (e.g. `/api/invoices/aging`) must be mounted **before** parameterized `/{id}` routers in `backend/main.py`.

---

**Last updated:** 2026-08-04
**Branch:** `main`
