"""
In-app updater — POST /api/system/update
Admin/owner only. Runs `git pull --ff-only`, then re-launches the
install-and-run script as a detached process so it can kill the running
servers (ports 8000 + 3000), rebuild Next.js, and restart everything.

The BackgroundTasks mechanism ensures the HTTP response is fully sent
before the script kills our own process.
"""
import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from auth import CurrentUserDep

router = APIRouter()

# Repo root: three parents up from this file
#   backend/routers/system_update.py → backend/routers → backend → repo root
_REPO = Path(__file__).parent.parent.parent

_lock  = threading.Lock()
_phase = "idle"   # idle | pulling | restarting | error


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
