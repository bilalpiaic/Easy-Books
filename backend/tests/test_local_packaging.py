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
