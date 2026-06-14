"""Packaged entrypoint: migrate the user's DB forward, then serve the API.

Used by the desktop build (PyInstaller). Unlike dev (which uses create_all),
packaged installs run Alembic so new COLUMNS on existing tables reach upgraded
users — create_all only ever adds new tables.
"""
import os
import shutil
import sys
from pathlib import Path


def _bundle_dir() -> Path:
    # PyInstaller sets sys._MEIPASS to the unpacked bundle; else the source dir.
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _app_version() -> str:
    """Read the bundled app version from the VERSION file written by prepare-resources."""
    version_file = _bundle_dir() / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "dev"


def backup_db(db_path: Path, data_dir: Path, version: str) -> Path | None:
    """Copy database.db → database.db.bak-<version> when the app version has changed.

    Skips if the DB doesn't exist (first install) or the version is unchanged.
    Returns the backup path if a backup was created, None otherwise.
    """
    if not db_path.exists():
        return None
    last_version_file = data_dir / ".last-app-version"
    last_version = last_version_file.read_text().strip() if last_version_file.exists() else ""
    if version == last_version:
        return None
    backup_path = db_path.parent / f"database.db.bak-{version}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def write_last_version(data_dir: Path, version: str) -> None:
    try:
        (data_dir / ".last-app-version").write_text(version)
    except OSError:
        pass


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
    os.environ.setdefault("SEED_DEMO", "true")  # auto-load demo on first install; SEED_DEMO=false for clean
    os.environ.setdefault("SCHEMA_BOOTSTRAP", "alembic")  # lifespan skips create_all

    from local_config import data_dir as get_data_dir, sqlite_path
    _data_dir = get_data_dir()
    _db_path = Path(sqlite_path())
    _version = _app_version()

    backup_path = backup_db(_db_path, _data_dir, _version)
    if backup_path:
        print(f"[migrate] Backed up DB → {backup_path}", flush=True)

    try:
        migrate()
    except Exception as exc:
        loc = f"\nBackup: {backup_path}" if backup_path else ""
        print(f"[migrate] FATAL: Migration failed: {exc}{loc}", flush=True)
        sys.exit(1)

    write_last_version(_data_dir, _version)

    # First-run only: load the demo companies BEFORE serving. autoseed is guarded
    # (skips once any user exists) so updates never re-seed.
    from scripts.autoseed_demo import main as autoseed_demo
    try:
        autoseed_demo()
    except Exception as exc:
        print(f"[autoseed] demo load failed (non-fatal): {exc}", flush=True)

    import uvicorn
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
