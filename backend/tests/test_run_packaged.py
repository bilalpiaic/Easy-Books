"""Tests for run_packaged.backup_db version-aware backup logic."""
from pathlib import Path
import pytest


from run_packaged import backup_db, write_last_version


def test_backup_skipped_when_no_db(tmp_path):
    """No DB file → no backup created, returns None."""
    db = tmp_path / "database.db"
    result = backup_db(db, tmp_path, "2.6.0")
    assert result is None


def test_backup_skipped_on_same_version(tmp_path):
    """DB exists but version unchanged → no backup."""
    db = tmp_path / "database.db"
    db.write_text("fake db")
    (tmp_path / ".last-app-version").write_text("2.6.0")
    result = backup_db(db, tmp_path, "2.6.0")
    assert result is None


def test_backup_created_on_version_change(tmp_path):
    """DB exists and version has changed → backup created."""
    db = tmp_path / "database.db"
    db.write_text("fake db content")
    (tmp_path / ".last-app-version").write_text("2.5.0")
    result = backup_db(db, tmp_path, "2.6.0")
    assert result is not None
    assert result == tmp_path / "database.db.bak-2.6.0"
    assert result.exists()
    assert result.read_text() == "fake db content"
    assert db.exists()          # original untouched


def test_backup_created_on_first_install(tmp_path):
    """DB exists but no .last-app-version file → backup on first update."""
    db = tmp_path / "database.db"
    db.write_text("data")
    result = backup_db(db, tmp_path, "2.6.0")
    assert result == tmp_path / "database.db.bak-2.6.0"
    assert result.exists()


def test_write_last_version(tmp_path):
    write_last_version(tmp_path, "2.6.0")
    assert (tmp_path / ".last-app-version").read_text() == "2.6.0"


def test_write_last_version_overwrites(tmp_path):
    (tmp_path / ".last-app-version").write_text("2.5.0")
    write_last_version(tmp_path, "2.6.0")
    assert (tmp_path / ".last-app-version").read_text() == "2.6.0"


def test_app_version_reads_version_file(monkeypatch, tmp_path):
    """_app_version() reads VERSION from the bundle dir."""
    import run_packaged
    (tmp_path / "VERSION").write_text("3.1.4")
    monkeypatch.setattr(run_packaged, "_bundle_dir", lambda: tmp_path)
    assert run_packaged._app_version() == "3.1.4"


def test_app_version_fallback_when_no_version_file(monkeypatch, tmp_path):
    """_app_version() returns 'dev' when VERSION file is absent."""
    import run_packaged
    monkeypatch.setattr(run_packaged, "_bundle_dir", lambda: tmp_path)
    assert run_packaged._app_version() == "dev"
