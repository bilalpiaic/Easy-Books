"""
In-app updater — POST /api/system/update
Admin/owner only. Runs `git pull --ff-only`, then re-launches the
install-and-run script as a detached process so it can kill the running
servers (ports 8000 + 3000), rebuild Next.js, and restart everything.

The BackgroundTasks mechanism ensures the HTTP response is fully sent
before the script kills our own process.
"""
import json as _json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from routers.common import CurrentUserDep

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
async def trigger_update(bg: BackgroundTasks, current_user: CurrentUserDep):
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

        _discard_lockfile_drift(_REPO)

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


def _discard_lockfile_drift(repo: Path) -> None:
    """`uv sync` (run on every launch by install-and-run.*) can rewrite
    backend/uv.lock even with no dependency changes (platform-specific
    resolution), leaving it locally modified. Once upstream also touches the
    file, that drift blocks `git pull --ff-only` (#138). uv.lock is fully
    machine-generated and never hand-edited, so discarding local changes to
    it before pulling is always safe — the next `uv sync` regenerates it."""
    subprocess.run(
        ["git", "checkout", "--", "backend/uv.lock"],
        capture_output=True, text=True, cwd=str(repo),
    )


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
