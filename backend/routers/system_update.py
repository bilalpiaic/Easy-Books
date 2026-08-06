"""
In-app updater — POST /api/system/update
Admin/owner only. Runs `git pull --ff-only`, then re-launches the
install-and-run script as a detached process so it can kill the running
servers (ports 8000 + 3000), rebuild Next.js, and restart everything.

The BackgroundTasks mechanism ensures the HTTP response is fully sent
before the script kills our own process.

Also serves what's-new notices for every logged-in user (popup + Alerts).
"""
import json as _json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from routers.common import CurrentUserDep, SessionDep

router = APIRouter()

# Repo root: three parents up from this file
#   backend/routers/system_update.py → backend/routers → backend → repo root
_REPO = Path(__file__).parent.parent.parent

_lock  = threading.Lock()
_phase = "idle"   # idle | pulling | restarting | error

# ── GitHub commit-level update check ─────────────────────────────────────────
_GITHUB_OWNER  = "bilalpiaic"
_GITHUB_REPO   = "Easy-Books"
_GITHUB_BRANCH = "main"

# Cache the remote-commit check for 30 min so we don't hammer the API
_status_cache: dict | None = None
_status_cache_at: float    = 0
_STATUS_TTL                = 30 * 60  # seconds


@router.post("/api/system/update")
async def trigger_update(
    bg: BackgroundTasks,
    current_user: CurrentUserDep,
    session: SessionDep,
):
    global _phase

    if current_user.role not in ("admin", "owner"):
        raise HTTPException(403, "Admin or owner required")

    script = _find_install_script()
    if script is None:
        return {
            "status": "no_script",
            "message": "install-and-run script not found — run the updater manually.",
        }

    with _lock:
        if _phase not in ("idle", "error"):
            raise HTTPException(409, "Update already in progress")
        _phase = "pulling"

    try:
        before = _git("rev-parse", "HEAD")

        _discard_installer_drift(_REPO)

        pull = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True, text=True, cwd=str(_REPO),
        )
        if pull.returncode != 0:
            _phase = "error"
            msg = (pull.stderr or pull.stdout or "git pull failed").strip()
            raise HTTPException(500, msg)

        after = _git("rev-parse", "HEAD")

        if before == after:
            _phase = "idle"
            return {"status": "up_to_date", "commit": after[:7]}

        # Fan out easy-language what's-new into every user's Alerts inbox
        # before the process restarts so returning sessions see the popup.
        try:
            from services.update_notices import sync_update_notices
            sync_update_notices(session, force_fanout=True)
        except Exception:
            pass

        _phase = "restarting"
        bg.add_task(_launch_script, script)
        return {"status": "restarting", "commit": after[:7]}

    except HTTPException:
        raise
    except Exception as e:
        _phase = "error"
        raise HTTPException(500, str(e))


# ── Status check (commit-level, not release-level) ───────────────────────────

@router.get("/api/system/update/status")
async def update_status_check(current_user: CurrentUserDep):
    """
    Returns whether there are new commits on main branch that the local install
    doesn't have yet. Caches the GitHub API response for 30 minutes.

    Response:
      status: "up_to_date" | "update_available" | "unknown"
      local:  short commit hash (7 chars)
      remote: short commit hash from GitHub (7 chars) or null on error
      behind: true when remote is ahead
    """
    global _status_cache, _status_cache_at

    local_full  = _git("rev-parse", "HEAD")
    local_short = local_full[:7] if local_full else "unknown"

    now = time.time()
    if _status_cache is None or (now - _status_cache_at) > _STATUS_TTL:
        remote_sha = _fetch_remote_sha()
        _status_cache    = remote_sha
        _status_cache_at = now
    else:
        remote_sha = _status_cache

    if remote_sha is None:
        return {"status": "unknown", "local": local_short, "remote": None, "behind": False}

    remote_short = remote_sha[:7]
    # "up to date" when local HEAD starts with the remote SHA
    # (or remote starts with local — covers shallow clones)
    up_to_date = (
        local_full.startswith(remote_sha[:40]) or
        remote_sha.startswith(local_full[:7])
    )
    return {
        "status":  "up_to_date" if up_to_date else "update_available",
        "local":   local_short,
        "remote":  remote_short,
        "behind":  not up_to_date,
    }


