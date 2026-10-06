"""Phase 0 — local packaging: per-install secret, SEED_DEMO toggle, backup.

The first two tests reload shared modules (local_config / auth / db) to
re-trigger import-time behaviour. They restore baseline module state at the
end so the file is order-independent regardless of which test runs next.
"""
import importlib
import os

import pytest
from sqlalchemy import create_engine


def _skip_unless_sqlite():
    """File backup is a local-install feature. The Postgres fixture never has a database.db to zip."""
    import db
    if db.engine.url.get_backend_name() != "sqlite":
        pytest.skip("file backup is SQLite installs only")


def _restore_baseline():
    """Reload local_config / auth / db under the (now-restored) real env so
    later tests see baseline module globals (engine, SECRET_KEY)."""
    import local_config, auth, db
    importlib.reload(local_config)
    importlib.reload(auth)
    importlib.reload(db)


def test_secret_is_persisted_per_install(tmp_path, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("APP_ENV", "development")
    import local_config
    importlib.reload(local_config)
    import auth
    importlib.reload(auth)
    key1 = auth.SECRET_KEY
    assert key1 and key1 != "super-secret-key-change-in-prod"
    key_file = tmp_path / ".secret.key"
    assert key_file.exists()
    if os.name == "posix":
        import stat
        assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    # Reload again → same persisted key (tokens survive restarts)
    importlib.reload(auth)
    assert auth.SECRET_KEY == key1
    monkeypatch.undo()
    _restore_baseline()


def test_seed_demo_off_creates_no_demo_users(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path / "x"))
    monkeypatch.setenv("SEED_DEMO", "false")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import local_config, db as dbmod
    importlib.reload(local_config)
    importlib.reload(dbmod)
    dbmod.create_db_and_tables()
    from sqlmodel import Session, select
    from models import User
    with Session(dbmod.engine) as s:
        demos = s.exec(select(User).where(User.email.like("demo.%"))).all()
    assert demos == []
    monkeypatch.undo()
    _restore_baseline()


def test_jwt_aborts_when_environment_production_without_secret(tmp_path, monkeypatch):
    """#419 — ENVIRONMENT=production is equivalent to APP_ENV=production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    import auth
    with pytest.raises(SystemExit, match="JWT_SECRET_KEY"):
        importlib.reload(auth)
    monkeypatch.undo()
    _restore_baseline()


def test_backup_download_returns_zip(client, admin_headers):
    _skip_unless_sqlite()
    r = client.get("/api/backup/download", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.content[:2] == b"PK"  # zip magic


def test_restore_rejects_zip_slip(client, admin_headers):
    """A backup containing a traversal path must be rejected (Zip Slip guard)."""
    _skip_unless_sqlite()
    import io, zipfile
    c = client
    auth = admin_headers
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("database.db", b"x")
        z.writestr("uploads/../../evil.txt", b"pwned")
    buf.seek(0)
    r = c.post("/api/backup/restore", headers=auth,
               files={"file": ("backup.zip", buf.read(), "application/zip")})
    assert r.status_code == 400, r.text
    assert "unsafe path" in r.json()["detail"].lower()


def test_backup_rejects_live_postgres_engine(client, admin_headers, monkeypatch):
    """Deploy CI sets DATABASE_URL to Postgres while the fixture serves SQLite.

    The guard must follow the engine tests install on `db`, not the one
    captured when the router was imported.
    """
    import db
    pg = create_engine("postgresql://localhost/unused")
    monkeypatch.setattr(db, "engine", pg)
    try:
        r = client.get("/api/backup/download", headers=admin_headers)
    finally:
        pg.dispose()
    assert r.status_code == 400, r.text
    assert "sqlite" in r.json()["detail"].lower()
