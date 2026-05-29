"""Phase 0 — local packaging: per-install secret, SEED_DEMO toggle, backup."""
import importlib


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
    assert (tmp_path / ".secret.key").exists()
    # Reload again → same persisted key (tokens survive restarts)
    importlib.reload(auth)
    assert auth.SECRET_KEY == key1


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
