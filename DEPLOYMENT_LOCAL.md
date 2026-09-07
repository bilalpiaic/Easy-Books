# Easy-Books — Local / Commercial Deployment Options

> Companion to [`DEPLOYMENT.md`](./DEPLOYMENT.md) (cloud/Vercel). This document covers shipping
> Easy-Books as a product an SME runs **on their own machine or office server** — data on-premise,
> works offline, no per-seat cloud subscription. (The **Manager.io / QuickBooks Desktop** model.)
>
> **Status:** Phase 1 (Docker Compose) complete · Phase 2 (Electron desktop) complete · v2.7 features included · **Last updated:** 2026-06-21

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

#### Zero-to-running in one line (clones the repo for you)
For a brand-new PC where the user hasn't even cloned the repo, `bootstrap` clones it (to
`~/Easy-Books` / `%USERPROFILE%\Easy-Books`, overridable) and then runs the installer:

- **macOS / Linux** (Terminal):
  ```bash
  curl -fsSL https://raw.githubusercontent.com/bilalpiaic/Easy-Books/main/bootstrap.sh | bash
  ```
  Custom location: `curl -fsSL …/bootstrap.sh | bash -s -- /path/to/folder` (or set `EB_INSTALL_DIR`).
- **Windows** — double-click **`bootstrap.bat`** (download just that one file), or in PowerShell:
  ```powershell
  irm https://raw.githubusercontent.com/bilalpiaic/Easy-Books/main/bootstrap.ps1 | iex
  ```

`bootstrap` uses **git clone** when git is present, and falls back to downloading the source ZIP when
it isn't — then hands off to the one-click installer below. Re-running updates the copy (`git pull`).

#### One-click install & run (recommended — auto-installs prerequisites)
The repo ships a bootstrap that **installs everything it needs and launches the app** — the user does
not need Python or Node pre-installed (one-time internet connection required to fetch them):

- **Windows:** double-click **`install-and-run.bat`**.
- **macOS / Linux:** run **`./install-and-run.sh`** (first time: `chmod +x install-and-run.sh`).

What it does automatically: installs **uv** (which also provisions Python 3.12), uses your system
**Node.js** or downloads a **local portable Node** into `./.node` (no system install, no admin),
installs backend deps, builds the frontend, then opens **http://127.0.0.1:3000**. Re-run any time;
pass `--rebuild` (sh) / `-Rebuild` (ps1) to force a fresh build. First run takes a few minutes
(downloads + build); later runs start in seconds.

Data lives in `EB_DATA_DIR` (default `~/.easy-books` / `%USERPROFILE%\.easy-books`). On first install the 5 demo companies are **auto-loaded** (takes ~20–30 s; guarded — fires only on a brand-new empty DB; updating an existing install is migrate-only and no demo data is added). Log in immediately with `demo1234`. Set `SEED_DEMO=false` before running for a clean install with no demo data. The first signup creates your own owner account.

> **Note:** the `.sh` is tested on Linux/macOS. The Windows `.bat`/`.ps1` mirror the same logic and
> use PowerShell-5.1-compatible constructs; validate on a real Windows box before distribution. The
> fully prerequisite-free **double-click `.exe`** (no internet fetch, bundled runtimes) is **Phase 2**
> (Tauri/Electron + PyInstaller).

#### Lower-level launcher (`run-local.sh`, assumes deps already installed)
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
- **`SEED_DEMO=false`** — skip auto-loading demo data; fresh install boots empty and the first signup becomes the owner. (The one-click installers default to `SEED_DEMO=true`; `run-local.sh` defaults to `false`.)
- Data is backed up/restored from **Settings → Backup & Restore** (zip of DB + uploads).

### Path C — Office Server: Docker Compose ✅ (complete)

A single `docker compose up -d --build` on any Linux / Windows / macOS server spins up three
containers behind an nginx entry point. Staff on the same network open a browser to the server's
IP — no client-side install needed.

```
Browser (any machine on LAN)
    │
    ▼  http://192.168.1.100  (or your domain)
nginx :80
    ├─ /api/*       → FastAPI backend  :8000  (internal only)
    ├─ /uploads/*   → FastAPI backend  :8000  (internal only)
    └─ /*           → Next.js frontend :3000  (internal only)
```

