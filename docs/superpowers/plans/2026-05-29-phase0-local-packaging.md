# Phase 0 — Local Packaging Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make Easy-Books packageable as a local/on-premise product — a self-contained Next.js server, a per-install secret + relocatable data directory, a demo-seeding toggle (fresh installs boot empty), in-app SQLite Backup/Restore, and a localhost launcher.

**Architecture:** Keep the two-runtime model (FastAPI + Next.js). Next builds to `output: 'standalone'` (no route refactor). The backend resolves its data directory and JWT secret from `EB_DATA_DIR` (defaulting to the repo for dev, OS app-data for installs), generating + persisting a per-install secret so tokens survive restarts. Demo seeding becomes opt-out via `SEED_DEMO`. Backup/Restore zips the SQLite file + uploads. Decisions confirmed: **keep Node (`standalone`)**, **include Backup/Restore**.

**Tech Stack:** FastAPI · SQLModel · SQLite · Alembic · Next.js 16 (App Router) · pytest.

---

## FILE STRUCTURE

| File | Responsibility |
|------|---------------|
| `frontend/next.config.ts` | add `output: 'standalone'` |
| `backend/local_config.py` (new) | resolve `EB_DATA_DIR`, SQLite path, persisted secret path |
| `backend/auth.py` | secret resolution falls back to a persisted per-install key file (not the shared default) in non-prod |
| `backend/db.py` | SQLite path from `local_config`; demo seeding gated by `SEED_DEMO` |
| `backend/routers/settings.py` | `UPLOADS_DIR` sourced from `local_config` |
| `backend/routers/backup.py` (new) | `GET /api/backup/download`, `POST /api/backup/restore` (SQLite only, admin) |
| `backend/main.py` | register `backup` router |
| `frontend/src/app/(dashboard)/settings/page.tsx` | Backup & Restore card |
| `run-local.sh` (new) | build + launch both servers on `127.0.0.1`, open browser |
| `backend/tests/test_local_packaging.py` (new) | secret persistence, SEED_DEMO off, backup download/restore guards |

---

## Task 1: Next.js standalone build

**Files:** Modify `frontend/next.config.ts`

- [ ] **Step 1: Add `output: 'standalone'`**
```ts
const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: { root: __dirname },
  async headers() {
    return [
      { source: "/(.*)", headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ] },
    ];
  },
};
```
- [ ] **Step 2: Build and verify the standalone bundle exists**
Run: `cd frontend && npx next build`
Expected: build succeeds and `frontend/.next/standalone/server.js` exists (`ls frontend/.next/standalone/server.js`).
- [ ] **Step 3: Commit**
```bash
git add frontend/next.config.ts && git commit -m "build(local): Next.js output: standalone for local packaging"
```

---

## Task 2: Local data dir + persisted per-install secret

**Files:** Create `backend/local_config.py`; Modify `backend/auth.py`, `backend/db.py`, `backend/routers/settings.py`; Test `backend/tests/test_local_packaging.py`

- [ ] **Step 1: Write the failing test**
```python
# backend/tests/test_local_packaging.py
import importlib, os
from pathlib import Path

def test_secret_is_persisted_per_install(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "development")
    import auth
    importlib.reload(auth)
    key1 = auth.SECRET_KEY
    assert key1 and key1 != "super-secret-key-change-in-prod"
    assert (tmp_path / ".secret.key").exists()
    # Reload again → same persisted key (tokens survive restarts)
    importlib.reload(auth)
    assert auth.SECRET_KEY == key1
```
- [ ] **Step 2: Run — expect FAIL**
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_local_packaging.py::test_secret_is_persisted_per_install -v`
Expected: FAIL (no `.secret.key`; SECRET_KEY is the default).
- [ ] **Step 3: Create `backend/local_config.py`**
```python
"""Local/on-premise install configuration: data directory + persisted secret.

EB_DATA_DIR points at where the SQLite DB, uploads, and per-install secret
live. Defaults to the backend dir for dev; an installer sets it to the OS
app-data dir (e.g. %APPDATA%/Easy-Books)."""
import os
import secrets
from pathlib import Path

_BASE = Path(__file__).resolve().parent


