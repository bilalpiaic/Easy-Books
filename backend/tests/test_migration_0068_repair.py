"""0068 repair — tenant SaaS columns restored after 0067 sqlite rebuild bug."""
import sqlite3
import subprocess
from pathlib import Path


def test_0068_repairs_tenant_saas_columns(tmp_path, monkeypatch):
    db = tmp_path / "broken.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
        INSERT INTO alembic_version VALUES ('0067_spinning_module');
        CREATE TABLE tenant (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            base_currency VARCHAR NOT NULL DEFAULT 'USD',
            business_model VARCHAR NOT NULL DEFAULT 'simple',
            enabled_modules VARCHAR NOT NULL DEFAULT '["base"]',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            cost_method VARCHAR NOT NULL DEFAULT 'wavg',
            module_meta VARCHAR NOT NULL DEFAULT '{}',
            is_suspended BOOLEAN NOT NULL DEFAULT 0
        );
        INSERT INTO tenant (id, name) VALUES (1, 'Test Co');
    """)
    conn.close()

    backend = Path(__file__).resolve().parents[1]
    env = {"PYTHONPATH": ".", "DATABASE_URL": f"sqlite:///{db}"}
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "0068_tenant_saas_repair"],
        cwd=backend,
        env={**dict(__import__("os").environ), **env},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(db)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(tenant)")}
    assert "plan" in cols
    assert "max_users" in cols
    plan, max_users = conn.execute("SELECT plan, max_users FROM tenant WHERE id=1").fetchone()
    assert plan == "free"
    assert max_users == 2