nginx is the only container that exposes a port. Because browser and API share one origin, CORS
never fires. Data persists in a Docker named volume (`eb_data`) — survives container rebuilds and
`git pull` updates. See **[Docker section below](#docker-compose--officeteam-server)** for the
step-by-step setup.

- **Pros:** single-command deploy and update; true multi-user over LAN; zero client prerequisites; keeps all multi-tenant / multi-user strengths; SQLite default, one env-var switch to PostgreSQL.
- **Cons:** requires Docker (+ Docker Compose plugin) on the server machine; not double-click friendly for end users.
- **Best for:** small-to-medium offices sharing one accounting instance (up to ~20 concurrent users on SQLite; add `DATABASE_URL` for PostgreSQL for larger teams).

### Path E — Books on OneDrive / Google Drive + local processes ✅

Consumer cloud storage cannot host FastAPI. **Path E** keeps SQLite (and optionally
the git checkout) on a synced folder while this PC runs the servers. Daily
launcher: `launch-cloud.bat` / `./launch-cloud.sh`. Frontend-only:
`launch-cloud --open` after `--backend` is in Login Items / Startup.

See **[`DEPLOYMENT_CLOUD.md`](./DEPLOYMENT_CLOUD.md)** (layouts, SQLite lock,
always-on alternatives).

### Path D — Bring-your-own-server install script
A guided `curl | bash` (or script) that provisions the same app on a customer VPS/NAS. Complements
the others rather than replacing them. **Effort:** Low.

---

## Cross-cutting concerns (any path)

- **Data location & backup:** SQLite file + uploads in the OS app-data dir
  (`%APPDATA%`, `~/Library/Application Support`, `~/.local/share`). Add in-app **Backup / Restore**
  (zip the `.db` + uploads); CSV export already exists.
- **First-run setup:** auto-generate & persist `JWT_SECRET_KEY`; run `alembic upgrade head`; run `scripts.autoseed_demo` (loads 5 demo companies on a brand-new empty DB when `SEED_DEMO=true`, the default for both script installers and the desktop app; guard skips if any user exists, so updating an existing install is migrate-only — no demo data added; set `SEED_DEMO=false` for a clean install); create your own owner via the signup wizard.
- **User preferences (theme, language, sidebar, home dashboard):** browser `localStorage` keys — `eb.theme` (light/dark/system), `eb.color` (color theme), `eb.lang` (language), `eb.sidebar.pinned`, `eb.sidebar.open`, `eb.home_dashboard` (`financial` \| `operations` \| `pra` — which home opens after login; also set under Settings → Advanced → Home dashboard), `eb.pra_portal_mode` (`1`/`0`). These survive application updates because they live in the browser, not in `~/.easy-books`. In Electron, the same Chromium `localStorage` persists across app restarts. **Widget layouts** (Financial + Operations grids) are **not** in localStorage — they are stored per user in the database via `UserDashboardLayout` / `GET|PUT /api/dashboard/layout` (schema v4 dual-slice). The `app_language` setting is additionally synced to `/api/settings` so the chosen language follows the user when they switch browsers.
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

| Phase | Outcome | Status |
|---|---|---|
| **Phase 0 — make it packageable** | `output: 'standalone'`; per-install secret + DB in app-data; demo-seeding toggle; in-app Backup/Restore; localhost launcher. | ✅ Complete |
| **Phase 1 — Server edition (Path C)** | Docker Compose (nginx + FastAPI + Next.js) — single-command office/team deploy; SQLite default, PostgreSQL via env var; auto-migration on startup. | ✅ Complete |
| **Phase 2 — Desktop edition (Path A)** | Electron shell + PyInstaller backend + bundled Node; Windows NSIS `.exe` + macOS `.dmg`; auto-update via GitHub Releases. | ✅ Complete |
| **Phase 3 — polish** | License-file check; trial→paid activation; opt-in telemetry; HTTPS/TLS config guide. | 🔲 Planned |
| **Path E — cloud-folder books** | Portable `EB_DATA_DIR` + `launch-cloud` + cloud-safe SQLite + instance lock. | ✅ Documented + shipped |

## Resolved decisions (Phase 2 complete)

| Decision | Resolution |
|----------|-----------|
| **Target user** | Non-technical single-business desktop (Path A) — Electron ships a `.exe`/`.dmg` installer with zero prerequisites |
| **OS priority** | Windows-first (NSIS `.exe`); macOS `.dmg` via the same `build-all.sh`; Linux `.AppImage` as a bonus |
| **Node-or-no-Node** | Kept path routes (`output: 'standalone'`) — Node is bundled in `desktop/resources/node`; no route refactor needed |
| **Licensing strictness** | Deferred — current build has no license gate; add offline signed-key check as a future phase |

## Remaining open items

- **Code signing** — Windows SmartScreen "Unknown publisher" warning until a code-signing cert is supplied via `CSC_LINK` / `CSC_KEY_PASSWORD`. Document the *More info → Run anyway* step for unsigned trial builds.
- **Invoice PDF export** — WeasyPrint needs the GTK runtime, which is not bundled in the desktop app. PDF download fails on a clean machine; the rest of the app is unaffected. (Docker install is unaffected — the backend container runs on Debian/slim where WeasyPrint works normally.)
- **macOS notarization** — requires `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID` on a macOS build host. Without it, Gatekeeper shows a quarantine warning on first open.
- **Payroll / IAS 19** — currently manual JV only; a dedicated payroll module is a future-scope item.
- **HTTPS / TLS for Docker** — the Docker setup serves plain HTTP on port 80. For internet-facing deploys, add a Certbot / Let's Encrypt sidecar or terminate TLS upstream (e.g. Cloudflare Tunnel, nginx on the host).

---

---

## Docker Compose — Office/Team Server

> **Prerequisites:** [Docker Desktop](https://docs.docker.com/get-docker/) (Windows/macOS) or
> Docker Engine + Compose plugin (Linux). No Python, Node, or git knowledge required on the server.

### 1. Get the code

```bash
git clone https://github.com/bilalpiaic/Easy-Books.git
cd Easy-Books
```

Or download and extract the ZIP if git is not installed.

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` — only **one line is required** for a team install:

```bash
# .env
APP_URL=http://192.168.1.100   # ← your server's LAN IP (or domain name)
JWT_SECRET_KEY=                # optional: auto-generated + persisted in the volume if blank
PORT=80                        # host port nginx listens on
SEED_DEMO=true                 # false for a clean install with no demo companies
DATABASE_URL=                  # optional: PostgreSQL URI; leave blank for SQLite
```

> Generate a stable JWT secret with: `openssl rand -hex 32`
> Without it, a secret is auto-generated and persisted in the data volume — tokens stay valid across restarts.

### 3. Start

```bash
docker compose up -d --build
```

First build takes **3–5 minutes** (downloads images, compiles Next.js). Watch progress:

```bash
docker compose logs -f
```

The backend logs `[startup] Starting API server...` when it's ready. Then open `http://<your-server-ip>` in any browser on the network.

### 4. Access from team machines

No install needed on client machines — just a modern browser. Point them to:

```
http://192.168.1.100      ← replace with your server's IP or hostname
```

Demo logins (if `SEED_DEMO=true`):

| Email | Model | Password |
|---|---|---|
| `demo.simple@easy-books.app` | Simple | `demo1234` |
| `demo.services@easy-books.app` | Services | `demo1234` |
| `demo.trader@easy-books.app` | Trader | `demo1234` |
| `demo.manufacturing@easy-books.app` | Manufacturing | `demo1234` |
| `demo.telecom@easy-books.app` | Telecom Franchise | `demo1234` |

### 5. Data location

All data (SQLite database + uploads) lives in the Docker named volume **`eb_data`**. It persists across container rebuilds, restarts, and `git pull` updates — never deleted unless you explicitly run `docker volume rm`.

To find where Docker stores it on the host:
```bash
docker volume inspect Easy-Books_eb_data
```

### 6. Backup

**Option A — in-app:** Settings → Backup & Restore → Download (zips the database + uploads).

**Option B — volume copy:**
```bash
# Stop app, copy volume to a .tar, restart
docker compose stop
docker run --rm -v Easy-Books_eb_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/eb-backup-$(date +%Y%m%d).tar.gz -C /data .
docker compose start
```

### 7. Update to a newer version

```bash
git pull
docker compose up -d --build
```

The backend entrypoint runs `alembic upgrade head` on every start — schema changes apply automatically. The `eb_data` volume is never touched during an update; your accounting data is safe.

### 8. Switch to PostgreSQL

For larger teams or higher concurrency, replace SQLite with a managed PostgreSQL instance:

1. Provision a PostgreSQL database (Neon, Supabase, Aiven, or a local Postgres container).
2. Add the connection string to `.env`:
   ```bash
   DATABASE_URL=postgresql://user:password@host:5432/easybooks
   ```
3. Restart: `docker compose up -d`

Alembic handles the schema setup on first connect. No other code changes are needed.

### 9. HTTPS / TLS (for internet access)

The default Docker setup serves plain HTTP on port 80. For external access or data-in-transit security:

**Option A — Cloudflare Tunnel** (simplest, free): create a tunnel from your Cloudflare dashboard pointing to `http://localhost:80`. No firewall ports to open.

**Option B — Certbot sidecar**: add a `certbot` service to docker-compose.yml and configure nginx to serve port 443. See the [nginx + certbot guide](https://mindsers.blog/post/https-using-nginx-certbot-docker/).

**Option C — Reverse proxy on the host**: run Caddy or nginx on the host machine as a TLS terminator in front of the Docker nginx container.

### Files reference

| File | Purpose |
|---|---|
| `docker-compose.yml` | Orchestrates backend, frontend, nginx |
| `.env.example` | All configurable variables with explanations |
| `nginx/nginx.conf` | Routes `/api/` and `/uploads/` to backend, `/*` to frontend |
| `backend/Dockerfile` | python:3.12-slim + uv; deps cached separately from code |
| `backend/docker-entrypoint.sh` | Runs migrations + demo seed before uvicorn starts |
| `frontend/Dockerfile` | 3-stage build; only the Next.js standalone bundle in the runtime image |

---

## Phase 2 — Bundled Desktop Installer (build & release)

Phase 2 packages Path A as a **double-click installer** (Windows `.exe`/NSIS, macOS `.dmg`)
that bundles every runtime — the end user installs like any app, with **no Python, Node, git,
internet-to-fetch-source, or terminal**. An **Electron** shell supervises two bundled sidecars:
the FastAPI backend as a **PyInstaller** one-dir binary and the **Next.js `standalone`** server
run by a **bundled Node**, both on `127.0.0.1`. On launch the shell sets `EB_DATA_DIR` to the
per-user OS app-data dir and runs **`alembic upgrade head`** so user data migrates safely across
versions (unlike dev's `create_all`, this delivers new *columns* to upgraded installs).

### What ships in the repo (OS-agnostic, Tasks 1–4 — done)
| File | Role |
|---|---|
| `backend/run_packaged.py` | Packaged entrypoint: `alembic upgrade head` → serve uvicorn on 127.0.0.1:8000 |
| `backend/easybooks-backend.spec` | PyInstaller one-dir spec (ships `alembic.ini` + `alembic/` + `templates/` as data) |
| `desktop/main.js` | Electron main: spawn + health-wait + supervise sidecars; sets `EB_DATA_DIR`; defaults `SEED_DEMO=true` so the guarded auto-seed runs on first install (set `SEED_DEMO=false` for a clean install); shows a "Starting up… first-time setup may take ~30 seconds" splash during the one-time seed |
| `desktop/preload.js` | Hardened preload (contextIsolation, no node in renderer) |
| `desktop/package.json` | Electron + electron-builder + electron-updater; `dist` → `electron-builder.yml` |
| `desktop/scripts/prepare-resources.sh` / `.ps1` | Build backend + Next standalone + fetch portable Node → stage `desktop/resources/{backend,frontend,node}` |

Verified on Linux: the PyInstaller bundle boots, runs the full migration chain from an empty DB,
and serves `GET /docs → 200`. Build artifacts (`backend/build`, `backend/dist`, `desktop/resources`,
`desktop/dist`, `desktop/node_modules`) are gitignored.

**v2.7 features included in the build** (no extra packaging steps required — they are pure frontend/UX changes):
- **Section Hub Pages** — `/receivable`, `/payable`, `/inventory`, `/banking` command-centre views
- **Collapsible sidebar** — 3-state (collapsed/open/pinned), hover tooltip nav, auto-pin on wide screens
- **3-mode voucher form** — Journal / Payment (CP/BP) / Receipt (CR/BR) with auto-prefixed JV numbers
- **Print system overhaul** — dot-matrix B&W, `dd-mm-yy` dates, correct portrait/landscape per page, `(amount)` negatives, `whitespace-nowrap` column alignment, no redundant voucher-type badges

### Building the installers (Tasks 5–9 — on the target OS)
electron-builder does **not** cross-compile signed installers, so each installer is built on its
own OS. Prerequisites per build host: Node + Python/`uv`; macOS also needs Xcode Command-Line Tools.

One command per OS — `build-all` finds Node itself (no `npm` on PATH needed), stops any running
instance, stages resources, then packages:

```powershell
# Windows build host → desktop\dist\Easy-Books Setup <ver>.exe  (+ win-unpacked\)
powershell -ExecutionPolicy Bypass -File desktop\build-all.ps1
```
```bash
# macOS / Linux build host → desktop/dist/Easy-Books-<ver>.dmg (mac) / .AppImage (linux)
./desktop/build-all.sh
```

Fast repackage after a `main.js` / `electron-builder.yml`-only change (reuses staged resources,
skips the backend/frontend rebuild): add `-SkipStaging` (PowerShell) or `--skip-staging` (bash).

`build-all` runs `prepare-resources.*` then `npm run dist`, which reads `desktop/electron-builder.yml`:
NSIS for Windows, dmg for macOS, `extraResources` copying `resources/{backend,frontend,node}`, and a
GitHub `publish` feed.

### Code signing & notarization (certs are external — never commit them)
Supply credentials via environment variables on the build host only:
- **Windows:** `CSC_LINK` (path or base64 of the `.pfx`) + `CSC_KEY_PASSWORD` → electron-builder signs the NSIS installer.
- **macOS:** `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID`, with `notarize: true`, plus a Developer ID Application cert in the keychain → electron-builder notarizes and staples during `dist`.

### Release & auto-update
Publish the installers to GitHub Releases; electron-builder uploads the `latest.yml` /
`latest-mac.yml` feeds that `electron-updater` (`autoUpdater.checkForUpdatesAndNotify()`) reads on
next launch. **Upgrade guarantee:** installing a newer version over an older one re-runs
`alembic upgrade head` on launch, preserving the user's `EB_DATA_DIR` data.

> **Maintainer note (prerequisites for a clean release):**
> - A published GitHub Release with the installer assets is required before `electron-updater` can serve updates.
> - A code-signing certificate is optional but recommended: without one, Windows SmartScreen will show an "Unknown publisher" warning on first install. Supply the cert via `CSC_LINK` / `CSC_KEY_PASSWORD` on the build host only — **never commit certs or credentials to the repo.**

### Publishing a release (one command — so the in-app update goes live)

The release **must** be built + published on the target OS (electron-builder can't cross-compile and the backend is a platform-specific PyInstaller binary). `build-all` has a `-Publish` (PowerShell) / `--publish` (bash) flag that runs `electron-builder --publish always` — it builds the installer **and** uploads it + `latest.yml` (the manifest `electron-updater` reads) to a GitHub Release.

1. **Bump the version** so it registers as an update for existing installs: set the same `version` in **`desktop/package.json`** (the electron-updater release version) **and** `frontend/package.json` (the in-app version badge / Update-modal "current"). They must match the release tag.
2. **On the target OS** (Windows for the `.exe`), set a token with `repo` scope and publish:
   ```powershell
   $env:GH_TOKEN = (gh auth token)          # or a PAT with repo scope
   powershell -ExecutionPolicy Bypass -File desktop\build-all.ps1 -Publish
   ```
   ```bash
   export GH_TOKEN=$(gh auth token)
   ./desktop/build-all.sh --publish
   ```
3. electron-builder creates a **draft** GitHub Release (its default) with `Easy-Books Setup <ver>.exe` + `latest.yml` + `.exe.blockmap`. **Review it on GitHub and click "Publish release"** — the moment it's published (repo is public), installed apps see the update: on launch (`checkForUpdatesAndNotify`) and via **Settings → Check for Updates**. (To skip the manual step, set `releaseType: release` in `electron-builder.yml`'s `publish` block — less safe for a first release.)

### Shipping to end users (runbook)

1. **Build** (Windows, full build — no `-SkipStaging`):
   `powershell -ExecutionPolicy Bypass -File desktop\build-all.ps1`
2. **Ship one file:** `desktop\dist\Easy-Books Setup <ver>.exe` — the NSIS installer (~250 MB). It
   bundles Python, Node, and the app, so the user needs **no** prerequisites. Do **not** distribute
   the `win-unpacked\` folder (that's for local testing). For auto-update, also publish `latest.yml`
   and the `…Setup….exe.blockmap` alongside it on the GitHub Release.
3. **The user** double-clicks the Setup → (unsigned build → Windows SmartScreen "unknown publisher"
   → *More info → Run anyway*) → installs → launches from the Start menu. First launch shows the
   ~30 s "Starting up…" splash (one-time seed), then it's ready. Their data lives in
   `%APPDATA%\Easy-Books` and survives updates/reinstalls.
4. **Updates:** if you publish GitHub Releases, installed apps auto-update on next launch; otherwise
   the user runs a newer `Setup.exe` over the old one. Either way data is preserved —
   `alembic upgrade head` runs on launch.

**Decide before shipping widely:**

- **Trial vs production build.** The default build auto-loads 5 demo companies on first run (great
  for trials/evaluation). For real users, set `SEED_DEMO=false` in `desktop/main.js` and rebuild so
  they start clean — demo data is still loadable any time from **Settings → Sample / Demo Data**.
- **Code signing** removes the SmartScreen "unknown publisher" warning (see the section above);
  without a cert, document the *More info → Run anyway* step for users.
- **Invoice PDF export** needs the GTK runtime, which isn't bundled — PDF download fails on a clean
  machine unless GTK is installed (the rest of the app is unaffected).

---

## Updating Easy-Books & Your Data

### Where your data lives

User data — the SQLite database, uploaded files, and the per-install secret key — is stored **outside** the app folder in a dedicated data directory:

| Platform | Default location |
|---|---|
| macOS / Linux | `~/.easy-books` (or `$EB_DATA_DIR`) |
| Windows | `%USERPROFILE%\.easy-books` (or `%EB_DATA_DIR%`) |
| Desktop (Electron) | OS `userData` dir set by Electron at launch |

Reinstalling or updating app files **never touches this directory**. Your accounts, invoices, settings, and uploaded documents are safe across updates.

### How updates migrate your database

Both install paths run `alembic upgrade head` on every launch:

- **Script installers** (`install-and-run.sh` / `install-and-run.bat` / `install-and-run.ps1`) — run Alembic before starting the servers. New columns and tables are added to your existing database; no data is wiped.
- **Desktop app** (`backend/run_packaged.py`) — runs Alembic before uvicorn starts, same guarantee.

This means pulling a newer version of Easy-Books and re-running the installer migrates your database **in place** — existing rows are preserved and new schema features are available immediately.

### Updating a Docker install

```bash
cd /path/to/Easy-Books
git pull
docker compose up -d --build
```

The backend entrypoint runs `alembic upgrade head` before uvicorn starts, so schema changes apply on every restart. The `eb_data` volume (SQLite + uploads) is never touched by `--build`.

### Updating a script install

```bash
# macOS / Linux
./update.sh

# Windows — choose one:
update.bat                  # double-click in Explorer
.\update.ps1               # PowerShell
```

`update.sh` / `update.bat` / `update.ps1` each: `git pull` the latest code, then call `install-and-run.*` (which runs Alembic, relaunches, and **auto-rebuilds the frontend whenever the code has changed** since the last build, tracked via `frontend/.next/.built-commit` vs `git rev-parse HEAD`). A plain re-run after any code change therefore always serves the latest UI. The `EB_DATA_DIR` data directory is never touched.

### Updating the desktop app

The desktop app uses `electron-updater` and **checks for a new release on every launch**. When an update is available you will be prompted to restart and apply it. The update re-runs `alembic upgrade head` on the next launch.

### Back up first

Before any major update, go to **Settings → Backup & Restore** and download a backup zip (database + uploads). This is the recommended safeguard in case you ever need to roll back.
