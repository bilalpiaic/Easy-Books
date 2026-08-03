# AGENTS.md

Project overview, architecture, and standard commands live in [`README.md`](./README.md) and [`CLAUDE.md`](./CLAUDE.md). Frontend-specific rules live in [`frontend/AGENTS.md`](./frontend/AGENTS.md). Read those first.

## Cursor Cloud specific instructions

The dependency-refresh update script (`uv sync --project backend` + `npm install --prefix frontend`) runs automatically on VM startup. `uv` is preinstalled on the snapshot (at `/usr/local/bin/uv`); it is the backend package manager and is **not** reinstalled by the update script. The notes below are the non-obvious things to know when running the app.

### Services (dev)
- **Backend** — FastAPI on `:8000`. Run from `backend/`: `uv run python main.py` (Swagger at `/docs`, health at `/api/health`). Uses embedded SQLite (`backend/database.db`) by default — no external DB needed.
- **Frontend** — Next.js 16 (Turbopack) on `:3000`. Run from `frontend/`: `npm run dev`. Reaches the API via `NEXT_PUBLIC_API_URL` (defaults to `http://127.0.0.1:8000`, which already matches the local backend — no `.env.local` required).
- `./dev.sh` starts both together and seeds demo data, but it requires `backend/.venv` (created by `uv sync`) and a Linux `node` on PATH.

### Non-obvious gotchas
- **Schema must exist before the rich seeder runs.** `scripts.seed_demo` assumes the tables already exist and fails with `no such table: user` against a brand-new/empty `database.db`. The schema is created by the backend on startup (`SQLModel.metadata.create_all()`), which also auto-seeds the 7 demo tenants. So on a fresh DB: start the backend once first, *then* run `PYTHONPATH=. uv run python -m scripts.seed_demo` for rich mock data. (Note `dev.sh` seeds before booting, so on a truly empty DB its first-run seed step logs errors that are harmless — the server then creates the schema.) To reset: delete `backend/database.db` and restart the backend.
- **Login is form-encoded OAuth2**, not JSON: `POST /api/auth/login` with `username=<email>&password=<pw>` (`application/x-www-form-urlencoded`). All 7 demo tenants use password `demo1234` (emails in `README.md` / `CLAUDE.md`, e.g. `demo.simple@easy-books.app`).
- **Redis is optional** — background jobs run inline in-process when `REDIS_URL` is unset (the default here). No worker/Redis needed for E2E.
- **PDF export (WeasyPrint) needs system libs** (Pango/Cairo) that are not installed; "Save PDF" returns a clear 503. This does not affect core accounting flows.
- **Pre-existing lint/test noise (not env issues):** `npm run lint` currently reports pre-existing errors/warnings across the source tree, and `uv run pytest` has ~14 pre-existing failures (period-close checklist now returns 400 by design, seed idempotency, and a migration edge case) out of ~780 tests. These reflect app/test drift on `main`, not the environment setup.
