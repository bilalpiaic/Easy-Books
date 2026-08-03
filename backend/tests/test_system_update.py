"""Installer drift must not block git pull --ff-only (#138 + version.json).

`uv sync` can rewrite tracked backend/uv.lock; older install-and-run scripts
also overwrote tracked frontend/public/version.json on every rebuild. Either
file left dirty blocks `git pull --ff-only` once upstream also touches it —
a common failure of ./update.sh on Debian script installs.
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
    pub = upstream / "frontend" / "public"
    pub.mkdir(parents=True)
    (pub / "version.json").write_text('{"version":"1.0.0","commit":"dev"}\n')
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-q", "-m", "initial")

    local = tmp_path / "local"
    _git(tmp_path, "clone", "-q", str(upstream), str(local))
    _git(local, "config", "user.email", "test@test.local")
    _git(local, "config", "user.name", "Test")

    # Upstream ships a new commit that also touches uv.lock (a real dependency bump).
    (upstream / "backend" / "uv.lock").write_text("version = 2\nnewer-release\n")
    (upstream / "frontend" / "public" / "version.json").write_text(
        '{"version":"1.1.0","commit":"dev"}\n'
    )
    _git(upstream, "add", ".")
    _git(upstream, "commit", "-q", "-m", "bump a dependency")

    # `uv sync` on the user's machine rewrote uv.lock locally, uncommitted —
    # simulating platform-specific resolution drift, not a real edit.
    (local / "backend" / "uv.lock").write_text("version = 1\nlocally-resolved-drift\n")
    # Old installer wrote live build identity into the tracked public path.
    (local / "frontend" / "public" / "version.json").write_text(
        '{"version":"1.0.0","commit":"deadbeef","built":"2026-01-01T00:00:00Z"}\n'
    )

    return local


def test_plain_pull_fails_on_uv_lock_drift(repo_with_upstream_lock_change):
    """Reproduces #138 exactly: an unpatched `git pull --ff-only` is blocked."""
    local = repo_with_upstream_lock_change
    result = _git(local, "pull", "--ff-only")
    assert result.returncode != 0
    assert "overwritten" in (result.stderr + result.stdout).lower()


def test_discard_lockfile_drift_unblocks_pull(repo_with_upstream_lock_change):
    """Discarding installer drift before pulling lets the fast-forward succeed."""
    from routers.system_update import _discard_installer_drift

    local = repo_with_upstream_lock_change
    _discard_installer_drift(local)
    result = _git(local, "pull", "--ff-only")
    assert result.returncode == 0, result.stderr

    assert (local / "backend" / "uv.lock").read_text() == "version = 2\nnewer-release\n"
    assert '"1.1.0"' in (local / "frontend" / "public" / "version.json").read_text()


def test_discard_lockfile_drift_is_a_safe_noop_when_clean(tmp_path):
    """Calling the helper on a clean repo must not error."""
    from routers.system_update import _discard_lockfile_drift

    repo = tmp_path / "clean"
    _init_repo(repo)
    (repo / "backend").mkdir()
    (repo / "backend" / "uv.lock").write_text("version = 1\n")
    pub = repo / "frontend" / "public"
    pub.mkdir(parents=True)
    (pub / "version.json").write_text('{"version":"1.0.0"}\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "initial")

    _discard_lockfile_drift(repo)  # must not raise
    assert (repo / "backend" / "uv.lock").read_text() == "version = 1\n"
