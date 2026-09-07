"""Local/on-premise install configuration: data directory + persisted secret.

EB_DATA_DIR points at where the SQLite DB, uploads, and per-install secret
live. Defaults to the backend dir for dev; an installer sets it to the OS
app-data dir (e.g. %APPDATA%/Easy-Books). Routing the SQLite path, uploads,
and JWT secret through this one module lets the same codebase run as dev,
hosted SaaS, or a packaged desktop app with no code forks — only environment.

Portable / cloud-folder installs (OneDrive, Google Drive, Dropbox):
  EB_PORTABLE=1 or a `.easy-books-portable` marker next to the repo root
  switches the default data dir to `<repo>/data` so the books travel with
  the folder. SQLite is then opened in cloud-safe mode (DELETE journal,
  busy timeout) and an instance lock refuses a second machine while this
  copy is running — consumer cloud drives are file sync, not a database
  server, and two writers will corrupt the file.
"""
from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_REPO_ROOT = _BASE.parent

_CLOUD_PATH_MARKERS = (
    "onedrive",
    "google drive",
    "googledrive",
    "google-drive",
    "dropbox",
    "icloud",
    "icloud drive",
    "mega",
    "pcloud",
    "box.com",
    "box sync",
)


def _on_vercel() -> bool:
    return os.environ.get("VERCEL", "").lower() in ("1", "true")


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _falsy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("0", "false", "no", "off")


def repo_root() -> Path:
    """Install / git checkout root (parent of `backend/`)."""
    return _REPO_ROOT


def is_portable() -> bool:
    if _falsy("EB_PORTABLE"):
        return False
    if _truthy("EB_PORTABLE"):
        return True
    return (repo_root() / ".easy-books-portable").is_file()


def path_looks_cloud_synced(path: Path | str) -> bool:
    text = str(path).replace("\\", "/").lower()
    return any(marker in text for marker in _CLOUD_PATH_MARKERS)


def _default_data_dir() -> str:
    if _on_vercel():
        return "/tmp/easy-books"
    if is_portable():
        override = os.environ.get("EB_CLOUD_DATA_DIR", "").strip()
        if override:
            return override
        return str(repo_root() / "data")
    return str(_BASE)


def data_dir() -> Path:
    # Vercel's function filesystem is read-only except /tmp. Prefer an
    # explicit EB_DATA_DIR; otherwise stay under the package for local/
    # desktop installs, and under /tmp on Vercel so import-time mkdirs work.
    # Portable / cloud-folder mode defaults to <repo>/data so the SQLite
    # file lives next to the checkout on the synced drive.
    default = _default_data_dir()
    d = Path(os.environ.get("EB_DATA_DIR", default))
    try:
        d.mkdir(parents=True, exist_ok=True)
        # The data dir holds the database + signing key — owner-only on POSIX.
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass
    except OSError:
        # Last resort: never fail module import on a read-only FS.
        if _on_vercel():
            d = Path("/tmp/easy-books")
            d.mkdir(parents=True, exist_ok=True)
        else:
            raise
    return d


def sqlite_path() -> str:
    return str(data_dir() / "database.db")


def cloud_safe_sqlite() -> bool:
    """True when the SQLite file sits on (or is treated as) consumer cloud sync.

    WAL + two machines + OneDrive/Drive sync is a well-known corruption
    pattern. Cloud-safe mode stays on DELETE journal + a long busy timeout.
    """
    if os.environ.get("DATABASE_URL"):
        return False
    if _falsy("EB_CLOUD_SAFE_SQLITE"):
        return False
    if _truthy("EB_CLOUD_SAFE_SQLITE"):
        return True
    if is_portable():
        return True
    try:
        return path_looks_cloud_synced(data_dir())
    except OSError:
        return False


def sqlite_connect_args() -> dict:
    timeout = 30.0 if cloud_safe_sqlite() else 5.0
    return {"check_same_thread": False, "timeout": timeout}


def configure_sqlite_connection(dbapi_conn) -> None:
    """Apply PRAGMAs on each new SQLite connection."""
    cur = dbapi_conn.cursor()
    try:
        if cloud_safe_sqlite():
            cur.execute("PRAGMA journal_mode=DELETE")
            cur.execute("PRAGMA synchronous=FULL")
            cur.execute("PRAGMA busy_timeout=30000")
        else:
            cur.execute("PRAGMA busy_timeout=5000")
    finally:
        cur.close()


def uploads_dir() -> Path:
    d = data_dir() / "uploads"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        if _on_vercel():
            d = Path("/tmp/easy-books/uploads")
            d.mkdir(parents=True, exist_ok=True)
        else:
            raise
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


def instance_lock_enabled() -> bool:
    """Refuse a second writer against the same data dir (cloud-sync safety)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if _falsy("EB_INSTANCE_LOCK"):
        return False
    if _truthy("EB_INSTANCE_LOCK"):
        return True
    return is_portable() or path_looks_cloud_synced(data_dir())


def _lock_path() -> Path:
    return data_dir() / ".instance.lock"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _lock_stale_seconds() -> float:
    try:
        return float(os.environ.get("EB_LOCK_STALE_SECONDS", "900"))
    except ValueError:
        return 900.0


def _read_lock(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _lock_is_stale(info: dict, path: Path) -> bool:
    host = str(info.get("host") or "")
    pid = int(info.get("pid") or 0)
    if host == socket.gethostname() and not _pid_alive(pid):
        return True
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return True
    # Other host: only treat as stale after the heartbeat window. A live
    # remote writer refreshes mtime; a crashed laptop eventually expires.
    return age > _lock_stale_seconds()


def acquire_instance_lock() -> Path:
    """Create `.instance.lock` or raise RuntimeError if another writer holds it."""
    path = _lock_path()
    payload = json.dumps(
        {
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        indent=2,
    ).encode()

    if path.exists():
        info = _read_lock(path)
        if not _lock_is_stale(info, path):
            other = info.get("host") or "another machine"
            raise RuntimeError(
                f"Easy-Books is already running against this data folder "
                f"(lock held by {other}, pid {info.get('pid', '?')}). "
                f"Cloud-synced SQLite cannot be opened by two computers at once. "
                f"Stop the other copy, or delete {path} if you are sure it is stale."
            )
        try:
            path.unlink()
        except OSError:
            pass

    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
    except FileExistsError:
        info = _read_lock(path)
        other = info.get("host") or "another machine"
        raise RuntimeError(
            f"Easy-Books is already running against this data folder "
            f"(lock held by {other}). Stop the other copy before starting here."
        ) from None
    return path


def refresh_instance_lock() -> None:
    path = _lock_path()
    if not path.exists():
        return
    try:
        path.touch()
    except OSError:
        pass


def release_instance_lock() -> None:
    path = _lock_path()
    if not path.exists():
        return
    info = _read_lock(path)
    if str(info.get("host") or "") not in ("", socket.gethostname()):
        return
    if int(info.get("pid") or 0) not in (0, os.getpid()):
        return
    try:
        path.unlink()
    except OSError:
        pass
