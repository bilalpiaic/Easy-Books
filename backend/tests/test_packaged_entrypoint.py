"""Phase 2 — packaged entrypoint: migrations build the schema to head."""
import importlib
from sqlalchemy import create_engine, inspect


def test_migrations_bring_empty_db_to_head(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import local_config
    importlib.reload(local_config)
    import run_packaged
    importlib.reload(run_packaged)
    run_packaged.migrate()  # alembic upgrade head against the temp SQLite
    eng = create_engine(f"sqlite:///{local_config.sqlite_path()}")
    tables = set(inspect(eng).get_table_names())
    # Core + Sprint 7-14 tables exist purely from the migration chain.
    assert {"account", "invoice", "creditnote", "debitnote", "customeradvance"} <= tables
