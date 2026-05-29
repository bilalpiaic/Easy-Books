"""Local/on-premise install configuration: data directory + persisted secret.

EB_DATA_DIR points at where the SQLite DB, uploads, and per-install secret
live. Defaults to the backend dir for dev; an installer sets it to the OS
app-data dir (e.g. %APPDATA%/Easy-Books). Routing the SQLite path, uploads,
and JWT secret through this one module lets the same codebase run as dev,
hosted SaaS, or a packaged desktop app with no code forks — only environment.
"""
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
