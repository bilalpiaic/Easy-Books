"""An existing DB that was built by create_all() (no alembic_version row) must
upgrade to head idempotently — this is what a script-installer user hits on
their first update after we start running Alembic on launch."""
import importlib
from sqlalchemy import inspect, text


def test_upgrade_over_create_all_db_is_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import local_config; importlib.reload(local_config)
    import db; importlib.reload(db)

    # 1. Simulate an old install: schema via create_all, a row of real data, NO alembic_version.
    db.SQLModel.metadata.create_all(db.engine)
    with db.engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tenant (name, base_currency, business_model, enabled_modules, cost_method, created_at) "
            "VALUES ('Acme', 'USD', 'simple', '[]', 'wavg', datetime('now'))"
        ))
    assert "alembic_version" not in set(inspect(db.engine).get_table_names())

    # 2. Run the same upgrade the installer will run.
    import run_packaged; importlib.reload(run_packaged)
    run_packaged.migrate()  # alembic upgrade head against the same sqlite file

    # 3. Schema is at head, the data survived, and a second upgrade is a no-op.
    insp = inspect(db.engine)
    assert "alembic_version" in set(insp.get_table_names())
    with db.engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM tenant")).scalar() == "Acme"
    run_packaged.migrate()  # idempotent second run must not raise
