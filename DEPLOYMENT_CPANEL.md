# Easy-Books — Production requirements on cPanel / CloudLinux / Imunify360

> **Audience:** hosting, ops, and reviewers deciding whether this server can run Easy-Books in production.  
> **Companion docs:** [`DEPLOYMENT.md`](./DEPLOYMENT.md) (Vercel + Neon), [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md) (Docker / desktop / script install), [`docker-compose.prod.yml`](./docker-compose.prod.yml) + [`.env.prod.example`](./.env.prod.example) (production compose).  
> **Status:** requirements for review — not a first-class installer. Easy-Books is **not** a PHP/`public_html` application.  
> **Last updated:** 2026-10-12

---

## 0. Decision for reviewers

Easy-Books is a long-running **FastAPI (Python 3.11+) + Next.js 16 (Node 24)** stack. Production books of record require **PostgreSQL 16**. Optional **Redis 7** runs background jobs (PDF, email, webhooks, recurring journals). Server PDF download needs **Pango/Cairo**.

cPanel + SSL + CloudLinux + Imunify360 can sit **in front of** that stack as the TLS reverse proxy and malware/WAF layer. They cannot replace PostgreSQL, uvicorn, or the Next.js production server.

| Hosting model | Recommendation |
|---|---|
| **VPS / dedicated with WHM + root** | **Viable.** Treat cPanel as HTTPS terminator. Run the app with Docker Compose (`docker-compose.prod.yml`) or systemd. Raise CloudLinux LVE limits. Carve Imunify360 exceptions for `/api/`. |
| **Shared cPanel account (no root)** | **Not viable.** Cannot install PostgreSQL, Node 24, WeasyPrint libraries, Redis, or always-on uvicorn. Use [`DEPLOYMENT.md`](./DEPLOYMENT.md) (Vercel + Neon) and keep this box for mail/DNS only. |
| **Default cPanel PHP + MySQL + Passenger** | **Do not use.** MySQL/MariaDB is unsupported. Passenger WSGI is the wrong process model for FastAPI (ASGI). |

**Preferred layout on a WHM box:** Docker Compose production stack **or** systemd units, with Apache/LiteSpeed only doing SSL + reverse proxy to `127.0.0.1:8000` (API) and `127.0.0.1:3000` (UI).

---

## 1. What this project actually is

| Layer | Technology | Production note |
|---|---|---|
| Frontend | Next.js 16 / React 19 / TypeScript | `output: 'standalone'`; `engines.node` is **`>=24 <25`** |
| Backend | FastAPI / uvicorn / SQLModel / Alembic | ASGI; bind to localhost; not CGI/Passenger |
| Database | PostgreSQL via `DATABASE_URL` | SQLite is for local/dev only; production boot **refuses** a missing `DATABASE_URL` |
| Queue | Redis 7 + ARQ (`REDIS_URL`) | Unset = jobs run **inline** in the API process |
| PDF | WeasyPrint | Needs Pango/Cairo or **Download PDF** returns HTTP 503 |
| Auth | JWT HS256 + bcrypt; optional TOTP | `JWT_SECRET_KEY` required; production defaults `REQUIRE_OWNER_TOTP=true` |
| Money / GL | `NUMERIC(18,4)`, banker's rounding, `∑Dr = ∑Cr` | Accuracy is application-enforced; concurrency needs PostgreSQL |

Related files: `frontend/package.json`, `backend/pyproject.toml` (`requires-python = ">=3.11"`), `backend/Dockerfile`, `nginx/nginx.conf`, `.env.prod.example`.

---

## 2. Target architecture (speed + CORS)

Same public origin is simpler and faster (no CORS, one certificate — the one already on cPanel):

```
Internet (HTTPS — existing cPanel SSL)
        │
        ▼
cPanel Apache / LiteSpeed  (ports 80/443 only)
  /api/*  and /uploads/*  →  127.0.0.1:8000   FastAPI (uvicorn)
  /*                      →  127.0.0.1:3000   Next.js standalone
        │
        ├── PostgreSQL 16     books of record (required)
        ├── Redis 7           ARQ worker (strongly recommended)
        └── local disk or S3  logos, PDFs, attachments
```

