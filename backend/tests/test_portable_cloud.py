"""Portable / cloud-folder data dir, SQLite safety, and instance lock."""
import json
import os
import time

import pytest


def test_portable_defaults_data_dir_to_repo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_PORTABLE", "1")
    monkeypatch.delenv("EB_DATA_DIR", raising=False)
    monkeypatch.delenv("EB_CLOUD_DATA_DIR", raising=False)
    import importlib
    import local_config
    importlib.reload(local_config)
    monkeypatch.setattr(local_config, "_REPO_ROOT", tmp_path)
    d = local_config.data_dir()
    assert d == tmp_path / "data"
    assert d.is_dir()


def test_eb_data_dir_wins_over_portable(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_PORTABLE", "1")
    target = tmp_path / "books"
    monkeypatch.setenv("EB_DATA_DIR", str(target))
    import importlib
    import local_config
    importlib.reload(local_config)
    assert local_config.data_dir() == target


def test_cloud_path_heuristic():
    import local_config
    assert local_config.path_looks_cloud_synced("/Users/x/Library/CloudStorage/OneDrive-Personal/Books")
    assert local_config.path_looks_cloud_synced(r"C:\Users\x\Google Drive\Easy-Books-data")
    assert local_config.path_looks_cloud_synced("/home/x/Dropbox/eb")
    assert not local_config.path_looks_cloud_synced("/home/x/.easy-books")


def test_cloud_safe_sqlite_on_portable(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_PORTABLE", "1")
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EB_CLOUD_SAFE_SQLITE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib
    import local_config
    importlib.reload(local_config)
    assert local_config.cloud_safe_sqlite() is True
    args = local_config.sqlite_connect_args()
    assert args["timeout"] == 30.0


def test_cloud_safe_sqlite_off_override(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_PORTABLE", "1")
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EB_CLOUD_SAFE_SQLITE", "false")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib
    import local_config
    importlib.reload(local_config)
    assert local_config.cloud_safe_sqlite() is False


def test_sqlite_pragmas_cloud_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_PORTABLE", "1")
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import importlib
    import sqlite3
    import local_config
    importlib.reload(local_config)
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    local_config.configure_sqlite_connection(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "delete"
    conn.close()


def test_instance_lock_blocks_second_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    import importlib
    import local_config
    importlib.reload(local_config)
    path = local_config.acquire_instance_lock()
    assert path.exists()
    with pytest.raises(RuntimeError, match="already running"):
        local_config.acquire_instance_lock()
    local_config.release_instance_lock()
    local_config.acquire_instance_lock()
    local_config.release_instance_lock()


def test_instance_lock_same_host_dead_pid_is_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EB_LOCK_STALE_SECONDS", "900")
    import importlib
    import socket
    import local_config
    importlib.reload(local_config)
    lock = tmp_path / ".instance.lock"
    lock.write_text(json.dumps({"host": socket.gethostname(), "pid": 999999991, "started": "x"}))
    local_config.acquire_instance_lock()  # should steal
    local_config.release_instance_lock()


def test_instance_lock_other_host_fresh_is_held(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EB_LOCK_STALE_SECONDS", "900")
    import importlib
    import local_config
    importlib.reload(local_config)
    lock = tmp_path / ".instance.lock"
    lock.write_text(json.dumps({"host": "other-pc", "pid": 1, "started": "x"}))
    os.utime(lock, (time.time(), time.time()))
    with pytest.raises(RuntimeError, match="already running"):
        local_config.acquire_instance_lock()


def test_instance_lock_other_host_old_mtime_is_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EB_LOCK_STALE_SECONDS", "60")
    import importlib
    import local_config
    importlib.reload(local_config)
    lock = tmp_path / ".instance.lock"
    lock.write_text(json.dumps({"host": "other-pc", "pid": 1, "started": "x"}))
    old = time.time() - 120
    os.utime(lock, (old, old))
    local_config.acquire_instance_lock()
    local_config.release_instance_lock()


def test_portable_marker_file(tmp_path, monkeypatch):
    monkeypatch.delenv("EB_PORTABLE", raising=False)
    monkeypatch.delenv("EB_DATA_DIR", raising=False)
    (tmp_path / ".easy-books-portable").write_text("")
    import importlib
    import local_config
    importlib.reload(local_config)
    monkeypatch.setattr(local_config, "_REPO_ROOT", tmp_path)
    assert local_config.is_portable() is True
    assert local_config.data_dir() == tmp_path / "data"