def data_dir() -> Path:
    d = Path(os.environ.get("EB_DATA_DIR", str(_BASE)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def sqlite_path() -> str:
    return str(data_dir() / "database.db")


def uploads_dir() -> Path:
    d = data_dir() / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_secret() -> str:
    """JWT secret: env var wins; otherwise a per-install random key persisted
    in the data dir (so tokens stay valid across restarts)."""
    env = os.environ.get("JWT_SECRET_KEY")
    if env:
        return env
    key_file = data_dir() / ".secret.key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return key
```
- [ ] **Step 4: Wire `auth.py` to the persisted secret**
Replace the secret block in `backend/auth.py`:
```python
_DEFAULT_SECRET = "super-secret-key-change-in-prod"
_ENV = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "development").lower()

_env_secret = os.environ.get("JWT_SECRET_KEY", "")
if _env_secret:
    SECRET_KEY = _env_secret
elif _ENV in ("production", "prod"):
    raise SystemExit(
        "FATAL: JWT_SECRET_KEY is unset while APP_ENV=production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
else:
    # Local/dev: stable per-install key persisted in the data dir.
    from local_config import resolve_secret
    SECRET_KEY = resolve_secret()
```
- [ ] **Step 5: Point SQLite + uploads at the data dir**
In `backend/db.py`, in the `else` (SQLite) branch replace the path lines:
```python
    from local_config import sqlite_path
    sqlite_url = f"sqlite:///{sqlite_path()}"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
```
In `backend/routers/settings.py` replace `UPLOADS_DIR = Path(__file__).parent.parent / "uploads"` with:
```python
from local_config import uploads_dir
UPLOADS_DIR = uploads_dir()
```
- [ ] **Step 6: Run — expect PASS**
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_local_packaging.py::test_secret_is_persisted_per_install -v`
Expected: PASS.
- [ ] **Step 7: Commit**
```bash
git add backend/local_config.py backend/auth.py backend/db.py backend/routers/settings.py backend/tests/test_local_packaging.py
git commit -m "feat(local): EB_DATA_DIR data dir + persisted per-install JWT secret"
```

---

## Task 3: Demo-seeding toggle (fresh installs boot empty)

**Files:** Modify `backend/db.py`; Test `backend/tests/test_local_packaging.py`

- [ ] **Step 1: Append the failing test**
```python
def test_seed_demo_off_creates_no_demo_users(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path / "x"))
    monkeypatch.setenv("SEED_DEMO", "false")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib, db as dbmod
    importlib.reload(dbmod)
    dbmod.create_db_and_tables()
    from sqlmodel import Session, select
    from models import User
    with Session(dbmod.engine) as s:
        demos = s.exec(select(User).where(User.email.like("demo.%"))).all()
    assert demos == []
```
- [ ] **Step 2: Run — expect FAIL** (demo users seeded unconditionally)
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_local_packaging.py::test_seed_demo_off_creates_no_demo_users -v`
- [ ] **Step 3: Gate the demo loop in `backend/db.py`**
Wrap the demo block (the `demo_configs = [...]` list through its `for` loop) in a flag check:
```python
        # Demo tenants are for the hosted demo only — packaged/local installs
        # set SEED_DEMO=false and start empty (the first signup creates the owner).
        if os.environ.get("SEED_DEMO", "true").lower() == "true":
            demo_configs = [
                ("demo.simple@easy-books.app", "simple", "Demo - Simple", "Demo User"),
                ("demo.services@easy-books.app", "services", "Demo - Services", "Demo User"),
                ("demo.trader@easy-books.app", "trader", "Demo - Trader", "Demo User"),
                ("demo.manufacturing@easy-books.app", "manufacturing", "Demo - Manufacturing", "Demo User"),
                ("demo.telecom@easy-books.app", "telecom_franchise", "Demo - Telecom Franchise", "Demo User"),
            ]
            demo_password_hash = get_password_hash("demo1234")
            for email, model, company, full_name in demo_configs:
                # ... existing body unchanged ...
```
(Indent the existing `demo_configs`/`for` body one level under the `if`.)
- [ ] **Step 4: Run — expect PASS**
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_local_packaging.py::test_seed_demo_off_creates_no_demo_users -v`
- [ ] **Step 5: Commit**
```bash
git add backend/db.py backend/tests/test_local_packaging.py
git commit -m "feat(local): SEED_DEMO toggle — packaged installs boot without demo tenants"
```

---

## Task 4: Backup / Restore backend (SQLite only, admin)

**Files:** Create `backend/routers/backup.py`; Modify `backend/main.py`; Test `backend/tests/test_local_packaging.py`

- [ ] **Step 1: Append the failing test**
```python
def test_backup_download_returns_zip(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from tests.test_improvements import _mk_engine, _get_session_override, _signup_and_login
    from db import get_session
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    c = TestClient(app)
    auth = _signup_and_login(c, "owner@bk.test", "BkCo")  # first signup = owner
    r = c.get("/api/backup/download", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.content[:2] == b"PK"  # zip magic
    app.dependency_overrides.clear()
```
- [ ] **Step 2: Run — expect FAIL** (404, no endpoint)
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_local_packaging.py::test_backup_download_returns_zip -v`
- [ ] **Step 3: Create `backend/routers/backup.py`**
```python
"""Local backup/restore of the SQLite database + uploads (admin only).

Only available on SQLite installs (on-premise). On Postgres this 400s —
cloud backups are the platform's responsibility."""
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response

from db import engine
from local_config import sqlite_path, uploads_dir, data_dir
from routers.common import AdminUserDep, log_audit, SessionDep

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _require_sqlite():
    if engine.url.get_backend_name() != "sqlite":
        raise HTTPException(400, "Backup/restore is only available on local SQLite installs.")


@router.get("/download")
def download_backup(user: AdminUserDep):
    _require_sqlite()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        db_path = Path(sqlite_path())
        if db_path.exists():
            z.write(db_path, "database.db")
        up = uploads_dir()
        for f in up.rglob("*"):
            if f.is_file():
                z.write(f, str(Path("uploads") / f.relative_to(up)))
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="easybooks-backup.zip"'},
    )


@router.post("/restore")
def restore_backup(session: SessionDep, user: AdminUserDep, file: UploadFile = File(...)):
    _require_sqlite()
    raw = file.file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Uploaded file is not a valid backup zip.")
    names = zf.namelist()
    if "database.db" not in names:
        raise HTTPException(400, "Backup is missing database.db.")
    # Safety copy of the current DB before overwriting.
    db_path = Path(sqlite_path())
    if db_path.exists():
        db_path.replace(db_path.with_suffix(".db.bak"))
    (data_dir() / "database.db").write_bytes(zf.read("database.db"))
    for n in names:
        if n.startswith("uploads/") and not n.endswith("/"):
            target = data_dir() / n
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(n))
    log_audit(session, user, "RESTORE", "backup", None, {"file": file.filename})
    session.commit()
    return {"restored": True, "note": "Restart the app to load the restored database."}
