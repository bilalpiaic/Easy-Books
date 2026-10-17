"""15-day trial lock for standalone / on-premise installs.

After ``EB_DEMO_TRIAL_DAYS`` (default 15) the *whole copy* is locked: login,
signup, and every API except health/version/trial status. The source folder
and ``EB_DATA_DIR`` books are **not** deleted so a licensed unlock can resume
the same data.

The clock is write-once in the **books data dir** (``.demo-trial-started`` under
``EB_DATA_DIR``, else portable ``<repo>/data``, else ``~/.easy-books`` — never
the ``backend/`` package folder) and, outside pytest, also in the install
checkout (``.easy-books-trial``) so this folder stays bound to the original
start date. SQLite ``tenant.created_at`` backfills if stamps are missing.
Once expiry is observed, expired markers stay set even if the system clock
is wound back.

Does **not** apply to:
- ``dev.sh`` / pytest (``APP_ENV`` is not ``local``, ``EB_STANDALONE`` unset)
- Vercel / ``APP_ENV=production``
- any process with ``EB_SKIP_DEMO_TRIAL=true`` (licensed / evaluation bypass)
"""
from __future__ import annotations

import math
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_TRIAL_DAYS = 15
STAMP_NAME = ".demo-trial-started"
EXPIRED_NAME = ".demo-trial-expired"
INSTALL_STAMP_NAME = ".easy-books-trial"
INSTALL_EXPIRED_NAME = ".easy-books-trial-expired"

def trial_expired_detail() -> str:
    return (
        f"The {trial_days()}-day trial on this installation has ended. "
        "This copy of Easy-Books is locked. Your source folder and books "
        "are not deleted. Paste a license token to activate this install, "
        "or contact Easy-Books."
    )


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _falsy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("0", "false", "no", "off")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def trial_days() -> int:
    raw = (os.environ.get("EB_DEMO_TRIAL_DAYS") or "").strip()
    if not raw:
        return DEFAULT_TRIAL_DAYS
    try:
        days = int(raw)
    except ValueError:
        return DEFAULT_TRIAL_DAYS
    return max(1, days)


def demo_trial_applies() -> bool:
    """True when this process is a standalone premises install with a demo clock."""
    if _truthy("EB_SKIP_DEMO_TRIAL"):
        return False
    from services.app_runtime import is_vercel

    if is_vercel():
        return False
    if _falsy("EB_STANDALONE"):
        return False
    if _truthy("EB_STANDALONE"):
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return (os.environ.get("APP_ENV") or "").strip().lower() == "local"


