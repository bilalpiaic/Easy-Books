"""#138 — git pull --ff-only must not be blocked by uv.lock drift.

`uv sync` (run on every app launch by install-and-run.*) can rewrite the
tracked backend/uv.lock even with no dependency changes (platform-specific
resolution). That leaves the file locally modified, so once upstream also
touches uv.lock, `git pull --ff-only` refuses to overwrite the dirty file.
"""
import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "Test")


@pytest.fixture
def repo_with_upstream_lock_change(tmp_path):
    """A local clone whose uv.lock has BOTH uncommitted local drift AND an
    upstream commit it hasn't pulled yet — the exact collision in #138."""
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    lock = upstream / "backend"
    lock.mkdir()
    lock_file = lock / "uv.lock"
    lock_file.write_text("version = 1\nlocked-at-release\n")
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-q", "-m", "initial")

    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(upstream), str(local))
    _git(local, "config", "user.email", "test@test.local")
    _git(local, "config", "user.name", "Test")

    # Upstream ships a new commit that also touches uv.lock (a real dependency bump).
    (upstream / "backend" / "uv.lock").write_text("version = 2\nnewer-release\n")
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-q", "-m", "bump a dependency")

    # `uv sync` on the user's machine rewrote uv.lock locally, uncommitted —
    # simulating platform-specific resolution drift, not a real edit.
    (local / "backend" / "uv.lock").write_text("version = 1\nlocally-resolved-drift\n")

    return local


def test_plain_pull_fails_on_uv_lock_drift(repo_with_upstream_lock_change):
    """Reproduces #138 exactly: an unpatched `git pull --ff-only` is blocked."""
    local = repo_with_upstream_lock_change
    result = _git(local, "pull", "--ff-only")
    assert result.returncode != 0
    assert "overwritten" in (result.stderr + result.stdout).lower()


def test_discard_lockfile_drift_unblocks_pull(repo_with_upstream_lock_change):
    """The fix: discarding local uv.lock drift before pulling lets the
    fast-forward succeed, and the pulled file matches upstream afterward."""
    from routers.system_update import _discard_lockfile_drift

    local = repo_with_upstream_lock_change
    _discard_lockfile_drift(local)
    result = _git(local, "pull", "--ff-only")
    assert result.returncode == 0, result.stderr

    assert (local / "backend" / "uv.lock").read_text() == "version = 2\nnewer-release\n"


def test_discard_lockfile_drift_is_a_safe_noop_when_clean(tmp_path):
    """Calling the helper on a repo with no local uv.lock changes must not error."""
    from routers.system_update import _discard_lockfile_drift

    repo = tmp_path / "clean"
    _init_repo(repo)
    (repo / "backend").mkdir()
    (repo / "backend" / "uv.lock").write_text("version = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "initial")

    _discard_lockfile_drift(repo)  # must not raise
    assert (repo / "backend" / "uv.lock").read_text() == "version = 1\n"
