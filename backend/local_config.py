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
    # The data dir holds the database + signing key — owner-only on POSIX.
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
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
    # Create the key file atomically at mode 0600 — no world-readable window,
    # and O_EXCL means a concurrent first-run can't clobber it.
    try:
        fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, key.encode())
        finally:
            os.close(fd)
    except FileExistsError:
        # Lost the race to another process — use the key it persisted.
        return key_file.read_text().strip()
    return key