This matches office Docker routing in `nginx/nginx.conf`:

- `client_max_body_size 20M`
- `/api/` `proxy_read_timeout 120s` (WeasyPrint, AI chat, period close)
- WebSocket upgrade on `/` for Next.js

If the UI and API use **different hostnames**, set `FRONTEND_ORIGIN` and `NEXT_PUBLIC_API_URL` to the exact origins (no trailing slash). `NEXT_PUBLIC_API_URL` is **inlined at frontend build time**; changing it later requires a rebuild.

Bind uvicorn and Next.js to **127.0.0.1**. Do not publish 8000, 3000, 5432, or 6379 on the public interface.

---

## 3. Hardware and CloudLinux LVE

| Size | vCPU | RAM | Disk | Approx. concurrent users |
|---|---|---|---|---|
| Minimum production | 2 | 4 GB | 40 GB SSD | 5–10 |
| Recommended | 4 | 8 GB | 80 GB SSD | 20–40 |
| Busy mill / hospital | 8 | 16 GB | 160 GB SSD + off-box backups | 40+ |

Resident memory (order of magnitude):

| Process | RAM |
|---|---|
| Next.js standalone | 250–400 MB |
| uvicorn (2 workers) | 300–600 MB |
| PostgreSQL 16 | 512 MB–2 GB |
| Redis 7 | 64–256 MB |
| ARQ worker | ~150 MB |
| WeasyPrint (brief spike) | +200–400 MB |

**WHM → CloudLinux → LVE Manager** for the account that runs the app (if not running as root/Docker):

| Limit | Floor | Why |
|---|---|---|
| PMEM | 4 GB (8 GB better) | Shared-host 1 GB defaults OOM-kill Node + Python + PDF |
| NPROC | 150 | Node, uvicorn workers, Postgres clients |
| EP (entry processes) | 50 | Reverse-proxy connections, not PHP |
| IOPS / IO | High | GL reports, period close, inventory |
| SPEED (CPU) | 200–400% of a core | Hierarchical trial balance / P&L / spinning GL |

CageFS: Docker/systemd as root is simpler. If the app runs as a cPanel user, allow Python 3.12, Node 24, the Postgres socket, and Redis inside CageFS.

**Clock:** enable chrony/NTP. JWT expiry, TOTP, period close, and Stripe webhooks depend on accurate time.

---

## 4. Software to install

Root/WHM packages. Prefer **Docker Engine + Compose** so the host only needs Docker plus the reverse proxy. Otherwise install the stack natively.

### 4.1 Required runtimes