```
- [ ] **Step 4: Register in `backend/main.py`** — add `backup` to the `from routers import (...)` block and append `backup.router` to the `_ROUTERS` list.
- [ ] **Step 5: Run — expect PASS**
Run: `cd backend && PYTHONPATH=. uv run pytest tests/test_local_packaging.py::test_backup_download_returns_zip -v`
- [ ] **Step 6: Commit**
```bash
git add backend/routers/backup.py backend/main.py backend/tests/test_local_packaging.py
git commit -m "feat(local): SQLite backup download + restore endpoints (admin)"
```

---

## Task 5: Backup & Restore Settings UI

**Files:** Modify `frontend/src/app/(dashboard)/settings/page.tsx`

- [ ] **Step 1: Add a Backup & Restore card** (place near the bottom of the settings form). Download uses an auth fetch → blob; restore posts multipart.
```tsx
{/* Backup & Restore (local installs) */}
<div className="bg-white border border-[#ede9e2] rounded-2xl p-6 space-y-3">
  <h2 className="text-lg font-serif text-[#1a1814]">Backup & Restore</h2>
  <p className="text-xs text-[#1a1814]/60">Download a full copy of your data (database + uploads), or restore from a backup. On-premise installs only.</p>
  <div className="flex flex-wrap gap-3">
    <button
      onClick={async () => {
        const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
        const res = await fetch(`${base}/api/backup/download`, { headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` } })
        if (!res.ok) { alert("Backup failed"); return }
        const blob = await res.blob()
        const url = URL.createObjectURL(blob); const a = document.createElement("a")
        a.href = url; a.download = "easybooks-backup.zip"; a.click(); URL.revokeObjectURL(url)
      }}
      className="px-4 py-2 bg-[#1a1814] text-white rounded-xl text-sm font-bold hover:bg-[#b8943f] hover:text-black">
      Download Backup
    </button>
    <label className="px-4 py-2 border border-[#ede9e2] rounded-xl text-sm font-bold cursor-pointer hover:bg-[#f6f3ee]">
      Restore from Backup…
      <input type="file" accept=".zip" className="hidden"
        onChange={async (e) => {
          const f = e.target.files?.[0]; if (!f) return
          if (!confirm("Restore will overwrite current data. Continue?")) return
          const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
          const fd = new FormData(); fd.append("file", f)
          const res = await fetch(`${base}/api/backup/restore`, { method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` }, body: fd })
          alert(res.ok ? "Restored. Restart the app to load the restored data." : "Restore failed")
        }} />
    </label>
  </div>
