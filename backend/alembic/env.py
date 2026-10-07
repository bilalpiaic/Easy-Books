"""
Alembic migration environment.

Pulls the DB URL from $DATABASE_URL (same precedence as the app) so the same
migrations apply to SQLite (dev) and Postgres (prod) without code changes.
Targets SQLModel.metadata so future `alembic revision --autogenerate` picks
up new tables and columns added in models.py.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, inspect, pool, text

# Make the backend package importable so we can pull in SQLModel metadata.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel
import models  # noqa: F401 — registers every table on SQLModel.metadata

config = context.config

# Resolve DATABASE_URL the same way db.py does — including the Heroku-style
# `postgres://` → `postgresql://` rewrite. Alembic prefers DATABASE_URL_DIRECT
# so it can talk to the primary instead of a transaction pooler (#424).
from services.app_runtime import resolve_database_url
from local_config import sqlite_path

db_url = resolve_database_url(for_alembic=True)
if not db_url:
    db_url = f"sqlite:///{sqlite_path()}"
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _ensure_wide_version_table(connection) -> None:
    """Alembic stamps ``version_num VARCHAR(32)``; three historical revision
    ids are 33–34 chars (0048/0069/0071). Widen before upgrade so empty
    Postgres can stamp them. SQLite ignores VARCHAR length."""
    if connection.dialect.name != "postgresql":
        return
    insp = inspect(connection)
    if insp.has_table("alembic_version"):
        connection.execute(text(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(128)"
        ))
    else:
        connection.execute(text(
            "CREATE TABLE alembic_version ("
            "version_num VARCHAR(128) NOT NULL PRIMARY KEY)"
        ))


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET lock_timeout = '5s'"))
            _ensure_wide_version_table(connection)
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
