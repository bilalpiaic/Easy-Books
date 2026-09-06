# Easy-Books on consumer cloud storage (OneDrive, Google Drive, Dropbox)

> Companion to [`DEPLOYMENT_LOCAL.md`](./DEPLOYMENT_LOCAL.md). This is **Path E**:
> keep the books file on a synced drive while FastAPI and Next.js still run on
> a real computer. Cloud folders are **not** an always-on server.

---

## What cloud storage can and cannot do

| Expectation | Reality |
|---|---|
| Put `database.db` on OneDrive / Google Drive so another PC sees the books | **Yes**, with a single-writer lock and cloud-safe SQLite |
| Put the app folder on the same drive and double-click a launcher | **Yes** — `launch-cloud.bat` / `./launch-cloud.sh` |
| User only opens the frontend (browser) after the API is already up | **Yes** — `launch-cloud --open` |
| Backend “runs on OneDrive / GDrive” and stays up when every PC is off | **No.** Those products sync files. They do not execute Python. |
| Two PCs use the same SQLite file at the same time | **No.** That corrupts the database. The instance lock refuses the second writer. |

Always-on accounting needs a machine that stays powered: a desktop left on,
a NAS/mini-PC with Docker ([Path C](./DEPLOYMENT_LOCAL.md)), or hosted Postgres
([`DEPLOYMENT.md`](./DEPLOYMENT.md)). A Drive folder cannot replace that.

---

## Recommended layouts

### 1. Code on the PC, books on the cloud (safest)

Install once with `install-and-run` on the local disk (so `.venv`, `node_modules`,
and `.next` are **not** synced). Point data at the cloud folder:

```bash
# macOS / Linux
export EB_DATA_DIR="$HOME/Library/CloudStorage/OneDrive-Personal/Easy-Books-data"
./install-and-run.sh
# later:
EB_DATA_DIR="$HOME/Library/CloudStorage/OneDrive-Personal/Easy-Books-data" ./launch-cloud.sh
```

```powershell
# Windows
$env:EB_DATA_DIR = "$env:USERPROFILE\OneDrive\Easy-Books-data"
.\install-and-run.ps1
# later:
.\launch-cloud.ps1
```

Or copy `easy-books-portable.env.example` to `easy-books-portable.env` and set
`EB_DATA_DIR` there. Installers and launchers load that file automatically.

### 2. Whole checkout in the cloud folder (portable)

Clone or copy the repo into `OneDrive\Easy-Books` (or Google Drive). Then:

```text
easy-books-portable.env.example  →  easy-books-portable.env
touch .easy-books-portable          # optional marker; env file is enough
./install-and-run.sh                # first time only (build + deps)
./launch-cloud.sh                   # every day — starts API if needed, opens the UI
```

Windows: double-click `launch-cloud.bat`.

Default data directory in this mode is **`<repo>/data`** (also on the same
drive): `database.db`, `uploads/`, `.secret.key`. To put the books on a
*different* cloud account, set `EB_DATA_DIR` / `EB_CLOUD_DATA_DIR` in the env file.

Do **not** rely on syncing `node_modules`, `.venv`, or `frontend/.next` across
Windows and macOS. Those are OS-specific. Either:

- run `install-and-run` once per computer, or
- keep the git checkout on each PC and only sync `data/`.

Mark the data folder **Always keep on this device** (OneDrive) / available
offline (Drive). Files On-Demand placeholders will break SQLite.

### 3. Frontend-only click after a keep-alive backend

On the PC that should stay on:

```bash
./launch-cloud.sh --backend          # API only, logs in .run/
# Windows:  powershell -File launch-cloud.ps1 -Backend
```

Add that command to **Login Items** (macOS), **Startup** / Task Scheduler
(Windows), or a systemd user service (Linux). Then from the same machine
(or any browser on localhost) the daily habit is:

```bash
./launch-cloud.sh --open             # opens the UI if :8000 is already healthy
```

The backend is still a **local process**. If that PC sleeps or the lid closes,
the API stops. Cloud sync will upload the SQLite file after it is closed
cleanly (`./launch-cloud.sh --stop` before you switch machines).

---

## SQLite rules on a synced folder

Easy-Books enables **cloud-safe SQLite** when `EB_PORTABLE=1`,
`EB_CLOUD_SAFE_SQLITE=true`, or `EB_DATA_DIR` looks like OneDrive / Google Drive
/ Dropbox / iCloud:

- `PRAGMA journal_mode=DELETE` (no `-wal` / `-shm` sidecar war with the sync client)
- `PRAGMA synchronous=FULL`
- 30 second busy timeout
- `.instance.lock` in the data dir — second computer is refused until the lock
  is released or older than `EB_LOCK_STALE_SECONDS` (default 15 minutes)

**Never** open the same `database.db` in two Easy-Books processes. Wait for
OneDrive/Drive to finish syncing (no “syncing” overlay on the file) before
starting on the other PC.

For more than one concurrent user, use Docker + PostgreSQL on a machine that
stays on — not a consumer Drive folder.

---

## Daily commands

| Action | macOS / Linux | Windows |
|---|---|---|
| First install / update build | `./install-and-run.sh` | `install-and-run.bat` |
| Start API + UI, open browser | `./launch-cloud.sh` | `launch-cloud.bat` |
| Open UI only (API must be up) | `./launch-cloud.sh --open` | `launch-cloud.ps1 -Open` |
| Keep API running | `./launch-cloud.sh --backend` | `launch-cloud.ps1 -Backend` |
| Stop local servers | `./launch-cloud.sh --stop` | `launch-cloud.ps1 -Stop` |

Electron desktop: set `EB_DATA_DIR` in the environment before launching the
app; the shell no longer overwrites it with `%APPDATA%`. Prefer the script
launcher for Drive-based books so the instance lock and cloud-safe PRAGMAs
are the default.

---

## Always-on options (if you need the API while nobody is logged in)

1. **Office mini-PC / NAS** — Docker Compose from `DEPLOYMENT_LOCAL.md`, data
   on a local volume; optional nightly copy of the volume to Drive as backup.
2. **This PC as the server** — disable sleep, `launch-cloud --backend` at login,
   other devices use a browser only if you bind beyond localhost (not default;
   keep `127.0.0.1` unless you know the LAN threat model).
3. **Hosted** — Neon/Postgres + Vercel (`DEPLOYMENT.md`). That is real 24/7,
   not a Drive folder.

---

## Checklist

- [ ] OneDrive/Drive: data folder **always available offline**
- [ ] `easy-books-portable.env` exists (from the example) **or** `EB_DATA_DIR` is set
- [ ] `install-and-run` succeeded once on this OS
- [ ] Only one PC runs Easy-Books against that data folder at a time
- [ ] In-app **Settings → Backup & Restore** still used as a real backup (Drive
      sync is not a substitute for a zip you control)