| Package | Version | Purpose |
|---|---|---|
| Python | **3.11+** (Docker/`uv` use **3.12**) | FastAPI, GL posting, Alembic |
| uv | latest ([astral.sh/uv](https://docs.astral.sh/uv/)) | Install from `backend/uv.lock` (`uv sync --frozen`) |
| Node.js | **24.x only** (`>=24 <25`) | Next.js 16 production server. CloudLinux Node Selector 18/20/22 **will fail** `npm run build` |
| npm | ships with Node 24 | `npm ci` and production build |
| PostgreSQL | **16** | Production database. **MySQL/MariaDB is not a substitute** |
| Git | 2.x | Deploy and update |
| openssl | system | `openssl rand -hex 32` for `JWT_SECRET_KEY` |

### 4.2 Strongly recommended

| Package | Purpose |
|---|---|
| Redis 7 | ARQ: PDF, email, webhooks, dunning, recurring journals. Without `REDIS_URL`, `enqueue()` runs **in-process** and blocks API requests |
| Docker Engine + Compose plugin | Matches `docker-compose.prod.yml` (api, migrate, frontend, worker, postgres, redis, caddy) |
| systemd | Keep uvicorn / Next / worker alive across reboot (native install) |

### 4.3 Native libraries (server PDF)

WeasyPrint **Download PDF** (invoices, bills, portal docs) needs these, or the API returns **503**. Browser **Save PDF** does not use WeasyPrint.

Debian/Ubuntu/WSL2 (also in `backend/Dockerfile` and `install-and-run.sh`):

```text
libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0
libffi8 shared-mime-info fonts-dejavu-core
```

CloudLinux / RHEL equivalents:

```text
cairo pango gdk-pixbuf2 libffi shared-mime-info dejavu-sans-fonts
```

(`libffi7` on older EL if `libffi8` is absent.)

### 4.4 Reverse proxy (SSL already present)

Enable one of:

- Apache `mod_proxy`, `mod_proxy_http`, `mod_proxy_wstunnel`, HTTP/2
- LiteSpeed reverse proxy (common on cPanel)
- nginx using the repo’s `nginx/nginx.conf` as the template

Required proxy behaviour:

| Setting | Value | Purpose |
|---|---|---|
| `/api/` and `/uploads/` | `http://127.0.0.1:8000` | FastAPI |
| `/` | `http://127.0.0.1:3000` + WebSocket upgrade | Next.js |
| Body size | **20 MB** | Logos and attachments |
| `/api/` read timeout | **120 s** | PDF, AI SSE, period close |
| Compression | gzip/brotli on text, JSON, JS | Payload size |
| Forwarded headers | `X-Forwarded-Proto`, `X-Forwarded-For`, `Host` | Secure cookies and client IP |
| `TRUSTED_PROXIES` | proxy IPs (default `127.0.0.1`) | App must trust the proxy for those headers |
| Cache | `/_next/static` long-lived; **never cache `/api/*`** | Speed vs correctness |

### 4.5 Optional production services

| Component | Env / notes | Purpose |
|---|---|---|
| SMTP | `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL` | Password reset and overdue reminders. **Silent no-op** if `SMTP_HOST` is unset (cPanel Exim can relay) |
| Object storage | `STORAGE_BACKEND=s3`, `S3_BUCKET`, `S3_ENDPOINT`, keys | Uploads survive disk rebuilds; local disk is fine if the volume is backed up |
| Stripe | `STRIPE_SECRET_KEY`, price IDs, `STRIPE_WEBHOOK_SECRET` | Paid plans and payment links |
| AI | Per-tenant key in Settings → AI, or `ANTHROPIC_API_KEY` fallback | Financial assistant module |
| OAuth | Google / Microsoft client IDs | SSO |

### 4.6 Do not use for this app

- PHP, MySQL, MariaDB as the application database
- Passenger / CGI / lsphp for FastAPI
- Node 18 / 20 / 22 from older Node Selector
- SQLite (`backend/database.db`) for internet multi-user production
- `ENABLE_SELF_UPDATE=true` (git-pull updater is for desktop/script installs)
- `SEED_DEMO=true` or `ALLOW_DEMO_LOGIN=true` (`demo1234` is a public backdoor)

---

## 5. Process model (structural)

Run **four** long-lived units (Docker services or systemd), not Apache children:

| Role | How | Notes |
|---|---|---|
| 1. Migrate | `APP_ROLE=migrate` or `alembic upgrade head` | Once per deploy, **before** traffic. Production **refuses** `SCHEMA_BOOTSTRAP=create_all` |
| 2. API | `uvicorn main:app --host 127.0.0.1 --port 8000` | `APP_ROLE=api`, `RUN_MIGRATIONS=false`, `RUN_BACKGROUND_JOBS=false`. Start with **2 workers** on 4 GB RAM |
| 3. Frontend | `node …/.next/standalone/server.js` on `:3000` | After `npm run build`. Never `next dev` in production |
| 4. Worker | `arq worker.WorkerSettings` | Needs `REDIS_URL`. Owns PDF, mail, webhooks, recurring JVs, overdue sweep when API has jobs disabled |

Health (uptime monitor):

- `GET /api/health/live` — process up (no database)
- `GET /api/health/ready` — database reachable

Worker count × `DB_POOL_SIZE` must stay under PostgreSQL `max_connections`. Recycle connections (`DB_POOL_RECYCLE=1800`) so CloudLinux idle kills do not leave dead sockets.

---

## 6. Environment (complete)

Fail-closed defaults when `APP_ENV=production` are documented in `.env.prod.example` and `backend/.env.example`.

### 6.1 Must set

| Variable | Example / rule | Purpose |
|---|---|---|
| `APP_ENV` | `production` | Secure cookies; refuse default JWT; refuse `create_all` |
| `DATABASE_URL` | `postgresql://user:pass@127.0.0.1:5432/easybooks` | Required; boot fails if missing |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` | Unique per install; never commit; never the repo default |
| `FRONTEND_ORIGIN` | `https://books.example.com` | CORS allow-list; no trailing slash; comma-separated if several origins |
| `SCHEMA_BOOTSTRAP` | `alembic` | Production refuses `create_all` |
| `SEED_DEMO` | `false` | Do not create demo companies |
| `ALLOW_DEMO_LOGIN` | `false` | Block `demo.*@easy-books.app` |
| `REQUIRE_OWNER_TOTP` | `true` | Owners must enable 2FA before posting |
| `ENABLE_SELF_UPDATE` | `false` | Do not git-pull from the running API |

Frontend **build-time**:

```bash
# Same-origin proxy (recommended): leave empty so the browser calls /api/...
NEXT_PUBLIC_API_URL=

# Split hosts only:
# NEXT_PUBLIC_API_URL=https://api.example.com
```

### 6.2 Should set

| Variable | Purpose |
|---|---|
| `APP_ROLE=api` on API | No Alembic on the request path |
| `RUN_MIGRATIONS=false` on API | Dedicated migrate job |
| `RUN_BACKGROUND_JOBS=false` on API | Worker owns crons |
| `REDIS_URL=redis://127.0.0.1:6379/0` | Queue instead of inline jobs |
| `DB_POOL_SIZE=5` `DB_MAX_OVERFLOW=5` `DB_POOL_TIMEOUT=30` `DB_POOL_RECYCLE=1800` | Connection pool |
| `DB_SSLMODE` | `require` for remote Postgres; `disable` for local compose |
| `DATABASE_URL_DIRECT` | Direct (non-pooler) URL for Alembic when the app URL is pooled |
| `TRUSTED_PROXIES=127.0.0.1` | Honour `X-Forwarded-*` from the cPanel proxy |
| `DATA_ENCRYPTION_KEY` | Fernet for TOTP and Settings secrets (not the JWT secret). Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STORAGE_BACKEND=local` + persistent upload dir, or `s3` | Attachments |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` / `SEED_COMPANY_NAME` | First empty-DB owner only |
| `OPS_ADMIN_EMAILS` | Platform ops entitle API (comma-separated). Empty = nobody |
| `ENFORCE_MODULE_PLANS=true` | Gate industry module install by plan |

### 6.3 Feature env (as contracted)

| Variable | Purpose |
|---|---|
| `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASSWORD` `FROM_EMAIL` | Mail |
| `STRIPE_SECRET_KEY` `STRIPE_PRICE_STARTER` `STRIPE_PRICE_PRO` `STRIPE_PRICE_ENTERPRISE` `STRIPE_WEBHOOK_SECRET` | Billing; webhook `https://<host>/api/stripe/webhook` |
| `PLAID_CLIENT_ID` `PLAID_SECRET` `PLAID_ENV` | Bank feeds |
| `GOOGLE_CLIENT_ID` `GOOGLE_CLIENT_SECRET` `MICROSOFT_CLIENT_ID` `MICROSOFT_CLIENT_SECRET` `ALLOW_SSO_SIGNUP` | SSO |
| `ANTHROPIC_API_KEY` | Dev/demo Anthropic fallback; tenant Settings → AI keys win |
| `OVERDUE_SWEEP_ENABLED` `OVERDUE_SWEEP_INTERVAL_HOURS` | Overdue flag + reminder scheduler (default 24 h). Prefer worker when Redis is on |
| `S3_BUCKET` `S3_ENDPOINT` `S3_ACCESS_KEY` `S3_SECRET_KEY` | Object storage |

Keep secrets in a file mode `600` (or Docker `--env-file`), never in git.

---

## 7. Accounting accuracy (not a package)

Posting already enforces `sum(debit) == sum(credit)` and decimal money. Production accuracy is an **ops** property:

| Control | Why |
|---|---|
| PostgreSQL, not SQLite | Concurrent posting must not corrupt books |
| Single write path `services/posting.py` | Do not bypass with ad-hoc SQL |
| `alembic upgrade head` on every deploy | Schema and code stay aligned |
| Daily Postgres dump + PITR if possible | In-app tenant ZIP is **not** a substitute |
| Restore drill before live invoices | Backup that has never been restored is unproven |
| `REQUIRE_OWNER_TOTP=true` | Owner sessions cannot post without 2FA |
| Imunify360 must **not** rewrite JSON bodies | WAF mutation of journal lines is a silent integrity failure |

---

## 8. Imunify360, firewall, and network

Imunify360 / ModSecurity / CSF will otherwise break or slow the API.

| Setting | Action | Why |
|---|---|---|
| WAF on `/api/` | Whitelist or relax SQLi/XSS heuristics | Invoice/JV JSON looks like injection |
| SSE `/api/ai/chat` | Do not buffer or inspect `text/event-stream` | Buffering truncates the assistant stream |
| `Authorization: Bearer` | Allow | JWT; some rules strip unknown headers |
| Uploads | Allow 20 MB | Logos and attachments |
| Proactive defence | Do not kill `python` / `node` / `uvicorn` / `postgres` / `redis` | Look like unknown daemons |
| CSF inbound | **443** (and 80→443). Nothing else public | — |
| CSF localhost only | 5432, 6379, 8000, 3000 | Never expose DB, Redis, or app ports |
| Outbound HTTPS | Stripe, Plaid, SMTP submission, AI providers, GitHub | Feature-dependent |
| HTTP/2 + keepalive | On 443 | UI JS/CSS |
| CDN | Optional on `/_next/static` only | Never cache `/api/*` |

Put PostgreSQL on the **same machine** (or same DC). Remote DB adds milliseconds per query; reports issue many queries. If using managed Postgres (Neon/Aiven), pick the closest region. On this VPS use a **direct** local socket / `127.0.0.1`, not a serverless pooler.

---

## 9. Performance tuning

| Layer | Action |
|---|---|
| PostgreSQL | `shared_buffers` ~25% RAM; `work_mem` 16–32 MB; SSD; autovacuum on. Schema indexes ship in Alembic |
| uvicorn | `--workers 2` (4 on 8 GB). More workers × pool size must fit `max_connections` |
| Next.js | Production `next build` + standalone; proxy-cache `/_next/static` for 1 year |
| Redis | Local; keeps PDF/email off the request thread |
| Proxy | gzip JSON; 120 s API timeout; WebSockets for Next |
| App | `APP_ROLE=api` so request processes do not run Alembic or crons |
| Reports | Hierarchical TB / BS / P&L are CPU + SQL heavy — size LVE CPU and Postgres RAM for month-end |
| AI assistant | Optional; **four** LLM calls per user turn. Keep off a tiny LVE during period close |

---

## 10. Disk layout and backup

| Path | Contents |
|---|---|
| PostgreSQL data directory | Books of record |
| `UPLOAD_ROOT` / `EB_DATA_DIR` or S3 | Logos, avatars, generated PDFs |
| `.env.prod` (mode 600) | JWT, Fernet, SMTP, Stripe |

Backup:

1. PostgreSQL daily dump; WAL/PITR if the volume justifies it.
2. In-app **Settings → Backup & Restore** (tenant ZIP of DB + uploads) as a **second** copy, not the only copy.
3. One documented restore drill before go-live.
4. Exclude Postgres data, `node_modules`, and `.next` from Imunify360 malware scans to avoid IO storms.

---

## 11. Suggested install sequence (WHM + root)

1. Confirm **WHM root**, not a shared account. Raise LVE if the app will run as a cPanel user.
2. Install **Docker + Compose**, *or* PostgreSQL 16 + Redis 7 + Python 3.12 + Node 24 + WeasyPrint libraries.
3. Point the DNS A record at the server; keep the existing cPanel SSL vhost.
4. Reverse-proxy `/api` + `/uploads` → `:8000` and `/` → `:3000` (see §4.4).
5. Copy `.env.prod.example` → `.env.prod`. Fill secrets. `SEED_DEMO=false`, `ALLOW_DEMO_LOGIN=false`, `REQUIRE_OWNER_TOTP=true`.
6. Run `alembic upgrade head`, then start API + frontend + worker.
7. Add Imunify360 exceptions (§8). Confirm CSF does not expose 5432/6379/8000/3000.
8. Smoke test:
   - `GET /api/health/live` and `/api/health/ready`
   - HTTPS login
   - Post one balanced invoice
   - Download PDF (WeasyPrint) and Save PDF (browser)
   - Backup download + restore on a staging copy
9. Leave `REQUIRE_OWNER_TOTP=true`. Create the real owner; do not ship demo tenants.

Lowest-risk path on this OS: **`docker compose -f docker-compose.prod.yml --env-file .env.prod up -d`** with Caddy **or** with cPanel still terminating TLS and proxying to the published container ports.

---

## 12. Review checklist

Use this as the sign-off list for onward review.

### Host

- [ ] WHM/root (not shared hosting)
- [ ] 4 GB RAM minimum (8 GB recommended), SSD, NTP/chrony
- [ ] CloudLinux LVE PMEM / NPROC / EP / SPEED raised
- [ ] Node **24**, Python **3.11+**, PostgreSQL **16**
- [ ] WeasyPrint native libraries installed (or Docker image)
- [ ] Redis 7 if background jobs must not block the API

### Network / TLS

- [ ] Existing SSL vhost proxies `/api` and `/uploads` to uvicorn, `/` to Next.js
- [ ] Body size 20 MB; API read timeout 120 s; WebSocket upgrade on UI
- [ ] 5432 / 6379 / 8000 / 3000 bound to localhost only
- [ ] Imunify360 WAF exceptions for `/api/` and SSE `/api/ai/chat`
- [ ] `TRUSTED_PROXIES` matches the reverse proxy

### Application

- [ ] `APP_ENV=production`, `SCHEMA_BOOTSTRAP=alembic`
- [ ] Unique `JWT_SECRET_KEY` and `DATA_ENCRYPTION_KEY`
- [ ] `SEED_DEMO=false`, `ALLOW_DEMO_LOGIN=false`, `REQUIRE_OWNER_TOTP=true`
- [ ] `ENABLE_SELF_UPDATE=false`
- [ ] Frontend built with the correct `NEXT_PUBLIC_API_URL` (or empty for same-origin)
- [ ] Migrate job runs before API replicas
- [ ] Health checks in an uptime monitor

### Data

- [ ] PostgreSQL backups scheduled; restore tested once
- [ ] Uploads on persistent disk or S3
- [ ] SMTP configured if password reset / overdue mail is required

### Accuracy / security

- [ ] No demo logins on the production database
- [ ] WAF does not mutate JSON bodies
- [ ] Owner TOTP enrolled before live posting
- [ ] Two-tenant isolation checked if this instance will be multi-tenant SaaS

---

## 13. If this box is shared cPanel only

Stop. Use the documented SaaS path:

1. Frontend + API on Vercel — [`DEPLOYMENT.md`](./DEPLOYMENT.md)
2. Database on Neon (pooled `DATABASE_URL`, `sslmode=require`)
3. This cPanel server: DNS and mail only

Serverless caveats from that guide still apply: WeasyPrint may be unavailable on the Vercel Python image; background jobs are off unless Redis/worker or an external cron is added; uploads should use S3.

---

## 14. Document map

| File | Role |
|---|---|
| This file | cPanel / CloudLinux / Imunify360 production **requirements** |
| [`DEPLOYMENT.md`](./DEPLOYMENT.md) | Vercel + Neon cloud deploy |
| [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md) | Script installer, Electron, office Docker |
| [`DEPLOYMENT_CLOUD.md`](./DEPLOYMENT_CLOUD.md) | Books on OneDrive/Drive (not an always-on server) |
| [`docker-compose.prod.yml`](./docker-compose.prod.yml) | Production compose (API, migrate, UI, worker, Postgres, Redis, Caddy) |
| [`.env.prod.example`](./.env.prod.example) | Production env template |
| [`nginx/nginx.conf`](./nginx/nginx.conf) | Reverse-proxy template (20 MB, 120 s, `/api` vs `/`) |
| [`backend/Dockerfile`](./backend/Dockerfile) | Python 3.12 + WeasyPrint libs |
| [`docs/superpowers/plans/2026-09-06-production-launch.md`](./docs/superpowers/plans/2026-09-06-production-launch.md) | Product go-live flags (TOTP, Stripe, PITR) |