def books_data_dir() -> Path:
    """Where standalone books and trial stamps live (same as install-and-run).

    ``EB_DATA_DIR`` if set, else portable ``<repo>/data``, else ``~/.easy-books``.
    Not ``backend/`` — that is only ``local_config.data_dir()``'s dev default.
    """
    raw = (os.environ.get("EB_DATA_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    from local_config import is_portable, repo_root

    if is_portable():
        cloud = (os.environ.get("EB_CLOUD_DATA_DIR") or "").strip()
        return Path(cloud).expanduser() if cloud else repo_root() / "data"
    return Path.home() / ".easy-books"


def _data_dir() -> Path:
    return books_data_dir()


def stamp_path() -> Path:
    return _data_dir() / STAMP_NAME


def expired_marker_path() -> Path:
    return _data_dir() / EXPIRED_NAME


def _install_paths() -> tuple[Path, Path] | None:
    """Checkout-root stamps so *this folder* stays bound to the trial clock.

    Skipped under pytest so tests never dirty the git worktree.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    try:
        from local_config import repo_root

        root = repo_root()
        return root / INSTALL_STAMP_NAME, root / INSTALL_EXPIRED_NAME
    except OSError:
        return None


def _parse_dt(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = payload.encode("utf-8")
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
    except FileExistsError:
        return
    except OSError:
        return


def _write_replace(path: Path, payload: str) -> None:
    """Overwrite a stamp (used by ``extend_trial`` / ``force_expire_trial``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = payload.encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _tenant_min_created_at() -> datetime | None:
    """Earliest tenant row in the on-disk SQLite file, if any.

    Uses stdlib sqlite3 so this module never imports ``db`` (``db`` already
    imports ``security_policy``).
    """
    try:
        from local_config import sqlite_path

        db_path = sqlite_path()
        if not Path(db_path).is_file():
            return None
        con = sqlite3.connect(db_path)
        try:
            row = con.execute("SELECT MIN(created_at) FROM tenant").fetchone()
        except sqlite3.Error:
            return None
        finally:
            con.close()
    except OSError:
        return None
    if not row or not row[0]:
        return None
    return _parse_dt(str(row[0]))


def _read_stamp_file(path: Path) -> datetime | None:
    try:
        return _parse_dt(path.read_text(encoding="utf-8").splitlines()[0])
    except (OSError, IndexError):
        return None


def _read_stamp() -> datetime | None:
    return _read_stamp_file(stamp_path())


def ensure_started_at() -> datetime:
    """Return the install clock, creating stamps on first observation.

    Existing stamp files are authoritative (so ``extend_trial`` can start a
    new window). ``tenant.created_at`` is only used when no stamp exists, so
    deleting the stamp files on an old install cannot reset the clock.
    """
    now = _now()
    skew = now + timedelta(minutes=5)
    stamps: list[datetime] = []
    data = _read_stamp()
    if data is not None and data <= skew:
        stamps.append(data)
    install = _install_paths()
    if install is not None:
        folder = _read_stamp_file(install[0])
        if folder is not None and folder <= skew:
            stamps.append(folder)
    if stamps:
        started = min(stamps)
    else:
        tenant = _tenant_min_created_at()
        started = tenant if tenant is not None and tenant <= skew else now
    line = _format_dt(started) + "\n"
    _write_once(stamp_path(), line)
    if install is not None:
        _write_once(install[0], line)
    return started


def _mark_expired() -> None:
    line = _format_dt(_now()) + "\n"
    _write_once(expired_marker_path(), line)
    install = _install_paths()
    if install is not None:
        _write_once(install[1], line)


def expired_marker_present() -> bool:
    try:
        if expired_marker_path().is_file():
            return True
    except OSError:
        pass
    install = _install_paths()
    if install is None:
        return False
    try:
        return install[1].is_file()
    except OSError:
        return False


def demo_trial_expired() -> bool:
    if not demo_trial_applies():
        return False
    if expired_marker_present():
        return True
    started = ensure_started_at()
    ends = started + timedelta(days=trial_days())
    if _now() >= ends:
        _mark_expired()
        return True
    return False


def install_locked() -> bool:
    """True when this standalone copy must refuse all work (not just demo logins)."""
    from services.standalone_license import is_licensed

    if is_licensed():
        return False
    return demo_trial_expired()


def extend_trial(*, days: int | None = None) -> dict[str, Any]:
    """Start a new trial window from now.

    ``days`` defaults to ``EB_DEMO_TRIAL_DAYS`` (15). Clears expired markers
    and rewrites start stamps in the **books data dir** (``~/.easy-books`` on
    a normal standalone install). Books and the source folder are not touched.
    Restart the app afterwards so the running process sees the new clock.
    """
    extra = trial_days() if days is None else max(1, int(days))
    os.environ["EB_DEMO_TRIAL_DAYS"] = str(extra)
    os.environ["EB_DATA_DIR"] = str(books_data_dir())
    started = _now()
    line = _format_dt(started) + "\n"
    _unlink_quiet(expired_marker_path())
    _write_replace(stamp_path(), line)
    install = _install_paths()
    if install is not None:
        _unlink_quiet(install[1])
        _write_replace(install[0], line)
    info = trial_info() or {
        "applies": True,
        "days": extra,
        "days_remaining": extra,
        "started_at": _format_dt(started),
        "ends_at": _format_dt(started + timedelta(days=extra)),
        "expired": False,
        "locked": False,
    }
    info["extended"] = True
    return info


def force_expire_trial() -> dict[str, Any]:
    """Backdate the trial clock and set expired latches (QA / force-lock).

    Writes in the **books data dir** (``~/.easy-books`` on a normal standalone
    install), never ``backend/``. Does not delete books, source, or a license
    file. If a valid license is present the copy stays unlocked.
    """
    os.environ["EB_DATA_DIR"] = str(books_data_dir())
    started = _now() - timedelta(days=trial_days() + 1)
    start_line = _format_dt(started) + "\n"
    expired_line = _format_dt(_now()) + "\n"
    _write_replace(stamp_path(), start_line)
    _write_replace(expired_marker_path(), expired_line)
    install = _install_paths()
    if install is not None:
        _write_replace(install[0], start_line)
        _write_replace(install[1], expired_line)
    from services.standalone_license import is_licensed

    licensed = is_licensed()
    info = trial_info() or {
        "applies": True,
        "days": trial_days(),
        "days_remaining": 0,
        "started_at": _format_dt(started),
        "ends_at": _format_dt(started + timedelta(days=trial_days())),
        "expired": True,
        "locked": not licensed,
        "licensed": licensed,
    }
    info["forced_expire"] = True
    return info


def trial_info() -> dict[str, Any] | None:
    """Payload for ``GET /api/auth/oauth/providers``. ``None`` when not standalone."""
    if not demo_trial_applies():
        return None
    days = trial_days()
    started = ensure_started_at()
    ends = started + timedelta(days=days)
    now = _now()
    expired = expired_marker_present() or now >= ends
    if expired:
        _mark_expired()
        remaining = 0
    else:
        remaining = max(1, math.ceil((ends - now).total_seconds() / 86400))
    from services.standalone_license import is_licensed

    licensed = is_licensed()
    return {
        "applies": True,
        "days": days,
        "days_remaining": remaining,
        "started_at": _format_dt(started),
        "ends_at": _format_dt(ends),
        "expired": expired,
        "locked": expired and not licensed,
        "licensed": licensed,
    }
