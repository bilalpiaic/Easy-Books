"""15-day demo-login trial for standalone / on-premise installs.

Script installers, the Electron desktop app, and ``APP_ENV=local`` premises
launches seed the nine ``demo.*@easy-books.app`` companies so a first-run
evaluation needs no signup. After ``EB_DEMO_TRIAL_DAYS`` (default 15) those
demo logins are refused. Real company accounts created via ``/signup`` are
not affected.

The clock is a write-once ISO timestamp in the install data dir
(``.demo-trial-started``), with a SQLite ``tenant.created_at`` backfill so
deleting only the stamp file cannot restart the window. Once expiry is
observed, ``.demo-trial-expired`` is created and stays expired even if the
system clock is wound back.

Does **not** apply to:
- ``dev.sh`` / pytest (``APP_ENV`` is not ``local``, ``EB_STANDALONE`` unset)
- Vercel / ``APP_ENV=production`` (``ALLOW_DEMO_LOGIN`` already defaults off)
- any process with ``EB_SKIP_DEMO_TRIAL=true``
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

def trial_expired_detail() -> str:
    return (
        f"The {trial_days()}-day demo trial on this installation has ended. "
        "Sign up for a company account to continue."
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


def _data_dir() -> Path:
    from local_config import data_dir

    return data_dir()


def stamp_path() -> Path:
    return _data_dir() / STAMP_NAME


def expired_marker_path() -> Path:
    return _data_dir() / EXPIRED_NAME


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


def _read_stamp() -> datetime | None:
    path = stamp_path()
    try:
        return _parse_dt(path.read_text(encoding="utf-8").splitlines()[0])
    except (OSError, IndexError):
        return None


def ensure_started_at() -> datetime:
    """Return the install clock, creating the stamp on first observation."""
    existing = _read_stamp()
    if existing is not None:
        now = _now()
        # A stamp in the future is clock-skew / tampering — do not grant extra days.
        if existing > now + timedelta(minutes=5):
            return now
        return existing
    started = _tenant_min_created_at() or _now()
    _write_once(stamp_path(), _format_dt(started) + "\n")
    return _read_stamp() or started


def _mark_expired() -> None:
    _write_once(expired_marker_path(), _format_dt(_now()) + "\n")


def expired_marker_present() -> bool:
    try:
        return expired_marker_path().is_file()
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
    return {
        "applies": True,
        "days": days,
        "days_remaining": remaining,
        "started_at": _format_dt(started),
        "ends_at": _format_dt(ends),
        "expired": expired,
    }
