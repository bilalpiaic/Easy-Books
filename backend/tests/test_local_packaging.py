"""Phase 0 — local packaging: per-install secret, SEED_DEMO toggle, backup.

The first two tests reload shared modules (local_config / auth / db) to
re-trigger import-time behaviour. They restore baseline module state at the
end so the file is order-independent regardless of which test runs next.
"""
import importlib
import os


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


def test_backup_download_returns_zip(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from tests.test_improvements import _mk_engine, _get_session_override, _signup_and_login
    from db import get_session
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    c = TestClient(app)
    auth = _signup_and_login(c, "owner@bk.test", "BkCo")  # first signup = owner
    r = c.get("/api/backup/download", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert r.content[:2] == b"PK"  # zip magic
    app.dependency_overrides.clear()


def test_restore_rejects_zip_slip(monkeypatch):
    """A backup containing a traversal path must be rejected (Zip Slip guard)."""
    import io, zipfile
    from fastapi.testclient import TestClient
    from main import app
    from tests.test_improvements import _mk_engine, _get_session_override, _signup_and_login
    from db import get_session
    engine = _mk_engine()
    app.dependency_overrides[get_session] = _get_session_override(engine)
    c = TestClient(app)
    auth = _signup_and_login(c, "owner@slip.test", "SlipCo")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("database.db", b"x")
        z.writestr("uploads/../../evil.txt", b"pwned")
    buf.seek(0)
    r = c.post("/api/backup/restore", headers=auth,
               files={"file": ("backup.zip", buf.read(), "application/zip")})
    assert r.status_code == 400, r.text
    assert "unsafe path" in r.json()["detail"].lower()
    app.dependency_overrides.clear()
