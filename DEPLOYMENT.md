# Easy-Books — Vercel Deployment Guide

> **Strategy:** Two separate Vercel projects + Neon Postgres
> Frontend → `easy-books-frontend.vercel.app` (Next.js)
> Backend → `easy-books-backend.vercel.app` (FastAPI on `@vercel/python`)
> Database → Neon Postgres (managed, serverless)

---

## 0. WHAT WAS PREPARED

| File | Purpose |
|---|---|
| `backend/db.py` | Now reads `DATABASE_URL` env var (Postgres on Vercel, SQLite fallback for dev) |
| `backend/requirements.txt` | pip dependencies for Vercel Python runtime (includes `psycopg2-binary`) |
| `backend/api/index.py` | Vercel entry point — imports FastAPI `app` from `main.py` |
| `backend/vercel.json` | Routes all requests to the Python serverless handler |
| `backend/.env.example` | Documents all required env vars |
| `backend/.vercelignore` | Keeps venv, .db files, tests out of the deploy bundle |
| `frontend/vercel.json` | Explicit Next.js framework config |
| `frontend/.env.example` | Documents `NEXT_PUBLIC_API_URL` |
| `.vercelignore` (root) | Excludes legacy root files (`server.js`, `db.js`, etc.) |

---

## 1. PREREQUISITES

```bash
# 1. Install Vercel CLI (one-time)
npm install -g vercel

# 2. Authenticate (opens browser)
vercel login

# 3. Verify
vercel whoami
```

---

## 2. PROVISION NEON POSTGRES (free tier)

1. Go to **https://neon.tech** → sign up / log in
2. Create project named `easy-books`
3. Region: pick one close to your Vercel region (e.g. `us-east-1`)
4. Copy the **pooled connection string** from the dashboard — looks like:
   ```
   postgresql://user:pass@ep-xxxxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Save this — it goes into `DATABASE_URL` on the backend.

Alternative: **Vercel Postgres** (Storage tab in Vercel dashboard) — same product, deeper integration. Auto-injects `DATABASE_URL`.

---

## 3. DEPLOY BACKEND

```bash
cd /home/mbilal71/projects/Easy-Books/backend
vercel
```

Answer prompts:
- **Set up and deploy?** Y
- **Scope?** Your account / team
- **Link to existing project?** N
- **Project name?** `easy-books-backend`
- **Directory?** `./` (we're already in /backend)
- **Override settings?** N

After the first `vercel` run (which deploys to preview), add env vars:

```bash
# These three are required
vercel env add DATABASE_URL production
# Paste the Neon connection string when prompted

vercel env add JWT_SECRET_KEY production
# Generate with: openssl rand -hex 32

vercel env add FRONTEND_ORIGIN production
# Use the frontend URL once you have it, e.g.
# https://easy-books-frontend.vercel.app

# Optional: seed an admin user on first run
vercel env add SEED_ADMIN_EMAIL production
vercel env add SEED_ADMIN_PASSWORD production
vercel env add SEED_COMPANY_NAME production
```

Then promote to production:

```bash
vercel --prod
```

Note the production URL printed (e.g. `https://easy-books-backend.vercel.app`).

**Verify:**
```bash
curl https://easy-books-backend.vercel.app/docs
# Should return Swagger UI HTML
```

---

## 4. DEPLOY FRONTEND

```bash
cd /home/mbilal71/projects/Easy-Books/frontend
vercel
```

Answer prompts the same way; project name `easy-books-frontend`.

Add the only required env var:

```bash
vercel env add NEXT_PUBLIC_API_URL production
# Value: https://easy-books-backend.vercel.app   (from previous step)
```

Deploy to production:

```bash
vercel --prod
```

Note the URL (e.g. `https://easy-books-frontend.vercel.app`).

---

## 5. UPDATE BACKEND CORS

Now that you know the frontend URL, update the backend env var:

```bash
cd /home/mbilal71/projects/Easy-Books/backend
vercel env rm FRONTEND_ORIGIN production
vercel env add FRONTEND_ORIGIN production
# Value: https://easy-books-frontend.vercel.app
vercel --prod
```

---

## 6. POST-DEPLOY SMOKE TEST

```bash
# 1. Backend health
curl -i https://easy-books-backend.vercel.app/docs
# → 200 OK, Swagger UI

# 2. Frontend serves
curl -I https://easy-books-frontend.vercel.app/
# → 307 redirect to /login (correct)

# 3. CORS check
curl -X OPTIONS \
  -H "Origin: https://easy-books-frontend.vercel.app" \
  -H "Access-Control-Request-Method: POST" \
  https://easy-books-backend.vercel.app/api/auth/login
# → 200 OK, Access-Control-Allow-Origin matches

# 4. Login flow
# Open https://easy-books-frontend.vercel.app/login
# Sign in with SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD
# Confirm dashboard loads, charts render
```

---

## 7. CONTINUOUS DEPLOYMENT (auto-deploy on git push)

After the first manual deploy, every push to GitHub triggers a deploy automatically:

