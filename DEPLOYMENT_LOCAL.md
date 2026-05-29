# Easy-Books — Local / Commercial Deployment Options

> Companion to [`DEPLOYMENT.md`](./DEPLOYMENT.md) (cloud/Vercel). This document covers shipping
> Easy-Books as a product an SME runs **on their own machine or office server** — data on-premise,
> works offline, no per-seat cloud subscription. (The **Manager.io / QuickBooks Desktop** model.)
>
> **Status:** strategy draft · **Last updated:** 2026-05-29

---

## Goal

Distribute Easy-Books to end users who run it locally:
- **Data sovereignty** — books never leave the user's machine.
- **Offline-capable** — no internet dependency for daily use.
- **One-time / tiered license** instead of (or alongside) cloud SaaS.

## What the current stack gives you (and the friction)

| Helps | Friction |
|---|---|
| **SQLite already supported** (`backend/database.db`) — ideal embedded, zero-config local DB | Two runtimes to ship: **Python** (FastAPI) **+ Node** (Next.js) |
| Clean frontend↔backend split (REST over `NEXT_PUBLIC_API_URL`); **no Next middleware, no Next route handlers** | 13 client-rendered `[id]` routes ⇒ **no clean static export**; use `output: 'standalone'` |
| Alembic migrations → safe forward-migration of the user's DB on upgrade | `JWT_SECRET_KEY` must be generated per-install (prod refuses the insecure default) |
| Multi-tenant model collapses cleanly to "one company per install" | Desktop packaging + OS code-signing/notarization is real effort |
| Existing CSV export + per-tenant branding | `next.config` `headers()` only applies under the Node server, not a static export |

---

## Packaging paths

### Path A — Desktop app: native shell + bundled servers ⭐ (recommended for end users)
A thin native shell opens `http://127.0.0.1:<port>` and supervises two bundled sidecars:
FastAPI (PyInstaller one-file) + Next.js (`output: 'standalone'` with a bundled Node).

| | Electron | Tauri |
|---|---|---|
| Shell size | ~100 MB (bundles Chromium) | ~10 MB (OS webview) |
| Maturity for "local server" apps | Very high | High, lighter, Rust glue |
| Python sidecar | well-trodden | sidecar API |

- **Pros:** real installable app, single icon, built-in auto-update, tray/launcher.
- **Cons:** bundling Python **and** Node in one installer is the heavy lift; sign both OSes.
- **Effort:** Medium–High. **Best for non-technical single-business desktop users.**

### Path B — Self-contained local server + browser (lightest engineering)
PyInstaller the FastAPI backend; run Next.js `standalone` alongside (or refactor the 13 `[id]`
routes to query-params and serve a **true static export** from FastAPI `StaticFiles`, dropping Node
entirely). A small launcher starts it and opens the default browser.

- **Pros:** fewest moving parts (especially the no-Node variant); tiny; trivial updates.
- **Cons:** "open your browser to localhost" is less polished; static-export route refactor is real work.
- **Effort:** Low–Medium. **Best for a v1/pilot or technically comfortable users.**

#### Running it today (`run-local.sh`)
Phase 0 ships a launcher that runs both servers bound to `127.0.0.1`:
```bash
# One-time build
cd backend  && uv sync
cd frontend && npm install && npx next build
# Next 'standalone' doesn't copy static assets — do it once after each build:
cp -r frontend/.next/static  frontend/.next/standalone/.next/static
cp -r frontend/public        frontend/.next/standalone/public

# Launch (data dir defaults to ~/.easy-books, demo seeding off)
./run-local.sh
# Override location/behaviour:  EB_DATA_DIR=/srv/easybooks SEED_DEMO=false ./run-local.sh
```
- **`EB_DATA_DIR`** — where the SQLite DB, uploads, and per-install secret (`.secret.key`) live.
- **`SEED_DEMO=false`** (default in the launcher) — fresh install boots empty; the first signup becomes the owner.
- Data is backed up/restored from **Settings → Backup & Restore** (zip of DB + uploads).

### Path C — On-prem Docker Compose ("Server edition")
Ship `docker-compose.yml` (FastAPI + Next standalone + Postgres) for a small office to run on one
machine; staff connect over the LAN. Close to ready — prod already targets Postgres.

- **Pros:** easiest to build; true multi-user over LAN; keeps multi-tenant strengths.
- **Cons:** requires Docker literacy; not double-click friendly.
- **Effort:** Low. **Best as a paid "Server/Pro" tier for multi-seat offices.**

### Path D — Bring-your-own-server install script
A guided `curl | bash` (or script) that provisions the same app on a customer VPS/NAS. Complements
the others rather than replacing them. **Effort:** Low.

---

## Cross-cutting concerns (any path)

- **Data location & backup:** SQLite file + uploads in the OS app-data dir
  (`%APPDATA%`, `~/Library/Application Support`, `~/.local/share`). Add in-app **Backup / Restore**
  (zip the `.db` + uploads); CSV export already exists.
- **First-run setup:** auto-generate & persist `JWT_SECRET_KEY`; run `alembic upgrade head`; boot with
  **no demo tenants**; create the first owner via the existing signup wizard.
- **Licensing (commercial lever):** offline **signed license file** — Ed25519 signature over
  `{customer, edition, seats, expiry}` verified against an embedded public key. Trial = time-limited
  license auto-issued on install. Editions map to the existing `enabled_modules`
  (Simple / Services / Trader / Manufacturing / Telecom). Optional online activation for stricter enforcement.
- **Updates:** Electron/Tauri auto-updater or signed installer downloads; **always run Alembic on launch**.
- **Security on localhost:** bind to `127.0.0.1`; keep JWT + bcrypt; CSRF may relax for same-origin
  localhost; if a static export is ever used, move `headers()` into FastAPI responses.
- **Whitelabel:** per-tenant company name/logo already exists; expose at install for resellers.

---

## Recommended roadmap

| Phase | Outcome |
|---|---|
| **Phase 0 — make it packageable** | `output: 'standalone'`; per-install secret + DB in app-data; demo-seeding toggle (fresh install boots empty); in-app Backup/Restore; localhost launcher. |
| **Phase 1 — Server edition (Path C)** | Docker Compose + Postgres + license-file check. Fastest to revenue for offices. |
| **Phase 2 — Desktop edition (Path A)** | Bundle FastAPI (PyInstaller) + Next standalone in Tauri/Electron; Windows `.msi` first, then notarized Mac `.dmg`. |
| **Phase 3 — polish** | Auto-update; trial→paid activation; opt-in telemetry. |

## Open decisions
1. **Target user** — non-technical single-business desktop (Path A) vs small office server (Path C)?
2. **OS priority** — Windows-first, or Mac/Linux too?
3. **Node-or-no-Node** — refactor `[id]` routes to query-params for a lighter static bundle, or keep
   path routes and ship Node (`standalone`)?
4. **Licensing strictness** — offline honor-system key vs enforced online activation?

> The architecture is already ~80% local-ready: the frontend never does server-side data fetching and
> SQLite is a first-class backend. The highest-leverage early decision is **Node-or-no-Node**.
