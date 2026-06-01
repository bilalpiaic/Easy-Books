"""Packaged entrypoint: migrate the user's DB forward, then serve the API.

Used by the desktop build (PyInstaller). Unlike dev (which uses create_all),
packaged installs run Alembic so new COLUMNS on existing tables reach upgraded
users — create_all only ever adds new tables.
"""
import os
import sys
from pathlib import Path


def _bundle_dir() -> Path:
    # PyInstaller sets sys._MEIPASS to the unpacked bundle; else the source dir.
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def migrate() -> None:
    from alembic.config import Config
    from alembic import command
    from local_config import sqlite_path
    bundle = _bundle_dir()
    cfg = Config(str(bundle / "alembic.ini"))
    cfg.set_main_option("script_location", str(bundle / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{sqlite_path()}")
    command.upgrade(cfg, "head")


def main() -> None:
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("SEED_DEMO", "true")  # auto-load demo on first install; SEED_DEMO=false for a clean install
    os.environ.setdefault("SCHEMA_BOOTSTRAP", "alembic")  # lifespan skips create_all
    migrate()
    # First-run only: load the demo companies BEFORE serving. autoseed is guarded
    # (skips once any user exists) so updates never re-seed; running it before
    # uvicorn.run means the heavy writes happen with no concurrent request
    # traffic, avoiding SQLite lock contention.
    from scripts.autoseed_demo import main as autoseed_demo
    try:
        autoseed_demo()
    except Exception as exc:  # a demo-seed hiccup must never stop the app starting
        print(f"[autoseed] demo load failed (non-fatal): {exc}", flush=True)
    import uvicorn
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
