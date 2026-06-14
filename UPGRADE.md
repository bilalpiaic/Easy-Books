# Easy-Books — Upgrade Guide

This guide explains how to upgrade Easy-Books to a newer version for each deployment target.
Your accounting data is never deleted during an upgrade; schema changes are applied forward via Alembic migrations.

---

## Before You Upgrade

1. **Know your current version** — visit `http://localhost:3000` → Settings → About, or call `GET /api/version`.
2. **Check the release notes** for the target version on the [Releases page](https://github.com/bilalpiaic/Easy-Books/releases).
3. **Read any breaking-change notices** in the release notes before proceeding.

---

## Script Installer (macOS / Linux — `install-and-run.sh`)

```bash
cd ~/easy-books          # wherever you cloned or extracted the repo
./update.sh
```

`update.sh` runs `git pull --ff-only` then re-invokes `install-and-run.sh --rebuild`.

`install-and-run.sh` will automatically:
- Install or update `uv` and Node.js if needed.
- Rebuild the frontend when the commit hash has changed.
- **Back up your SQLite database** (`~/.easy-books/*.db → ~/.easy-books/backups/`) before applying any pending migration.
- Run `alembic upgrade head` to apply pending schema migrations.
- Restart both servers.

> **Note:** Demo data is never re-seeded on update — only on a brand-new install (no existing users).

---

## Script Installer (Windows — `install-and-run.bat` / `install-and-run.ps1`)

Double-click **`update.bat`** in the Easy-Books folder, or run:

```powershell
powershell -ExecutionPolicy Bypass -File update.ps1
```

The Windows scripts follow the same steps as the macOS/Linux version above (backup → migrate → rebuild → restart).

---

## Desktop App (Electron)

1. Open the app — it checks for updates on launch via `electron-updater`.
2. When an update is available you will see a banner in the lower-right corner.
3. Click **Download** → wait for the progress bar → click **Restart & Install**.

Alternatively: **Settings → Check for Updates** → **Download** → **Restart & Install**.

The Electron updater applies the database migration automatically on the next launch (same `alembic upgrade head` path).

---

## Docker / Self-Hosted

```bash
# Pull the latest image
docker pull ghcr.io/bilalpiaic/easy-books:latest

# Stop and remove the old container (data volume is separate)
docker stop easy-books && docker rm easy-books

# Start with the same volume mount
docker run -d --name easy-books \
  -v easy-books-data:/data \
  -e EB_DATA_DIR=/data \
  -p 3000:3000 -p 8000:8000 \
  ghcr.io/bilalpiaic/easy-books:latest
```

The new container runs `alembic upgrade head` before starting the app.

---

## Manual / Development

```bash
git pull
cd backend && uv sync && uv run alembic upgrade head
cd ../frontend && npm install && npm run build
# Restart servers
```

---

## Rollback Procedure

If a migration fails or the app behaves unexpectedly after upgrading:

### SQLite (script / desktop installs)

Backups are written to `~/.easy-books/backups/` (Linux/macOS) or `%USERPROFILE%\.easy-books\backups\` (Windows) before each migration run. Filenames follow the pattern `database_YYYYMMDD_HHMMSS.bak`.

```bash
# Stop the app first, then restore
cp ~/.easy-books/backups/database_20260614_120000.bak ~/.easy-books/database.db
```

Then downgrade the code to the previous version (`git checkout <previous-tag>`) and re-run `install-and-run.sh`.

### PostgreSQL (production)

Restore from your latest DB snapshot/dump before downgrading the code:

```bash
pg_restore -d easy_books latest_backup.dump
```

Then roll back the Alembic migration:

```bash
cd backend && uv run alembic downgrade -1
```

---

## Verifying a Successful Upgrade

After upgrading, confirm:

1. `GET /api/version` returns the expected `version` and `alembic_head` values.
2. The app loads at `http://localhost:3000` without errors.
3. Your existing journals, invoices, and reports are still accessible.

---

## Adding Schema Changes (for contributors)

1. Edit `backend/models.py`.
2. Generate the migration: `cd backend && uv run alembic revision --autogenerate -m "describe_change"`.
3. Review the generated file in `backend/alembic/versions/`.
4. Apply it locally: `uv run alembic upgrade head`.
5. **SQLite caveat:** Remove any `ADD CONSTRAINT` / FK lines from the generated migration; use `op.batch_alter_table()` for all ALTER TABLE operations; add `bind.dialect.has_table()` guards for new tables (see migrations 0016/0017/0020 for patterns).

---

*For support, open an issue at https://github.com/bilalpiaic/Easy-Books/issues*