@router.get("/api/system/update/changelog")
async def get_changelog(
    current_user: CurrentUserDep,
    since: str = "",
    limit: int = 10,
):
    """Return recent git commit messages (for post-update what's-new display)."""
    if current_user.role not in ("admin", "owner"):
        from fastapi import HTTPException
        raise HTTPException(403, "Admin or owner required")

    limit = max(1, min(limit, 30))
    if since:
        raw = _git("log", f"{since}..HEAD", f"--max-count={limit}", "--pretty=format:%h|%s|%as")
    else:
        raw = _git("log", f"--max-count={limit}", "--pretty=format:%h|%s|%as")

    commits = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) >= 2:
            commits.append({
                "sha":     parts[0],
                "message": parts[1],
                "date":    parts[2] if len(parts) > 2 else "",
            })

    return {"commits": commits}


# ── What's-new notices (every logged-in user) ────────────────────────────────

class AckBody(BaseModel):
    alert_ids: Optional[List[int]] = None


@router.get("/api/system/update/notices")
def list_update_notices(session: SessionDep, current_user: CurrentUserDep):
    """Sync shipped commits → this user's Alerts, return unread what's-new.

    Called on dashboard load and periodically while the session is open so
    updates that land mid-session (or while the user was logged out) popup.

    Intentionally per-user only — never fans out to every active account on
    this hot path (that exhausted Neon pool_size=1 and timed out at 60s).
    """
    from services.update_notices import (
        ensure_notice_table,
        sync_update_notices,
        unread_update_alerts,
    )

    sync: dict = {}
    try:
        ensure_notice_table(session)
    except Exception as exc:
        return {"sync": {"error": f"schema:{str(exc)[:160]}"}, "items": []}

    try:
        sync = sync_update_notices(session, for_user=current_user)
    except Exception as exc:
        sync = {"error": str(exc)[:200]}
        try:
            session.rollback()
        except Exception:
            pass

    try:
        # sync already called ensure_user_notices for this user
        rows = unread_update_alerts(session, current_user, ensure=False)
    except Exception as exc:
        try:
            session.rollback()
        except Exception:
            pass
        return {"sync": {**sync, "unread_error": str(exc)[:160]}, "items": []}

    return {
        "sync": sync,
        "items": [
            {
                "id": a.id,
                "title": a.title,
                "body": a.body,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "dedupe_key": a.dedupe_key,
            }
            for a in rows
        ],
    }


@router.post("/api/system/update/notices/ack")
def ack_update_notices(
    body: AckBody,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Mark what's-new alerts as read after the user dismisses the popup."""
    from services.update_notices import ack_update_alerts

    n = ack_update_alerts(session, current_user, body.alert_ids)
    return {"ok": True, "acked": n}


def _fetch_remote_sha() -> str | None:
    """Fetch latest commit SHA on main branch from GitHub API."""
    url = (
        f"https://api.github.com/repos/{_GITHUB_OWNER}/{_GITHUB_REPO}"
        f"/commits/{_GITHUB_BRANCH}"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = _json.loads(r.read())
            return data.get("sha")
    except Exception:
        return None


# ── helpers ──────────────────────────────────────────────────────────────────

def _find_install_script() -> str | None:
    import sys
    # Prefer platform-native script; fall back to the other
    order = (
        ["install-and-run.ps1", "install-and-run.sh"]
        if sys.platform == "win32"
        else ["install-and-run.sh", "install-and-run.ps1"]
    )
    for name in order:
        p = _REPO / name
        if p.exists():
            return str(p)
    return None


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=str(_REPO),
    ).stdout.strip()


def _discard_installer_drift(repo: Path) -> None:
    """Discard machine-generated files that block `git pull --ff-only`.

    - `backend/uv.lock`: `uv sync` can rewrite it with platform-specific
      resolution drift even when dependencies did not change (#138).
    - `frontend/public/version.json`: older installers wrote the live build
      identity into this *tracked* path, leaving it dirty after every rebuild
      and blocking the next update on Debian/script installs.

    Both files are regenerated on the next install/build, so discarding local
    edits is always safe.
    """
    subprocess.run(
        [
            "git", "checkout", "--",
            "backend/uv.lock",
            "frontend/public/version.json",
        ],
        capture_output=True, text=True, cwd=str(repo),
    )


# Back-compat alias for tests / callers that still use the #138 name.
_discard_lockfile_drift = _discard_installer_drift


def _launch_script(script: str) -> None:
    """
    Sleep 1.5 s so FastAPI flushes the response, then detach the install
    script so it can freely kill us and the Next.js server.
    """
    global _phase
    time.sleep(1.5)
    import sys
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", script, "-Rebuild"],
                cwd=str(_REPO),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            subprocess.Popen(
                ["/bin/bash", script, "--rebuild"],
                cwd=str(_REPO),
                start_new_session=True,
            )
    except Exception:
        _phase = "error"
