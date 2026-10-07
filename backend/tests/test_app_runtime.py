"""#424 — pool kwargs, Alembic URL, production create_all gate, entrypoint roles."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from services.app_runtime import (
    allow_create_all_bootstrap,
    app_role,
    postgres_pool_kwargs,
    resolve_database_url,
    run_background_jobs,
    run_in_process_schedulers,
)


def test_vercel_pool_is_one_plus_zero(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DB_POOL_SIZE", "20")
    assert postgres_pool_kwargs() == {"pool_size": 1, "max_overflow": 0}


def test_default_pool_is_five(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    kw = postgres_pool_kwargs()
    assert kw["pool_size"] == 5
    assert kw["max_overflow"] == 5


def test_alembic_prefers_direct_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://pooler/db")
    monkeypatch.setenv("DATABASE_URL_DIRECT", "postgresql://primary/db")
    monkeypatch.setenv("DB_SSLMODE", "require")
    app = resolve_database_url()
    alembic = resolve_database_url(for_alembic=True)
    assert app.startswith("postgresql+psycopg2://")
    assert "pooler" in app
    assert "primary" in alembic
    assert "sslmode=require" in alembic


def test_sslmode_disable(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@postgres:5432/db")
    monkeypatch.setenv("DB_SSLMODE", "disable")
    url = resolve_database_url()
    assert url.startswith("postgresql+psycopg2://")
    assert url.endswith("sslmode=disable")


def test_postgres_scheme_pins_psycopg2(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    monkeypatch.setenv("DB_SSLMODE", "require")
    url = resolve_database_url()
    assert url.startswith("postgresql+psycopg2://")
    assert "sslmode=require" in url


def test_explicit_driver_is_preserved(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@host/db")
    monkeypatch.setenv("DB_SSLMODE", "require")
    url = resolve_database_url()
    assert url.startswith("postgresql+psycopg://")
    assert "+psycopg2" not in url
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@host/db?sslmode=require")
    assert resolve_database_url() == "postgresql+psycopg2://u:p@host/db?sslmode=require"


def test_sqlalchemy_selects_psycopg2_not_psycopg(monkeypatch):
    """Bare postgresql:// must not load sqlalchemy.dialects.postgresql.psycopg."""
    from sqlalchemy.engine.url import make_url

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("DB_SSLMODE", "disable")
    dialect = make_url(resolve_database_url()).get_dialect()
    assert dialect.driver == "psycopg2"


def test_create_all_forbidden_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SCHEMA_BOOTSTRAP", raising=False)
    with pytest.raises(RuntimeError, match="create_all"):
        allow_create_all_bootstrap()
    monkeypatch.setenv("SCHEMA_BOOTSTRAP", "alembic")
    assert allow_create_all_bootstrap() is False


def test_create_all_ok_in_dev(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("SCHEMA_BOOTSTRAP", raising=False)
    assert allow_create_all_bootstrap() is True


def test_api_role_skips_background_jobs(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("RUN_BACKGROUND_JOBS", raising=False)
    monkeypatch.delenv("RUN_SCHEDULERS", raising=False)
    monkeypatch.setenv("APP_ROLE", "api")
    assert app_role() == "api"
    assert run_background_jobs() is False
    monkeypatch.setenv("APP_ROLE", "worker")
    assert run_background_jobs() is True


def test_in_process_schedulers_skip_when_redis_configured(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("RUN_BACKGROUND_JOBS", raising=False)
    monkeypatch.delenv("RUN_SCHEDULERS", raising=False)
    monkeypatch.delenv("APP_ROLE", raising=False)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    assert run_background_jobs() is True
    assert run_in_process_schedulers() is False
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert run_in_process_schedulers() is True


def test_entrypoint_migrate_role_does_not_exec_uvicorn(tmp_path, monkeypatch):
    """Dry-run: source the migrate-decision logic with a stubbed uv."""
    script = Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"
    stub = tmp_path / "bin"
    stub.mkdir()
    log = tmp_path / "log.txt"
    uv = stub / "uv"
    uv.write_text(
        "#!/bin/sh\necho \"uv $*\" >> \"%s\"\n" % log
    )
    uv.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{stub}:{env['PATH']}"
    env["APP_ROLE"] = "migrate"
    env["EB_DATA_DIR"] = str(tmp_path / "data")
    r = subprocess.run(
        ["sh", str(script)],
        cwd=str(script.parent),
        env=env,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    text = log.read_text()
    assert "alembic upgrade head" in text
    assert "uvicorn" not in text
    assert "arq" not in text