</div>
```
- [ ] **Step 2: Verify** — `cd frontend && npx tsc --noEmit` → 0 errors.
- [ ] **Step 3: Commit**
```bash
git add frontend/src/app/\(dashboard\)/settings/page.tsx
git commit -m "feat(local): Backup & Restore card in Settings"
```

---

## Task 6: Local launcher + docs

**Files:** Create `run-local.sh`; Modify `DEPLOYMENT_LOCAL.md`

- [ ] **Step 1: Create `run-local.sh`**
```bash
#!/usr/bin/env bash
# Launch Easy-Books locally (on-premise): both servers bound to 127.0.0.1.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export EB_DATA_DIR="${EB_DATA_DIR:-$HOME/.easy-books}"
export SEED_DEMO="${SEED_DEMO:-false}"
export APP_ENV="${APP_ENV:-local}"
mkdir -p "$EB_DATA_DIR"

# Backend (FastAPI) on 127.0.0.1:8000
( cd "$ROOT/backend" && PYTHONPATH=. uv run uvicorn main:app --host 127.0.0.1 --port 8000 ) &
BACK=$!
# Frontend (Next standalone) on 127.0.0.1:3000
( cd "$ROOT/frontend" && PORT=3000 HOSTNAME=127.0.0.1 node .next/standalone/server.js ) &
FRONT=$!

trap 'kill $BACK $FRONT 2>/dev/null' EXIT INT TERM
sleep 2
( command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:3000 ) || \
( command -v open >/dev/null && open http://127.0.0.1:3000 ) || \
echo "Open http://127.0.0.1:3000"
wait
```
Run: `chmod +x run-local.sh`
- [ ] **Step 2: Document** in `DEPLOYMENT_LOCAL.md` under Path B: prerequisites (build frontend once with `npx next build`; copy `.next/static` + `public` into `.next/standalone` per Next standalone docs), env vars (`EB_DATA_DIR`, `SEED_DEMO=false`), and the `./run-local.sh` command.
- [ ] **Step 3: Commit**
```bash
git add run-local.sh DEPLOYMENT_LOCAL.md && git commit -m "feat(local): run-local.sh launcher + docs"
```

---

## VERIFICATION
```bash
# Backend — new tests + full suite green
cd backend && PYTHONPATH=. uv run pytest tests/test_local_packaging.py -v
cd backend && PYTHONPATH=. uv run pytest -q
# Frontend
cd frontend && npx tsc --noEmit && npx next build && ls .next/standalone/server.js
# End-to-end local run (empty install)
EB_DATA_DIR=/tmp/eb-local SEED_DEMO=false ./run-local.sh   # → browser opens; sign up creates the owner
```
**Manual golden path:** fresh `EB_DATA_DIR` → no demo tenants → sign up as owner → create an invoice →
Settings → Download Backup (zip downloads) → Restore (re-upload) → restart → data intact. Confirm a
`.secret.key` and `database.db` exist in `EB_DATA_DIR` and that login still works after restart (stable secret).

## NOTES / RISKS
- **Restore needs a restart** to rebind the SQLite engine to the swapped file — the endpoint says so; a desktop shell (Phase 2) can automate the relaunch. A `.db.bak` safety copy is kept.
- Backup/Restore is **SQLite-only** (Postgres 400s) — correct for on-premise; cloud uses platform backups.
- `next build` for `standalone` still needs the one-time static-asset copy step (documented) — Next does not copy `.next/static`/`public` into `standalone/` automatically.
- Keep `SEED_DEMO=true` for the hosted demo; packaged builds set it false.