- Push to `saas-transition-foundation` → preview deploy
- Push to `main` → production deploy

To wire it up:

1. In each Vercel project's dashboard → Settings → Git
2. Connect to `bilalpiaic/Easy-Books`
3. Set **Root Directory** = `backend/` (for backend project) or `frontend/` (for frontend project)
4. Set **Production Branch** = `main`

---

## 8. ENVIRONMENT VARIABLE REFERENCE

### Backend (`easy-books-backend`)

| Variable | Required | Example |
|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql://user:pass@host/db?sslmode=require` |
| `JWT_SECRET_KEY` | ✅ | 64-hex generated via `openssl rand -hex 32` |
| `FRONTEND_ORIGIN` | ✅ | `https://easy-books-frontend.vercel.app` |
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
Make sure `requirements.txt` includes `psycopg2-binary` (already done). Redeploy with `vercel --prod`.

### Frontend can't reach backend (CORS error)
1. Verify `FRONTEND_ORIGIN` exactly matches the frontend's deployed URL (no trailing slash)
2. Confirm `NEXT_PUBLIC_API_URL` on the frontend points to the right backend
3. Check backend logs: `vercel logs --follow` (from backend project dir)

### "JWT_SECRET_KEY is not set" warning in logs
Set the env var (Step 3) and redeploy. The warning is harmless during local dev.

### Backend cold-start latency (3-5 seconds first request)
Normal for serverless Python. Subsequent requests within the same instance are fast (≤200ms).
For lower latency, consider a long-running host like Railway or Fly.io for the backend instead.

### Database tables missing on first deploy
`SQLModel.metadata.create_all()` runs at startup alongside Alembic. If the first cold start times out before the schema is ready, hit any endpoint twice to trigger a warm-start retry. Subsequent boots are instant since `CREATE TABLE IF NOT EXISTS` is a no-op.

### Lockfile warning on Next.js build
Already mitigated — the root `package.json`/`package-lock.json` are legacy artifacts
of an earlier Express prototype. The `.vercelignore` at the root excludes them from
deploys. If they still cause warnings, delete them locally:
```bash
rm /home/mbilal71/projects/Easy-Books/{package.json,package-lock.json,db.js,server.js}
```

---

## 9.1 SEEDING DEMO DATA (optional)

Once production is live, demo tenants are auto-created on the first database init. To populate them with realistic mock data (customers, vendors, invoices, bills), you have two options:

**Option A: Seed via backend API (recommended for production)**
- Write a script that calls `POST /api/auth/login` with `demo.simple@easy-books.app` / `demo1234`
- Use the returned JWT to call `POST /api/invoices`, `POST /api/bills`, etc. via the public API
- This respects all business logic (GL postings, permissions, audit logging)

**Option B: Direct database seeding (dev/test only)**
- In your local backend, run: `cd backend && PYTHONPATH=. uv run python -m scripts.seed_demo`
- This populates all five demo tenants with 100 invoices, 100 bills, 70 payments, 25 customers, 25 vendors, 3 bank accounts, 4 payment terms, 6 recurring templates, and 60+ journal entries per tenant — spread across two fiscal years, with correct voucher types, deferred-revenue origination (services tenant), and multiple users. Every tenant (real or demo) is created with a hierarchical Chart of Accounts.
- **WARNING:** This approach bypasses the API and should only be used in dev/staging — it does not generate audit logs or trigger webhooks

---

## 11. ROLLBACK

```bash
# List recent deployments
vercel ls easy-books-backend

# Promote a previous deploy to production
vercel promote <deployment-url>
```

---

## 12. WHAT'S NOT INCLUDED (and why)

| Feature | Status | Why |
|---|---|---|
| Custom domain | Manual | Add via Vercel Dashboard → Domains |
| Email send | Not setup | Needs SMTP/SendGrid integration |
| File uploads | Limited | Vercel /tmp is ephemeral — use S3/R2 for production uploads |
| Background jobs | Not supported | Vercel is request/response only — use Inngest or Trigger.dev |
| Long-running tasks (>10s) | Use Edge | Default Vercel function timeout is 10s on hobby tier |

---

## 13. TOTAL COST (free tier)

| Service | Free tier | Sufficient for |
|---|---|---|
| Vercel (frontend) | 100GB bandwidth/mo | A few thousand active users |
| Vercel (backend) | 100k function invocations/mo | Same |
| Neon Postgres | 0.5 GB storage, 100 hrs compute/mo | ~5-10 small businesses |

All-in: **$0/month** to get started. Upgrade path is clean once you exceed limits.

---

---

## 14. ROUTER ORDERING NOTE

FastAPI matches routes in registration order. If you add new named sub-routes under a resource (e.g. `/api/invoices/aging`, `/api/invoices/bulk`), ensure those routers are mounted **before** the parameterized router (`/{invoice_id}`) in `backend/main.py`. In the current codebase this means `aging.router` is listed before `invoices.router` and `bills.router` in the `_ROUTERS` list.

---

**Last updated:** 2026-06-20
**Branch:** `main`
